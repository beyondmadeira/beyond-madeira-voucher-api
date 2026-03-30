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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Airtable
AT_TOKEN        = os.environ.get("AIRTABLE_TOKEN", "")
BASE_RESERVAS   = "appR8ZKP5ygR8o8Q0"
BASE_CONHECIMENTO = "appKhPwEBxolWaO9r"
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
    try:
        with open(os.path.join(BASE_DIR, "logo_clean.png"), "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except:
        # Fallback: return empty string if logo not found
        return "https://res.cloudinary.com/dvrzzxu5b/image/upload/v1772828506/logo-beyond-madeira-_rvh6zt.png"

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


# =========================================================================
# RENT CAR
# =========================================================================
# =========================================================================
# RENT CAR
# =========================================================================
def _load_template(fname):
    """Load HTML template from file next to main.py, strip external font imports for speed."""
    import os, re
    p = os.path.join(os.path.dirname(__file__), fname)
    try:
        with open(p, encoding='utf-8') as f:
            html = f.read()
        # Remove Google Fonts imports (causes 30-60s delay in WeasyPrint)
        html = re.sub(r"@import url\('https://fonts\.googleapis\.com/[^']*'\);?", "", html)
        html = re.sub(r'<link[^>]*fonts\.googleapis\.com[^>]*>', "", html)
        # Replace Montserrat with system font
        html = html.replace("'Montserrat',", "'Liberation Sans',")
        html = html.replace('"Montserrat",', '"Liberation Sans",')
        return html
    except Exception as e:
        print(f"[WARN] Could not load {fname}: {e}")
        return ""

RC_TEMPLATE = _load_template("voucher_rc_template.html")


def build_rc_html(d):
    tmpl = RC_TEMPLATE

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

    empresa = d.get("empresa", "")
    if not d.get("empresa_telefone") and empresa in OPERATOR_CONTACTS:
        d["empresa_telefone"], d["empresa_email"] = OPERATOR_CONTACTS[empresa]
    d.setdefault("empresa_telefone", "")
    d.setdefault("empresa_email", "")

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

    beyond_card = '<div class="contact-card"><div class="contact-lbl">Beyond Madeira</div><div class="contact-name">Booking Support</div><div class="contact-det">+351 939 566 415<br>booking@beyondmadeira.com</div></div>'
    if d["empresa_contact_block"]:
        d["contacts_row_html"] = f'<div class="contacts-row">{d["empresa_contact_block"]}{beyond_card}</div>'
    else:
        d["contacts_row_html"] = f'<div class="contacts-row">{beyond_card}</div>'

    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    return fill(tmpl, d)


AT_TEMPLATE = _load_template("voucher_at_template.html")


def build_at_html(d):
    tmpl = AT_TEMPLATE

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


@app.route("/gerar-voucher", methods=["POST"])
def gerar_voucher():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400
        html  = build_rc_html(d)
        pdf   = HTML(string=html).write_pdf()
        b64   = base64.b64encode(pdf).decode()
        ref   = d.get("referencia", "voucher")
        cli   = d.get("cliente", "").replace(" ", "_")
        fname = f"Voucher_{ref}_{cli}.pdf"
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


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
        print(f"[DEBUG] AT_TOKEN: {AT_TOKEN[:10] if AT_TOKEN else 'EMPTY'}")
        print(f"[DEBUG] BASE_RESERVAS: {BASE_RESERVAS}")
        records = airtable_list(BASE_RESERVAS, "Rent Car")
        print(f"[DEBUG] RC records fetched: {len(records)}")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":          rec["id"],
                "ref":         f.get("Referência", f.get("Referencia", "")),
                "nome":        f.get("Nome do cliente", f.get("Nome do Cliente", "")),
                "tel":         f.get("Número de Telemovel", f.get("Telefone", "")),
                "email":       f.get("Email do cliente", f.get("Email", "")),
                "idade":       f.get("Idade", ""),
                "parceiro":    (f["Fornecedor/Parceiro"][0] if isinstance(f.get("Fornecedor/Parceiro"), list) else f.get("Fornecedor/Parceiro", f.get("Parceiro", ""))),
                "carro":       (f["Carro"][0] if isinstance(f.get("Carro"), list) else f.get("Carro", f.get("Modelo de Carro", f.get("Veículo", "")))),
                "estado":      f.get("Estado de Reserva", f.get("Estado do Reserva", f.get("Estado da Reserva", ""))),
                "pagamento":   f.get("Estado de Pagamento", f.get("Pagamento", "")),
                "pdt":         f.get("Data da Pick-up", f.get("Data Pick-up", "")),
                "ploc":        f.get("Localização Pick-up", f.get("Local Pick-up", "")),
                "pvoo":        f.get("Voo Pick-up", ""),
                "pdet":        f.get("Detalhes Pick Up", f.get("Detalhe Pick-up", "")),
                "ddt":         f.get("Data do Drop Off", f.get("Data Drop-off", "")),
                "dloc":        f.get("Localização Drop-off", f.get("Local Drop-off", "")),
                "dvoo":        f.get("Voo Drop-off", ""),
                "ddet":        f.get("Detalhes Drop Off", f.get("Detalhe Drop-off", "")),
                "total":       f.get("Valor da Reserva (€)", f.get("Total", 0)),
                "com":         f.get("Comissão", f.get("Comissao", 0)),
                "dur":         f.get("Duração", f.get("Duracao", 0)),
                "ext":         f.get("Extras", ""),
                "obs":         f.get("Observações", f.get("Observacoes", "")),
                "refp":        f.get("Referência Parceiro", ""),
                "eEnv":        f.get("Email Enviado", False),
                "rEnv":        f.get("Review Enviado", False),
                "dataFeita":   f.get("Data Feita a Reserva", f.get("Data Feita", f.get("Created Time", ""))),
            })
        cache_set("rc", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        import traceback
        print(f"[ERROR] RC: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


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
                "ref":         f.get("Referência", f.get("Referencia", "")),
                "nome":        f.get("Nome do Cliente", ""),
                "tel":         f.get("Contacto Telefonico", f.get("Telefone", "")),
                "email":       f.get("Email Clientes", f.get("Email", "")),
                "atv":         f.get("Atividade", ""),
                "cat":         f.get("Categoria", ""),
                "par":         f.get("Fornecedor/Parceiro", f.get("Parceiro", "")),
                "pess":        f.get("Nº Pessoas", f.get("Pessoas", "")),
                "data":        f.get("Data da Atividade", f.get("Data", "")),
                "hora":        f.get("Hora", ""),
                "total":       f.get("Preço Total", f.get("Valor da Reserva (€)", f.get("Total", 0))),
                "com":         f.get("Comissão", f.get("Comissao", 0)),
                "estado":      f.get("Estado da Reserva", ""),
                "estado_res":  f.get("Estado da Reserva", ""),
                "pagamento":   f.get("Estado de Pagamento", f.get("Pagamento", "")),
                "obs":         f.get("Observação", f.get("Observacoes", "")),
                "local":       f.get("Pick-up local", f.get("Local", "")),
                "stripe":      f.get("Stripe Link", ""),
                "idiomas":     f.get("Idiomas", ""),
                "eEnv":        f.get("Email Enviado", False),
                "tyEnv":       f.get("Thank You Enviado", False),
                "rEnv":        f.get("Review Pedida", False),
                "dataFeita":   f.get("Created", f.get("Data Feita", f.get("Created Time", ""))),
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
# HEALTH
# =========================================================================
@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    cache_clear()
    return jsonify({"success": True, "message": "Cache cleared"})




# =========================================================================
# WAZZUP PROXY  (evita CORS do browser)
# =========================================================================
WAZZUP_API_KEY  = os.environ.get("WAZZUP_API_KEY", "3c681e9848a14ceaa6c6bb1f27d33880")
WAZZUP_CHANNEL  = os.environ.get("WAZZUP_CHANNEL", "345da32d-f391-4d42-b22f-660539d73085")
WAZZUP_BASE     = "https://api.wazzup24.com/v3"

@app.route("/wazzup/iframe", methods=["POST"])
def wazzup_iframe():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json(silent=True) or {}
        user_id   = body.get("userId", "milton")
        user_name = body.get("userName", "Milton")
        payload = {
            "channelId": WAZZUP_CHANNEL,
            "userId":    user_id,
            "userName":  user_name,
        }
        r = req_lib.post(
            WAZZUP_BASE + "/iframe",
            headers={"X-Api-Key": WAZZUP_API_KEY, "Content-Type": "application/json"},
            json=payload, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        return jsonify({"url": data.get("url", ""), "iframeUrl": data.get("iframeUrl", data.get("url", ""))})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "detail": traceback.format_exc()}), 500


@app.route("/wazzup/chats", methods=["GET"])
def wazzup_chats():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        r = req_lib.get(
            WAZZUP_BASE + "/chats",
            headers={"X-Api-Key": WAZZUP_API_KEY}, timeout=15
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/wazzup/messages", methods=["GET"])
def wazzup_messages():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        chat_id = request.args.get("chatId", "")
        params = {"chatId": chat_id} if chat_id else {}
        r = req_lib.get(
            WAZZUP_BASE + "/messages",
            headers={"X-Api-Key": WAZZUP_API_KEY},
            params=params, timeout=15
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/wazzup/send", methods=["POST"])
def wazzup_send():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json()
        body["channelId"] = WAZZUP_CHANNEL
        r = req_lib.post(
            WAZZUP_BASE + "/messages/text",
            headers={"X-Api-Key": WAZZUP_API_KEY, "Content-Type": "application/json"},
            json=body, timeout=15
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# =========================================================================
# EXTRATO DE COMISSÕES (WeasyPrint - server side, tabela sem flex)
# =========================================================================
BASE_EXTRATO  = "appRGJjirAzgEe46q"
TAB_EXTRATO   = "tblHmWDHM64Dy4iwi"

def calc_totais(rows):
    rows_v    = [r for r in rows if r["status"] != "Cancelado"]
    n_can     = sum(1 for r in rows if r["status"] == "Cancelado")
    n_norm    = sum(1 for r in rows_v if r["status"] != "Devemos")
    n_dev     = sum(1 for r in rows_v if r["status"] == "Devemos")
    comiss    = sum(r["comm"]  for r in rows_v if r["status"] != "Devemos")
    credito   = sum(r["total"] - r["comm"] for r in rows_v if r["status"] == "Devemos")
    gt        = sum(r["total"] for r in rows_v)
    gc        = sum(r["comm"]  for r in rows_v if r["status"] != "Devemos")
    total_fim = comiss - credito
    return dict(n=len(rows), n_can=n_can, n_norm=n_norm, n_dev=n_dev,
                comiss=comiss, credito=credito, gt=gt, gc=gc, total_fim=total_fim)

def build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots, rows_by_month=None):
    from datetime import datetime
    today = datetime.now().strftime("%d/%m/%Y")
    t = tots

    def _status_class(s):
        return {"Pago": "status-pago", "Devemos": "status-devemos", "Cancelado": "status-cancel"}.get(s, "")

    def _row_html(r, bg, strike=False):
        sc  = _status_class(r["status"])
        sk  = " strike" if strike else ""
        pax = str(r.get("pax") or "—").replace(" Pessoas","").replace(" Pessoa","").strip()
        ref_r = r.get("ref","") or "—"
        return (
            f'<tr style="background:{bg}">'
            f'<td class="muted{sk}">{r["date"]}</td>'
            f'<td class="muted{sk}" style="font-size:8px;">{ref_r[:14]}</td>'
            f'<td class="{sk}">{(r["client"] or "—")[:30]}</td>'
            f'<td class="muted{sk}">{(r["act"] or "—")[:28]}</td>'
            f'<td class="c muted{sk}">{pax}</td>'
            f'<td class="r{sk}">€{abs(r["total"]):,.2f}</td>'
            f'<td class="comm{sk}">€{abs(r["comm"]):,.2f}</td>'
            f'<td class="c {sc}{sk}">{r["status"]}</td>'
            f'</tr>'
        )

    rows_html = ""
    if rows_by_month and len(rows_by_month) > 1:
        row_idx = 0
        for m_nome_i, m_ano_i, m_rows_i in rows_by_month:
            if not m_rows_i: continue
            rows_html += (
                f'<tr class="month-sep"><td colspan="8">{m_nome_i} {m_ano_i} — {len(m_rows_i)} reservas</td></tr>'
            )
            for i, r in enumerate(m_rows_i):
                cancelled = r["status"] == "Cancelado"
                rows_html += _row_html(r, "#F9FAFB" if (row_idx+i)%2==0 else "#FFFFFF", strike=cancelled)
            row_idx += len(m_rows_i)
    else:
        for i, r in enumerate(rows):
            cancelled = r["status"] == "Cancelado"
            rows_html += _row_html(r, "#F9FAFB" if i%2==0 else "#FFFFFF", strike=cancelled)

    if not rows_html:
        rows_html = '<tr><td colspan="8" style="padding:14px 8px;color:var(--text3);font-style:italic;">Sem reservas para este período.</td></tr>'

    title_mes = " + ".join([f"{mn} {my}" for mn,my,_ in rows_by_month]) if rows_by_month and len(rows_by_month)>1 else f"{mes_nome} {ano}"

    tmpl = _load_template("extrato_template.html")
    tmpl = tmpl.replace("{{LOGO_SRC}}", logo_b64())
    replacements = {
        "{{parceiro}}":    parceiro,
        "{{ref}}":         ref,
        "{{today}}":       today,
        "{{title_mes}}":   title_mes,
        "{{total_fim}}":   f'{abs(t["total_fim"]):,.2f}',
        "{{rows_html}}":   rows_html,
        "{{n_reservas}}":  str(t["n"]),
        "{{n_canceladas}}":str(t["n_can"]),
        "{{gt}}":          f'{abs(t["gt"]):,.2f}',
        "{{gc}}":          f'{abs(t["gc"]):,.2f}',
        "{{n_norm}}":      str(t["n_norm"]),
        "{{n_dev}}":       str(t["n_dev"]),
        "{{comiss}}":      f'{abs(t["comiss"]):,.2f}',
        "{{credito}}":     f'{abs(t["credito"]):,.2f}',
    }
    for k, v in replacements.items():
        tmpl = tmpl.replace(k, str(v))
    return tmpl

def eur_val(v):
    try: return float(str(v).replace("€","").replace(",",".").strip())
    except: return 0.0

def get_text_f(v):
    if isinstance(v, list): return ", ".join(str(x) for x in v)
    return str(v) if v else ""

def fget_f(rec, *keys):
    for k in keys:
        if k in rec and rec[k] not in (None, "", []):
            return rec[k]
    return None

def norm_act(v):
    s = get_text_f(v)
    if len(s) > 35: s = s[:33] + "…"
    return s

def airtable_upload_attachment(base_id, table_name, record_id, field_name, pdf_bytes, fname):
    import base64
    url = f"https://api.airtable.com/v0/{base_id}/{req_lib.utils.quote(table_name)}/{record_id}/files/{req_lib.utils.quote(field_name)}"
    r = req_lib.post(url, headers={"Authorization": f"Bearer {AT_TOKEN}"},
        json={"file": base64.b64encode(pdf_bytes).decode(), "filename": fname}, timeout=30)
    r.raise_for_status()


@app.route("/gerar-extrato-parceiro", methods=["POST"])
def gerar_extrato_parceiro():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d        = request.get_json() or {}
        parceiro = d.get("parceiro", "")
        upload   = d.get("upload", False)
        record_id= d.get("record_id", "")
        meses_pt = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

        # Accept mes as "Março 2026" string OR as separate mes/ano integers
        mes_raw = d.get("mes", "")
        mes_num = 0
        ano     = 0
        from datetime import datetime as _dt2
        if isinstance(mes_raw, str) and " " in mes_raw:
            parts = mes_raw.strip().split()
            if len(parts) == 2:
                for i, m in enumerate(meses_pt):
                    if m.lower() == parts[0].lower():
                        mes_num = i; break
                try: ano = int(parts[1])
                except: ano = _dt2.now().year
        else:
            try: mes_num = int(mes_raw)
            except: mes_num = _dt2.now().month
            try: ano = int(d.get("ano", _dt2.now().year))
            except: ano = _dt2.now().year

        mes_nome = meses_pt[mes_num] if 1 <= mes_num <= 12 else str(mes_num)

        recs_rc = airtable_list(BASE_RESERVAS, "Rent Car")
        recs_at = airtable_list(BASE_RESERVAS, "Atividades")
        rows = []
        for rf in recs_rc:
            f = rf.get("fields", {})
            par = f.get("Fornecedor/Parceiro", f.get("Parceiro", ""))
            if isinstance(par, list): par = ", ".join(str(x) for x in par)
            if par.lower() != parceiro.lower(): continue
            raw_date = f.get("Data do Drop Off", f.get("Data Drop-off", ""))
            if not raw_date: continue
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(str(raw_date)[:10])
                if dt.month != mes_num or dt.year != ano: continue
            except: continue
            status_raw = f.get("Estado do Reserva", f.get("Estado da Reserva", ""))
            if status_raw in ("Cancelado","Cancelada"): status = "Cancelado"
            elif status_raw == "Devemos": status = "Devemos"
            elif status_raw == "Pago": status = "Pago"
            else: status = "Por Pagar"
            total = eur_val(f.get("Valor da Reserva (€)", f.get("Total", 0)))
            comm  = eur_val(f.get("Comissão", f.get("Comissao", 0)))
            client= f.get("Nome do cliente", f.get("Nome do Cliente", ""))
            act   = norm_act(f.get("Modelo de Carro", f.get("Veículo", "")))
            pax   = str(f.get("Duração", f.get("Duracao", "")))
            ref_r = f.get("Referência", f.get("Referencia", rf.get("id","")))
            rows.append(dict(date=dt.strftime("%d/%m"), ref=ref_r, client=client, act=act,
                             pax=pax, total=total, comm=comm, status=status, ddt=raw_date))
        for rf in recs_at:
            f = rf.get("fields", {})
            par = f.get("Fornecedor/Parceiro", f.get("Parceiro", ""))
            if isinstance(par, list): par = ", ".join(str(x) for x in par)
            if par.lower() != parceiro.lower(): continue
            raw_date = f.get("Data da Atividade", f.get("Data", ""))
            if not raw_date: continue
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(str(raw_date)[:10])
                if dt.month != mes_num or dt.year != ano: continue
            except: continue
            status_raw = f.get("Estado da Reserva", "")
            if status_raw in ("Cancelado","Cancelada"): status = "Cancelado"
            elif status_raw == "Devemos": status = "Devemos"
            elif status_raw == "Pago": status = "Pago"
            else: status = "Por Pagar"
            total = eur_val(f.get("Preço Total", f.get("Valor da Reserva (€)", 0)))
            comm  = eur_val(f.get("Comissão", f.get("Comissao", 0)))
            client= f.get("Nome do Cliente", "")
            act   = norm_act(f.get("Atividade", ""))
            pax   = str(f.get("Nº Pessoas", f.get("Pessoas", "")))
            ref_r = f.get("Referência", f.get("Referencia", rf.get("id","")))
            rows.append(dict(date=dt.strftime("%d/%m"), ref=ref_r, client=client, act=act,
                             pax=pax, total=total, comm=comm, status=status, ddt=raw_date))
        rows.sort(key=lambda x: x["date"])
        tots  = calc_totais(rows)
        import re as _re
        sl    = _re.sub(r'[^a-zA-Z0-9]', '', parceiro)
        ref   = f'EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}'
        fname = f'BeyondMadeira_{sl}_{mes_nome}{ano}.pdf'
        html_str = build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots)
        pdf_bytes = HTML(string=html_str).write_pdf()
        b64 = base64.b64encode(pdf_bytes).decode()
        if upload and record_id and record_id.startswith("rec"):
            try:
                airtable_upload_attachment(BASE_RESERVAS, TAB_EXTRATO, record_id, "Extrato Beyond", pdf_bytes, fname)
            except: pass
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64,
                        "reservas": rows, "total": tots["total_fim"], "total_fim": tots["total_fim"]})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500
    try:
        body      = request.get_json() or {}
        messages  = body.get("messages", [])
        model     = body.get("model", "claude-sonnet-4-20250514")
        max_tokens= body.get("max_tokens", 1024)
        system    = body.get("system", "")
        stream    = body.get("stream", False)
        payload   = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            payload["system"] = system

        if stream:
            payload["stream"] = True
            from flask import Response, stream_with_context
            def generate():
                with req_lib.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json=payload, stream=True, timeout=60
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                yield decoded + "\n\n"
            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )

        r = req_lib.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=payload, timeout=60
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ── ACTIVITY TIPS DATABASE ────────────────────────────────────────────────────
ACTIVITY_TIPS = {
    "hike": {
        "bring": ["Comfortable hiking shoes","Water (min 1.5L)","Sunscreen & sunglasses","Light rain jacket","Snacks","Small backpack"],
        "not_included": [],
        "tips": ["Wear layers — mornings can be cool","Start well-rested and hydrated"],
    },
    "sunrise": {
        "bring": ["Warm layers (near 0°C at altitude)","Headlamp or phone torch","Water & snacks","Camera / tripod"],
        "not_included": [],
        "tips": ["Set multiple alarms — departure is very early","Dress warmer than you think"],
    },
    "cabo girao": {
        "bring": ["Comfortable shoes","Camera"],
        "not_included": ["Cabo Girão skywalk entry — €5 per person (cash or card on site)"],
        "tips": ["Entry paid on site — bring cash as backup"],
    },
    "queimadas": {
        "bring": ["Warm layers","Waterproof jacket — often misty","Water 1.5L"],
        "not_included": [],
        "tips": ["Waterproof shoes recommended — path can be muddy"],
    },
    "caldeirão verde": {
        "bring": ["Headlamp (MANDATORY — tunnel sections)","Waterproof jacket","Water 1.5L"],
        "not_included": [],
        "tips": ["You MUST bring a headlamp — tunnels are pitch dark","Trail shoes strongly recommended"],
    },
    "pico ruivo": {
        "bring": ["Warm layers — summit above 1800m","Sunscreen","Water 2L","Energy snacks"],
        "not_included": [],
        "tips": ["Weather changes fast at altitude — always bring a jacket","No water points on trail"],
    },
    "island tour": {
        "bring": ["Sunscreen","Camera","Light jacket","Water","Comfortable walking shoes"],
        "not_included": ["Lunch (unless specified)","Entry fees to attractions (if any)"],
        "tips": ["Bring cash for optional stops","Confirm pick-up point the day before"],
    },
    "jeep": {
        "bring": ["Sunscreen","Camera","Light jacket","Water"],
        "not_included": ["Lunch (unless specified)"],
        "tips": ["Off-road sections can be bumpy — avoid if back issues","Bring cash for food stops"],
    },
    "mini van": {
        "bring": ["Sunscreen","Camera","Comfortable shoes","Water"],
        "not_included": ["Lunch (unless specified)","Entry fees if applicable"],
        "tips": ["Confirm pick-up location the night before"],
    },
    "boat": {
        "bring": ["Swimwear","Towel","Waterproof sunscreen","Change of clothes","Seasickness tablets if needed"],
        "not_included": [],
        "tips": ["Take seasickness medication 30min before if prone","Bring a waterproof bag for your phone"],
    },
    "dolphin": {
        "bring": ["Sunscreen","Warm layer for sea breeze","Seasickness tablets if needed","Camera"],
        "not_included": [],
        "tips": ["Sightings are very likely but not 100% guaranteed — it's nature","Confirm departure marina"],
    },
    "whale": {
        "bring": ["Warm windproof layer","Sunscreen","Seasickness tablets (strongly recommended)","Binoculars"],
        "not_included": [],
        "tips": ["Boats go further offshore — sea can be rough","Sightings not guaranteed but likelihood high"],
    },
    "canyoning": {
        "bring": ["Swimwear (worn under wetsuit)","Old trainers or water shoes","Towel & change of clothes"],
        "not_included": ["Wetsuit and all equipment are provided"],
        "tips": ["Do not eat heavy 2h before","Inform operator of any health issues"],
    },
    "surf": {
        "bring": ["Swimwear","Towel","Waterproof sunscreen","Change of clothes"],
        "not_included": ["Surfboard and wetsuit included"],
        "tips": ["No experience needed for beginner lessons","Arrive 15min early for briefing"],
    },
    "paragliding": {
        "bring": ["Comfortable clothes (no skirts)","Closed-toe shoes","Sunglasses"],
        "not_included": ["Photos/video package (optional extra — ask operator)"],
        "tips": ["Weight limit ~100-110kg — confirm with operator","Flights are weather dependent — confirmed morning of"],
    },
    "quad": {
        "bring": ["Clothes you don't mind getting dusty","Closed-toe shoes","Sunglasses","Sunscreen"],
        "not_included": ["Helmet provided"],
        "tips": ["Minimum age may apply — confirm with operator"],
    },
    "via ferrata": {
        "bring": ["Sport clothing","Trail shoes or hiking boots","Water 1.5L","Sunscreen"],
        "not_included": ["Harness, helmet and via ferrata kit all provided"],
        "tips": ["Some upper body strength required","Not suitable for severe fear of heights"],
    },
    "default": {
        "bring": ["Comfortable clothes for outdoor activity","Sunscreen & sunglasses","Water","Camera","Cash for optional extras"],
        "not_included": [],
        "tips": ["Confirm meeting point the day before","Arrive 10 minutes early"],
    },
}

