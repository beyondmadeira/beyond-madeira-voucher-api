from flask import Blueprint, request, jsonify
from app.utils.auth import require_api_key
from app.utils.formatting import load_template
from app.utils.activity_rules import get_activity_tips, build_tips_html, is_no_payment_activity, get_email_template_key
from app.services.email_service import send_html_email, send_plain_email

bp = Blueprint("email", __name__)


def _build_voucher_html(d, tipo):
    """Build the voucher email HTML for AT or RC — shared by send and preview."""
    if tipo == "at":
        tmpl = load_template("email_at_template.html")
        atividade = d.get("atividade", "")
        operador = d.get("operador", "")
        pickup_local = d.get("pickup_local", "") or d.get("local", "")
        local_type = d.get("local_type", "pickup")
        local_det = d.get("local_det", "")
        if pickup_local or local_type == "pickup":
            if local_type == "meeting":
                pickup_label = "\U0001f4cd Meeting Point"
                pickup_note = f'<p style="margin:6px 0 0;font-size:12px;color:#6b7280;">{local_det}</p>' if local_det else ""
            else:
                pickup_label = "\U0001f698 Pick-up"
                pickup_note = f'<p style="margin:6px 0 0;font-size:12px;color:#0d6e7a;font-style:italic;">{local_det or "Please be ready at the entrance / reception."}</p>'
                if not pickup_local:
                    pickup_local = "We will pick you up at your accommodation"
            maps_link = d.get("maps_link", "")
            maps_html = f' <a href="{maps_link}" style="color:#0d6e7a;font-size:12px;">View on Maps</a>' if maps_link else ""
            pickup_block = (
                f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">'
                f"<tr><td style=\"background:#f2f9fa;border-left:4px solid #0d6e7a;"
                f'border-radius:0 8px 8px 0;padding:20px 22px;">'
                f'<p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:1.5px;'
                f'color:#0d6e7a;text-transform:uppercase;">{pickup_label}</p>'
                f'<p style="margin:0;font-size:14px;color:#2a2a2a;line-height:1.8;">'
                f"{pickup_local}{maps_html}</p>{pickup_note}</td></tr></table>"
            )
        else:
            pickup_block = ""
        # Check if this activity should skip payment link
        no_pay = is_no_payment_activity(atividade)
        tpl_key = get_email_template_key(atividade)

        # Try to load custom subject from DB
        db_subject = None
        try:
            from app.models.email_template import EmailTemplate
            db_tpl = EmailTemplate.query.filter_by(key=tpl_key).first()
            if db_tpl and db_tpl.subject:
                db_subject = db_tpl.subject
        except Exception:
            pass

        pagamento = d.get("pagamento", "")
        pag_map = {
            "Pago": "Payment already received.",
            "Devemos": "Payment to be discussed.",
            "Por Pagar": "Cash on the day of the activity.",
        }
        if no_pay:
            payment_note = "Payment on the day — no advance payment required."
        elif pagamento in pag_map:
            payment_note = pag_map[pagamento]
        elif "cash" in pagamento.lower():
            payment_note = "Cash on the day of the activity."
        elif "card" in pagamento.lower():
            payment_note = "Payment by card on the day."
        else:
            payment_note = "To be confirmed."
        subject = d.get(
            "email_subject",
            db_subject or f"Your Activity is Confirmed \u2014 {atividade} | Beyond Madeira",
        )
        replacements = {
            "{{cliente}}": d.get("cliente", ""),
            "{{atividade}}": atividade,
            "{{data}}": d.get("data", ""),
            "{{hora}}": d.get("hora", "09:00"),
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

    return tmpl, subject


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

        # Auto-detect tipo if not sent
        if not tipo or tipo == "rc":
            if d.get("atividade"):
                tipo = "at"

        if tipo == "simple":
            # Simple raw HTML email — used for pickup updates, notifications
            tmpl = d.get("email_body", "")
            subject = d.get("email_subject", "Beyond Madeira")
            send_html_email(to, subject, tmpl, pdf_b64, pdf_fname)
            return jsonify({"success": True, "method": "simple"})

        tmpl, subject = _build_voucher_html(d, tipo)

        send_html_email(to, subject, tmpl, pdf_b64, pdf_fname)
        return jsonify({"success": True, "method": "smtp"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/preview-extrato-email", methods=["POST"])
@require_api_key
def preview_extrato_email():
    """Return the HTML email template for preview (no sending)."""
    try:
        d = request.get_json() or {}
        parceiro = d.get("parceiro", "")
        mes = d.get("mes", "")
        body_txt = d.get("body") or (
            f"Olá,\n\nSegue em anexo o extrato de comissões referente a {mes}.\n\n"
            f"O PDF em anexo contém o detalhe completo das reservas.\n"
            f"Qualquer dúvida estamos disponíveis.\n\nCom os melhores cumprimentos,"
        )
        # Generate total from data
        total = 0
        if parceiro and mes:
            from app.blueprints.extratos import _gerar_extrato_interno
            try:
                result = _gerar_extrato_interno(parceiro, mes, d.get("tipo", ""))
                total = result.get("total_fim", result.get("total", 0))
            except Exception:
                pass
        html = _build_extrato_html_email(parceiro, mes, body_txt, total)
        return jsonify({"success": True, "html": html})
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
            result = _gerar_extrato_interno(parceiro, mes, d.get("tipo", ""), meses=d.get("meses"))
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
    # Split body into two parts: before and after the month reference line
    lines = (body_txt or "").split("\n")
    split_idx = -1
    for idx, line in enumerate(lines):
        if mes.lower() in line.lower() or "referente" in line.lower():
            split_idx = idx
            break
    if split_idx >= 0:
        body_part1 = "<br>".join(lines[:split_idx + 1])
        body_part2 = "<br>".join(lines[split_idx + 1:]).strip().lstrip("<br>")
    else:
        body_part1 = "<br>".join(lines)
        body_part2 = ""
    try:
        total_val = f"{float(total):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        total_val = "0,00"
    logo = "https://beyond-madeira-voucher-api-production-2651.up.railway.app/static/logo_clean.png"
    # All contact icons in teal (#0a8f82) via icons8
    _ic = "https://img.icons8.com/ios-filled/20/0a8f82"
    ico_email = f'<img src="{_ic}/new-post.png" width="14" height="14" style="vertical-align:middle;margin-right:6px" />'
    ico_phone = f'<img src="{_ic}/phone.png" width="14" height="14" style="vertical-align:middle;margin-right:6px" />'
    ico_web = f'<img src="{_ic}/globe--v1.png" width="14" height="14" style="vertical-align:middle;margin-right:6px" />'
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#ffffff">
      <!-- Header bar -->
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="background:linear-gradient(135deg,#0a8f82 0%,#0a6b7c 100%);padding:28px 28px 24px">
          <div style="font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:rgba(255,255,255,.6);margin-bottom:6px">Beyond Madeira</div>
          <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-.3px">Extrato de Comissões</div>
          <div style="font-size:14px;color:rgba(255,255,255,.8);margin-top:4px">{parceiro} &mdash; {mes}</div>
        </td></tr>
      </table>

      <div style="padding:28px">
        <!-- Body part 1 (up to and including the month reference line) -->
        <div style="font-size:14px;color:#333;line-height:1.8;margin-bottom:20px">{body_part1}</div>

        <!-- Total card -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px">
          <tr><td style="background:#0a8f82;border-radius:12px;padding:22px;text-align:center">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,.65);margin-bottom:6px">Total a receber</div>
            <div style="font-size:36px;font-weight:800;color:#ffffff;letter-spacing:-1.5px;line-height:1">&euro;{total_val}</div>
          </td></tr>
        </table>

        <!-- Body part 2 (rest of the message) -->
        <div style="font-size:14px;color:#333;line-height:1.8;margin-bottom:24px">{body_part2}</div>

        <!-- Signature -->
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td style="border-top:2px solid #e5e7eb;padding-top:24px">
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td width="110" style="vertical-align:middle;text-align:center;padding-right:20px;border-right:3px solid #0a8f82">
                  <img src="{logo}" width="95" alt="Beyond Madeira" style="display:block;margin:0 auto" />
                </td>
                <td style="vertical-align:middle;padding-left:20px">
                  <div style="font-size:16px;font-weight:800;color:#1a1a1a;letter-spacing:-.2px">Hugo Vieira</div>
                  <div style="font-size:11px;color:#0a8f82;font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin:3px 0 12px">Reservations</div>
                  <table cellpadding="0" cellspacing="0" style="font-size:12px;color:#4b5563">
                    <tr>
                      <td width="22" style="padding:4px 0;vertical-align:middle">{ico_email}</td>
                      <td style="padding:4px 0;vertical-align:middle"><a href="mailto:info@beyondmadeira.com" style="color:#4b5563;text-decoration:none">info@beyondmadeira.com</a></td>
                    </tr>
                    <tr>
                      <td width="22" style="padding:4px 0;vertical-align:middle">{ico_phone}</td>
                      <td style="padding:4px 0;vertical-align:middle"><a href="tel:+351939566415" style="color:#4b5563;text-decoration:none">+351 939 566 415</a></td>
                    </tr>
                    <tr>
                      <td width="22" style="padding:4px 0;vertical-align:middle">{ico_web}</td>
                      <td style="padding:4px 0;vertical-align:middle"><a href="https://beyondmadeira.com" style="color:#4b5563;text-decoration:none">beyondmadeira.com</a></td>
                    </tr>
                  </table>
                  <table cellpadding="0" cellspacing="0" style="margin-top:14px">
                    <tr>
                      <td style="padding-right:6px"><a href="https://wa.me/351939566415" style="display:block;width:30px;height:30px;border-radius:50%;background:#0a8f82;text-align:center;line-height:30px;text-decoration:none"><img src="https://img.icons8.com/ios-glyphs/18/ffffff/whatsapp.png" width="16" height="16" alt="WA" style="vertical-align:middle"/></a></td>
                      <td style="padding-right:6px"><a href="https://facebook.com/beyondmadeira" style="display:block;width:30px;height:30px;border-radius:50%;background:#0a8f82;text-align:center;line-height:30px;text-decoration:none"><img src="https://img.icons8.com/ios-glyphs/18/ffffff/facebook-new.png" width="16" height="16" alt="FB" style="vertical-align:middle"/></a></td>
                      <td style="padding-right:6px"><a href="https://instagram.com/beyondmadeira" style="display:block;width:30px;height:30px;border-radius:50%;background:#0a8f82;text-align:center;line-height:30px;text-decoration:none"><img src="https://img.icons8.com/ios-glyphs/18/ffffff/instagram-new.png" width="16" height="16" alt="IG" style="vertical-align:middle"/></a></td>
                      <td><a href="https://tiktok.com/@beyondmadeira" style="display:block;width:30px;height:30px;border-radius:50%;background:#0a8f82;text-align:center;line-height:30px;text-decoration:none"><img src="https://img.icons8.com/ios-glyphs/18/ffffff/tiktok.png" width="16" height="16" alt="TT" style="vertical-align:middle"/></a></td>
                    </tr>
                  </table>
            </td>
          </tr>
        </table>
      </div>
    </div>"""


@bp.route("/preview-email", methods=["POST"])
@require_api_key
def preview_email():
    try:
        d = request.get_json() or {}
        tipo = d.get("tipo", "rc")

        tmpl, _subject = _build_voucher_html(d, tipo)

        return jsonify({"success": True, "html": tmpl})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


# ── Email Templates CRUD ──────────────────────────────────────────────────

@bp.route("/api/email-templates", methods=["GET"])
@require_api_key
def list_email_templates():
    from app.models.email_template import EmailTemplate
    rows = EmailTemplate.query.order_by(EmailTemplate.key).all()
    return jsonify({"success": True, "templates": [r.to_api() for r in rows]})


@bp.route("/api/email-templates", methods=["POST"])
@require_api_key
def save_email_template():
    from app.models.email_template import EmailTemplate
    from app.extensions import db
    from datetime import datetime
    d = request.get_json() or {}
    tpl_id = d.get("id")
    if tpl_id:
        row = EmailTemplate.query.get(tpl_id)
        if row:
            for f in ["key", "name", "subject", "body_html", "no_payment_link", "activities", "notes"]:
                if f in d:
                    setattr(row, f, d[f])
            row.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"success": True, "template": row.to_api()})
    row = EmailTemplate(
        key=d.get("key", ""),
        name=d.get("name", ""),
        subject=d.get("subject", ""),
        body_html=d.get("body_html", ""),
        no_payment_link=d.get("no_payment_link", False),
        activities=d.get("activities", ""),
        notes=d.get("notes", ""),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "template": row.to_api()})


@bp.route("/api/email-templates/<int:tpl_id>", methods=["DELETE"])
@require_api_key
def delete_email_template(tpl_id):
    from app.models.email_template import EmailTemplate
    from app.extensions import db
    row = EmailTemplate.query.get(tpl_id)
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({"success": True})
