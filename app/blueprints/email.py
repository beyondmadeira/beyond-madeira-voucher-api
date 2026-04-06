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
        total = 0
        if not pdf_b64 and parceiro and mes:
            from app.blueprints.extratos import _gerar_extrato_interno
            result = _gerar_extrato_interno(parceiro, mes, d.get("tipo", ""))
            if result and result.get("pdf_base64"):
                pdf_b64 = result["pdf_base64"]
                pdf_fname = result.get("filename", f"Extrato_{parceiro}_{mes}.pdf")
                total = result.get("total_fim", result.get("total", 0))

        if not pdf_fname:
            pdf_fname = f"BeyondMadeira_{parceiro}_{mes.replace(' ', '')}.pdf"

        # Build HTML email
        html_body = _build_extrato_html_email(parceiro, mes, body_txt, total)
        send_html_email(to, subject, html_body, pdf_b64, pdf_fname)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _build_extrato_html_email(parceiro, mes, body_txt, total=0):
    """Build a professional HTML email for the extrato."""
    body_html = (body_txt or "").replace("\n", "<br>")
    try:
        total_val = f"{float(total):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        total_val = "0,00"
    logo = "https://beyond-madeira-voucher-api-production-2651.up.railway.app/static/logo_clean.png"
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#ffffff">
      <!-- Header with logo -->
      <div style="padding:28px 28px 0;text-align:center">
        <img src="{logo}" width="160" alt="Beyond Madeira" style="display:inline-block" />
      </div>
      <div style="padding:16px 28px 0;text-align:center">
        <div style="font-size:13px;color:#888;font-weight:500">Extrato de Comissões</div>
        <div style="font-size:18px;font-weight:700;color:#1a1a1a;margin-top:4px">{parceiro} &mdash; {mes}</div>
      </div>

      <div style="padding:24px 28px 28px">
        <!-- Total card -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
          <tr><td style="background:#0a8f82;border-radius:14px;padding:24px;text-align:center">
            <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:8px">Total a receber</div>
            <div style="font-size:38px;font-weight:800;color:#ffffff;letter-spacing:-1.5px;line-height:1">&euro;{total_val}</div>
            <div style="font-size:12px;color:rgba(255,255,255,.55);margin-top:10px">{parceiro} &middot; {mes}</div>
          </td></tr>
        </table>

        <!-- Body -->
        <div style="font-size:14px;color:#333;line-height:1.8;margin-bottom:28px">{body_html}</div>

        <!-- Signature -->
        <div style="border-top:1px solid #eee;padding-top:20px">
          <table cellpadding="0" cellspacing="0" style="font-size:13px;color:#333">
            <tr>
              <td style="padding-right:16px;vertical-align:top;border-right:2px solid #0a8f82">
                <img src="{logo}" width="90" alt="Beyond Madeira" style="display:block" />
              </td>
              <td style="padding-left:16px;vertical-align:top">
                <div style="font-size:15px;font-weight:700;color:#1a1a1a">Hugo Vieira</div>
                <div style="font-size:12px;color:#0a8f82;font-weight:600;margin-bottom:10px">Reservations</div>
                <div style="font-size:12px;color:#555;line-height:2">
                  &#128231; info@beyondmadeira.com<br>
                  &#128222; +351 939 566 415<br>
                  &#127760; beyondmadeira.com
                </div>
                <div style="margin-top:12px">
                  <a href="https://wa.me/351939566415" style="text-decoration:none;margin-right:8px"><img src="https://img.icons8.com/color/28/whatsapp--v1.png" width="24" height="24" alt="WA" style="vertical-align:middle"/></a>
                  <a href="https://facebook.com/beyondmadeira" style="text-decoration:none;margin-right:8px"><img src="https://img.icons8.com/color/28/facebook-new.png" width="24" height="24" alt="FB" style="vertical-align:middle"/></a>
                  <a href="https://instagram.com/beyondmadeira" style="text-decoration:none;margin-right:8px"><img src="https://img.icons8.com/color/28/instagram-new--v1.png" width="24" height="24" alt="IG" style="vertical-align:middle"/></a>
                  <a href="https://tiktok.com/@beyondmadeira" style="text-decoration:none"><img src="https://img.icons8.com/color/28/tiktok--v1.png" width="24" height="24" alt="TT" style="vertical-align:middle"/></a>
                </div>
              </td>
            </tr>
          </table>
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
