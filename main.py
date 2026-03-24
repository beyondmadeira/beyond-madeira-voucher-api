"""
Beyond Madeira - Voucher API
POST /gerar-voucher              -> Car Rental PDF
POST /gerar-voucher-atividade    -> Activity PDF
GET  /airtable/rc                -> List RC reservations
PATCH /airtable/rc/<id>          -> Update RC reservation
GET  /airtable/at                -> List AT reservations
PATCH /airtable/at/<id>          -> Update AT reservation
GET  /airtable/sitemap           -> List Sitemap records
PATCH /airtable/sitemap/<id>     -> Update Sitemap record
GET  /airtable/biblioteca        -> List FAQ/Biblioteca records
PATCH /airtable/biblioteca/<id>  -> Update Biblioteca record
GET  /airtable/guia              -> List Madeira Guide records
PATCH /airtable/guia/<id>        -> Update Guia record
GET  /                           -> Health check
"""

import os, re, base64, requests as req_lib
from flask import Flask, request, jsonify
from flask_cors import CORS
from weasyprint import HTML

app = Flask(__name__)
CORS(app, origins=["https://hub.beyondmadeira.com", "https://hub-crm.8vesjw.easypanel.host", "http://localhost", "file://"])

# =========================================================================
# CACHE — 30 minute TTL
# =========================================================================
import time
_cache = {}
CACHE_TTL = 6 * 60 * 60  # 6 hours