def get_activity_tips(atividade_str, categoria_str=""):
    """Return tips dict for a given activity string."""
    search = (atividade_str + " " + categoria_str).lower()
    # Specific matches first (longer strings win)
    for key in ["caldeirão verde", "cabo girao", "queimadas", "pico ruivo",
                "via ferrata", "island tour", "mini van",
                "dolphin", "canyoning", "paragliding", "sunrise",
                "whale", "boat", "surf", "hike", "jeep", "quad"]:
        if key in search:
            return ACTIVITY_TIPS[key]
    return ACTIVITY_TIPS["default"]

def build_tips_html(tips):
    """Build HTML block for tips section in email."""
    html = ""

    if tips.get("bring"):
        items = "".join(f'<li style="margin:0 0 6px;font-size:13px;color:#2a2a2a;">{i}</li>' for i in tips["bring"])
        html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
          <tr>
            <td style="background:#f2f9fa;border-radius:10px;padding:18px 22px;">
              <p style="margin:0 0 12px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#0d6e7a;text-transform:uppercase;">🎒 What to Bring</p>
              <ul style="margin:0;padding-left:18px;">{items}</ul>
            </td>
          </tr>
        </table>"""

    if tips.get("not_included"):
        items = "".join(f'<li style="margin:0 0 6px;font-size:13px;color:#7a5c00;">{i}</li>' for i in tips["not_included"])
        html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
          <tr>
            <td style="background:#fffbf0;border-radius:10px;padding:18px 22px;">
              <p style="margin:0 0 12px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#b45309;text-transform:uppercase;">⚠️ Not Included / Extra Costs</p>
              <ul style="margin:0;padding-left:18px;">{items}</ul>
            </td>
          </tr>
        </table>"""

    if tips.get("tips"):
        items = "".join(f'<li style="margin:0 0 6px;font-size:13px;color:#2a2a2a;">{i}</li>' for i in tips["tips"])
        html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
          <tr>
            <td style="background:#e8f6f7;border-radius:10px;padding:18px 22px;">
              <p style="margin:0 0 12px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#0d6e7a;text-transform:uppercase;">💡 Tips</p>
              <ul style="margin:0;padding-left:18px;">{items}</ul>
            </td>
          </tr>
        </table>"""

    return html



@app.route("/enviar-voucher-email", methods=["POST"])
def enviar_voucher_email():
    """Send voucher PDF by email with HTML template."""
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d         = request.get_json() or {}
        to        = d.get("to", "")
        pdf_b64   = d.get("pdf_base64", "")
        pdf_fname = d.get("pdf_filename", "voucher.pdf")
        tipo      = d.get("tipo", "rc")  # "rc" or "at"
        if not to:
            return jsonify({"error": "Missing 'to' email"}), 400

        # Build HTML email from template
        if tipo == "at":
            tmpl = _load_template("email_at_template.html")
            atividade   = d.get("atividade", "")
            operador    = d.get("operador", "")
            # Meeting point block
            pickup_local = d.get("pickup_local", "")
            if pickup_local:
                pickup_block = f'''<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
              <tr>
                <td style="background:#f2f9fa;border-left:4px solid #0d6e7a;border-radius:0 8px 8px 0;padding:20px 22px;">
                  <p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#0d6e7a;text-transform:uppercase;">📍 Meeting Point</p>
                  <p style="margin:0;font-size:14px;color:#2a2a2a;line-height:1.8;">{pickup_local}</p>
                </td>
              </tr>
            </table>'''
            else:
                pickup_block = ""
            pagamento = d.get("pagamento", "cash")
            payment_note = "Cash on the day of the activity." if "cash" in pagamento else "Payment by card on the day." if "card" in pagamento else "To be confirmed."
            subject = d.get("email_subject", f"Your Activity is Confirmed — {atividade} | Beyond Madeira")
            replacements = {
                "{{cliente}}":      d.get("cliente", ""),
                "{{atividade}}":    atividade,
                "{{data}}":         d.get("data", ""),
                "{{hora}}":         d.get("hora", "TBC"),
                "{{participantes}}":d.get("participantes", ""),
                "{{operador}}":     operador,
                "{{referencia}}":   d.get("referencia", ""),
                "{{total}}":        str(d.get("total", "")),
                "{{pickup_block}}": pickup_block,
                "{{payment_note}}": payment_note,
            "{{tips_block}}":    build_tips_html(get_activity_tips(atividade, d.get("categoria", ""))),
            }
        else:
            tmpl = _load_template("email_rc_template.html")
            empresa = d.get("empresa", "")
            subject = d.get("email_subject", f"Your Car Rental is Confirmed — Beyond Madeira")
            replacements = {
                "{{cliente}}":      d.get("cliente", ""),
                "{{empresa}}":      empresa,
                "{{veiculo}}":      d.get("veiculo", ""),
                "{{referencia}}":   d.get("referencia", ""),
                "{{total}}":        str(d.get("total", "")),
                "{{pickup_data}}":  d.get("pickup_data", ""),
                "{{pickup_hora}}":  d.get("pickup_hora", ""),
                "{{pickup_local}}": d.get("pickup_local", ""),
                "{{dropoff_data}}": d.get("dropoff_data", ""),
                "{{dropoff_hora}}": d.get("dropoff_hora", ""),
                "{{dropoff_local}}":d.get("dropoff_local", ""),
            }

        for k, v in replacements.items():
            tmpl = tmpl.replace(k, str(v) if v else "")

        import smtplib, ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        SMTP_USER = os.environ.get("SMTP_USER", "booking@beyondmadeira.com")
        SMTP_PASS = os.environ.get("SMTP_PASS", "")
        SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

        msg = MIMEMultipart("mixed")
        msg["From"]    = f"Beyond Madeira <{SMTP_USER}>"
        msg["To"]      = to
        msg["Subject"] = subject

        # HTML body
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText("Please view this email in an HTML-capable client.", "plain"))
        alt.attach(MIMEText(tmpl, "html"))
        msg.attach(alt)

        # PDF attachment
        if pdf_b64:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(base64.b64decode(pdf_b64))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{pdf_fname}"')
            msg.attach(part)

        if SMTP_PASS:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls(context=ctx)
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to, msg.as_string())
            return jsonify({"success": True, "method": "smtp"})
        else:
            return jsonify({"success": False, "error": "SMTP_PASS not configured"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/enviar-extrato-email", methods=["POST"])
def enviar_extrato_email():
    """Generate extrato PDF and send by email."""
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d        = request.get_json() or {}
        to       = d.get("to", "")
        subject  = d.get("subject", "Extrato de Comissões — Beyond Madeira")
        body_txt = d.get("body", "Segue em anexo o extrato de comissões.")
        pdf_b64  = d.get("pdf_base64", "")
        pdf_fname= d.get("pdf_filename", "extrato.pdf")
        if not to:
            return jsonify({"error": "Missing 'to' email"}), 400
        import smtplib, ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        SMTP_USER = os.environ.get("SMTP_USER", "booking@beyondmadeira.com")
        SMTP_PASS = os.environ.get("SMTP_PASS", "")
        SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_txt, "plain"))
        if pdf_b64:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(base64.b64decode(pdf_b64))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{pdf_fname}"')
            msg.attach(part)
        if SMTP_PASS:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls(context=ctx)
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to, msg.as_string())
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "SMTP_PASS not configured"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/gerar-extratos-mes", methods=["POST"])
def gerar_extratos_mes():
    """Generate all partner extratos for a given month."""
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d      = request.get_json() or {}
        mes_str= d.get("mes", "")
        meses_pt = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        mes_num, ano = 0, 0
        from datetime import datetime as _dt2
        if " " in mes_str:
            parts = mes_str.strip().split()
            for i, m in enumerate(meses_pt):
                if m.lower() == parts[0].lower(): mes_num = i; break
            try: ano = int(parts[1])
            except: ano = _dt2.now().year
        if not mes_num:
            return jsonify({"error": "Invalid mes format. Use 'Março 2026'"}), 400
        mes_nome = meses_pt[mes_num]
        # Get all records and group by partner
        from collections import defaultdict
        recs_rc = airtable_list(BASE_RESERVAS, "Rent Car")
        recs_at = airtable_list(BASE_RESERVAS, "Atividades")
        parceiros = defaultdict(list)
        for rf in recs_rc:
            f = rf.get("fields", {})
            par = f.get("Fornecedor/Parceiro", f.get("Parceiro", ""))
            if isinstance(par, list): par = ", ".join(str(x) for x in par)
            if not par: continue
            raw = f.get("Data do Drop Off", f.get("Data Drop-off", ""))
            if not raw: continue
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(str(raw)[:10])
                if dt.month != mes_num or dt.year != ano: continue
            except: continue
            parceiros[par].append(rf)
        for rf in recs_at:
            f = rf.get("fields", {})
            par = f.get("Fornecedor/Parceiro", f.get("Parceiro", ""))
            if isinstance(par, list): par = ", ".join(str(x) for x in par)
            if not par: continue
            raw = f.get("Data da Atividade", f.get("Data", ""))
            if not raw: continue
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(str(raw)[:10])
                if dt.month != mes_num or dt.year != ano: continue
            except: continue
            parceiros[par].append(rf)
        results = []
        total_geral = 0
        import re as _re
        for par, rfs in parceiros.items():
            try:
                rows = []
                for rf in rfs:
                    f = rf.get("fields", {})
                    raw_d = f.get("Data do Drop Off", f.get("Data da Atividade", f.get("Data", "")))
                    dt = __import__("datetime").datetime.fromisoformat(str(raw_d)[:10])
                    status_raw = f.get("Estado do Reserva", f.get("Estado da Reserva", ""))
                    if status_raw in ("Cancelado","Cancelada"): status = "Cancelado"
                    elif status_raw == "Devemos": status = "Devemos"
                    elif status_raw == "Pago": status = "Pago"
                    else: status = "Por Pagar"
                    total = eur_val(f.get("Valor da Reserva (€)", f.get("Preço Total", 0)))
                    comm  = eur_val(f.get("Comissão", f.get("Comissao", 0)))
                    client= f.get("Nome do cliente", f.get("Nome do Cliente", ""))
                    act   = norm_act(f.get("Modelo de Carro", f.get("Atividade", "")))
                    pax   = str(f.get("Duração", f.get("Nº Pessoas", "")))
                    ref_r = f.get("Referência", rf.get("id",""))
                    rows.append(dict(date=dt.strftime("%d/%m"), ref=ref_r, client=client, act=act,
                                     pax=pax, total=total, comm=comm, status=status, ddt=raw_d))
                rows.sort(key=lambda x: x["date"])
                tots  = calc_totais(rows)
                sl    = _re.sub(r'[^a-zA-Z0-9]', '', par)
                ref   = f'EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}'
                fname = f'BeyondMadeira_{sl}_{mes_nome}{ano}.pdf'
                html_str = build_extrato_html(par, rows, ref, mes_nome, ano, tots)
                pdf_bytes = HTML(string=html_str).write_pdf()
                b64 = base64.b64encode(pdf_bytes).decode()
                total_geral += abs(tots["total_fim"])
                results.append({"parceiro": par, "success": True, "filename": fname,
                                 "pdf_base64": b64, "total": tots["total_fim"]})
            except Exception as ep:
                results.append({"parceiro": par, "success": False, "error": str(ep)})
        return jsonify({"success": True, "results": results, "total_geral": total_geral})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug/rc-fields", methods=["GET"])
def debug_rc_fields():
    """Returns raw field names from first 3 RC records — use to check Airtable field names."""
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Rent Car")
        sample = [{"id": r["id"], "fields": list(r.get("fields", {}).keys())} for r in records[:3]]
        return jsonify({"success": True, "sample": sample})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/diario", methods=["GET", "POST", "PATCH"])
def airtable_diario():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "GET":
            recs = airtable_list("appOrdG5Fsr7N0RmH", "Registos Diários")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id": r["id"],
                    "data": f.get("Data", f.get("Date", "")),
                    "fat":  float(f.get("Faturação Diária", f.get("Faturacao Diaria", 0)) or 0),
                    "fatRC": float(f.get("Faturação RC", 0) or 0),
                    "fatAT": float(f.get("Faturação AT", 0) or 0),
                    "obs":  f.get("Notas do Dia", ""),
                    "resp": f.get("Responsável", ""),
                })
            return jsonify({"success": True, "records": out})
        elif request.method == "POST":
            body = request.get_json() or {}
            result = req_lib.post(
                "https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/" + req_lib.utils.quote("Registos Diários"),
                headers=AT_HEADERS(), json={"fields": body.get("fields", {})}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
        else:
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/diario/<record_id>", methods=["PATCH"])
def airtable_diario_patch(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        result = airtable_patch("appOrdG5Fsr7N0RmH", "Registos Diários", record_id, body.get("fields", {}))
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/despesas-fixas", methods=["GET", "POST"])
@app.route("/airtable/despesas-fixas/<record_id>", methods=["PATCH", "DELETE"])
def airtable_despesas_fixas(**kwargs):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        record_id = kwargs.get("record_id", "")
        if request.method == "GET":
            recs = airtable_list("appOrdG5Fsr7N0RmH", "Despesas Fixas")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id":        r["id"],
                    "nome":      f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))),
                    "descricao": f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))),
                    "valor":     float(f.get("Valor", 0) or 0),
                    "mes":       f.get("Mês", f.get("Mes", f.get("Notas", ""))),
                    "categoria": f.get("Categoria", ""),
                    "pago":      bool(f.get("Pago?", f.get("Pago", False))),
                    "fatura":    bool(f.get("Fatura?", f.get("Fatura", False))),
                    "tipo":      "fixa",
                })
            return jsonify({"success": True, "records": out})
        elif request.method == "POST":
            body = request.get_json() or {}
            fields = body.get("fields", body)
            # Map frontend fields to Airtable fields
            at_fields = {
                "Fornecedor": fields.get("Fornecedor", fields.get("nome", fields.get("descricao", ""))),
                "Valor": float(fields.get("Valor", fields.get("valor", 0)) or 0),
                "Categoria": fields.get("Categoria", fields.get("categoria", "")),
                "Pago?": bool(fields.get("Pago?", fields.get("pago", False))),
            }
            if fields.get("Notas") or fields.get("mes"): at_fields["Notas"] = fields.get("Notas", fields.get("mes", ""))
            result = req_lib.post(
                "https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/" + req_lib.utils.quote("Despesas Fixas"),
                headers=AT_HEADERS(), json={"fields": at_fields}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
        elif request.method == "PATCH":
            body = request.get_json() or {}
            fields = body.get("fields", body)
            at_fields = {}
            if "pago" in fields or "Pago?" in fields: at_fields["Pago?"] = bool(fields.get("Pago?", fields.get("pago", False)))
            if "valor" in fields or "Valor" in fields: at_fields["Valor"] = float(fields.get("Valor", fields.get("valor", 0)) or 0)
            if "nome" in fields or "Fornecedor" in fields: at_fields["Fornecedor"] = fields.get("Fornecedor", fields.get("nome", ""))
            if not at_fields: at_fields = fields
            result = airtable_patch("appOrdG5Fsr7N0RmH", "Despesas Fixas", record_id, at_fields)
            return jsonify({"success": True, "record": result})
        elif request.method == "DELETE":
            r = req_lib.delete(
                f"https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/{req_lib.utils.quote('Despesas Fixas')}/{record_id}",
                headers=AT_HEADERS(), timeout=15
            )
            r.raise_for_status()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/despesas-variaveis", methods=["GET", "POST"])
@app.route("/airtable/despesas-variaveis/<record_id>", methods=["PATCH", "DELETE"])
@app.route("/airtable/financeiro/despesas", methods=["GET", "POST"])
@app.route("/airtable/financeiro/despesas/<record_id>", methods=["PATCH", "DELETE"])
def airtable_despesas(**kwargs):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        record_id = kwargs.get("record_id", "")
        if request.method == "GET":
            recs = airtable_list("appOrdG5Fsr7N0RmH", "Despesas Variáveis")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id":        r["id"],
                    "nome":      f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))),
                    "descricao": f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))),
                    "valor":     float(f.get("Valor", 0) or 0),
                    "mes":       f.get("Mês", f.get("Mes", f.get("Notas", ""))),
                    "categoria": f.get("Categoria", ""),
                    "pago":      bool(f.get("Pago?", f.get("Pago", False))),
                    "fatura":    bool(f.get("Fatura?", f.get("Fatura", False))),
                    "tipo":      "variavel",
                })
            return jsonify({"success": True, "records": out})
        elif request.method == "POST":
            body = request.get_json() or {}
            fields = body.get("fields", body)
            at_fields = {
                "Fornecedor": fields.get("Fornecedor", fields.get("nome", fields.get("descricao", ""))),
                "Valor": float(fields.get("Valor", fields.get("valor", 0)) or 0),
                "Categoria": fields.get("Categoria", fields.get("categoria", "")),
                "Pago?": bool(fields.get("Pago?", fields.get("pago", False))),
            }
            if fields.get("Notas") or fields.get("mes"): at_fields["Notas"] = fields.get("Notas", fields.get("mes", ""))
            result = req_lib.post(
                "https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/" + req_lib.utils.quote("Despesas Variáveis"),
                headers=AT_HEADERS(), json={"fields": at_fields}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
        elif request.method == "PATCH":
            body = request.get_json() or {}
            fields = body.get("fields", body)
            at_fields = {}
            if "pago" in fields or "Pago?" in fields: at_fields["Pago?"] = bool(fields.get("Pago?", fields.get("pago", False)))
            if "valor" in fields or "Valor" in fields: at_fields["Valor"] = float(fields.get("Valor", fields.get("valor", 0)) or 0)
            if "nome" in fields or "Fornecedor" in fields: at_fields["Fornecedor"] = fields.get("Fornecedor", fields.get("nome", ""))
            if not at_fields: at_fields = fields
            result = airtable_patch("appOrdG5Fsr7N0RmH", "Despesas Variáveis", record_id, at_fields)
            return jsonify({"success": True, "record": result})
        elif request.method == "DELETE":
            r = req_lib.delete(
                f"https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/{req_lib.utils.quote('Despesas Variáveis')}/{record_id}",
                headers=AT_HEADERS(), timeout=15
            )
            r.raise_for_status()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/parceiros", methods=["GET"])
def airtable_parceiros():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("parceiros")
        if cached: return jsonify({"success": True, "records": cached, "cached": True})
        recs = airtable_list(BASE_RESERVAS, "Parceiros")
        out = []
        for r in recs:
            f = r.get("fields", {})
            out.append({
                "id":       r["id"],
                "nome":     f.get("Nome", f.get("Name", "")),
                "email":    f.get("Email", ""),
                "telefone": f.get("Telefone", f.get("Tel", "")),
                "tipo":     f.get("Tipo", f.get("Categoria", "")),
                "ativo":    f.get("Ativo", f.get("Active", True)),
            })
        cache_set("parceiros", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/tarefas", methods=["GET", "POST"])
def airtable_tarefas():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "GET":
            recs = airtable_list(BASE_RESERVAS, "Tarefas")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id":       r["id"],
                    "desc":     f.get("Descrição", f.get("Descricao", f.get("Tarefa", ""))),
                    "status":   f.get("Status", f.get("Estado", "pendente")),
                    "pri":      f.get("Prioridade", f.get("Priority", "media")),
                    "resp":     f.get("Responsável", f.get("Responsavel", "")),
                    "data":     f.get("Data", ""),
                    "feita":    bool(f.get("Feita", f.get("Done", False))),
                })
            return jsonify({"success": True, "records": out})
        else:
            body = request.get_json() or {}
            result = req_lib.post(
                f"https://api.airtable.com/v0/{BASE_RESERVAS}/Tarefas",
                headers=AT_HEADERS(), json={"fields": body.get("fields", {})}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/tarefas/<record_id>", methods=["PATCH"])
def airtable_tarefas_patch(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        result = airtable_patch(BASE_RESERVAS, "Tarefas", record_id, body.get("fields", {}))
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/objetivos", methods=["GET", "POST"])
def airtable_objetivos():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "GET":
            recs = airtable_list("appOrdG5Fsr7N0RmH", "Objetivos & Crescimento")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id":  r["id"],
                    "mes": f.get("Mês", f.get("Mes", 0)),
                    "ano": f.get("Ano", 0),
                    "fat": float(f.get("Faturação", f.get("Faturacao", f.get("Objetivo", 0))) or 0),
                })
            return jsonify({"success": True, "records": out})
        else:
            body = request.get_json() or {}
            result = req_lib.post(
                "https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/Objetivos%20%26%20Crescimento",
                headers=AT_HEADERS(), json={"fields": body.get("fields", {})}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas", methods=["GET", "POST"])
def airtable_notas():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "GET":
            recs = airtable_list(BASE_RESERVAS, "Notas")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({
                    "id":       r["id"],
                    "titulo":   f.get("Título", f.get("Titulo", f.get("Nome", ""))),
                    "texto":    f.get("Texto", f.get("Nota", f.get("Conteúdo", ""))),
                    "data":     f.get("Data", f.get("Created", "")),
                    "cor":      f.get("Cor", ""),
                })
            return jsonify({"success": True, "records": out})
        else:
            body = request.get_json() or {}
            result = req_lib.post(
                f"https://api.airtable.com/v0/{BASE_RESERVAS}/Notas",
                headers=AT_HEADERS(), json={"fields": body.get("fields", {})}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas/<record_id>", methods=["PATCH", "DELETE"])
def airtable_notas_patch(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "DELETE":
            r = req_lib.delete(
                f"https://api.airtable.com/v0/{BASE_RESERVAS}/Notas/{record_id}",
                headers=AT_HEADERS(), timeout=15
            )
            r.raise_for_status()
            return jsonify({"success": True})
        body = request.get_json() or {}
        result = airtable_patch(BASE_RESERVAS, "Notas", record_id, body.get("fields", {}))
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/wa-templates", methods=["GET"])
def airtable_wa_templates():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        recs = airtable_list("appKhPwEBxolWaO9r", "Templates Mensagens")
        out = []
        for r in recs:
            f = r.get("fields", {})
            # Real field names from Airtable: Name, Categoria, Empresa, Tópico, Contexto, Subject 🇬🇧, Message 🇬🇧
            name     = f.get("Name", f.get("Nome", ""))
            empresa  = f.get("Empresa", "")
            if isinstance(empresa, list): empresa = empresa[0] if empresa else ""
            cat      = f.get("Categoria", "")
            if isinstance(cat, list): cat = cat[0] if cat else ""
            contexto = f.get("Contexto", f.get("Tópico", f.get("Topico", "")))
            # Message fields — try both emoji and plain versions
            msg_en   = f.get("Message 🇬🇧", f.get("Message", f.get("Mensagem EN", "")))
            msg_pt   = f.get("Message 🇵🇹", f.get("Mensagem PT", f.get("Mensagem", "")))
            msg_fr   = f.get("Message 🇫🇷", f.get("Mensagem FR", ""))
            subj_en  = f.get("Subject 🇬🇧", f.get("Subject", f.get("Assunto EN", "")))
            subj_pt  = f.get("Subject 🇵🇹", f.get("Assunto PT", f.get("Assunto", "")))
            out.append({
                "id":        r["id"],
                "name":      name,
                "nome":      name,
                "label":     name,
                "empresa":   empresa,
                "categoria": cat,
                "contexto":  contexto,
                "msg_en":    msg_en,
                "msg_pt":    msg_pt,
                "msg_fr":    msg_fr,
                "subj_en":   subj_en,
                "subj_pt":   subj_pt,
                "text_en":   msg_en,
                "text_pt":   msg_pt,
                "text":      msg_pt or msg_en,
                "subject":   subj_pt or subj_en,
                "idioma":    f.get("Idioma", "EN"),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/extrato-parceiros", methods=["GET"])
@app.route("/airtable/extrato-parceiros/<record_id>", methods=["GET", "PATCH"])
@app.route("/airtable/extrato-parceiros/criar-mes", methods=["POST"])
def airtable_extrato_parceiros(**kwargs):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        BASE_EP = "appRGJjirAzgEe46q"
        if request.method == "GET":
            mes = request.args.get("mes", "")
            ano = request.args.get("ano", "")
            params = {}
            if mes:
                params["filterByFormula"] = f"{{Mês}}='{mes}'"
            elif ano:
                params["filterByFormula"] = f"FIND('{ano}',{{Mês}})>0"
            recs = airtable_list(BASE_EP, "Extrato Parceiros", max_records=500)
            out = []
            for r in recs:
                f = r.get("fields", {})
                mes_val = f.get("Mês", f.get("Mes", ""))
                if mes and mes_val != mes: continue
                if ano and str(ano) not in str(mes_val): continue
                out.append({
                    "id":          r["id"],
                    "parceiro":    f.get("Parceiro", ""),
                    "mes":         mes_val,
                    "total":       float(f.get("Total", f.get("Valor", 0)) or 0),
                    "mailEnviado": bool(f.get("Mail enviado / pedido?", False)),
                    "pago":        bool(f.get("Pago", False)),
                })
            return jsonify({"success": True, "records": out})
        elif request.method == "PATCH":
            record_id = kwargs.get("record_id", "")
            body = request.get_json() or {}
            result = airtable_patch(BASE_EP, "Extrato Parceiros", record_id, body.get("fields", {}))
            return jsonify({"success": True, "record": result})
        else:
            return jsonify({"success": True, "records": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/resumos-mensais", methods=["GET"])
def airtable_resumos_mensais():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        recs = airtable_list("appOrdG5Fsr7N0RmH", "Resumos Mensais")
        out = []
        for r in recs:
            f = r.get("fields", {})
            out.append({
                "id":  r["id"],
                "mes": f.get("Mês", f.get("Mes", "")),
                "fat": float(f.get("Faturação", f.get("Faturacao", 0)) or 0),
                "com": float(f.get("Comissões", f.get("Comissoes", 0)) or 0),
                "desp": float(f.get("Despesas", 0) or 0),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/caixa-mensal", methods=["GET", "POST"])
@app.route("/airtable/caixa-mensal/<record_id>", methods=["PATCH"])
def airtable_caixa_mensal(**kwargs):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        if request.method == "GET":
            recs = airtable_list("appOrdG5Fsr7N0RmH", "Caixa Mensal")
            out = []
            for r in recs:
                f = r.get("fields", {})
                out.append({"id": r["id"], **{k: v for k, v in f.items()}})
            return jsonify({"success": True, "records": out})
        elif request.method == "POST":
            body = request.get_json() or {}
            result = req_lib.post(
                "https://api.airtable.com/v0/appOrdG5Fsr7N0RmH/Caixa%20Mensal",
                headers=AT_HEADERS(), json={"fields": body.get("fields", {})}, timeout=15
            )
            result.raise_for_status()
            return jsonify({"success": True, "record": result.json()})
        else:
            record_id = kwargs.get("record_id", "")
            body = request.get_json() or {}
            result = airtable_patch("appOrdG5Fsr7N0RmH", "Caixa Mensal", record_id, body.get("fields", {}))
            return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/preview-email", methods=["POST"])
def preview_email():
    """Return rendered HTML email for preview."""
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        d    = request.get_json() or {}
        tipo = d.get("tipo", "rc")

        if tipo == "at":
            tmpl     = _load_template("email_at_template.html")
            atividade = d.get("atividade", "")
            operador  = d.get("operador", "")
            pickup_local = d.get("pickup_local", "")
            pickup_block = f'''<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
              <tr><td style="background:#f2f9fa;border-left:4px solid #0d6e7a;border-radius:0 8px 8px 0;padding:20px 22px;">
                <p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:1.5px;color:#0d6e7a;text-transform:uppercase;">📍 Meeting Point</p>
                <p style="margin:0;font-size:14px;color:#2a2a2a;line-height:1.8;">{pickup_local}</p>
              </td></tr></table>''' if pickup_local else ""
            pagamento    = d.get("pagamento", "cash")
            payment_note = "Cash on the day of the activity." if "cash" in pagamento else "Payment by card on the day." if "card" in pagamento else "To be confirmed."
            tips_html    = build_tips_html(get_activity_tips(atividade, d.get("categoria", "")))
            replacements = {
                "{{cliente}}":      d.get("cliente", "Guest"),
                "{{atividade}}":    atividade,
                "{{data}}":         d.get("data", ""),
                "{{hora}}":         d.get("hora", "TBC"),
                "{{participantes}}":str(d.get("participantes", "")),
                "{{operador}}":     operador,
                "{{referencia}}":   d.get("referencia", ""),
                "{{total}}":        str(d.get("total", "")),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", pickup_local),
                "{{payment_note}}": payment_note,
                "{{tips_block}}":   tips_html,
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }
        else:
            tmpl = _load_template("email_rc_template.html")
            replacements = {
                "{{cliente}}":      d.get("cliente", "Guest"),
                "{{empresa}}":      d.get("empresa", ""),
                "{{veiculo}}":      d.get("veiculo", ""),
                "{{referencia}}":   d.get("referencia", ""),
                "{{total}}":        str(d.get("total", "")),
                "{{pickup_data}}":  d.get("pickup_data", ""),
                "{{pickup_hora}}":  d.get("pickup_hora", ""),
                "{{pickup_local}}": d.get("pickup_local", ""),
                "{{dropoff_data}}": d.get("dropoff_data", ""),
                "{{dropoff_hora}}": d.get("dropoff_hora", ""),
                "{{dropoff_local}}":d.get("dropoff_local", ""),
                "{{pickup_instrucoes}}": d.get("pickup_instrucoes", ""),
                "{{parceiro_tel}}": d.get("parceiro_tel", ""),
            }

        for k, v in replacements.items():
            tmpl = tmpl.replace(k, str(v) if v else "")

        return jsonify({"success": True, "html": tmpl})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Beyond Madeira Voucher API",
        "endpoints": [
            "/gerar-voucher",
            "/gerar-voucher-atividade",
            "/airtable/rc",
            "/airtable/at",
            "/airtable/sitemap",
            "/airtable/biblioteca",
            "/airtable/guia",
        ]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
