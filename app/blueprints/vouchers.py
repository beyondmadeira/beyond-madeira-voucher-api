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


@bp.route("/gerar-voucher-multi", methods=["POST"])
@require_api_key
def gerar_voucher_multi():
    """Generate a multi-activity package voucher PDF."""
    try:
        d = request.get_json() or {}
        cliente = d.get("cliente", "")
        email = d.get("email", "")
        atividades = d.get("atividades", [])
        if not cliente or not atividades:
            return jsonify({"error": "cliente and atividades required"}), 400
        total = sum(float(a.get("total", 0)) for a in atividades)
        n = len(atividades)
        discount_pct = 15 if n >= 10 else (10 if n >= 5 else 0)
        discount = round(total * discount_pct / 100, 2)
        final_total = round(total - discount, 2)

        rows = ""
        for i, a in enumerate(atividades):
            rows += (
                f'<div style="display:flex;justify-content:space-between;padding:10px 0;'
                f'border-bottom:1px solid #eee;font-size:13px;">'
                f'<div><strong>{i+1}. {a.get("nome","")}</strong><br>'
                f'<span style="color:#666;font-size:12px;">{a.get("data","")} \u00b7 {a.get("hora","TBC")} \u00b7 {a.get("pax","1")} pax</span></div>'
                f'<div style="font-weight:700;white-space:nowrap;">\u20ac{float(a.get("total",0)):.2f}</div></div>'
            )
        discount_html = ""
        if discount > 0:
            discount_html = (
                f'<div style="display:flex;justify-content:space-between;padding:10px 0;color:#16a34a;font-weight:700;">'
                f'<span>Package discount ({discount_pct}% \u2014 {n} activities)</span>'
                f'<span>-\u20ac{discount:.2f}</span></div>'
            )
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <style>body{{font-family:'Helvetica Neue',Arial,sans-serif;margin:0;padding:40px;color:#1a1a1a;}}</style></head><body>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding-bottom:20px;border-bottom:2px solid #0d6e7a;">
          <div style="font-size:22px;font-weight:800;color:#0d6e7a;">Beyond Madeira</div>
          <span style="background:#0d6e7a;color:#fff;padding:6px 14px;border-radius:20px;font-size:11px;font-weight:700;">EXPERIENCE PACKAGE</span>
        </div>
        <div style="margin-bottom:24px;">
          <div style="font-size:20px;font-weight:800;">{cliente}</div>
          <div style="font-size:13px;color:#666;">{email} \u00b7 {n} activities</div>
        </div>
        <div style="background:#f8fafa;border-radius:12px;padding:20px;margin-bottom:24px;">
          {rows}{discount_html}
          <div style="display:flex;justify-content:space-between;padding:14px 0 0;border-top:2px solid #0d6e7a;margin-top:10px;">
            <span style="font-size:16px;font-weight:800;">Total</span>
            <span style="font-size:20px;font-weight:800;color:#0d6e7a;">\u20ac{final_total:.2f}</span>
          </div>
        </div>
        <div style="background:#f0faf8;border-radius:10px;padding:16px;font-size:12px;color:#0d6e7a;">
          <strong>Package benefits:</strong> Free cancellation up to 48h \u00b7 Payment on the day \u00b7 24h support \u00b7 Hotel pick-up included (where applicable)
        </div>
        <div style="font-size:11px;color:#999;text-align:center;margin-top:30px;">Beyond Madeira \u00b7 RNAVT 13020 \u00b7 beyondmadeira.com \u00b7 +351 939 566 415</div>
        </body></html>"""
        pdf = generate_pdf(html)
        b64 = base64.b64encode(pdf).decode()
        fname = f"BeyondMadeira_Package_{cliente.replace(' ','_')}_{n}activities.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64,
                        "total": total, "discount": discount, "discount_pct": discount_pct,
                        "final_total": final_total, "n_activities": n})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