def cache_get(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def cache_set(key, data):
    _cache[key] = (data, time.time())

def cache_clear(key=None):
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
API_KEY  = os.environ.get("VOUCHER_API_KEY", "beyond-madeira-voucher-2026")
BASE_DIR = os.path.dirname(__file__)

# Airtable
AT_TOKEN        = os.environ.get("AIRTABLE_TOKEN", "")
BASE_RESERVAS   = "appR8ZKP5ygR8o8Q0"
BASE_CONHECIMENTO = "appKhPwEBxolWaO9r"
BASE_FINANCEIRO   = "appOrdG5Fsr7N0RmH"
AT_HEADERS      = lambda: {"Authorization": f"Bearer {AT_TOKEN}", "Content-Type": "application/json"}


# =========================================================================
# OPERATOR CONTACTS  (auto-filled — no need to send from Make)
# =========================================================================
OPERATOR_CONTACTS = {
    # Activity operators
    "Safari Madeira":            ("+351 919 864 485", "geral@safarimadeira.com"),
    "Madeira Surreal":           ("+351 922 250 684", ""),
    "Green Devil":               ("+351 961 858 780", "info@greendevilsafari.com"),
    "Jungle Lost":               ("+351 962 168 343", ""),
    "101 Routes":                ("+351 936 478 827", ""),
    "Bearded Madeira Tours":     ("+351 939 145 577", ""),
    "Madeira Discovery":         ("+351 964 571 656", ""),
    "Madeira Horizon":           ("+351 963 319 263", ""),
    "Madeira Tours":             ("+351 938 665 493", ""),
    "Warriors Adventure":        ("+351 963 359 570", ""),
    "Icon Travel":               ("+351 925 559 159", ""),
    "Fado & Fado Madeira":       ("+351 963 005 343", ""),
    "SeaBorn":                   ("+351 291 231 312", ""),
    "VMT":                       ("+351 963 796 860", ""),
    "VIP Dolphins":              ("+351 924 438 001", "info@vipdolphins.com"),
    "Bonita da Madeira":         ("+351 918 118 771", ""),
    "SeaMotions":                ("+351 910 308 804", ""),
    "On Tales":                  ("+351 911 911 777", ""),
    "Rota dos Cetáceos":         ("+351 918 828 242", "rotacetaceos@gmail.com"),
    "Azul Diving":               ("+351 914 526 675", "info@azuldiving.com"),
    "Sea La Vie":                ("+351 965 710 036", ""),
    "Surf Club Madeira":         ("+351 963 356 674", ""),
    "Be Local":                  ("+351 935 124 260", ""),
    "Epic Madeira":              ("+351 913 988 682", ""),
    "Trail4Fun":                 ("+351 913 211 323", ""),
    "Quad Xperience":            ("+351 933 914 781", ""),
    "Fly on Madeira":            ("+351 966 712 882", ""),
    "E-Bike Madeira":            ("+351 926 672 808", ""),
    "Madeira Explorers":         ("+351 962 797 887", ""),
    "Lido Tours":                ("+351 916 609 726", ""),
    "Free Spirit":               ("+351 927 390 020", ""),
    "Wilder Madeira":            ("+351 911 993 345", "info@wildermadeira.com"),
    "DamWalk":                   ("+351 915 667 020", ""),
    "Madeira Adventure Kingdom": ("+351 918 080 557", ""),
    "Nau Santa Maria":           ("+351 965 010 180", ""),
    "Fishing Family":            ("+351 966 377 701", ""),
    "Do It Madeira":             ("+351 912 345 678", ""),
    # Rent car
    "Point Car":                 ("+351 968 888 026", "booking@pointcarrental.pt"),
    "Atlantic Rent Car":         ("+351 962 403 756", "reservations@atlanticrentacar.pt"),
    "RentCar Madeira":           ("+351 936 716 627", "booking@rentcarmadeira.com"),
    "AB4rent":                   ("+351 961 932 738", "info@ab4rent.com"),
    "Amsterdam Car":             ("+351 968 566 790", ""),
}


# =========================================================================
# ACTIVITY RULES  (keyword-based auto-detection)
# =========================================================================
TIPS_TEXT = {
    "warm":       "Dress very warmly — it can be very cold at high altitude.",
    "jacket":     "Bring a light jacket — temperatures change quickly in the mountains.",
    "swimsuit":   "Bring swimsuit and towel.",
    "sunscreen":  "Don't forget sunscreen.",
    "water":      "Bring water.",
    "snack":      "Bring a snack.",
    "shoes":      "Wear comfortable walking shoes.",
    "flashlight": "Bring a flashlight/torch — essential for tunnel sections.",
}

ACTIVITY_RULES = [
    {"kw": ["sunrise", "pico areeiro"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["warm", "water", "snack", "shoes"],
     "note": "Dress very warmly — Pico Areeiro can be below 0°C at sunrise."},

    {"kw": ["caldeirao verde", "caldeirão verde"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "water", "flashlight", "snack", "shoes"],
     "note": "A flashlight is essential for the tunnel section of the trail."},

    {"kw": ["west", "jeep"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "swimsuit", "water", "snack"],
     "note": "The tour may include a swim stop — bring swimwear just in case."},

    {"kw": ["west", "minivan"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "swimsuit", "water", "snack"],
     "note": "The tour may include a swim stop — bring swimwear just in case."},

    {"kw": ["east", "jeep"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "water", "snack"], "note": ""},

    {"kw": ["east", "minivan"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "water", "snack"], "note": ""},

    {"kw": ["whale", "dolphin"],
     "payment": "cash_card", "pickup": "meeting_point",
     "tips": ["jacket", "swimsuit", "sunscreen", "water"],
     "note": "Please arrive at the marina 30 minutes before departure for check-in and payment."},

    {"kw": ["sunset"],
     "payment": "cash_card", "pickup": "meeting_point",
     "tips": ["jacket", "sunscreen", "water"], "note": ""},

    {"kw": ["canyoning"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "swimsuit", "sunscreen", "snack"],
     "note": "All equipment is included. Bring swimwear and warm clothes for after."},

    {"kw": ["coasteering"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "swimsuit", "sunscreen", "water"],
     "note": "All equipment is included."},

    {"kw": ["hike", "levada", "stairway to heaven"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "water", "snack", "shoes"], "note": ""},

    {"kw": ["buggy", "quad"],
     "payment": "cash_card", "pickup": "pickup_hotel",
     "tips": ["jacket", "water", "snack"], "note": ""},

    {"kw": ["paragliding", "paraglide"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "shoes"],
     "note": "Wear comfortable clothes and closed shoes."},

    {"kw": ["kayak"],
     "payment": "cash_card", "pickup": "meeting_point",
     "tips": ["swimsuit", "sunscreen", "water", "snack"], "note": ""},

    {"kw": ["diving", "scuba"],
     "payment": "cash", "pickup": "meeting_point",
     "tips": ["swimsuit", "sunscreen", "water"],
     "note": "All equipment provided. No experience needed."},

    {"kw": ["surf"],
     "payment": "cash", "pickup": "meeting_point",
     "tips": ["swimsuit", "sunscreen", "water"],
     "note": "All equipment provided."},

    {"kw": ["fishing"],
     "payment": "cash", "pickup": "meeting_point",
     "tips": ["jacket", "sunscreen", "water", "snack"], "note": ""},

    {"kw": ["private"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "water"], "note": ""},
]


def detect_activity(nome):
    """Match activity name to rule using keywords."""
    n = nome.lower()
    for rule in ACTIVITY_RULES:
        if all(kw in n for kw in rule["kw"]):
            return rule
    return None


# =========================================================================
# HELPERS
# =========================================================================
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
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%-d %b %Y")
    except:
        return s

def fmt_time(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%H:%M")
    except:
        return s


def airtable_list(base_id, table_name, max_records=1000):
    """Fetch all records from an Airtable table."""
    url = f"https://api.airtable.com/v0/{base_id}/{req_lib.utils.quote(table_name)}"
    records = []
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = req_lib.get(url, headers=AT_HEADERS(), params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def airtable_patch(base_id, table_name, record_id, fields):
    """Patch a single Airtable record."""
    url = f"https://api.airtable.com/v0/{base_id}/{req_lib.utils.quote(table_name)}/{record_id}"
    r = req_lib.patch(url, headers=AT_HEADERS(), json={"fields": fields}, timeout=15)
    r.raise_for_status()
    return r.json()


def airtable_create(base_id, table_name, fields):
    """Create a single Airtable record."""
    url = f"https://api.airtable.com/v0/{base_id}/{req_lib.utils.quote(table_name)}"
    r = req_lib.post(url, headers=AT_HEADERS(), json={"fields": fields}, timeout=15)
    r.raise_for_status()
    return r.json()


@app.route("/airtable/rc", methods=["POST"])
def create_rc():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_create(BASE_RESERVAS, "Rent Car", fields)
        cache_clear("rc")
        # Return a simplified record with the new ID
        rec_id = result.get("id", "")
        rec_fields = result.get("fields", {})
        return jsonify({"success": True, "record": {"id": rec_id, "fields": rec_fields}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/at", methods=["POST"])
def create_at():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_create(BASE_RESERVAS, "Atividades", fields)
        cache_clear("at")
        rec_id = result.get("id", "")
        rec_fields = result.get("fields", {})
        return jsonify({"success": True, "record": {"id": rec_id, "fields": rec_fields}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================================
# RENT CAR
# =========================================================================
def build_rc_html(d):
    with open(os.path.join(BASE_DIR, "voucher_rc_template.html")) as f:
        tmpl = f.read()

    for field in ["pickup_data", "dropoff_data"]:
        val = d.get(field, "")
        if "T" in val or "Z" in val:
            d[field.replace("data", "hora")] = fmt_time(val)
            d[field] = fmt_date(val)

    pu_extra = ""
    if d.get("pickup_voo"):   pu_extra += f'<div class="date-sub">Flight: {d["pickup_voo"]}</div>'
    if d.get("pickup_hotel"): pu_extra += f'<div class="date-sub">{d["pickup_hotel"]}</div>'
    do_extra = ""
    if d.get("dropoff_voo"):   do_extra += f'<div class="date-sub">Flight: {d["dropoff_voo"]}</div>'
    if d.get("dropoff_hotel"): do_extra += f'<div class="date-sub">{d["dropoff_hotel"]}</div>'

    d["pickup_extra"]  = pu_extra
    d["dropoff_extra"] = do_extra
    d.setdefault("extras", "None")

    # Auto-fill operator contacts
    empresa = d.get("empresa", "")
    if not d.get("empresa_telefone") and empresa in OPERATOR_CONTACTS:
        d["empresa_telefone"], d["empresa_email"] = OPERATOR_CONTACTS[empresa]
    d.setdefault("empresa_telefone", "")
    d.setdefault("empresa_email", "")

    # Build empresa contact block — only show if there's actual contact info
    tel = d.get("empresa_telefone", "")
    eml = d.get("empresa_email", "")
    if tel or eml:
        det = ""
        if tel: det += tel
        if tel and eml: det += "<br>"
        if eml: det += eml
        d["empresa_contact_block"] = f'<div class="contact-card"><div class="contact-lbl">Rental Company</div><div class="contact-name">{empresa}</div><div class="contact-det">{det}</div></div>'
    else:
        d["empresa_contact_block"] = ""

    # Build contacts row — full width if no partner contact
    beyond_card = '<div class="contact-card"><div class="contact-lbl">Beyond Madeira</div><div class="contact-name">Booking Support</div><div class="contact-det">+351 939 566 415<br>booking@beyondmadeira.com</div></div>'
    if d["empresa_contact_block"]:
        d["contacts_row_html"] = f'<div class="contacts-row">{d["empresa_contact_block"]}{beyond_card}</div>'
    else:
        d["contacts_row_html"] = f'<div class="contacts-row">{beyond_card}</div>'

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
        required = ["referencia", "total", "veiculo", "empresa", "cliente",
                    "telefone", "email", "pickup_data", "pickup_hora",
                    "pickup_local", "dropoff_data", "dropoff_hora", "dropoff_local"]
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
            tips_html = '<div class="special-req"><div class="sr-label">What to Bring &amp; Useful Tips</div><div class="sr-text">' + "<br>".join(f"&#183; {t}" for t in tips_lines) + "</div></div>"
    if d.get("pedido_especial"):
        tips_html += f'<div class="special-req"><div class="sr-label">Special Requests</div><div class="sr-text">{d["pedido_especial"]}</div></div>'
    d["special_requests_html"] = tips_html

    status    = d.get("status", "confirmed").lower()
    pagamento = d.get("pagamento", "cash").lower()

    if status == "paid":
        d["status_label"] = "Paid \u2713"
        d["status_class"] = "paid"
        d["price_class"]  = "paid"
        d["price_note"]   = "Payment received"
    elif status == "awaiting":
        d["status_label"] = "Awaiting Payment"
        d["status_class"] = "awaiting"
        d["price_class"]  = "awaiting"
        d["price_note"]   = "Payment required"
    else:
        d["status_label"] = "Confirmed"
        d["status_class"] = ""
        d["price_class"]  = "cash"
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
        if stripe_link:
            pay_btn = f'<a href="{stripe_link}" style="display:inline-block;margin-top:12px;background:var(--amber);color:#fff;font-weight:800;font-size:13px;padding:10px 24px;border-radius:8px;text-decoration:none;letter-spacing:-.2px;">Pay Now &rarr;</a>'
        else:
            pay_btn = ""
        d["payment_alert_html"] = f'<div class="pay-alert awaiting"><div class="pa-dot awaiting">!</div><div><div class="pa-title awaiting">Payment Required Before the Activity</div><div class="pa-body awaiting">To secure your booking, please complete your payment securely online.{pay_btn}</div></div></div>'
    elif status == "paid":
        d["payment_alert_html"] = f'<div class="pay-alert paid"><div class="pa-dot paid">&#10003;</div><div><div class="pa-title paid">Payment Confirmed</div><div class="pa-body paid">Your payment of <strong>{total}&euro;</strong> has been received. No further payment required &mdash; just show up and enjoy!</div></div></div>'
    else:
        d["payment_alert_html"] = ""

    if status == "confirmed":
        pm_map = {
            "cash":      ("Payment: Cash Only",    "To be paid in cash on the day of the activity."),
            "card":      ("Payment: Card Only",    "To be paid by card on the day of the activity."),
            "cash_card": ("Payment: Cash or Card", "To be paid on the day &mdash; cash or card both accepted."),
        }
        pm_key = "cash_card" if ("card" in pagamento and "cash" in pagamento) else "card" if "card" in pagamento else "cash"
        pt, pb = pm_map[pm_key]
        d["payment_method_html"] = f'<div class="paymethod"><div class="pm-dot">$</div><div><div class="pm-title">{pt}</div><div class="pm-body">{pb}</div></div></div>'
    else:
        d["payment_method_html"] = ""

    pickup_mode = d.get("pickup_mode", "none")
    pickup_loc  = d.get("pickup_local", "")
    hotel_det   = d.get("hotel_detail", "")
    hora_conf   = d.get("hora_confirmada", "")

    if pickup_mode != "none" and pickup_loc:
        labels = {
            "meeting_point":        ("MEETING POINT",    "Please make your own way to the meeting point at the time indicated."),
            "pickup_time_confirmed":("PICK-UP",          f"Pick-up at <strong>{hora_conf}</strong>." if hora_conf else "Pick-up time confirmed."),
            "pickup_day_before":    ("PICK-UP LOCATION", "Pick-up time will be sent to you the day before the activity."),
        }
        loc_label, loc_note = labels.get(pickup_mode, ("PICK-UP LOCATION", "Pick-up time will be confirmed closer to the date."))
        hotel_line = f'<div class="pickup-sub">{hotel_det}</div>' if hotel_det else ""
        d["pickup_html"] = f'<div class="pickup-card"><div class="pickup-dot">&#9679;</div><div><div class="pickup-lbl">{loc_label}</div><div class="pickup-loc">{pickup_loc}</div>{hotel_line}<div class="pickup-note">{loc_note}</div></div></div>'
    else:
        d["pickup_html"] = ""

    items = d.get("items", [])
    if not items:
        items = [{"nome": d.get("atividade",""), "detalhe": f"{d.get('data','')} &middot; {d.get('hora','TBC')}", "qty": d.get("pax",""), "unit": d.get("preco_unit",""), "sub": d.get("total","")}]
    rows_html = ""
    for it in items:
        unit_str = f"&euro;{it['unit']}" if it.get("unit") else ""
        rows_html += f'<div class="inv-row"><div class="inv-prod"><div class="inv-name">{it.get("nome","")}</div><div class="inv-detail">{it.get("detalhe","")}</div></div><div class="inv-qty">{it.get("qty","")}x</div><div class="inv-unit">{unit_str}</div><div class="inv-sub">&euro;{it.get("sub","")}</div></div>'
    d["invoice_rows_html"] = rows_html

    d.setdefault("cancelamento", "Free cancellation up to <strong>48 hours</strong> before the activity. Late cancellations or no-shows may incur a fee.")
    d.setdefault("mensagem_confirmacao", "Your reservation is confirmed &mdash; no payment required at this stage. The total amount is to be paid in cash on the day of the activity. You will receive further details closer to the date, including your exact pick-up time.")
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
# AIRTABLE — RESERVAS (RC + AT)  base: appR8ZKP5ygR8o8Q0
# =========================================================================

@app.route("/airtable/rc", methods=["GET"])
def get_rc():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("rc")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_RESERVAS, "Rent Car")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "ref":         f.get("Referência", f.get("Referencia", "")),
                "nome":        f.get("Nome do cliente", ""),
                "tel":         f.get("Número de Telemovel", ""),
                "email":       f.get("Email do cliente", ""),
                "idade":       f.get("Idade", ""),
                "parceiro":    f.get("Fornecedor/Parceiro", ""),
                "carro":       f.get("Modelo de Carro", ""),
                "estado":      f.get("Estado de Reserva", ""),
                "pagamento":   "",  # RC has no payment status field
                "pdt":         f.get("Data da Pick-up", ""),
                "ploc":        f.get("Localização Pick-up", f.get("Local Pick-up", "")),
                "pvoo":        "",  # RC has no flight field
                "pdet":        f.get("Detalhes Pick Up", ""),
                "ddt":         f.get("Data do Drop Off", ""),
                "dloc":        f.get("Localização Drop-off", f.get("Local Drop-off", "")),
                "dvoo":        "",  # RC has no flight field
                "ddet":        f.get("Detalhes Drop Off", ""),
                "total":       f.get("Valor da Reserva (€)", 0),
                "com":         f.get("Comissão", 0),
                "dur":         f.get("Duração", 0),
                "ext":         f.get("Extras", ""),
                "obs":         f.get("Observações", ""),
                "refp":        f.get("Referência Parceiro", ""),
                "eEnv":        f.get("Email Enviado", False),
                "rEnv":        f.get("Review Enviado", False),
                "dataFeita":   f.get("Data Feita a Reserva", ""),
            })
        cache_set("rc", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/rc/<record_id>", methods=["PATCH"])
def patch_rc(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_RESERVAS, "Rent Car", record_id, fields)
        cache_clear("rc")  # invalidate cache after update
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/at", methods=["GET"])
def get_at():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("at")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_RESERVAS, "Atividades")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "ref":         f.get("Referência", rec["id"]),
                "nome":        f.get("Nome do Cliente", ""),
                "tel":         f.get("Contacto Telefonico", ""),
                "email":       f.get("Email Clientes", ""),
                "atv":         f.get("Atividade", ""),
                "cat":         f.get("Categoria", ""),
                "par":         f.get("Fornecedor/Parceiro", ""),
                "pess":        f.get("Nº Pessoas", ""),
                "data":        f.get("Data da Atividade", ""),
                "hora":        (f.get("Data da Atividade","") or "").split("T")[1][:5] if "T" in (f.get("Data da Atividade","") or "") else "",
                "total":       f.get("Preço Total", 0),
                "com":         f.get("Comissão", 0),
                "estado_res":  f.get("Estado da Reserva", ""),
                "pagamento":   f.get("Estado de Pagamento", ""),
                "obs":         f.get("Observação", ""),
                "local":       f.get("Pick-up local", ""),
                "stripe":      f.get("Stripe Link", ""),
                "idiomas":     f.get("Idiomas", ""),
                "eEnv":        f.get("Email Enviado", False),
                "tyEnv":       f.get("Thank You Enviado", False),
                "rEnv":        f.get("Review Pedida", False),
                "dataFeita":   f.get("Created", ""),
            })
        cache_set("at", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/at/<record_id>", methods=["PATCH"])
def patch_at(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_RESERVAS, "Atividades", record_id, fields)
        cache_clear("at")  # invalidate cache after update
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================================
# AIRTABLE — CONHECIMENTO  base: appKhPwEBxolWaO9r
# =========================================================================

@app.route("/airtable/sitemap", methods=["GET"])
def get_sitemap():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_CONHECIMENTO, "Sitemap")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":        rec["id"],
                "nome":      f.get("Nome de Página", f.get("Nome de Pagina", "")),
                "estado":    f.get("Estado", ""),
                "categoria": f.get("Categoria Principal", ""),
                "url":       f.get("URL", ""),
                "cat":       f.get("Categoria", ""),
                "conteudo":  f.get("Conteúdo", f.get("Conteudo", "")),
                "modified":  f.get("Last Modified", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/sitemap/<record_id>", methods=["PATCH"])
def patch_sitemap(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_CONHECIMENTO, "Sitemap", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/biblioteca", methods=["GET"])
def get_biblioteca():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_CONHECIMENTO, "Biblioteca")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":       rec["id"],
                "titulo":   f.get("Answer Title", ""),
                "gatilho":  f.get("Trigger / Customer Question", ""),
                "resposta": f.get("Answer", ""),
                "categoria":f.get("Category", ""),
                "estado":   f.get("Status", ""),
                "obs":      f.get("Observação", f.get("Observacao", "")),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/biblioteca/<record_id>", methods=["PATCH"])
def patch_biblioteca(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_CONHECIMENTO, "Biblioteca", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/guia", methods=["GET"])
def get_guia():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_CONHECIMENTO, "Madeira Guide")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "titulo":      f.get("Nome", ""),
                "categoria":   f.get("Categoria", ""),
                "descricao":   f.get("Descrição", f.get("Descricao", "")),
                "localizacao": f.get("Localização", f.get("Localizacao", "")),
                "estado":      f.get("Estado", ""),
                "prioridade":  f.get("Prioridade", ""),
                "tags":        f.get("Tags", ""),
                "notas":       f.get("Notas Internas", ""),
                "recomendado": f.get("Recomendado?", False),
                "preco":       f.get("Preço Nível", f.get("Preco Nivel", "")),
                "horario":     f.get("Horário", f.get("Horario", "")),
                "distancia":   f.get("Distância", f.get("Distancia", "")),
                "dificuldade": f.get("Dificuldade", ""),
                "website":     f.get("Website", ""),
                "contacto":    f.get("Contacto", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/guia/<record_id>", methods=["PATCH"])
def patch_guia(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_CONHECIMENTO, "Madeira Guide", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# =========================================================================
# AIRTABLE — FINANCEIRO  base: appOrdG5Fsr7N0RmH
# Tabelas: Registos Diários, Resumos Mensais, Despesas Fixas,
#          Despesas Variáveis, Objetivos & Crescimento, Caixa Mensal
# =========================================================================

@app.route("/airtable/diario", methods=["GET"])
def get_diario():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("diario")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_FINANCEIRO, "Registos Diários")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":       rec["id"],
                "data":     f.get("Data", ""),
                "fat":      f.get("Faturação Diária", 0),
                "fat_rc":   f.get("Faturação RC", 0),
                "fat_at":   f.get("Faturação AT", 0),
                "mes":      f.get("Resumo Mensal", ""),
                "notas":    f.get("Notas do Dia", ""),
                "resp":     f.get("Responsável", ""),
            })
        cache_set("diario", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/diario", methods=["POST"])
def create_diario():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_create(BASE_FINANCEIRO, "Registos Diários", fields)
        cache_clear("diario")
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/diario/<record_id>", methods=["PATCH"])
def patch_diario(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_FINANCEIRO, "Registos Diários", record_id, fields)
        cache_clear("diario")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/resumos-mensais", methods=["GET"])
def get_resumos_mensais():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("resumos_mensais")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_FINANCEIRO, "Resumos Mensais")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "mes":         f.get("Resumo Mensal", rec["id"]),
                "fat":         f.get("Total de Faturação Mensal (€)", 0),
                "fat_rc":      f.get("Faturação RC", 0),
                "fat_at":      f.get("Faturação AT", 0),
                "lucro":       f.get("Lucro Mensal (Automático)", 0),
                "caixa":       f.get("Caixa Final (€)", 0),
                "receita":     f.get("Receita Realizada", 0),
                "obj":         f.get("Objetivo Mensal (€)", 0),
                "diff_obj":    f.get("Diferença vs Objetivo", 0),
                "desp_fixas":  f.get("Total de Despesas Fixas (€)", 0),
                "desp_var":    f.get("Total de Despesas Variáveis (€)", 0),
                "desp_total":  f.get("Total de Despesas (€)", 0),
                "media_diaria":f.get("Média Diária de Faturação (€)", 0),
                "dias_fat":    f.get("N.º de Dias com Faturação", 0),
                "nres_rc":     f.get("Nº Reservas RC", 0),
                "nres_at":     f.get("Nº Reservas AT", 0),
                "status":      f.get("Status do Mês", ""),
                "notas":       f.get("Notas do Mês", ""),
            })
        cache_set("resumos_mensais", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/despesas-fixas", methods=["GET"])
def get_despesas_fixas():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_FINANCEIRO, "Despesas Fixas")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "categoria":   f.get("Categoria", ""),
                "valor":       f.get("Valor Mensal", 0),
                "mes":         f.get("Resumo Mensal(s)", ""),
                "fornecedor":  f.get("Fornecedor", ""),
                "nif":         f.get("NIF Fornecedor", ""),
                "metodo":      f.get("Método Pagamento", ""),
                "recorrente":  f.get("Recorrente?", False),
                "pago":        f.get("Pago?", False),
                "notas":       f.get("Notas", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/despesas-variaveis", methods=["GET"])
def get_despesas_variaveis():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_FINANCEIRO, "Despesas Variáveis")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "categoria":   f.get("Categoria", ""),
                "valor":       f.get("Valor", 0),
                "tipo":        f.get("Tipo Despesa", ""),
                "fornecedor":  f.get("Fornecedor", ""),
                "nif":         f.get("NIF Fornecedor", ""),
                "metodo":      f.get("Método Pagamento", ""),
                "pago":        f.get("Pago?", False),
                "notas":       f.get("Notas", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/objetivos", methods=["GET"])
def get_objetivos():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_FINANCEIRO, "Objetivos & Crescimento")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":              rec["id"],
                "mes":             f.get("Objetivos", rec["id"]),
                "obj_fat":         f.get("🎯 Objetivo Faturação (€)", 0),
                "res_fat":         f.get("Resultado Faturação (€)", 0),
                "dif_fat":         f.get("📊 Diferença Faturação (€)", 0),
                "obj_lucro":       f.get("🎯 Objetivo Lucro (€)", 0),
                "res_lucro":       f.get("Resultado Lucro (€)", 0),
                "obj_reviews":     f.get("🎯 Objetivo Reviews", 0),
                "res_reviews":     f.get("Resultado Reviews", 0),
                "obj_ig":          f.get("🎯 Objetivo Instagram", 0),
                "res_ig":          f.get("Resultado Instagram", 0),
                "obj_fb":          f.get("🎯 Objetivo Facebook", 0),
                "res_fb":          f.get("Resultado Facebook", 0),
                "obj_tiktok":      f.get("🎯 Objetivo Tiktok", 0),
                "res_tiktok":      f.get("Resultado Tiktok", 0),
                "obj_views":       f.get("🎯 Objetivo Website Views", 0),
                "res_views":       f.get("Resultado Website Views", 0),
                "obj_users":       f.get("🎯 Objetivo Utilizadores Ativos", 0),
                "res_users":       f.get("Resultado Utilizadores Ativos", 0),
                "status":          f.get("Status Geral", ""),
                "acoes":           f.get("Ações do Mês", ""),
                "notas":           f.get("Notas", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/caixa-mensal", methods=["GET"])
def get_caixa_mensal():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_FINANCEIRO, "Caixa Mensal")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "mes":         f.get("Caixa Mensal", rec["id"]),
                "saldo_dinheiro": f.get("Saldo Dinheiro (€)", 0),
                "saldo_banco": f.get("Saldo Banco (€)", 0),
                "saldo_total": f.get("Saldo Total (€)", 0),
                "fat_mes":     f.get("Faturação do Mês (€)", 0),
                "desp_mes":    f.get("Despesas do Mês (€)", 0),
                "lucro":       f.get("Lucro Calculado (€)", 0),
                "diferenca":   f.get("Diferença vs Caixa Real (€)", 0),
                "notas":       f.get("Notas", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/parceiros", methods=["GET"])
def get_parceiros():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("parceiros")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_RESERVAS, "Parceiros")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":                   rec["id"],
                "nome":                 f.get("Nome", f.get("Name", rec["id"])),
                "categoria":            f.get("Categoria", ""),
                "tel":                  f.get("Contacto Telefone", ""),
                "email":                f.get("Email", ""),
                "website":              f.get("Website", ""),
                "morada":               f.get("Morada Office", ""),
                "meeting_point":        f.get("Meeting Point", ""),
                "comissao_tipo":        f.get("Comissão Tipo", ""),
                "comissao_valor":       f.get("Comissão Valor", 0),
                "comissao_notas":       f.get("Comissão Notas", ""),
                "instrucoes_aeroporto": f.get("Instruções Aeroporto", ""),
                "instrucoes_hotel":     f.get("Instruções Hotel", ""),
                "instrucoes_office":    f.get("Instruções Office", ""),
                "atividades":           f.get("Atividades / Passeios", ""),
                "logo_url":             f.get("Logo URL", ""),
                "notas":                f.get("Notas Internas", ""),
                "ativo":                f.get("Ativo?", True),
            })
        cache_set("parceiros", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/parceiros/<record_id>", methods=["PATCH"])
def patch_parceiros(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400
        result = airtable_patch(BASE_RESERVAS, "Parceiros", record_id, fields)
        cache_clear("parceiros")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/clientes", methods=["GET"])
def get_clientes():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("clientes")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list(BASE_RESERVAS, "Clientes")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":               rec["id"],
                "email":            f.get("Email", ""),
                "tel":              f.get("Telefone", ""),
                "n_rc":             f.get("N RC", 0),
                "n_at":             f.get("N AT", 0),
                "total_rc":         f.get("Total Gasto RC", 0),
                "total_at":         f.get("Total Gasto AT", 0),
                "total":            f.get("Total Gasto", 0),
                "n_total":          f.get("N Total Reservas", 0),
                "primeira_reserva": f.get("Primeira Reserva", ""),
                "ultima_reserva":   f.get("Ultima Reserva", ""),
                "pais":             f.get("País", ""),
                "notas":            f.get("Notas", ""),
                "vip":              f.get("VIP?", False),
            })
        cache_set("clientes", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/reviews", methods=["GET"])
def get_reviews():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Reviews")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":         rec["id"],
                "nome":       f.get("Nome Cliente", ""),
                "email":      f.get("Email Cliente", ""),
                "nota":       f.get("Nota (1-5)", 0),
                "texto":      f.get("Texto Review", ""),
                "data":       f.get("Data", ""),
                "reserva":    f.get("Reserva Relacionada", ""),
                "tipo":       f.get("Tipo Reserva", ""),
                "respondido": f.get("Respondido?", False),
                "resposta":   f.get("Resposta", ""),
                "link":       f.get("Link Review", ""),
                "notas":      f.get("Notas Internas", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/reviews/<record_id>", methods=["PATCH"])
def patch_reviews(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_RESERVAS, "Reviews", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/disponibilidade", methods=["GET"])
def get_disponibilidade():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Disponibilidade")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "carro":       f.get("Carro", ""),
                "data_inicio": f.get("Data Início", ""),
                "data_fim":    f.get("Data Fim", ""),
                "motivo":      f.get("Motivo", ""),
                "alternativa": f.get("Alternativa Sugerida", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/disponibilidade", methods=["POST"])
def create_disponibilidade():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_create(BASE_RESERVAS, "Disponibilidade", fields)
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/disponibilidade/<record_id>", methods=["PATCH"])
def patch_disponibilidade(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_RESERVAS, "Disponibilidade", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/frota", methods=["GET"])
def get_frota():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Carros")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":            rec["id"],
                "carro":         f.get("Carro", ""),
                "tipo":          f.get("Tipo", ""),
                "preco_baixa_12":  f.get("Preço Baixa 1-2d", 0),
                "preco_baixa_36":  f.get("Preço Baixa 3-6d", 0),
                "preco_baixa_7p":  f.get("Preço Baixa 7d+", 0),
                "preco_alta_12":   f.get("Preço Alta 1-2d", 0),
                "preco_alta_36":   f.get("Preço Alta 3-6d", 0),
                "preco_alta_7p":   f.get("Preço Alta 7d+", 0),
                "epoca_baixa_ini": f.get("Época Baixa Início", ""),
                "epoca_baixa_fim": f.get("Época Baixa Fim", ""),
                "epoca_alta_ini":  f.get("Época Alta Início", ""),
                "epoca_alta_fim":  f.get("Época Alta Fim", ""),
                "com_tipo":        f.get("Comissão Tipo", ""),
                "com_valor":       f.get("Comissão Valor", 0),
                "posicao":         f.get("Posição Hierarquia", 0),
                "obs":             f.get("Observações", ""),
                "ativo":           f.get("Ativo?", True),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/frota/<record_id>", methods=["PATCH"])
def patch_frota(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_RESERVAS, "Carros", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/tarefas", methods=["GET"])
def get_tarefas():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Tarefas")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            # Primary field is the task title (first field, no fixed name)
            titulo = ""
            for k, v in f.items():
                if isinstance(v, str) and k not in ["Responsável","Status","Urgência","Notas","Data Limite","Categoria","Criado Em","Concluído Em"]:
                    titulo = v; break
            out.append({
                "id":          rec["id"],
                "titulo":      titulo,
                "responsavel": f.get("Responsável", ""),
                "status":      f.get("Status", "Por Fazer"),
                "urgencia":    f.get("Urgência", ""),
                "notas":       f.get("Notas", ""),
                "data_limite": f.get("Data Limite", ""),
                "categoria":   f.get("Categoria", ""),
                "criado_em":   f.get("Criado Em", ""),
                "concluido_em":f.get("Concluído Em", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/tarefas", methods=["POST"])
def create_tarefa():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_create(BASE_RESERVAS, "Tarefas", fields)
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/tarefas/<record_id>", methods=["PATCH"])
def patch_tarefa(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_RESERVAS, "Tarefas", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================================================================
# HEALTH
# =========================================================================
@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    cache_clear()
    return jsonify({"success": True, "message": "Cache cleared"})


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Beyond Madeira Voucher API",
        "endpoints": [
            "/gerar-voucher",
            "/gerar-voucher-atividade",
            "GET  /airtable/rc",
            "POST /airtable/rc",
            "PATCH /airtable/rc/<id>",
            "GET  /airtable/at",
            "POST /airtable/at",
            "PATCH /airtable/at/<id>",
            "/airtable/sitemap",
            "/airtable/biblioteca",
            "/airtable/guia",
            "/airtable/reviews",
            "/airtable/disponibilidade",
            "/airtable/frota",
            "/airtable/tarefas",
            "/airtable/diario",
            "/airtable/resumos-mensais",
            "/airtable/despesas-fixas",
            "/airtable/despesas-variaveis",
            "/airtable/objetivos",
            "/airtable/caixa-mensal",
        ]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
