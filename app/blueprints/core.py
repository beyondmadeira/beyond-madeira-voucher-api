import os
import requests as req_lib
from flask import Blueprint, jsonify, request
from app.utils.auth import require_api_key

bp = Blueprint("core", __name__)


@bp.route("/ai/parse-reserva", methods=["POST"])
@require_api_key
def ai_parse_reserva():
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    tipo = (body.get("tipo") or "rc").lower()
    if not text:
        return jsonify({"error": "text required"}), 400

    from flask import current_app
    anthropic_key = current_app.config.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500

    from datetime import date
    today_str = date.today().strftime("%d/%m/%Y")
    year = date.today().year

    if tipo == "rc":
        schema = '''{
  "nome": "full client name",
  "ref": "BYD reference (e.g. BYD3836)",
  "parceiro": "car rental partner name",
  "carro": "car model string",
  "pdt": "YYYY-MM-DDTHH:MM (pick-up datetime)",
  "ploc": "one of: Airport | Office | Hotel/Airbnb",
  "pvoo": "pick-up flight number or empty string",
  "pdet": "hotel name/address if Hotel/Airbnb, else empty",
  "ddt": "YYYY-MM-DDTHH:MM (drop-off datetime)",
  "dloc": "one of: Airport | Office | Hotel/Airbnb",
  "dvoo": "drop-off flight number or empty string",
  "ddet": "hotel name/address if Hotel/Airbnb, else empty",
  "dur": "number_of_days_as_integer",
  "total": "price_as_number",
  "com": "commission_as_number",
  "tel": "phone number with country code",
  "email": "email address or empty",
  "obs": "any extra notes"
}'''
    else:
        schema = '''{
  "nome": "full client name",
  "ref": "BYD reference (e.g. BYD-JEEP-130726)",
  "parceiro": "partner/operator name",
  "atv": "activity name",
  "data": "YYYY-MM-DD",
  "hora": "HH:MM",
  "local": "pick-up location description",
  "pess": "number of people as string (e.g. 2)",
  "total": "price_as_number",
  "com": "commission_as_number",
  "tel": "phone number with country code",
  "email": "email address or empty",
  "obs": "any extra notes or special instructions"
}'''

    system_prompt = f"""You are a reservation parser for Beyond Madeira, a tourism company in Madeira, Portugal.
Today is {today_str}. Current year is {year}.
Rules:
- Accept ANY format: formal, informal, incomplete, shorthand. E.g. "reserva pointcar joao 924430084 renault clio" is valid.
- For dates written as DD/MM (no year): if that date is in the future or today use {year}, otherwise use {year + 1}.
- Convert all DD/MM dates to YYYY-MM-DD format.
- If a field is missing from the text, use empty string "" for text fields and 0 for numbers.
- Common partner names: PointCar, Point Car, Atlantic Rent Car, Ab4 Rent, Amsterdam Rent Car, LidoTours, RentCar Madeira.
- Phone numbers: always include country code. If just 9 digits starting with 9, prefix +351.
- Be smart: "airport" = Airport, "hotel X" = Hotel/Airbnb with pdet=X, "office" = Office.
Parse the reservation text and return ONLY a valid JSON object matching this schema:
{schema}
Return ONLY the JSON object, no explanation, no markdown, no extra text."""

    resp = req_lib.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": text}],
        },
        timeout=20,
    )

    if resp.status_code != 200:
        return jsonify({"error": "Claude API error", "detail": resp.text}), 500

    raw = resp.json()
    content = raw.get("content", [{}])[0].get("text", "")
    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    content = content.strip()

    try:
        import json as _json
        parsed = _json.loads(content)
        return jsonify({"success": True, "data": parsed})
    except Exception:
        return jsonify({"error": "JSON parse error", "raw": content}), 500


@bp.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Beyond Madeira CRM API",
        "version": "2.0",
        "database": "postgresql",
        "endpoints": [
            "/gerar-voucher",
            "/gerar-voucher-atividade",
            "/airtable/rc",
            "/airtable/at",
            "/airtable/sitemap",
            "/airtable/biblioteca",
            "/airtable/guia",
        ],
    })


@bp.route("/debug/force-pull", methods=["POST"])
@require_api_key
def debug_force_pull():
    """Force pull a specific table and report orphans."""
    d = request.get_json() or {}
    model = d.get("model", "DespesaFixa")
    try:
        from app.services.airtable_sync import pull_table
        n = pull_table(model)
        return jsonify({"success": True, "model": model, "synced": n})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/debug/push-dirty", methods=["POST"])
