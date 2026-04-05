from flask import Blueprint, jsonify
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
    """Manually trigger Airtable -> PostgreSQL sync."""
    from app.services.airtable_sync import pull_all
    try:
        total = pull_all()
        return jsonify({"success": True, "records_synced": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
