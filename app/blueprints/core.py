from flask import Blueprint, jsonify, request
from app.utils.auth import require_api_key

bp = Blueprint("core", __name__)


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
