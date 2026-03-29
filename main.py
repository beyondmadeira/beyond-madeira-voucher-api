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


# =========================================================================
# RENT CAR
# =========================================================================
# =========================================================================
# RENT CAR
# =========================================================================
def _load_template(fname):
    """Load HTML template from file next to main.py, fallback to empty string."""
    import os
    p = os.path.join(os.path.dirname(__file__), fname)
    try:
        with open(p, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[WARN] Could not load {fname}: {e}")
        return ""

RC_TEMPLATE = _load_template("voucher_rc_template.html")

# =========================================================================
# ACTIVITY VOUCHER
# =========================================================================
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
                "nome":        f.get("Nome do cliente", f.get("Nome do Cliente", "")),
                "tel":         f.get("Número de Telemovel", f.get("Telefone", "")),
                "email":       f.get("Email do cliente", f.get("Email", "")),
                "idade":       f.get("Idade", ""),
                "parceiro":    f.get("Fornecedor/Parceiro", f.get("Parceiro", "")),
                "carro":       f.get("Modelo de Carro", f.get("Veículo", f.get("Veiculo", ""))),
                "estado":      f.get("Estado do Reserva", f.get("Estado da Reserva", "")),
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
                "ref":         f.get("Referência", f.get("Referencia", str(rec.get("id","")))),
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
        return jsonify({"url": data.get("url", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

    def _row_html(r, bg):
        sc = {"Pago":"#166534","Por Pagar":"#111827","Devemos":"#991B1B","Cancelado":"#6B7280"}.get(r["status"],"#6B7280")
        strike = "text-decoration:line-through;opacity:0.5;" if r["status"]=="Cancelado" else ""
        _em = "\u2014"
        pax = str(r.get("pax") or _em).replace(" Pessoas","").replace(" Pessoa","").strip()
        return (
            f'<tr style="background:{bg}">'
            f'<td style="padding:7px 8px;font-size:8pt;color:#6B7280;{strike}">{r["date"]}</td>'
            f'<td style="padding:7px 8px;font-size:8.5pt;color:#111827;{strike}">{(r["client"] or _em)[:32]}</td>'
            f'<td style="padding:7px 8px;font-size:8.5pt;color:#374151;{strike}">{(r["act"] or _em)[:28]}</td>'
            f'<td style="padding:7px 8px;font-size:8pt;color:#6B7280;text-align:center">{pax}</td>'
            f'<td style="padding:7px 8px;font-size:8.5pt;color:#111827;text-align:right;{strike}">&euro; {abs(r["total"]):,.2f}</td>'
            f'<td style="padding:7px 8px;font-size:8.5pt;font-weight:700;color:#0A616B;text-align:right;{strike}">&euro; {abs(r["comm"]):,.2f}</td>'
            f'<td style="padding:7px 8px;font-size:7.5pt;color:{sc};text-align:center;font-weight:600">{r["status"]}</td>'
            f'</tr>'
        )

    rows_html = ""
    if rows_by_month and len(rows_by_month) > 1:
        row_idx = 0
        for m_nome_i, m_ano_i, m_rows_i in rows_by_month:
            if not m_rows_i: continue
            m_tots = calc_totais(m_rows_i)
            rows_html += (
                f'<tr><td colspan="7" style="padding:8px 8px 4px;background:#f0faf9;border-top:1.5pt solid #0A616B;border-bottom:0.5pt solid #9CA3AF">'
                f'<span style="font-size:9pt;font-weight:800;color:#0A616B">{m_nome_i} {m_ano_i}</span>'
                f'<span style="font-size:8pt;color:#6B7280;margin-left:8px">{len(m_rows_i)} reservas</span></td></tr>'
            )
            for i, r in enumerate(m_rows_i):
                rows_html += _row_html(r, "#F9FAFB" if (row_idx + i) % 2 == 0 else "#FFFFFF")
            row_idx += len(m_rows_i)
            rows_html += (
                f'<tr style="background:#f0faf9">'
                f'<td colspan="4" style="padding:5px 8px;font-size:8pt;color:#374151;font-style:italic">Subtotal {m_nome_i} {m_ano_i}</td>'
                f'<td style="padding:5px 8px;font-size:8.5pt;font-weight:700;text-align:right">&euro; {abs(m_tots["gt"]):,.2f}</td>'
                f'<td style="padding:5px 8px;font-size:8.5pt;font-weight:700;color:#0A616B;text-align:right">&euro; {abs(m_tots["gc"]):,.2f}</td>'
                f'<td></td></tr>'
            )
    else:
        for i, r in enumerate(rows):
            rows_html += _row_html(r, "#F9FAFB" if i % 2 == 0 else "#FFFFFF")

    logo_src = logo_b64()
    title_mes = "&nbsp;+&nbsp;".join([f"{mn} {my}" for mn,my,_ in rows_by_month]) if rows_by_month and len(rows_by_month)>1 else f"{mes_nome} {ano}"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 1.8cm 1.8cm 1.6cm 1.8cm; }}
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ font-family: Helvetica, Arial, sans-serif; color:#111827; font-size:9pt; }}
  .top-bar {{ position:fixed;top:-1.8cm;left:-1.8cm;right:-1.8cm;height:5mm;background:#0A616B; }}
  .footer {{ position:fixed;bottom:-1.6cm;left:-1.8cm;right:-1.8cm;border-top:0.5pt solid #E5E7EB;padding:4pt 0; }}
  .footer-inner {{ display:table;width:100%;padding:0 1.8cm; }}
  .footer-l {{ display:table-cell;font-size:6.5pt;color:#6B7280; }}
  .footer-r {{ display:table-cell;font-size:6.5pt;color:#6B7280;text-align:right; }}
  table.main {{ width:100%;border-collapse:collapse; }}
  .dt {{ margin-bottom:20pt;width:100%;border-collapse:collapse; }}
  .dt th {{ font-size:7.5pt;font-weight:700;color:#6B7280;padding:7px 8px;border-bottom:1pt solid #9CA3AF;text-align:left;background:#fff; }}
  .dt tfoot td {{ border-top:1pt solid #9CA3AF;font-weight:700;background:#F3F4F6; }}
</style>
</head><body>
<div class="top-bar"></div>
<table class="main" style="margin-bottom:14pt"><tr>
  <td style="width:45%;vertical-align:top;padding-top:4pt">
    <img src="{logo_src}" style="height:38pt;margin-bottom:8pt;display:block" alt="Beyond Madeira">
    <div style="font-size:7.5pt;color:#6B7280;line-height:1.8">Largo da Sa\u00fade 1, 9000-221 Funchal<br>RNAVT 13020 \u00b7 NIPC 518 827 119<br>info@beyondmadeira.com \u00b7 +351 939 566 415</div>
  </td>
  <td style="text-align:right;vertical-align:top">
    <div style="font-size:9pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt">Extrato de Comiss\u00f5es</div>
    <div style="font-size:20pt;font-weight:700;color:#111827;line-height:1.2;margin:4pt 0">{title_mes}</div>
    <div style="font-size:8pt;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.5pt;margin-top:6pt">PARA</div>
    <div style="font-size:14pt;font-weight:700;color:#0A616B;margin-top:2pt">{parceiro}</div>
    <div style="font-size:7.5pt;color:#6B7280;font-style:italic;margin-top:4pt">Ref. {ref} \u00b7 Emitido a {today}</div>
  </td>
</tr></table>
<hr style="border:none;border-top:1pt solid #111827;margin:0 0 14pt 0">
<div style="font-size:7pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt;margin-bottom:5pt">Detalhe das Reservas</div>
<table class="dt">
  <thead><tr>
    <th style="width:44pt">Data</th><th style="width:110pt">Cliente</th><th>Atividade / Carro</th>
    <th style="width:28pt;text-align:center">Pax</th><th style="width:58pt;text-align:right">Total</th>
    <th style="width:62pt;text-align:right">Comiss\u00e3o</th><th style="width:54pt;text-align:center">Estado</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
  <tfoot><tr>
    <td colspan="4" style="padding:7px 8px"></td>
    <td style="padding:7px 8px;font-size:9pt;color:#111827;text-align:right">\u20ac {abs(t["gt"]):,.2f}</td>
    <td style="padding:7px 8px;font-size:9pt;color:#0A616B;text-align:right">\u20ac {abs(t["gc"]):,.2f}</td>
    <td style="padding:7px 8px;font-size:7.5pt;color:#6B7280;text-align:center">TOTAL</td>
  </tr></tfoot>
</table>
<table class="main"><tr>
  <td style="width:52%;vertical-align:top;padding-right:16pt">
    <div style="font-size:7pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt;margin-bottom:5pt">Resumo Financeiro</div>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#fff;border-bottom:0.5pt solid #E5E7EB">
        <td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Total faturado</div><div style="font-size:7pt;color:#9CA3AF">{t["n"]} reservas \u00b7 {t["n_can"]} canceladas</div></td>
        <td style="text-align:right;font-size:9pt;color:#6B7280;padding:10px 8px;white-space:nowrap">\u20ac {abs(t["gt"]):,.2f}</td>
      </tr>
      <tr style="background:#F3F4F6;border-bottom:0.5pt solid #E5E7EB">
        <td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Comiss\u00f5es a pagar</div><div style="font-size:7pt;color:#9CA3AF">{t["n_norm"]} reservas \u2014 cliente pagou ao parceiro</div></td>
        <td style="text-align:right;font-size:9pt;font-weight:700;color:#0A616B;padding:10px 8px;white-space:nowrap">\u20ac {abs(t["comiss"]):,.2f}</td>
      </tr>
      <tr style="background:#fff">
        <td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Cr\u00e9dito a descontar</div><div style="font-size:7pt;color:#9CA3AF">{t["n_dev"]} reservas \u2014 cliente pagou \u00e0 Beyond</div></td>
        <td style="text-align:right;font-size:9pt;color:#6B7280;padding:10px 8px;white-space:nowrap">\u2212 \u20ac {abs(t["credito"]):,.2f}</td>
      </tr>
    </table>
    <table style="width:100%;border-collapse:collapse;margin-top:8pt;background:#0A616B">
      <tr>
        <td style="padding:12px 14px;font-size:10pt;font-weight:700;color:white">TOTAL A RECEBER</td>
        <td style="padding:12px 14px;font-size:16pt;font-weight:700;color:white;text-align:right;white-space:nowrap">\u20ac {abs(t["total_fim"]):,.2f}</td>
      </tr>
    </table>
  </td>
  <td style="width:48%;vertical-align:top">
    <table style="width:100%;border-collapse:collapse;background:#0A616B">
      <tr><td colspan="2" style="padding:14px 16px 6px;font-size:7pt;font-weight:700;color:#A7F3D0;text-transform:uppercase;letter-spacing:1pt">Dados para Pagamento</td></tr>
      <tr><td style="padding:5px 16px;font-size:7pt;font-weight:700;color:#A7F3D0;width:70pt">Banco</td><td style="padding:5px 16px;font-size:9pt;color:white">Santander</td></tr>
      <tr><td style="padding:5px 16px;font-size:7pt;font-weight:700;color:#A7F3D0">IBAN</td><td style="padding:5px 16px;font-size:8.5pt;font-weight:700;color:white">PT50 0018 0003 6587 1568 0201 8</td></tr>
      <tr><td style="padding:5px 16px;font-size:7pt;font-weight:700;color:#A7F3D0">Titular</td><td style="padding:5px 16px;font-size:9pt;color:white">Milton Quintal Lda</td></tr>
      <tr><td style="padding:5px 16px 14px;font-size:7pt;font-weight:700;color:#A7F3D0">Refer\u00eancia</td><td style="padding:5px 16px 14px;font-size:9pt;color:white">{ref}</td></tr>
    </table>
  </td>
</tr></table>
<hr style="border:none;border-top:0.5pt solid #E5E7EB;margin-top:20pt">
<div style="font-size:7.5pt;color:#6B7280;font-style:italic;margin-top:6pt">Em caso de d\u00favida ou discrepância, contacte-nos antes de efetuar qualquer transfer\u00eancia. Obrigado pela parceria.</div>
<div class="footer"><div class="footer-inner">
  <span class="footer-l">Beyond Madeira \u00b7 RNAVT 13020 \u00b7 NIPC 518 827 119 \u00b7 +351 939 566 415</span>
  <span class="footer-r">Ref. {ref}</span>
</div></div>
</body></html>"""


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

        recs_rc = airtable_list(BASE_RESERVAS, "tblGc8HoEYOA5uG5Q")
        recs_at = airtable_list(BASE_RESERVAS, "tblla0uOKTcyboVXU")
        rows = []
        for rf in recs_rc + recs_at:
            f = rf.get("fields", {})
            par = get_text_f(fget_f(f, "Parceiro", "Empresa", "Rent Car Company") or "")
            if par.lower() != parceiro.lower(): continue
            raw_date = get_text_f(fget_f(f, "Data de Devolução", "Data de Drop Off", "Data de Fim", "Data") or "")
            if not raw_date: continue
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(raw_date[:10])
                if dt.month != mes_num or dt.year != ano: continue
            except: continue
            status_raw = get_text_f(fget_f(f, "Estado de Reserva", "Estado da Reserva") or "")
            if status_raw in ("Cancelado","Cancelada"): status = "Cancelado"
            elif status_raw == "Devemos": status = "Devemos"
            elif status_raw == "Pago": status = "Pago"
            else: status = "Por Pagar"
            total = eur_val(fget_f(f, "Preço Total", "Valor da Reserva (€)") or 0)
            comm  = eur_val(fget_f(f, "Comissão") or 0)
            client= get_text_f(fget_f(f, "Nome do Cliente", "Nome do cliente") or "")
            act   = norm_act(fget_f(f, "Atividade", "Modelo de Carro") or "")
            pax   = get_text_f(fget_f(f, "Nº Pessoas", "Duração") or "")
            rows.append(dict(date=dt.strftime("%d/%m"), client=client, act=act,
                             pax=pax, total=total, comm=comm, status=status))
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
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500
    try:
        body = request.get_json() or {}
        messages  = body.get("messages", [])
        model     = body.get("model", "claude-sonnet-4-20250514")
        max_tokens= body.get("max_tokens", 1024)
        system    = body.get("system", "")
        payload   = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            payload["system"] = system
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
