from flask import Blueprint, request, jsonify
from app.utils.auth import require_api_key
from app.utils.formatting import load_template
from app.utils.activity_rules import get_activity_tips, build_tips_html
from app.services.email_service import send_html_email, send_plain_email

bp = Blueprint("email", __name__)


@bp.route("/enviar-voucher-email", methods=["POST"])
@require_api_key
def enviar_voucher_email():
    try:
        d = request.get_json() or {}
        to = d.get("to", "")
        pdf_b64 = d.get("pdf_base64", "")
        pdf_fname = d.get("pdf_filename", "voucher.pdf")
        tipo = d.get("tipo", "rc")

        if not to:
            return jsonify({"error": "Missing 'to' email"}), 400

        if tipo == "at":
            tmpl = load_template("email_at_template.html")
            atividade = d.get("atividade", "")
            operador = d.get("operador", "")
            pickup_local = d.get("pickup_local", "")
            if pickup_local:
                pickup_block = (
                    f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">'
                    f"<tr><td style=\"background:#f2f9fa;border-left:4px solid #0d6e7a;"
                    f'border-radius:0 8px 8px 0;padding:20px 22px;">'
                    f'<p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:1.5px;'
                    f'color:#0d6e7a;text-transform:uppercase;">\U0001f4cd Meeting Point</p>'
                    f'<p style="margin:0;font-size:14px;color:#2a2a2a;line-height:1.8;">'
                    f"{pickup_local}</p></td></tr></table>"
                )
            else:
                pickup_block = ""
            pagamento = d.get("pagamento", "cash")
            if "cash" in pagamento:
                payment_note = "Cash on the day of the activity."
            elif "card" in pagamento:
                payment_note = "Payment by card on the day."
            else:
                payment_note = "To be confirmed."
            subject = d.get(
                "email_subject",
                f"Your Activity is Confirmed \u2014 {atividade} | Beyond Madeira",
            )
            replacements = {
                "{{cliente}}": d.get("cliente", ""),
                "{{atividade}}": atividade,
                "{{data}}": d.get("data", ""),
                "{{hora}}": d.get("hora", "TBC"),
                "{{participantes}}": d.get("participantes", ""),
                "{{operador}}": operador,
                "{{referencia}}": d.get("referencia", ""),
                "{{total}}": str(d.get("total", "")),
                "{{pickup_block}}": pickup_block,
                "{{payment_note}}": payment_note,
                "{{tips_block}}": build_tips_html(
                    get_activity_tips(atividade, d.get("categoria", ""))
                ),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", pickup_local),
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }
        else:
            tmpl = load_template("email_rc_template.html")
            subject = d.get(
                "email_subject",
                "Your Car Rental is Confirmed \u2014 Beyond Madeira",
            )
            replacements = {
                "{{cliente}}": d.get("cliente", ""),
                "{{empresa}}": d.get("empresa", ""),
                "{{veiculo}}": d.get("veiculo", ""),
                "{{referencia}}": d.get("referencia", ""),
                "{{total}}": str(d.get("total", "")),
                "{{pickup_data}}": d.get("pickup_data", ""),
                "{{pickup_hora}}": d.get("pickup_hora", ""),
                "{{pickup_local}}": d.get("pickup_local", ""),
                "{{dropoff_data}}": d.get("dropoff_data", ""),
                "{{dropoff_hora}}": d.get("dropoff_hora", ""),
                "{{dropoff_local}}": d.get("dropoff_local", ""),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", ""),
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }

        for k, v in replacements.items():
            tmpl = tmpl.replace(k, str(v) if v else "")

        send_html_email(to, subject, tmpl, pdf_b64, pdf_fname)
        return jsonify({"success": True, "method": "smtp"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/enviar-extrato-email", methods=["POST"])
@require_api_key
def enviar_extrato_email():
    try:
        d = request.get_json() or {}
        to = d.get("to", "")
        parceiro = d.get("parceiro", "")
        mes = d.get("mes", "")
        subject = d.get("subject") or f"Extrato de Comissões — {parceiro} | {mes}"
        body_txt = d.get("body", "")
        pdf_b64 = d.get("pdf_base64") or None
        pdf_fname = d.get("pdf_filename", "")

        if not to:
            return jsonify({"error": "Missing 'to' email"}), 400

        # Auto-generate PDF if not provided
        if not pdf_b64 and parceiro and mes:
            from app.blueprints.extratos import _gerar_extrato_interno
            result = _gerar_extrato_interno(parceiro, mes, d.get("tipo", ""))
            if result and result.get("pdf_base64"):
                pdf_b64 = result["pdf_base64"]
                pdf_fname = result.get("filename", f"Extrato_{parceiro}_{mes}.pdf")

        if not pdf_fname:
            pdf_fname = f"BeyondMadeira_{parceiro}_{mes.replace(' ', '')}.pdf"

        # Build HTML email
        html_body = _build_extrato_html_email(parceiro, mes, body_txt)
        send_html_email(to, subject, html_body, pdf_b64, pdf_fname)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _build_extrato_html_email(parceiro, mes, body_txt):
    """Build a professional HTML email for the extrato."""
    body_html = (body_txt or "").replace("\n", "<br>")
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#ffffff">
      <div style="background:linear-gradient(135deg,#0a8f82 0%,#0a6b7c 100%);padding:32px 28px;border-radius:0 0 24px 24px">
        <div style="font-size:12px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:8px">Beyond Madeira</div>
        <div style="font-size:24px;font-weight:800;color:#ffffff;letter-spacing:-.5px">Extrato de Comissões</div>
        <div style="font-size:15px;color:rgba(255,255,255,.85);margin-top:6px">{parceiro} — {mes}</div>
      </div>
      <div style="padding:28px">
        <div style="font-size:14px;color:#333;line-height:1.8;margin-bottom:24px">{body_html}</div>
        <div style="background:#f8faf9;border:1px solid #e0ece8;border-radius:12px;padding:18px 20px;margin-bottom:24px">
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:40px;height:40px;border-radius:10px;background:#0a8f82;display:flex;align-items:center;justify-content:center">
              <span style="font-size:18px">📄</span>
            </div>
            <div>
              <div style="font-size:13px;font-weight:700;color:#1a1a1a">PDF em anexo</div>
              <div style="font-size:12px;color:#888">BeyondMadeira_{parceiro.replace(' ', '_')}_{mes.replace(' ', '_')}.pdf</div>
            </div>
          </div>
        </div>
        <div style="font-size:12px;color:#999;border-top:1px solid #eee;padding-top:16px;line-height:1.6">
          Beyond Madeira · Turismo & Aventura<br>
          +351 939 566 415 · info@beyondmadeira.com<br>
          beyondmadeira.com
        </div>
      </div>
    </div>"""


@bp.route("/preview-email", methods=["POST"])
@require_api_key
def preview_email():
    try:
        d = request.get_json() or {}
        tipo = d.get("tipo", "rc")

        if tipo == "at":
            tmpl = load_template("email_at_template.html")
            atividade = d.get("atividade", "")
            pickup_local = d.get("pickup_local", "")
            if pickup_local:
                pickup_block = (
                    f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">'
                    f"<tr><td style=\"background:#f2f9fa;border-left:4px solid #0d6e7a;"
                    f'border-radius:0 8px 8px 0;padding:20px 22px;">'
                    f'<p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:1.5px;'
                    f'color:#0d6e7a;text-transform:uppercase;">\U0001f4cd Meeting Point</p>'
                    f'<p style="margin:0;font-size:14px;color:#2a2a2a;line-height:1.8;">'
                    f"{pickup_local}</p></td></tr></table>"
                )
            else:
                pickup_block = ""
            pagamento = d.get("pagamento", "cash")
            if "cash" in pagamento:
                payment_note = "Cash on the day of the activity."
            elif "card" in pagamento:
                payment_note = "Payment by card on the day."
            else:
                payment_note = "To be confirmed."
            replacements = {
                "{{cliente}}": d.get("cliente", "Guest"),
                "{{atividade}}": atividade,
                "{{data}}": d.get("data", ""),
                "{{hora}}": d.get("hora", "TBC"),
                "{{participantes}}": str(d.get("participantes", "")),
                "{{operador}}": d.get("operador", ""),
                "{{referencia}}": d.get("referencia", ""),
                "{{total}}": str(d.get("total", "")),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", pickup_local),
                "{{payment_note}}": payment_note,
                "{{tips_block}}": build_tips_html(
                    get_activity_tips(atividade, d.get("categoria", ""))
                ),
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }
        else:
            tmpl = load_template("email_rc_template.html")
            replacements = {
                "{{cliente}}": d.get("cliente", "Guest"),
                "{{empresa}}": d.get("empresa", ""),
                "{{veiculo}}": d.get("veiculo", ""),
                "{{referencia}}": d.get("referencia", ""),
                "{{total}}": str(d.get("total", "")),
                "{{pickup_data}}": d.get("pickup_data", ""),
                "{{pickup_hora}}": d.get("pickup_hora", ""),
                "{{pickup_local}}": d.get("pickup_local", ""),
                "{{dropoff_data}}": d.get("dropoff_data", ""),
                "{{dropoff_hora}}": d.get("dropoff_hora", ""),
                "{{dropoff_local}}": d.get("dropoff_local", ""),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", ""),
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }

        for k, v in replacements.items():
            tmpl = tmpl.replace(k, str(v) if v else "")

        return jsonify({"success": True, "html": tmpl})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
