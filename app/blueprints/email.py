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
        subject = d.get("subject", "Extrato de Comiss\u00f5es \u2014 Beyond Madeira")
        body_txt = d.get("body", "Segue em anexo o extrato de comiss\u00f5es.")
        pdf_b64 = d.get("pdf_base64", "")
        pdf_fname = d.get("pdf_filename", "extrato.pdf")

        if not to:
            return jsonify({"error": "Missing 'to' email"}), 400

        send_plain_email(to, subject, body_txt, pdf_b64, pdf_fname)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
