import json
import logging
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.utils.auth import require_api_key
from app.utils.anthropic_usage import log_usage
from app.extensions import db
from app.models.chat import ChatHistory, AgentNote

bp = Blueprint("chat", __name__)
log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _clamp_max_tokens(requested):
    """Impede pedidos absurdamente grandes (proteção de custo). O teto é
    configurável via CHAT_MAX_TOKENS_CEILING; default generoso de 8192."""
    ceiling = current_app.config.get("CHAT_MAX_TOKENS_CEILING", 8192)
    try:
        val = int(requested)
    except (TypeError, ValueError):
        val = 1024
    if val < 1:
        val = 1024
    return min(val, ceiling)


def _resolve_model(requested):
    """Se CHAT_ALLOWED_MODELS estiver definido (lista separada por vírgulas),
    modelos fora da lista caem para o default — evita que um cliente force
    um modelo caro por engano. Vazio = aceita qualquer modelo (comportamento
    original), mas o modelo fica sempre registado no log de consumo."""
    model = (requested or DEFAULT_MODEL).strip()
    allowed = current_app.config.get("CHAT_ALLOWED_MODELS", "")
    if allowed:
        allow_list = [m.strip() for m in allowed.split(",") if m.strip()]
        if model not in allow_list:
            log.warning(
                "[CHAT] modelo '%s' fora da whitelist — a usar default '%s'",
                model, DEFAULT_MODEL,
            )
            return DEFAULT_MODEL
    return model


def _cacheable_system(system):
    """Marca o system prompt como cacheável (cache_control ephemeral).
    O prefixo repetido passa a custar ~10% nas chamadas seguintes."""
    if not system:
        return None
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


@bp.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    api_key = current_app.config["ANTHROPIC_API_KEY"]
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    try:
        body = request.get_json() or {}
        messages = body.get("messages", [])
        model = _resolve_model(body.get("model"))
        max_tokens = _clamp_max_tokens(body.get("max_tokens", 1024))
        system = body.get("system", "")
        stream = body.get("stream", False)
        user_name = body.get("user_name") or body.get("agent_name") or ""

        payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
        cached_system = _cacheable_system(system)
        if cached_system:
            payload["system"] = cached_system

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        if stream:
            payload["stream"] = True

            def generate():
                usage_acc = {}
                stream_model = model
                with requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=60,
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                # Acumular usage a partir dos eventos SSE para
                                # registar o custo no fim do stream.
                                try:
                                    evt = json.loads(decoded[6:])
                                    if evt.get("type") == "message_start":
                                        msg = evt.get("message", {})
                                        stream_model = msg.get("model", stream_model)
                                        usage_acc.update(msg.get("usage", {}) or {})
                                    elif evt.get("type") == "message_delta":
                                        usage_acc.update(evt.get("usage", {}) or {})
                                except Exception:
                                    pass
                                yield decoded + "\n\n"
                # Fim do stream — regista consumo (best-effort).
                log_usage("/api/chat", stream_model, usage_acc, user_name)

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        log_usage("/api/chat", data.get("model", model), data.get("usage"), user_name)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Usage / Custos ────────────────────────────────────────

@bp.route("/api/usage/summary", methods=["GET"])
@require_api_key
def usage_summary():
    """Resumo de consumo da API Claude nos últimos N dias.

    Query params:
      - days: janela em dias (default 7)
    Devolve totais, e repartição por dia, por modelo e por utilizador,
    com custo estimado em USD. É a resposta a "onde vai o dinheiro?".
    """
    from datetime import timedelta
    from app.models.usage_log import ApiUsageLog

    try:
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 90))
    cutoff = datetime.utcnow() - timedelta(days=days)

    rows = ApiUsageLog.query.filter(ApiUsageLog.created_at >= cutoff).all()

    def _blank():
        return {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.0}

    total = _blank()
    by_day, by_model, by_user = {}, {}, {}

    def _acc(bucket, r):
        bucket["calls"] += 1
        bucket["input_tokens"] += r.input_tokens or 0
        bucket["output_tokens"] += r.output_tokens or 0
        bucket["cache_read_tokens"] += r.cache_read_tokens or 0
        bucket["cache_write_tokens"] += r.cache_write_tokens or 0
        bucket["cost_usd"] += r.est_cost_usd or 0.0

    for r in rows:
        _acc(total, r)
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "?"
        _acc(by_day.setdefault(day, _blank()), r)
        _acc(by_model.setdefault(r.model or "?", _blank()), r)
        _acc(by_user.setdefault(r.user_name or "-", _blank()), r)

    def _round(d):
        out = {}
        for k, v in d.items():
            v = dict(v)
            v["cost_usd"] = round(v["cost_usd"], 4)
            out[k] = v
        return out

    total["cost_usd"] = round(total["cost_usd"], 4)
    # Ordenar utilizadores/modelos por custo desc (quem mais gasta primeiro).
    top_users = dict(sorted(by_user.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True))
    top_models = dict(sorted(by_model.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True))

    return jsonify({
        "success": True,
        "window_days": days,
        "total": total,
        "by_day": _round(dict(sorted(by_day.items()))),
        "by_model": _round(top_models),
        "by_user": _round(top_users),
    })


