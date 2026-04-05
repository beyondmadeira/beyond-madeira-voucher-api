"""
PDF generation service for vouchers and extratos.
Uses WeasyPrint to render HTML templates to PDF.
"""

import re
from datetime import datetime
from app.utils.formatting import (
    logo_b64, fill, fmt_date, fmt_time, eur_val, get_text_f, norm_act, load_template,
)
from app.utils.operator_contacts import OPERATOR_CONTACTS
from app.utils.activity_rules import (
    TIPS_TEXT, detect_activity, get_activity_tips, build_tips_html,
)


def build_rc_html(d):
    tmpl = load_template("voucher_rc_template.html")

    for field in ["pickup_data", "dropoff_data"]:
        val = d.get(field, "")
        if "T" in val or "Z" in val:
            d[field.replace("data", "hora")] = fmt_time(val)
            d[field] = fmt_date(val)

    pu_extra = ""
    if d.get("pickup_voo"):
        pu_extra += f'<div class="date-sub">Flight: {d["pickup_voo"]}</div>'
    if d.get("pickup_hotel"):
        pu_extra += f'<div class="date-sub">{d["pickup_hotel"]}</div>'
    do_extra = ""
    if d.get("dropoff_voo"):
        do_extra += f'<div class="date-sub">Flight: {d["dropoff_voo"]}</div>'
    if d.get("dropoff_hotel"):
        do_extra += f'<div class="date-sub">{d["dropoff_hotel"]}</div>'

    d["pickup_extra"] = pu_extra
    d["dropoff_extra"] = do_extra
    d.setdefault("extras", "None")

    empresa = d.get("empresa", "")
    if not d.get("empresa_telefone") and empresa in OPERATOR_CONTACTS:
        d["empresa_telefone"], d["empresa_email"] = OPERATOR_CONTACTS[empresa]
    d.setdefault("empresa_telefone", "")
    d.setdefault("empresa_email", "")

    tel = d.get("empresa_telefone", "")
    eml = d.get("empresa_email", "")
    if tel or eml:
        det = ""
        if tel:
            det += tel
        if tel and eml:
            det += "<br>"
        if eml:
            det += eml
        d["empresa_contact_block"] = (
            f'<div class="contact-card"><div class="contact-lbl">Rental Company</div>'
            f'<div class="contact-name">{empresa}</div>'
            f'<div class="contact-det">{det}</div></div>'
        )
    else:
        d["empresa_contact_block"] = ""

    beyond_card = (
        '<div class="contact-card"><div class="contact-lbl">Beyond Madeira</div>'
        '<div class="contact-name">Booking Support</div>'
        '<div class="contact-det">+351 939 566 415<br>booking@beyondmadeira.com</div></div>'
    )
    if d["empresa_contact_block"]:
        d["contacts_row_html"] = f'<div class="contacts-row">{d["empresa_contact_block"]}{beyond_card}</div>'
    else:
        d["contacts_row_html"] = f'<div class="contacts-row">{beyond_card}</div>'

    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    return fill(tmpl, d)


