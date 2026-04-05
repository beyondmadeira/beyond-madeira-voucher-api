import base64
from flask import Blueprint, request, jsonify
from app.utils.auth import require_api_key
from app.services.pdf import build_rc_html, build_at_html, generate_pdf

bp = Blueprint("vouchers", __name__)


@bp.route("/gerar-voucher", methods=["POST"])
@require_api_key
def gerar_voucher():
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400
        html = build_rc_html(d)
        pdf = generate_pdf(html)
        b64 = base64.b64encode(pdf).decode()
        ref = d.get("referencia", "voucher")
        cli = d.get("cliente", "").replace(" ", "_")
        fname = f"Voucher_{ref}_{cli}.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/gerar-voucher-atividade", methods=["POST"])
@require_api_key
def gerar_voucher_atividade():
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400
        required = ["referencia", "atividade", "data", "cliente", "total"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        html = build_at_html(d)
        pdf = generate_pdf(html)
        b64 = base64.b64encode(pdf).decode()
        fname = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ', '_')}.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