# ── Chat History ──────────────────────────────────────────

@bp.route("/api/chat-history", methods=["GET"])
@require_api_key
def list_chat_history():
    user = request.args.get("user", "")
    q = ChatHistory.query
    if user:
        q = q.filter(ChatHistory.user_name == user)
    rows = q.order_by(ChatHistory.updated_at.desc()).limit(20).all()
    # Auto-cleanup: if user has more than 20, delete oldest (keep good insights via notes)
    if user:
        all_count = ChatHistory.query.filter(ChatHistory.user_name == user).count()
        if all_count > 20:
            old = ChatHistory.query.filter(ChatHistory.user_name == user).order_by(
                ChatHistory.updated_at.asc()
            ).limit(all_count - 20).all()
            for r in old:
                db.session.delete(r)
            db.session.commit()
    return jsonify({"success": True, "conversations": [r.to_api() for r in rows]})


@bp.route("/api/chat-history/<int:conv_id>", methods=["GET"])
@require_api_key
def get_chat_history(conv_id):
    row = ChatHistory.query.get(conv_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True, "conversation": row.to_api()})


@bp.route("/api/chat-history", methods=["POST"])
@require_api_key
def save_chat_history():
    body = request.get_json() or {}
    conv_id = body.get("id")
    if conv_id:
        row = ChatHistory.query.get(conv_id)
        if row:
            row.messages = body.get("messages", row.messages)
            row.title = body.get("title", row.title)
            row.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"success": True, "conversation": row.to_api()})

    row = ChatHistory(
        agent_id=body.get("agent_id", 0),
        agent_name=body.get("agent_name", ""),
        title=body.get("title", ""),
        messages=body.get("messages", []),
        user_name=body.get("user_name", ""),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "conversation": row.to_api()})


@bp.route("/api/chat-history/<int:conv_id>", methods=["DELETE"])
@require_api_key
def delete_chat_history(conv_id):
    row = ChatHistory.query.get(conv_id)
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({"success": True})


# ── Agent Notes ───────────────────────────────────────────

@bp.route("/api/agent-notes", methods=["GET"])
@require_api_key
def list_agent_notes():
    rows = AgentNote.query.order_by(AgentNote.updated_at.desc()).all()
    return jsonify({"success": True, "notes": [r.to_api() for r in rows]})


@bp.route("/api/agent-notes", methods=["POST"])
@require_api_key
def save_agent_note():
    body = request.get_json() or {}
    note_id = body.get("id")
    if note_id:
        row = AgentNote.query.get(note_id)
        if row:
            row.content = body.get("content", row.content)
            row.category = body.get("category", row.category)
            row.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"success": True, "note": row.to_api()})

    row = AgentNote(
        category=body.get("category", "Geral"),
        content=body.get("content", ""),
        user_name=body.get("user_name", ""),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "note": row.to_api()})


@bp.route("/api/agent-notes/<int:note_id>", methods=["DELETE"])
@require_api_key
def delete_agent_note(note_id):
    row = AgentNote.query.get(note_id)
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({"success": True})


# ── Beyond Memory ─────────────────────────────────────────

@bp.route("/api/memory", methods=["GET"])
@require_api_key
def list_memory():
    from app.models.memory import BeyondMemory
    cat = request.args.get("category", "")
    key = request.args.get("key", "")
    q = BeyondMemory.query
    if cat:
        q = q.filter(BeyondMemory.category == cat)
    if key:
        q = q.filter(db.func.lower(BeyondMemory.key) == key.lower())
    rows = q.order_by(BeyondMemory.updated_at.desc()).all()
    return jsonify({"success": True, "memories": [r.to_api() for r in rows]})


@bp.route("/api/memory", methods=["POST"])
@require_api_key
def save_memory():
    from app.models.memory import BeyondMemory
    d = request.get_json() or {}
    mem_id = d.get("id")
    if mem_id:
        row = BeyondMemory.query.get(mem_id)
        if row:
            for f in ["category", "key", "content", "source"]:
                if f in d:
                    setattr(row, f, d[f])
            row.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"success": True, "memory": row.to_api()})
    row = BeyondMemory(
        category=d.get("category", "insight"),
        key=d.get("key", ""),
        content=d.get("content", ""),
        source=d.get("source", "user"),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "memory": row.to_api()})


@bp.route("/api/memory/context", methods=["GET"])
@require_api_key
def memory_context():
    """Return all memories formatted as context string for agents."""
    try:
        from app.models.memory import BeyondMemory
        rows = BeyondMemory.query.order_by(BeyondMemory.category, BeyondMemory.key).all()
        if not rows:
            return jsonify({"success": True, "context": ""})
        lines = []
        cur_cat = ""
        for r in rows:
            if r.category != cur_cat:
                cur_cat = r.category
                lines.append(f"\n[{cur_cat.upper()}]")
            lines.append(f"- {r.key}: {r.content}")
        return jsonify({"success": True, "context": "\n".join(lines)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
