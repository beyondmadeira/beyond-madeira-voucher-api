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
