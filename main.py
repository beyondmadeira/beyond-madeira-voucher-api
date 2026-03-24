"""
Beyond Madeira - Voucher API
POST /gerar-voucher           -> Car Rental PDF
POST /gerar-voucher-atividade -> Activity PDF
GET  /                        -> Health check
"""

import os, io, base64
from flask import Flask, request, jsonify
from weasyprint import HTML

app = Flask(__name__)

API_KEY  = os.environ.get("VOUCHER_API_KEY", "beyond-madeira-voucher-2026")
BASE_DIR = os.path.dirname(__file__)

# ── PARTNER CONTACTS ──────────────────────────────────────────────────────────
RC_PARTNERS = {
    "Point Car":         ("+351 968 888 026", "booking@pointcarrental.pt"),
    "Atlantic Rent Car": ("+351 962 403 756", "reservations@atlanticrentacar.pt"),
    "RentCar Madeira":   ("+351 936 716 627", "booking@rentcarmadeira.com"),
    "AB4rent":           ("+351 961 932 738", "info@ab4rent.com"),
}


def logo_b64():
    with open(os.path.join(BASE_DIR, "logo_clean.png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

def fill(tmpl, data):
    for k, v in data.items():
        tmpl = tmpl.replace("{{" + k + "}}", str(v) if v is not None else "")
    return tmpl

def check_key():
    return request.headers.get("X-API-Key") == API_KEY

def fmt_date(s):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%-d %b %Y")
    except:
        return s

def fmt_time(s):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except:
        return s


# =========================================================================
# RENT CAR
# =========================================================================

def build_rc_html(d):
    with open(os.path.join(BASE_DIR, "voucher_rc_template.html")) as f:
        tmpl = f.read()

    # Parse ISO datetimes if needed
    for field in ["pickup_data", "dropoff_data"]:
        val = d.get(field, "")
        if "T" in val or "Z" in val:
            d[field.replace("data","hora")] = fmt_time(val)
            d[field] = fmt_date(val)

    # Optional sub-lines (flight / hotel)
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

    d["pickup_extra"]  = pu_extra
    d["dropoff_extra"] = do_extra
    d.setdefault("extras", "None")
    # Auto-fill partner contacts if not provided
    empresa = d.get("empresa", "")
    if not d.get("empresa_telefone") and empresa in RC_PARTNERS:
        d["empresa_telefone"], d["empresa_email"] = RC_PARTNERS[empresa]
    d.setdefault("empresa_telefone", "")
    d.setdefault("empresa_email", "")

    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    return fill(tmpl, d)


@app.route("/gerar-voucher", methods=["POST"])
def gerar_voucher():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400

        required = ["referencia", "total", "veiculo", "empresa",
                    "cliente", "telefone", "email",
                    "pickup_data", "pickup_hora", "pickup_local",
                    "dropoff_data", "dropoff_hora", "dropoff_local"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        html  = build_rc_html(d)
        pdf   = HTML(string=html).write_pdf()
        b64   = base64.b64encode(pdf).decode()
        fname = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ','_')}.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================================
# ACTIVITY VOUCHER
# =========================================================================

def build_at_html(d):
    with open(os.path.join(BASE_DIR, "voucher_at_template.html")) as f:
        tmpl = f.read()

    status   = d.get("status", "confirmed").lower()
    pagamento = d.get("pagamento", "cash").lower()

    # Status label
    if status == "paid":
        d["status_label"] = "Paid \u2713"
        d["status_class"] = "paid"
    elif status == "awaiting":
        d["status_label"] = "Awaiting Payment"
        d["status_class"] = "awaiting"
    else:
        d["status_label"] = "Confirmed"
        d["status_class"] = ""

    # Price card class
    if status == "paid":
        d["price_class"] = "paid"
        d["price_note"]  = "Payment received"
    elif status == "awaiting":
        d["price_class"] = "awaiting"
        d["price_note"]  = "Payment required"
    else:
        d["price_class"] = "cash"
        if "card" in pagamento and "cash" in pagamento:
            d["price_note"] = "Cash or card on the day"
        elif "card" in pagamento:
            d["price_note"] = "Card on the day"
        else:
            d["price_note"] = "Cash on the day"

    # Start time style
    hora = d.get("hora", "TBC")
    d["start_time_class"] = "tbc" if hora == "TBC" else "accent"

    # Payment alert block
    total = d.get("total", "")
    if status == "awaiting":
        d["payment_alert_html"] = f"""
<div class="pay-alert awaiting">
  <div class="pa-dot awaiting">!</div>
  <div>
    <div class="pa-title awaiting">Payment Required Before the Activity</div>
    <div class="pa-body awaiting">Please transfer <strong>{total}&euro;</strong> via MB Way
    (+351 939 566 415) or bank transfer. Send proof of payment to
    <strong>booking@beyondmadeira.com</strong></div>
  </div>
</div>"""
    elif status == "paid":
        d["payment_alert_html"] = f"""
<div class="pay-alert paid">
  <div class="pa-dot paid">&#10003;</div>
  <div>
    <div class="pa-title paid">Payment Confirmed</div>
    <div class="pa-body paid">Your payment of <strong>{total}&euro;</strong> has been received.
    No further payment required &mdash; just show up and enjoy!</div>
  </div>
</div>"""
    else:
        d["payment_alert_html"] = ""

    # Payment method block (only for confirmed)
    if status == "confirmed":
        pm_map = {
            "cash":      ("Payment: Cash Only",    "To be paid in cash on the day of the activity."),
            "card":      ("Payment: Card Only",    "To be paid by card on the day of the activity."),
            "cash_card": ("Payment: Cash or Card", "To be paid on the day &mdash; cash or card both accepted."),
        }
        pm_key = "cash_card" if ("card" in pagamento and "cash" in pagamento) else \
                 "card" if "card" in pagamento else "cash"
        pm_title, pm_body = pm_map[pm_key]
        d["payment_method_html"] = f"""
<div class="paymethod">
  <div class="pm-dot">$</div>
  <div><div class="pm-title">{pm_title}</div><div class="pm-body">{pm_body}</div></div>
</div>"""
    else:
        d["payment_method_html"] = ""

    # Pickup / meeting point block
    pickup_mode = d.get("pickup_mode", "none")
    pickup_loc  = d.get("pickup_local", "")
    hotel_det   = d.get("hotel_detail", "")
    hora_conf   = d.get("hora_confirmada", "")

    if pickup_mode != "none" and pickup_loc:
        if pickup_mode == "meeting_point":
            loc_label = "MEETING POINT"
            loc_note  = "Please make your own way to the meeting point at the time indicated."
        elif pickup_mode == "pickup_time_confirmed":
            loc_label = "PICK-UP"
            loc_note  = f"Pick-up at <strong>{hora_conf}</strong>." if hora_conf else "Pick-up time confirmed."
        elif pickup_mode == "pickup_day_before":
            loc_label = "PICK-UP LOCATION"
            loc_note  = "Pick-up time will be sent to you the day before the activity."
        else:
            loc_label = "PICK-UP LOCATION"
            loc_note  = "Pick-up time will be confirmed closer to the date."

        hotel_line = f'<div class="pickup-sub">{hotel_det}</div>' if hotel_det else ""
        d["pickup_html"] = f"""
<div class="pickup-card">
  <div class="pickup-dot">&#9679;</div>
  <div>
    <div class="pickup-lbl">{loc_label}</div>
    <div class="pickup-loc">{pickup_loc}</div>
    {hotel_line}
    <div class="pickup-note">{loc_note}</div>
  </div>
</div>"""
    else:
        d["pickup_html"] = ""

    # Special requests
    if d.get("pedido_especial"):
        d["special_requests_html"] = f"""
<div class="special-req">
  <div class="sr-label">Special Requests</div>
  <div class="sr-text">{d["pedido_especial"]}</div>
</div>"""
    else:
        d["special_requests_html"] = ""

    # Invoice rows
    items = d.get("items", [])
    if not items:
        hora_inv = d.get("hora", "TBC")
        items = [{
            "nome":    d.get("atividade", ""),
            "detalhe": f"{d.get('data','')} &middot; {hora_inv}",
            "qty":     d.get("pax", ""),
            "unit":    d.get("preco_unit", ""),
            "sub":     d.get("total", ""),
        }]
    rows_html = ""
    for it in items:
        unit_str = f"&euro;{it['unit']}" if it.get("unit") else ""
        rows_html += f"""
<div class="inv-row">
  <div class="inv-prod">
    <div class="inv-name">{it.get("nome","")}</div>
    <div class="inv-detail">{it.get("detalhe","")}</div>
  </div>
  <div class="inv-qty">{it.get("qty","")}x</div>
  <div class="inv-unit">{unit_str}</div>
  <div class="inv-sub">&euro;{it.get("sub","")}</div>
</div>"""
    d["invoice_rows_html"] = rows_html

    d.setdefault("cancelamento",
        "Free cancellation up to <strong>48 hours</strong> before the activity. "
        "Late cancellations or no-shows may incur a fee.")
    d.setdefault("mensagem_confirmacao",
        "Your reservation is confirmed &mdash; no payment required at this stage. "
        "The total amount is to be paid in cash on the day of the activity. "
        "You will receive further details closer to the date, including your exact pick-up time.")
    d.setdefault("operador_telefone", "")
    d.setdefault("operador_email", "")
    d.setdefault("bokun_ref", "")

    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    return fill(tmpl, d)


@app.route("/gerar-voucher-atividade", methods=["POST"])
def gerar_voucher_atividade():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400

        required = ["referencia", "atividade", "data", "cliente", "total"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        html  = build_at_html(d)
        pdf   = HTML(string=html).write_pdf()
        b64   = base64.b64encode(pdf).decode()
        fname = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ','_')}.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================================
# HEALTH
# =========================================================================

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Beyond Madeira Voucher API",
        "endpoints": ["/gerar-voucher", "/gerar-voucher-atividade"]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
