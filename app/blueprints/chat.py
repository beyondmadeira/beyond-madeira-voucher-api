import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.utils.auth import require_api_key
from app.extensions import db
from app.models.chat import ChatHistory, AgentNote

bp = Blueprint("chat", __name__)


@bp.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    api_key = current_app.config["ANTHROPIC_API_KEY"]
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    try:
        body = request.get_json() or {}
        messages = body.get("messages", [])
        model = body.get("model", "claude-sonnet-4-20250514")
        max_tokens = body.get("max_tokens", 1024)
        system = body.get("system", "")
        stream = body.get("stream", False)

        payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        if stream:
            payload["stream"] = True

            def generate():
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
                                yield decoded + "\n\n"

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
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