@require_api_key
def debug_push_dirty():
    """Manually trigger push for a specific model."""
    from app.services.airtable_sync import push_dirty
    d = request.get_json() or {}
    model = d.get("model", "ComissaoParceiro")
    try:
        n = push_dirty(model)
        return jsonify({"success": True, "model": model, "pushed": n})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/debug/email-config", methods=["GET"])
@require_api_key
def debug_email_config():
    from flask import current_app
    cfg = current_app.config
    return jsonify({
        "SMTP_USER": cfg.get("SMTP_USER", ""),
        "SMTP_PASS_SET": bool(cfg.get("SMTP_PASS")),
        "SMTP_PASS_LEN": len(cfg.get("SMTP_PASS", "")),
        "GMAIL_CLIENT_ID_SET": bool(cfg.get("GMAIL_CLIENT_ID")),
        "GMAIL_CLIENT_SECRET_SET": bool(cfg.get("GMAIL_CLIENT_SECRET")),
        "GMAIL_REFRESH_TOKEN_SET": bool(cfg.get("GMAIL_REFRESH_TOKEN")),
        "GMAIL_SENDER": cfg.get("GMAIL_SENDER", ""),
    })


@bp.route("/cache/clear", methods=["POST"])
@require_api_key
def clear_cache():
    return jsonify({"success": True, "message": "Cache cleared (now using PostgreSQL)"})


@bp.route("/debug/rc-fields", methods=["GET"])
@require_api_key
def debug_rc_fields():
    from app.models.reservas import RentCar
    sample = RentCar.query.limit(3).all()
    fields = [c.name for c in RentCar.__table__.columns]
    return jsonify({
        "success": True,
        "fields": fields,
        "sample_count": len(sample),
    })


@bp.route("/sync/trigger", methods=["POST"])
@require_api_key
def sync_trigger():
    """Trigger sync in background, return immediately."""
    import threading
    from flask import current_app

    app = current_app._get_current_object()

    def _run_sync():
        with app.app_context():
            from app.services.airtable_sync import pull_all
            try:
                total = pull_all()
                print(f"[SYNC TRIGGER] Done: {total} records")
            except Exception as e:
                print(f"[SYNC TRIGGER] Error: {e}")

    t = threading.Thread(target=_run_sync, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Sync started in background. Check /sync/status in ~2 minutes."})


@bp.route("/sync/test-airtable", methods=["GET"])
@require_api_key
def sync_test_airtable():
    """Direct test: fetch 1 record from Airtable to verify token works."""
    import requests
    from flask import current_app
    token = current_app.config.get("AIRTABLE_TOKEN", "")
    token_preview = token[:15] + "..." if len(token) > 15 else token or "(empty)"
    base_id = "appR8ZKP5ygR8o8Q0"
    table = "Rent Car"
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table)}"
    try:
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"pageSize": 1},
            timeout=15,
        )
        return jsonify({
            "success": r.ok,
            "status_code": r.status_code,
            "token_preview": token_preview,
            "token_length": len(token),
            "response_keys": list(r.json().keys()) if r.ok else None,
            "record_count": len(r.json().get("records", [])) if r.ok else 0,
            "error": r.text if not r.ok else None,
        })
    except Exception as e:
        return jsonify({"error": str(e), "token_preview": token_preview}), 500


@bp.route("/sync/status", methods=["GET"])
@require_api_key
def sync_status():
    """Check sync status — how many records in each table."""
    from app.models.reservas import RentCar, Atividade, Parceiro, Tarefa, Nota
    from app.models.conhecimento import Sitemap, Biblioteca, MadeiraGuide, TemplateMensagem
    from app.models.financeiro import RegistoDiario, DespesaFixa, DespesaVariavel, Objetivo, ResumoMensal, CaixaMensal
    from app.models.extrato import ComissaoParceiro
    counts = {
        "rent_car": RentCar.query.count(),
        "atividade": Atividade.query.count(),
        "parceiro": Parceiro.query.count(),
        "tarefa": Tarefa.query.count(),
        "nota": Nota.query.count(),
        "sitemap": Sitemap.query.count(),
        "biblioteca": Biblioteca.query.count(),
        "madeira_guide": MadeiraGuide.query.count(),
        "template_mensagem": TemplateMensagem.query.count(),
        "comissao_parceiro": ComissaoParceiro.query.count(),
        "registo_diario": RegistoDiario.query.count(),
        "despesa_fixa": DespesaFixa.query.count(),
        "despesa_variavel": DespesaVariavel.query.count(),
        "objetivo": Objetivo.query.count(),
        "resumo_mensal": ResumoMensal.query.count(),
        "caixa_mensal": CaixaMensal.query.count(),
    }
    total = sum(counts.values())
    return jsonify({"success": True, "total": total, "tables": counts})