def build_at_html(d):
    tmpl = load_template("voucher_at_template.html")

    rule = detect_activity(d.get("atividade", ""))

    operador = d.get("operador", "")
    if not d.get("operador_telefone") and operador in OPERATOR_CONTACTS:
        d["operador_telefone"], d["operador_email"] = OPERATOR_CONTACTS[operador]
    d.setdefault("operador_telefone", "")
    d.setdefault("operador_email", "")

    if rule and not d.get("pagamento"):
        d["pagamento"] = rule["payment"]
    if rule and not d.get("pickup_mode"):
        d["pickup_mode"] = rule["pickup"]

    tips_html = ""
    if rule and rule.get("tips"):
        tips_lines = [TIPS_TEXT[t] for t in rule["tips"] if t in TIPS_TEXT]
        if rule.get("note"):
            tips_lines.insert(0, f"<strong>{rule['note']}</strong>")
        if tips_lines:
            tips_html = (
                '<div class="special-req"><div class="sr-label">What to Bring &amp; Useful Tips</div>'
                '<div class="sr-text">'
                + "<br>".join(f"&#183; {t}" for t in tips_lines)
                + "</div></div>"
            )
    if d.get("pedido_especial"):
        tips_html += (
            f'<div class="special-req"><div class="sr-label">Special Requests</div>'
            f'<div class="sr-text">{d["pedido_especial"]}</div></div>'
        )
    d["special_requests_html"] = tips_html

    status = d.get("status", "confirmed").lower()
    pagamento = d.get("pagamento", "cash").lower()

    if status == "paid":
        d["status_label"] = "Paid \u2713"
        d["status_class"] = "paid"
        d["price_class"] = "paid"
        d["price_note"] = "Payment received"
    elif status == "awaiting":
        d["status_label"] = "Awaiting Payment"
        d["status_class"] = "awaiting"
        d["price_class"] = "awaiting"
        d["price_note"] = "Payment required"
    else:
        d["status_label"] = "Confirmed"
        d["status_class"] = ""
        d["price_class"] = "cash"
        if "card" in pagamento and "cash" in pagamento:
            d["price_note"] = "Cash or card on the day"
        elif "card" in pagamento:
            d["price_note"] = "Card on the day"
        else:
            d["price_note"] = "Cash on the day"

    hora = d.get("hora", "TBC")
    d["start_time_class"] = "tbc" if hora == "TBC" else "accent"

    total = d.get("total", "")
    if status == "awaiting":
        stripe_link = d.get("stripe_link", "")
        pay_btn = (
            f'<a href="{stripe_link}" style="display:inline-block;margin-top:12px;'
            f'background:var(--amber);color:#fff;font-weight:800;font-size:13px;'
            f'padding:10px 24px;border-radius:8px;text-decoration:none;letter-spacing:-.2px;">'
            f"Pay Now &rarr;</a>"
            if stripe_link
            else ""
        )
        d["payment_alert_html"] = (
            f'<div class="pay-alert awaiting"><div class="pa-dot awaiting">!</div><div>'
            f'<div class="pa-title awaiting">Payment Required Before the Activity</div>'
            f'<div class="pa-body awaiting">To secure your booking, please complete your payment securely online.{pay_btn}'
            f"</div></div></div>"
        )
    elif status == "paid":
        d["payment_alert_html"] = (
            f'<div class="pay-alert paid"><div class="pa-dot paid">&#10003;</div><div>'
            f'<div class="pa-title paid">Payment Confirmed</div>'
            f'<div class="pa-body paid">Your payment of <strong>{total}&euro;</strong> has been received. '
            f"No further payment required &mdash; just show up and enjoy!</div></div></div>"
        )
    else:
        d["payment_alert_html"] = ""

    if status == "confirmed":
        pm_map = {
            "cash": ("Payment: Cash Only", "To be paid in cash on the day of the activity."),
            "card": ("Payment: Card Only", "To be paid by card on the day of the activity."),
            "cash_card": ("Payment: Cash or Card", "To be paid on the day &mdash; cash or card both accepted."),
        }
        pm_key = (
            "cash_card"
            if ("card" in pagamento and "cash" in pagamento)
            else "card" if "card" in pagamento else "cash"
        )
        pt, pb = pm_map[pm_key]
        d["payment_method_html"] = (
            f'<div class="paymethod"><div class="pm-dot">$</div><div>'
            f'<div class="pm-title">{pt}</div><div class="pm-body">{pb}</div></div></div>'
        )
    else:
        d["payment_method_html"] = ""

    pickup_mode = d.get("pickup_mode", "none")
    pickup_loc = d.get("pickup_local", "")
    hotel_det = d.get("hotel_detail", "")
    hora_conf = d.get("hora_confirmada", "")

    if pickup_mode != "none" and pickup_loc:
        labels = {
            "meeting_point": (
                "MEETING POINT",
                "Please make your own way to the meeting point at the time indicated.",
            ),
            "pickup_time_confirmed": (
                "PICK-UP",
                f"Pick-up at <strong>{hora_conf}</strong>." if hora_conf else "Pick-up time confirmed.",
            ),
            "pickup_day_before": (
                "PICK-UP LOCATION",
                "Pick-up time will be sent to you the day before the activity.",
            ),
        }
        loc_label, loc_note = labels.get(
            pickup_mode, ("PICK-UP LOCATION", "Pick-up time will be confirmed closer to the date.")
        )
        hotel_line = f'<div class="pickup-sub">{hotel_det}</div>' if hotel_det else ""
        d["pickup_html"] = (
            f'<div class="pickup-card"><div class="pickup-dot">&#9679;</div><div>'
            f'<div class="pickup-lbl">{loc_label}</div>'
            f'<div class="pickup-loc">{pickup_loc}</div>{hotel_line}'
            f'<div class="pickup-note">{loc_note}</div></div></div>'
        )
    else:
        d["pickup_html"] = ""

    items = d.get("items", [])
    if not items:
        items = [
            {
                "nome": d.get("atividade", ""),
                "detalhe": f"{d.get('data', '')} &middot; {d.get('hora', 'TBC')}",
                "qty": d.get("pax", ""),
                "unit": d.get("preco_unit", ""),
                "sub": d.get("total", ""),
            }
        ]
    rows_html = ""
    for it in items:
        unit_str = f"&euro;{it['unit']}" if it.get("unit") else ""
        rows_html += (
            f'<div class="inv-row"><div class="inv-prod">'
            f'<div class="inv-name">{it.get("nome", "")}</div>'
            f'<div class="inv-detail">{it.get("detalhe", "")}</div></div>'
            f'<div class="inv-qty">{it.get("qty", "")}x</div>'
            f'<div class="inv-unit">{unit_str}</div>'
            f'<div class="inv-sub">&euro;{it.get("sub", "")}</div></div>'
        )
    d["invoice_rows_html"] = rows_html

    d.setdefault(
        "cancelamento",
        "Free cancellation up to <strong>48 hours</strong> before the activity. "
        "Late cancellations or no-shows may incur a fee.",
    )
    d.setdefault(
        "mensagem_confirmacao",
        "Your reservation is confirmed &mdash; no payment required at this stage. "
        "The total amount is to be paid in cash on the day of the activity. "
        "You will receive further details closer to the date, including your exact pick-up time.",
    )
    d.setdefault("bokun_ref", "")

    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    return fill(tmpl, d)


def calc_totais(rows):
    rows_v = [r for r in rows if r["status"] != "Cancelado"]
    n_can = sum(1 for r in rows if r["status"] == "Cancelado")
    n_norm = sum(1 for r in rows_v if r["status"] != "Devemos")
    n_dev = sum(1 for r in rows_v if r["status"] == "Devemos")
    comiss = sum(r["comm"] for r in rows_v if r["status"] != "Devemos")
    credito = sum(r["total"] - r["comm"] for r in rows_v if r["status"] == "Devemos")
    gt = sum(r["total"] for r in rows_v)
    gc = sum(r["comm"] for r in rows_v if r["status"] != "Devemos")
    total_fim = comiss - credito
    return dict(
        n=len(rows), n_can=n_can, n_norm=n_norm, n_dev=n_dev,
        comiss=comiss, credito=credito, gt=gt, gc=gc, total_fim=total_fim,
    )


def build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots, rows_by_month=None):
    today = datetime.now().strftime("%d/%m/%Y")
    t = tots

    def _status_class(s):
        return {"Pago": "status-pago", "Devemos": "status-devemos", "Cancelado": "status-cancel"}.get(s, "")

    def _row_html(r, bg, strike=False):
        sc = _status_class(r["status"])
        sk = " strike" if strike else ""
        pax = str(r.get("pax") or "\u2014").replace(" Pessoas", "").replace(" Pessoa", "").strip()
        ref_r = (r.get("ref", "") or "\u2014")[:14]
        client = (r["client"] or "\u2014")[:30]
        act = (r["act"] or "\u2014")[:28]
        total_abs = abs(r["total"])
        comm_abs = abs(r["comm"])
        return (
            f'<tr style="background:{bg}">'
            f'<td class="muted{sk}">{r["date"]}</td>'
            f'<td class="muted{sk}" style="font-size:8px;">{ref_r}</td>'
            f'<td class="{sk}">{client}</td>'
            f'<td class="muted{sk}">{act}</td>'
            f'<td class="c muted{sk}">{pax}</td>'
            f'<td class="r{sk}">\u20ac{total_abs:,.2f}</td>'
            f'<td class="comm{sk}">\u20ac{comm_abs:,.2f}</td>'
            f'<td class="c {sc}{sk}">{r["status"]}</td>'
            f"</tr>"
        )

    rows_html = ""
    if rows_by_month and len(rows_by_month) > 1:
        row_idx = 0
        for m_nome_i, m_ano_i, m_rows_i in rows_by_month:
            if not m_rows_i:
                continue
            rows_html += (
                f'<tr class="month-sep"><td colspan="8">{m_nome_i} {m_ano_i} \u2014 {len(m_rows_i)} reservas</td></tr>'
            )
            for i, r in enumerate(m_rows_i):
                cancelled = r["status"] == "Cancelado"
                rows_html += _row_html(r, "#F9FAFB" if (row_idx + i) % 2 == 0 else "#FFFFFF", strike=cancelled)
            row_idx += len(m_rows_i)
    else:
        for i, r in enumerate(rows):
            cancelled = r["status"] == "Cancelado"
            rows_html += _row_html(r, "#F9FAFB" if i % 2 == 0 else "#FFFFFF", strike=cancelled)

    if not rows_html:
        rows_html = (
            '<tr><td colspan="8" style="padding:14px 8px;color:var(--text3);font-style:italic;">'
            "Sem reservas para este per\u00edodo.</td></tr>"
        )

    title_mes = (
        " + ".join([f"{mn} {my}" for mn, my, _ in rows_by_month])
        if rows_by_month and len(rows_by_month) > 1
        else f"{mes_nome} {ano}"
    )

    tmpl = load_template("extrato_template.html")
    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    replacements = {
        "{{parceiro}}": parceiro,
        "{{ref}}": ref,
        "{{today}}": today,
        "{{title_mes}}": title_mes,
        "{{total_fim}}": "{:,.2f}".format(abs(t["total_fim"])),
        "{{rows_html}}": rows_html,
        "{{n_reservas}}": str(t["n"]),
        "{{n_canceladas}}": str(t["n_can"]),
        "{{gt}}": "{:,.2f}".format(abs(t["gt"])),
        "{{gc}}": "{:,.2f}".format(abs(t["gc"])),
        "{{n_norm}}": str(t["n_norm"]),
        "{{n_dev}}": str(t["n_dev"]),
        "{{comiss}}": "{:,.2f}".format(abs(t["comiss"])),
        "{{credito}}": "{:,.2f}".format(abs(t["credito"])),
    }
    for k, v in replacements.items():
        tmpl = tmpl.replace(k, str(v))
    return tmpl


def generate_pdf(html_string):
    from weasyprint import HTML
    return HTML(string=html_string).write_pdf()
