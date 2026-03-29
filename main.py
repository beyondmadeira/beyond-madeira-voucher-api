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
POST /gerar-extrato-parceiro      -> Partner commission statement PDF
POST /gerar-extratos-mes          -> All partner statements for a month
GET  /airtable/extrato-parceiros  -> List Extrato Parceiros records
GET  /                           -> Health check
"""

import os, re, base64, json, urllib.parse, urllib.request, urllib.error, requests as req_lib
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from weasyprint import HTML

app = Flask(__name__)
CORS(app, origins="*")

import time
_cache = {}
CACHE_TTL = 6 * 60 * 60

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

AT_TOKEN        = os.environ.get("AIRTABLE_TOKEN", "")
BASE_RESERVAS   = "appR8ZKP5ygR8o8Q0"
BASE_CONHECIMENTO = "appKhPwEBxolWaO9r"
BASE_FINANCEIRO   = "appOrdG5Fsr7N0RmH"
AT_HEADERS      = lambda: {"Authorization": f"Bearer {AT_TOKEN}", "Content-Type": "application/json"}

OPERATOR_CONTACTS = {
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
    "Point Car":                 ("+351 968 888 026", "booking@pointcarrental.pt"),
    "Atlantic Rent Car":         ("+351 962 403 756", "reservations@atlanticrentacar.pt"),
    "RentCar Madeira":           ("+351 936 716 627", "booking@rentcarmadeira.com"),
    "AB4rent":                   ("+351 961 932 738", "info@ab4rent.com"),
    "Amsterdam Car":             ("+351 968 566 790", ""),
}

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
    {"kw": ["sunrise", "pico areeiro"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["warm", "water", "snack", "shoes"], "note": "Dress very warmly — Pico Areeiro can be below 0°C at sunrise."},
    {"kw": ["caldeirao verde", "caldeirão verde"], "payment": "cash", "pickup": "pickup_hotel", "tips": ["jacket", "water", "flashlight", "snack", "shoes"], "note": "A flashlight is essential for the tunnel section of the trail."},
    {"kw": ["west", "jeep"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["jacket", "swimsuit", "water", "snack"], "note": "The tour may include a swim stop — bring swimwear just in case."},
    {"kw": ["west", "minivan"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["jacket", "swimsuit", "water", "snack"], "note": "The tour may include a swim stop — bring swimwear just in case."},
    {"kw": ["east", "jeep"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["jacket", "water", "snack"], "note": ""},
    {"kw": ["east", "minivan"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["jacket", "water", "snack"], "note": ""},
    {"kw": ["whale", "dolphin"], "payment": "cash_card", "pickup": "meeting_point", "tips": ["jacket", "swimsuit", "sunscreen", "water"], "note": "Please arrive at the marina 30 minutes before departure for check-in and payment."},
    {"kw": ["sunset"], "payment": "cash_card", "pickup": "meeting_point", "tips": ["jacket", "sunscreen", "water"], "note": ""},
    {"kw": ["canyoning"], "payment": "cash", "pickup": "pickup_hotel", "tips": ["jacket", "swimsuit", "sunscreen", "snack"], "note": "All equipment is included. Bring swimwear and warm clothes for after."},
    {"kw": ["coasteering"], "payment": "cash", "pickup": "pickup_hotel", "tips": ["jacket", "swimsuit", "sunscreen", "water"], "note": "All equipment is included."},
    {"kw": ["hike", "levada", "stairway to heaven"], "payment": "cash", "pickup": "pickup_day_before", "tips": ["jacket", "water", "snack", "shoes"], "note": ""},
    {"kw": ["buggy", "quad"], "payment": "cash_card", "pickup": "pickup_hotel", "tips": ["jacket", "water", "snack"], "note": ""},
    {"kw": ["paragliding", "paraglide"], "payment": "cash", "pickup": "pickup_hotel", "tips": ["jacket", "shoes"], "note": "Wear comfortable clothes and closed shoes."},
    {"kw": ["kayak"], "payment": "cash_card", "pickup": "meeting_point", "tips": ["swimsuit", "sunscreen", "water", "snack"], "note": ""},
    {"kw": ["diving", "scuba"], "payment": "cash", "pickup": "meeting_point", "tips": ["swimsuit", "sunscreen", "water"], "note": "All equipment provided. No experience needed."},
    {"kw": ["surf"], "payment": "cash", "pickup": "meeting_point", "tips": ["swimsuit", "sunscreen", "water"], "note": "All equipment provided."},
    {"kw": ["fishing"], "payment": "cash", "pickup": "meeting_point", "tips": ["jacket", "sunscreen", "water", "snack"], "note": ""},
    {"kw": ["private"], "payment": "cash", "pickup": "pickup_hotel", "tips": ["jacket", "water"], "note": ""},
]

def detect_activity(nome):
    n = nome.lower()
    for rule in ACTIVITY_RULES:
        if all(kw in n for kw in rule["kw"]):
            return rule
    return None

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
    url = f"https://api.airtable.com/v0/{base_id}/{req_lib.utils.quote(table_name)}/{record_id}"
    r = req_lib.patch(url, headers=AT_HEADERS(), json={"fields": fields}, timeout=15)
    r.raise_for_status()
    return r.json()

def airtable_create(base_id, table_name, fields):
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
        return jsonify({"success": True, "record": {"id": result.get("id", ""), "fields": result.get("fields", {})}})
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
        return jsonify({"success": True, "record": {"id": result.get("id", ""), "fields": result.get("fields", {})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route("/gerar-voucher", methods=["POST"])
def gerar_voucher():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400
        required = ["referencia", "total", "veiculo", "empresa", "cliente", "telefone", "email", "pickup_data", "pickup_hora", "pickup_local", "dropoff_data", "dropoff_hora", "dropoff_local"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        html_str = build_rc_html(d)
        pdf      = HTML(string=html_str).write_pdf()
        b64      = base64.b64encode(pdf).decode()
        fname    = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ','_')}.pdf"
        uploaded = False
        record_id = d.get("record_id", "")
        if record_id and record_id.startswith("rec") and AT_TOKEN:
            try:
                airtable_patch(BASE_RESERVAS, "Rent Car", record_id, {"Ficheiro": []})
                airtable_upload_attachment(BASE_RESERVAS, record_id, "Ficheiro", pdf, fname)
                cache_clear("rc")
                uploaded = True
            except Exception as upload_err:
                pass
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64, "uploaded": uploaded})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        html_str = build_at_html(d)
        pdf      = HTML(string=html_str).write_pdf()
        b64      = base64.b64encode(pdf).decode()
        fname    = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ','_')}.pdf"
        uploaded = False
        record_id = d.get("record_id", "")
        if record_id and record_id.startswith("rec") and AT_TOKEN:
            try:
                airtable_patch(BASE_RESERVAS, "Atividades", record_id, {"Ficheiro": []})
                airtable_upload_attachment(BASE_RESERVAS, record_id, "Ficheiro", pdf, fname)
                cache_clear("at")
                uploaded = True
            except Exception as upload_err:
                pass
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64, "uploaded": uploaded})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
                "parceiro":    get_text_f(f.get("Fornecedor/Parceiro", "")),
                "carro":       get_text_f(f.get("Modelo de Carro", "")),
                "estado":      get_text_f(f.get("Estado de Reserva", "")),
                "pagamento":   "",
                "pdt":         f.get("Data da Pick-up", ""),
                "ploc":        f.get("Localização Pick-up", f.get("Local Pick-up", "")),
                "pvoo":        "",
                "pdet":        f.get("Detalhes Pick Up", ""),
                "ddt":         f.get("Data do Drop Off", ""),
                "dloc":        f.get("Localização Drop-off", f.get("Local Drop-off", "")),
                "dvoo":        "",
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
        cache_clear("rc")
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
                "email":       f.get("Email Clientes", f.get("Email do Cliente", f.get("Email", ""))),
                "atv":         f.get("Atividade", ""),
                "cat":         f.get("Categoria", ""),
                "par":         get_text_f(f.get("Fornecedor/Parceiro", "")),
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
                "template_id": f.get("Template ID", ""),
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
        cache_clear("at")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/sitemap", methods=["GET"])
def get_sitemap():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_CONHECIMENTO, "Sitemap")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({"id": rec["id"], "nome": f.get("Nome de Página", f.get("Nome de Pagina", "")), "estado": f.get("Estado", ""), "categoria": f.get("Categoria Principal", ""), "url": f.get("URL", ""), "cat": f.get("Categoria", ""), "conteudo": f.get("Conteúdo", f.get("Conteudo", "")), "modified": f.get("Last Modified", "")})
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
            out.append({"id": rec["id"], "titulo": f.get("Answer Title", ""), "gatilho": f.get("Trigger / Customer Question", ""), "resposta": f.get("Answer", ""), "categoria": f.get("Category", ""), "estado": f.get("Status", ""), "obs": f.get("Observação", f.get("Observacao", ""))})
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
            out.append({"id": rec["id"], "titulo": f.get("Nome", ""), "categoria": f.get("Categoria", ""), "descricao": f.get("Descrição", f.get("Descricao", "")), "localizacao": f.get("Localização", f.get("Localizacao", "")), "estado": f.get("Estado", ""), "prioridade": f.get("Prioridade", ""), "tags": f.get("Tags", ""), "notas": f.get("Notas Internas", ""), "recomendado": f.get("Recomendado?", False), "preco": f.get("Preço Nível", f.get("Preco Nivel", "")), "horario": f.get("Horário", f.get("Horario", "")), "distancia": f.get("Distância", f.get("Distancia", "")), "dificuldade": f.get("Dificuldade", ""), "website": f.get("Website", ""), "contacto": f.get("Contacto", "")})
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
        result = airtable_patch(BASE_CONHECIMENTO, "Madeira Guide", record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            out.append({"id": rec["id"], "data": f.get("Data", ""), "fat": f.get("Faturação Diária", 0), "fat_rc": f.get("Faturação RC", 0), "fat_at": f.get("Faturação AT", 0), "mes": (f.get("Resumo Mensal") or [{}])[0].get("name","") if isinstance(f.get("Resumo Mensal"), list) else str(f.get("Resumo Mensal","")), "notas": f.get("Notas do Dia", ""), "resp": f.get("Responsável", "")})
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
        # "Resumo Mensal" é linked record — Airtable rejeita strings, remover
        fields.pop("Resumo Mensal", None)
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
            out.append({"id": rec["id"], "mes": f.get("Resumo Mensal", rec["id"]), "fat": f.get("Total de Faturação Mensal (€)", 0), "fat_rc": f.get("Faturação RC", 0), "fat_at": f.get("Faturação AT", 0), "lucro": f.get("Lucro Mensal (Automático)", 0), "caixa": f.get("Caixa Final (€)", 0), "receita": f.get("Receita Realizada", 0), "obj": f.get("Objetivo Mensal (€)", 0), "diff_obj": f.get("Diferença vs Objetivo", 0), "desp_fixas": f.get("Total de Despesas Fixas (€)", 0), "desp_var": f.get("Total de Despesas Variáveis (€)", 0), "desp_total": f.get("Total de Despesas (€)", 0), "media_diaria": f.get("Média Diária de Faturação (€)", 0), "dias_fat": f.get("N.º de Dias com Faturação", 0), "nres_rc": f.get("Nº Reservas RC", 0), "nres_at": f.get("Nº Reservas AT", 0), "status": f.get("Status do Mês", ""), "notas": f.get("Notas do Mês", "")})
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
            mes_raw = f.get("Resumo Mensal(s)", "") or f.get("Resumo Mensal", "")
            if isinstance(mes_raw, list):
                mes_str = mes_raw[0].get("name","") if mes_raw and isinstance(mes_raw[0],dict) else (str(mes_raw[0]) if mes_raw else "")
            else:
                mes_str = str(mes_raw)
            out.append({"id": rec["id"], "nome": f.get("Fornecedor", f.get("Nome", "")), "cat": f.get("Categoria", ""), "valor": float(f.get("Valor Mensal", 0) or 0), "mes": mes_str, "pago": bool(f.get("Pago?", False)), "fatura": bool(f.get("Fatura Recebida?", False) or f.get("Fatura?", False)), "recorrente": bool(f.get("Recorrente?", False)), "notas": f.get("Notas", ""), "tipo": "fixa"})
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
            mes_raw2 = f.get("Resumo Mensal(s)", "") or f.get("Resumo Mensal", "")
            if isinstance(mes_raw2, list):
                mes_str2 = mes_raw2[0].get("name","") if mes_raw2 and isinstance(mes_raw2[0],dict) else (str(mes_raw2[0]) if mes_raw2 else "")
            else:
                mes_str2 = str(mes_raw2)
            out.append({"id": rec["id"], "nome": f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))), "cat": f.get("Categoria", f.get("Tipo Despesa", "")), "valor": float(f.get("Valor", 0) or 0), "mes": mes_str2, "pago": bool(f.get("Pago?", False)), "fatura": bool(f.get("Fatura Recebida?", False) or f.get("Fatura?", False)), "notas": f.get("Notas", ""), "tipo": "variavel"})
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
            out.append({"id": rec["id"], "mes": f.get("Objetivos", rec["id"]), "obj_fat": f.get("🎯 Objetivo Faturação (€)", 0), "res_fat": f.get("Resultado Faturação (€)", 0), "dif_fat": f.get("📊 Diferença Faturação (€)", 0), "obj_lucro": f.get("🎯 Objetivo Lucro (€)", 0), "res_lucro": f.get("Resultado Lucro (€)", 0), "obj_reviews": f.get("🎯 Objetivo Reviews", 0), "res_reviews": f.get("Resultado Reviews", 0), "obj_ig": f.get("🎯 Objetivo Instagram", 0), "res_ig": f.get("Resultado Instagram", 0), "obj_fb": f.get("🎯 Objetivo Facebook", 0), "res_fb": f.get("Resultado Facebook", 0), "obj_tiktok": f.get("🎯 Objetivo Tiktok", 0), "res_tiktok": f.get("Resultado Tiktok", 0), "obj_views": f.get("🎯 Objetivo Website Views", 0), "res_views": f.get("Resultado Website Views", 0), "obj_users": f.get("🎯 Objetivo Utilizadores Ativos", 0), "res_users": f.get("Resultado Utilizadores Ativos", 0), "status": f.get("Status Geral", ""), "acoes": f.get("Ações do Mês", ""), "notas": f.get("Notas", "")})
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

TAB_CAIXA = "tblW32WemgLNYH9jO"

def parse_eur(val):
    if val is None or val == "": return 0
    if isinstance(val, (int, float)): return float(val)
    return float(str(val).replace("€","").replace(",","").strip() or 0)

@app.route("/airtable/caixa-mensal", methods=["GET"])
def get_caixa_mensal():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cached = cache_get("caixa")
        if cached is not None:
            return jsonify({"success": True, "records": cached, "cached": True})
        records = airtable_list_table(BASE_FINANCEIRO, TAB_CAIXA)
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({"id": rec["id"], "mes": f.get("Mês/Ano", ""), "saldo_dinheiro": parse_eur(f.get("Saldo Dinheiro (€)")), "saldo_banco": parse_eur(f.get("Saldo Banco (€)")), "saldo_total": parse_eur(f.get("Saldo Total (€)")), "fat_mes": parse_eur(f.get("Faturação do Mês (€)")), "desp_mes": parse_eur(f.get("Despesas do Mês (€)")), "lucro": parse_eur(f.get("Lucro Calculado (€)")), "diferenca": parse_eur(f.get("Diferença vs Caixa Real (€)")), "notas": f.get("Notas", "")})
        cache_set("caixa", out)
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/caixa-mensal/<record_id>", methods=["PATCH"])
def patch_caixa_mensal(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = {}
        if "saldo_dinheiro" in body: fields["Saldo Dinheiro (€)"] = float(body["saldo_dinheiro"] or 0)
        if "saldo_banco" in body: fields["Saldo Banco (€)"] = float(body["saldo_banco"] or 0)
        if "notas" in body: fields["Notas"] = str(body["notas"])
        if not fields:
            return jsonify({"error": "Nenhum campo para actualizar"}), 400
        result = airtable_patch(BASE_FINANCEIRO, TAB_CAIXA, record_id, fields)
        cache_clear("caixa")
        return jsonify({"success": True, "record": result})
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
            out.append({"id": rec["id"], "nome": f.get("Nome", f.get("Name", rec["id"])), "categoria": f.get("Categoria", ""), "tel": f.get("Contacto Telefone", ""), "email": f.get("Email", ""), "website": f.get("Website", ""), "morada": f.get("Morada Office", ""), "meeting_point": f.get("Meeting Point", ""), "comissao_tipo": f.get("Comissão Tipo", ""), "comissao_valor": f.get("Comissão Valor", 0), "comissao_notas": f.get("Comissão Notas", ""), "instrucoes_aeroporto": f.get("Instruções Aeroporto", ""), "instrucoes_hotel": f.get("Instruções Hotel", ""), "instrucoes_office": f.get("Instruções Office", ""), "atividades": f.get("Atividades / Passeios", ""), "logo_url": f.get("Logo URL", ""), "notas": f.get("Notas Internas", ""), "ativo": f.get("Ativo?", True)})
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
            out.append({"id": rec["id"], "email": f.get("Email", ""), "tel": f.get("Telefone", ""), "n_rc": f.get("N RC", 0), "n_at": f.get("N AT", 0), "total_rc": f.get("Total Gasto RC", 0), "total_at": f.get("Total Gasto AT", 0), "total": f.get("Total Gasto", 0), "n_total": f.get("N Total Reservas", 0), "primeira_reserva": f.get("Primeira Reserva", ""), "ultima_reserva": f.get("Ultima Reserva", ""), "pais": f.get("País", ""), "notas": f.get("Notas", ""), "vip": f.get("VIP?", False)})
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
            out.append({"id": rec["id"], "nome": f.get("Nome Cliente", ""), "email": f.get("Email Cliente", ""), "nota": f.get("Nota (1-5)", 0), "texto": f.get("Texto Review", ""), "data": f.get("Data", ""), "reserva": f.get("Reserva Relacionada", ""), "tipo": f.get("Tipo Reserva", ""), "respondido": f.get("Respondido?", False), "resposta": f.get("Resposta", ""), "link": f.get("Link Review", ""), "notas": f.get("Notas Internas", "")})
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
            out.append({"id": rec["id"], "carro": f.get("Carro", ""), "data_inicio": f.get("Data Início", ""), "data_fim": f.get("Data Fim", ""), "motivo": f.get("Motivo", ""), "alternativa": f.get("Alternativa Sugerida", "")})
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
            out.append({"id": rec["id"], "carro": f.get("Carro", ""), "tipo": f.get("Tipo", ""), "preco_baixa_12": f.get("Preço Baixa 1-2d", 0), "preco_baixa_36": f.get("Preço Baixa 3-6d", 0), "preco_baixa_7p": f.get("Preço Baixa 7d+", 0), "preco_alta_12": f.get("Preço Alta 1-2d", 0), "preco_alta_36": f.get("Preço Alta 3-6d", 0), "preco_alta_7p": f.get("Preço Alta 7d+", 0), "epoca_baixa_ini": f.get("Época Baixa Início", ""), "epoca_baixa_fim": f.get("Época Baixa Fim", ""), "epoca_alta_ini": f.get("Época Alta Início", ""), "epoca_alta_fim": f.get("Época Alta Fim", ""), "com_tipo": f.get("Comissão Tipo", ""), "com_valor": f.get("Comissão Valor", 0), "posicao": f.get("Posição Hierarquia", 0), "obs": f.get("Observações", ""), "ativo": f.get("Ativo?", True)})
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
            titulo = ""
            for k, v in f.items():
                if isinstance(v, str) and k not in ["Responsável","Status","Urgência","Notas","Data Limite","Categoria","Criado Em","Concluído Em"]:
                    titulo = v; break
            out.append({"id": rec["id"], "titulo": titulo, "responsavel": f.get("Responsável", ""), "status": f.get("Status", "Por Fazer"), "urgencia": f.get("Urgência", ""), "notas": f.get("Notas", ""), "data_limite": f.get("Data Limite", ""), "categoria": f.get("Categoria", ""), "criado_em": f.get("Criado Em", ""), "concluido_em": f.get("Concluído Em", "")})
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

BASE_EXTRATO = "appRGJjirAzgEe46q"
TAB_EXTRATO  = "tblHmWDHM64Dy4iwi"
TAB_AT_ID   = "tblla0uOKTcyboVXU"
TAB_RC_ID   = "tblGc8HoEYOA5uG5Q"

MESES_PT = {1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"}
MESES_IDX = {v:k for k,v in MESES_PT.items()}

ALIASES_PARC = {
    "jungle lost":"junglelost","surreal":"surrealmadeira","surreal madeira":"surrealmadeira","be local":"belocal","trail 4 fun":"trail4fun","trail4fun":"trail4fun","warriors adventure":"warriorsadventure","warriors":"warriorsadventure","green devil":"greendevil","101 routes":"101routes","madeira tours":"madeiratourspt","madeira discovery":"madeiradiscovery","icon travel":"icontravel","wildermadeira":"wildermadeira","wilder madeira":"wildermadeira","lido tours":"lidotours","madeira explorers":"madeiraexplorers","vmt":"vmt","seaborn":"seaborn","nau santa maria":"nausantamaria","epicmadeira":"epicmadeira","epic madeira":"epicmadeira","quad xperience":"quadxperience","damwalk":"damwalk","free spirit":"freespirit","bearded":"bearded","mak":"mak","amsterdam rent car":"amsterdamrentcar","atlantic rent car":"atlanticrentcar","pointcar":"pointcar","point car":"pointcar","ab4rent":"ab4rent","rent car madeira":"rentcarmadeira",
}

def slug_norm_p(s):
    s2 = re.sub(r"[^a-z0-9]", "", str(s).lower().strip())
    key = str(s).lower().strip()
    return ALIASES_PARC.get(key, s2)

def eur_val(v):
    try: return float(str(v or 0).replace("€","").replace(",",".").strip() or 0)
    except: return 0.0

def get_text_f(v):
    if not v: return ""
    if isinstance(v, list):
        first = v[0] if v else ""
        if isinstance(first, dict): return first.get("name", str(first))
        return str(first)
    if isinstance(v, dict): return v.get("name", str(v))
    return str(v)

def fget_f(rf, *keys):
    for k in keys:
        val = rf.get(k)
        if val not in (None, ""): return val
    rf_s = {k.strip(): v for k,v in rf.items()}
    for k in keys:
        val = rf_s.get(k.strip())
        if val not in (None, ""): return val
    return None

def parse_date_ext(s):
    from datetime import datetime
    if not s: return None
    s = str(s).strip()
    s = s.split("T")[0].split(" ")[0]
    for fmt_ in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt_)
            if not (2010 <= dt.year <= 2035):
                return None
            return dt
        except:
            pass
    return None

NORM_RULES = [
    (["private","west"],"Private West Tour"),(["private","east"],"Private East Tour"),(["private","jeep"],"Private Jeep Tour"),(["private","mini","van"],"Private Mini Van"),(["private","levada"],"Private Levada Walk"),(["private","walk"],"Private Guided Walk"),(["private","tour"],"Private Tour"),(["west"],"West Tour"),(["east"],"East Tour"),(["mini","van"],"Mini Van Tour"),(["25","fountain"],"25 Fountains"),(["rabaçal"],"25 Fountains"),(["jeep"],"Jeep Safari"),(["safari"],"Jeep Safari"),(["canyoning","beginner"],"Canyoning Beginner"),(["canyoning","intermediate"],"Canyoning Intermediate"),(["canyoning"],"Canyoning"),(["buggy"],"Buggy Experience"),(["sunrise"],"Sunrise Tour"),(["pico"],"Pico Arieiro"),(["levada","alecrim"],"Levada do Alecrim"),(["levada","rei"],"Levada do Rei"),(["levada"],"Levada Walk"),(["caldeirão"],"Caldeirão Verde"),(["whale"],"Whale & Dolphin"),(["boat"],"Boat Tour"),(["e-bike"],"E-Bike Experience"),(["quad"],"Quad Experience"),(["surf"],"Surf Lesson"),(["scuba"],"Scuba Diving"),(["fishing"],"Fishing"),(["coasteering"],"Coasteering"),(["fanal"],"Fanal Walk"),
]

def norm_act(raw):
    raw = get_text_f(raw)
    if not raw: return "—"
    low = raw.lower()
    for kws, name in NORM_RULES:
        if all(k in low for k in kws): return name
    return raw.strip()[:30]

def airtable_list_table(base_id, table_id, formula=None):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    params = {"pageSize": 100}
    if formula: params["filterByFormula"] = formula
    records = []
    while True:
        r = req_lib.get(url, headers=AT_HEADERS(), params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset: break
        params["offset"] = offset
    return records

def airtable_upload_attachment(base_id, record_id, field_name, pdf_bytes, filename):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    field_enc = req_lib.utils.quote(field_name, safe="")
    url = f"https://content.airtable.com/v0/{base_id}/{record_id}/{field_enc}/uploadAttachment"
    headers = {"Authorization": f"Bearer {AT_TOKEN}", "Content-Type": "application/json"}
    r = req_lib.post(url, headers=headers, json={"filename": filename, "contentType": "application/pdf", "file": b64}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_reservas_parceiro(parceiro, mes_num, ano, is_rc):
    from datetime import datetime, date
    import calendar
    sn_parc = slug_norm_p(parceiro)
    first_day = date(ano, mes_num, 1)
    last_day  = date(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
    fonte = airtable_list_table(BASE_RESERVAS, TAB_RC_ID if is_rc else TAB_AT_ID)
    rows = []
    for rec in fonte:
        rf = rec.get("fields", {})
        pname = get_text_f(fget_f(rf, "Fornecedor/Parceiro") or "")
        if slug_norm_p(pname) != sn_parc:
            continue
        date_raw = fget_f(rf, "Data do Drop Off") if is_rc else fget_f(rf, "Data da Atividade")
        dt = parse_date_ext(date_raw)
        if not dt:
            continue
        dt_date = dt.date() if hasattr(dt, "date") else dt
        if not (first_day <= dt_date <= last_day):
            continue
        estado = get_text_f(fget_f(rf, "Estado de Reserva") or "") if is_rc else get_text_f(fget_f(rf, "Estado da Reserva") or "")
        if estado in ("Cancelado", "Cancelada"):
            status = "Cancelado"
        elif estado == "Devemos":
            status = "Devemos"
        elif estado == "Pago":
            status = "Pago"
        else:
            status = "Por Pagar"
        if is_rc:
            total  = eur_val(fget_f(rf, "Valor da Reserva (€)") or 0)
            comm   = eur_val(fget_f(rf, "Comissão") or 0)
            client = get_text_f(fget_f(rf, "Nome do cliente") or "")
            act    = get_text_f(fget_f(rf, "Modelo de Carro") or "")
            pax    = str(fget_f(rf, "Duração") or "").strip()
        else:
            total  = eur_val(fget_f(rf, "Preço Total") or 0)
            comm   = eur_val(fget_f(rf, "Comissão") or 0)
            client = get_text_f(fget_f(rf, "Nome do Cliente") or "")
            act    = norm_act(fget_f(rf, "Atividade") or "")
            pax    = str(fget_f(rf, "Nº Pessoas") or "").strip()
        rows.append({"date": dt.strftime("%d/%m"), "client": client, "act": act, "pax": pax, "total": total, "comm": comm, "status": status})
    rows.sort(key=lambda x: x["date"])
    return rows

def calc_totais(rows):
    n       = len(rows)
    n_can   = sum(1 for r in rows if r["status"] == "Cancelado")
    rows_v  = [r for r in rows if r["status"] != "Cancelado"]
    n_norm  = sum(1 for r in rows_v if r["status"] != "Devemos")
    n_dev   = sum(1 for r in rows_v if r["status"] == "Devemos")
    gt      = sum(r["total"] for r in rows_v)
    gc      = sum(r["comm"]  for r in rows_v)
    comiss  = sum(r["comm"]  for r in rows_v if r["status"] != "Devemos")
    credito = sum(r["total"] - r["comm"] for r in rows_v if r["status"] == "Devemos")
    total_fim = comiss - credito
    return dict(n=n, n_can=n_can, n_norm=n_norm, n_dev=n_dev, gt=gt, gc=gc, comiss=comiss, credito=credito, total_fim=total_fim)

def build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots, rows_by_month=None):
    from datetime import datetime
    today = datetime.now().strftime("%d/%m/%Y")
    t = tots

    def _row_html(r, bg):
        sc = {"Pago":"#166534","Por Pagar":"#111827","Devemos":"#991B1B","Cancelado":"#6B7280"}.get(r["status"],"#6B7280")
        strike = "text-decoration:line-through;opacity:0.5;" if r["status"]=="Cancelado" else ""
        _em = "—"
        pax = str(r.get("pax") or _em).replace(" Pessoas","").replace(" Pessoa","").strip()
        return (f'<tr style="background:{bg}"><td style="padding:7px 8px;font-size:8pt;color:#6B7280;{strike}">{r["date"]}</td><td style="padding:7px 8px;font-size:8.5pt;color:#111827;{strike}">{(r["client"] or _em)[:32]}</td><td style="padding:7px 8px;font-size:8.5pt;color:#374151;{strike}">{(r["act"] or _em)[:28]}</td><td style="padding:7px 8px;font-size:8pt;color:#6B7280;text-align:center">{pax}</td><td style="padding:7px 8px;font-size:8.5pt;color:#111827;text-align:right;{strike}">&euro; {abs(r["total"]):,.2f}</td><td style="padding:7px 8px;font-size:8.5pt;font-weight:700;color:#0A616B;text-align:right;{strike}">&euro; {abs(r["comm"]):,.2f}</td><td style="padding:7px 8px;font-size:7.5pt;color:{sc};text-align:center;font-weight:600">{r["status"]}</td></tr>')

    rows_html = ""
    if rows_by_month and len(rows_by_month) > 1:
        row_idx = 0
        for m_nome_i, m_ano_i, m_rows_i in rows_by_month:
            if not m_rows_i:
                continue
            m_tots = calc_totais(m_rows_i)
            rows_html += f'<tr><td colspan="7" style="padding:8px 8px 4px;background:#f0faf9;border-top:1.5pt solid #0A616B;border-bottom:0.5pt solid #9CA3AF"><span style="font-size:9pt;font-weight:800;color:#0A616B">{m_nome_i} {m_ano_i}</span><span style="font-size:8pt;color:#6B7280;margin-left:8px">{len(m_rows_i)} reservas</span></td></tr>'
            for i, r in enumerate(m_rows_i):
                rows_html += _row_html(r, "#F9FAFB" if (row_idx + i) % 2 == 0 else "#FFFFFF")
            row_idx += len(m_rows_i)
            rows_html += f'<tr style="background:#f0faf9"><td colspan="4" style="padding:5px 8px;font-size:8pt;color:#374151;font-style:italic">Subtotal {m_nome_i} {m_ano_i}</td><td style="padding:5px 8px;font-size:8.5pt;font-weight:700;text-align:right">&euro; {abs(m_tots["gt"]):,.2f}</td><td style="padding:5px 8px;font-size:8.5pt;font-weight:700;color:#0A616B;text-align:right">&euro; {abs(m_tots["gc"]):,.2f}</td><td></td></tr>'
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
  .footer {{ position:fixed;bottom:-1.6cm;left:-1.8cm;right:-1.8cm;border-top:0.5pt solid #E5E7EB;padding:4pt 1.8cm;display:flex;justify-content:space-between;align-items:center; }}
  .footer span {{ font-size:6.5pt;color:#6B7280; }}
  table.main {{ width:100%;border-collapse:collapse; }}
  .dt th {{ font-size:7.5pt;font-weight:700;color:#6B7280;padding:7px 8px;border-bottom:1pt solid #9CA3AF;text-align:left;background:#fff; }}
  .dt {{ margin-bottom:20pt;width:100%;border-collapse:collapse; }}
</style>
</head><body>
<div class="top-bar"></div>
<table class="main" style="margin-bottom:14pt"><tr>
  <td style="width:45%;vertical-align:top;padding-top:4pt">
    <img src="{logo_src}" style="height:38pt;margin-bottom:8pt;display:block" alt="Beyond Madeira">
    <div style="font-size:7.5pt;color:#6B7280;line-height:1.8">Largo da Saúde 1, 9000-221 Funchal<br>RNAVT 13020 · NIPC 518 827 119<br>info@beyondmadeira.com · +351 939 566 415</div>
  </td>
  <td style="text-align:right;vertical-align:top">
    <div style="font-size:9pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt">Extrato de Comissões</div>
    <div style="font-size:20pt;font-weight:700;color:#111827;line-height:1.2;margin:4pt 0">{title_mes}</div>
    <div style="font-size:8pt;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.5pt;margin-top:6pt">PARA</div>
    <div style="font-size:14pt;font-weight:700;color:#0A616B;margin-top:2pt">{parceiro}</div>
    <div style="font-size:7.5pt;color:#6B7280;font-style:italic;margin-top:4pt">Ref. {ref} · Emitido a {today}</div>
  </td>
</tr></table>
<hr style="border:none;border-top:1pt solid #111827;margin:0 0 14pt 0">
<div style="font-size:7pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt;margin-bottom:5pt">Detalhe das Reservas</div>
<table class="dt">
  <thead><tr><th style="width:44pt">Data</th><th style="width:110pt">Cliente</th><th>Atividade / Carro</th><th style="width:28pt;text-align:center">Pax</th><th style="width:58pt;text-align:right">Total</th><th style="width:62pt;text-align:right">Comissão</th><th style="width:54pt;text-align:center">Estado</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<div style="border-top:1pt solid #9CA3AF;background:#F3F4F6;display:flex;justify-content:flex-end;padding:7px 8px;margin-bottom:20pt">
  <div style="width:44pt"></div><div style="width:110pt"></div><div style="flex:1"></div><div style="width:28pt"></div>
  <div style="width:58pt;text-align:right;font-size:9pt;font-weight:700;color:#111827;padding:0 8px">€ {abs(t["gt"]):,.2f}</div>
  <div style="width:62pt;text-align:right;font-size:9pt;font-weight:700;color:#0A616B;padding:0 8px">€ {abs(t["gc"]):,.2f}</div>
  <div style="width:54pt;text-align:center;font-size:7.5pt;color:#6B7280;font-weight:600;padding:0 8px">TOTAL</div>
</div>
<table class="main"><tr>
  <td style="width:52%;vertical-align:top;padding-right:16pt">
    <div style="font-size:7pt;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:1pt;margin-bottom:5pt">Resumo Financeiro</div>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#fff;border-bottom:0.5pt solid #E5E7EB"><td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Total faturado</div><div style="font-size:7pt;color:#9CA3AF">{t["n"]} reservas · {t["n_can"]} canceladas</div></td><td style="text-align:right;font-size:9pt;color:#6B7280;padding:10px 8px">€ {abs(t["gt"]):,.2f}</td></tr>
      <tr style="background:#F3F4F6;border-bottom:0.5pt solid #E5E7EB"><td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Comissões a pagar</div><div style="font-size:7pt;color:#9CA3AF">{t["n_norm"]} reservas — cliente pagou ao parceiro</div></td><td style="text-align:right;font-size:9pt;font-weight:700;color:#0A616B;padding:10px 8px">€ {abs(t["comiss"]):,.2f}</td></tr>
      <tr style="background:#fff"><td style="padding:10px 8px"><div style="font-weight:700;font-size:9pt">Crédito a descontar</div><div style="font-size:7pt;color:#9CA3AF">{t["n_dev"]} reservas — cliente pagou à Beyond</div></td><td style="text-align:right;font-size:9pt;color:#6B7280;padding:10px 8px">− € {abs(t["credito"]):,.2f}</td></tr>
    </table>
    <div style="background:#0A616B;border-radius:6pt;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;margin-top:8pt">
      <span style="font-size:10pt;font-weight:700;color:white">TOTAL A RECEBER</span>
      <span style="font-size:16pt;font-weight:700;color:white">€ {abs(t["total_fim"]):,.2f}</span>
    </div>
  </td>
  <td style="width:48%;vertical-align:top">
    <div style="background:#0A616B;border-radius:10pt;padding:16px 18px;color:white">
      <div style="font-size:7pt;font-weight:700;color:#A7F3D0;margin-bottom:12pt">DADOS PARA PAGAMENTO</div>
      <div style="margin-bottom:10pt"><div style="font-size:7pt;font-weight:700;color:#A7F3D0">Banco</div><div style="font-size:9pt">Santander</div></div>
      <div style="margin-bottom:10pt"><div style="font-size:7pt;font-weight:700;color:#A7F3D0">IBAN</div><div style="font-size:8.5pt;font-weight:700">PT50 0018 0003 6587 1568 0201 8</div></div>
      <div style="margin-bottom:10pt"><div style="font-size:7pt;font-weight:700;color:#A7F3D0">Titular</div><div style="font-size:9pt">Milton Quintal Lda</div></div>
      <div><div style="font-size:7pt;font-weight:700;color:#A7F3D0">Referência</div><div style="font-size:9pt">{ref}</div></div>
    </div>
  </td>
</tr></table>
<hr style="border:none;border-top:0.5pt solid #E5E7EB;margin-top:20pt">
<div style="font-size:7.5pt;color:#6B7280;font-style:italic;margin-top:6pt">Em caso de dúvida ou discrepância, contacte-nos antes de efetuar qualquer transferência. Obrigado pela parceria.</div>
<div class="footer"><span>Beyond Madeira · RNAVT 13020 · NIPC 518 827 119 · +351 939 566 415</span><span>Ref. {ref}</span></div>
</body></html>"""

@app.route("/gerar-extrato-parceiro", methods=["POST"])
def gerar_extrato_parceiro():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from datetime import datetime
        d = request.get_json() or {}
        parceiro  = d.get("parceiro", "").strip()
        mes_str   = d.get("mes", "").strip()
        tipo      = d.get("tipo", "").strip()
        record_id = d.get("record_id", "").strip()
        do_upload = d.get("upload", True)
        data_only = d.get("data_only", False)  # se True, devolve dados sem gerar PDF
        if not parceiro or not mes_str:
            return jsonify({"error": "parceiro e mes obrigatórios"}), 400
        meses_list = d.get("meses", [])
        if not meses_list:
            meses_list = [mes_str]
        parsed_months = []
        for m_str in meses_list:
            parts = m_str.strip().split(" ")
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            m_nome = parts[0]
            m_ano  = int(parts[1])
            m_num  = MESES_IDX.get(m_nome)
            if m_num:
                parsed_months.append((m_nome, m_ano, m_num))
        if not parsed_months:
            return jsonify({"error": f"Nenhum mês válido em: {meses_list}"}), 400
        mes_nome, ano, mes_num = parsed_months[0]
        is_rc = tipo.lower() in ("rent car", "rc", "rentcar")
        rows = []
        for m_nome_i, m_ano_i, m_num_i in parsed_months:
            rows += get_reservas_parceiro(parceiro, m_num_i, m_ano_i, is_rc)
        tots = calc_totais(rows)
        sl    = re.sub(r"[^a-zA-Z0-9]", "", parceiro)
        if len(parsed_months) > 1:
            ref   = f"EXT-{ano}-{sl[:10].upper()}-ACUMULADO"
            fname = f"BeyondMadeira_{sl}_Acumulado{ano}.pdf"
        else:
            ref   = f"EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}"
            fname = f"BeyondMadeira_{sl}_{mes_nome}{ano}.pdf"
        html_str  = build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots)
        # data_only: devolve dados + reservas sem gerar PDF (frontend faz render)
        if data_only:
            reservas_out = []
            for r in rows:
                reservas_out.append({
                    "ref":    r.get("ref",""),
                    "nome":   r.get("nome",""),
                    "ddt":    r.get("ddt",""),
                    "total":  r.get("total",0),
                    "com":    r.get("com",0),
                    "estado": r.get("estado",""),
                    "dur":    r.get("dur",""),
                })
            return jsonify({"success": True, "reservas": reservas_out, "total": round(tots["comiss"],2), "total_fim": round(tots["total_fim"],2), "n_reservas": tots["n"], "parceiro": parceiro, "mes": mes_str})
        pdf_bytes = HTML(string=html_str).write_pdf()
        b64       = base64.b64encode(pdf_bytes).decode()
        uploaded = False
        if do_upload and record_id and record_id.startswith("rec"):
            try:
                airtable_patch(BASE_EXTRATO, TAB_EXTRATO, record_id, {"Extrato Beyond": []})
                airtable_upload_attachment(BASE_EXTRATO, record_id, "Extrato Beyond", pdf_bytes, fname)
                airtable_patch(BASE_EXTRATO, TAB_EXTRATO, record_id, {"Valor do mês (€)": round(tots["comiss"], 2), "Confirmado pela Beyond Madeira?": True})
                cache_clear("extrato")
                uploaded = True
            except Exception as ue:
                uploaded = False
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64, "ref": ref, "parceiro": parceiro, "mes": mes_str, "is_rc": is_rc, "n_reservas": tots["n"], "n_canceladas": tots["n_can"], "comissoes": round(tots["comiss"], 2), "credito": round(tots["credito"], 2), "total_fim": round(tots["total_fim"], 2), "uploaded": uploaded})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/gerar-extratos-mes", methods=["POST"])
def gerar_extratos_mes():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json() or {}
        mes_str = d.get("mes", "").strip()
        if not mes_str:
            return jsonify({"error": "mes obrigatório"}), 400
        formula = f'{{Mês}} = "{mes_str}"'
        registos = airtable_list_table(BASE_EXTRATO, TAB_EXTRATO, formula=formula)
        if not registos:
            return jsonify({"success": True, "results": [], "message": f"Nenhum parceiro em {mes_str}"})
        results = []
        for reg in registos:
            f   = reg.get("fields", {})
            par = get_text_f(f.get("Parceiro", ""))
            tip = get_text_f(f.get("Tipo", ""))
            if not par: continue
            try:
                mes_parts = mes_str.split(" ")
                mes_num   = MESES_IDX.get(mes_parts[0])
                ano       = int(mes_parts[1])
                is_rc     = tip.lower() in ("rent car",)
                rows      = get_reservas_parceiro(par, mes_num, ano, is_rc)
                tots      = calc_totais(rows)
                sl        = re.sub(r"[^a-zA-Z0-9]", "", par)
                ref       = f"EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}"
                fname     = f"BeyondMadeira_{sl}_{mes_parts[0]}{ano}.pdf"
                html_str  = build_extrato_html(par, rows, ref, mes_parts[0], ano, tots)
                pdf_bytes = HTML(string=html_str).write_pdf()
                uploaded  = False
                if reg["id"].startswith("rec") and tots["comiss"] > 0:
                    try:
                        airtable_patch(BASE_EXTRATO, TAB_EXTRATO, reg["id"], {"Extrato Beyond": []})
                        airtable_upload_attachment(BASE_EXTRATO, reg["id"], "Extrato Beyond", pdf_bytes, fname)
                        airtable_patch(BASE_EXTRATO, TAB_EXTRATO, reg["id"], {"Valor do mês (€)": round(tots["comiss"], 2), "Confirmado pela Beyond Madeira?": True})
                        uploaded = True
                    except: pass
                results.append({"parceiro": par, "success": True, "tipo": tip, "total_fim": round(tots["total_fim"], 2), "comissoes": round(tots["comiss"], 2), "n_reservas": tots["n"] - tots["n_can"], "uploaded": uploaded})
            except Exception as e:
                results.append({"parceiro": par, "success": False, "error": str(e)})
        total_geral = sum(r.get("comissoes", 0) for r in results if r.get("success"))
        return jsonify({"success": True, "mes": mes_str, "n_parceiros": len(results), "total_geral": round(total_geral, 2), "results": results})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/airtable/extrato-parceiros/<record_id>", methods=["PATCH"])
def patch_extrato_parceiro(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_EXTRATO, TAB_EXTRATO, record_id, fields)
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/extrato-parceiros", methods=["GET"])
def get_extrato_parceiros():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        mes  = request.args.get("mes", "")
        ano  = request.args.get("ano", "")
        if mes:
            formula = f'{{Mês}} = "{mes}"'
        elif ano:
            # Carregar todos os meses do ano — ex: "2026" → filtra por ano no campo Mês
            meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
            or_parts = [f'{{Mês}} = "{m} {ano}"' for m in meses_pt]
            formula = "OR(" + ",".join(or_parts) + ")"
        else:
            formula = None
        records = airtable_list_table(BASE_EXTRATO, TAB_EXTRATO, formula=formula)
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({"id": rec["id"], "parceiro": get_text_f(f.get("Parceiro", "")), "mes": f.get("Mês", ""), "tipo": get_text_f(f.get("Tipo", "")), "valor": eur_val(f.get("Valor do mês (€)", 0)), "ajustes": eur_val(f.get("Ajustes / Atrasos (€)", 0)), "total": eur_val(f.get("Total a Receber (€)", 0)), "confirmadoParceiro": f.get("Confirmado pelo parceiro?") == "checked", "mailEnviado": f.get("Mail enviado / pedido?") == "checked", "recebido": f.get("Recebido?") == "checked", "confirmadoBeyond": bool(f.get("Confirmado pela Beyond Madeira?", False)), "dataRecebimento": f.get("Data de Recebimento", ""), "obs": f.get("Observações - Faltou Reservas no papel? E na capa?", ""), "categoria": get_text_f(f.get("Categoria Parceiro", "")), "comissaoCalc": eur_val(f.get("Comissão Calculada (€)", 0))})
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            return jsonify({"error": "ANTHROPIC_API_KEY nao configurada no Railway"}), 500
        body = request.get_json() or {}
        r = req_lib.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body, timeout=60)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================================================================
# GMAIL OAuth2 HELPER
# Usa: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_TOKEN (refresh_token JSON)
# =========================================================================
def gmail_send_oauth2(to, subject, body_text, pdf_b64=None, pdf_filename=None, html_body=None):
    """Envia email via Gmail API com OAuth2. Retorna (success, error_msg)."""
    import json as _json
    client_id     = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    token_raw     = os.environ.get("GMAIL_TOKEN", "")
    if not client_id or not client_secret or not token_raw:
        return False, "GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_TOKEN não configurados no Railway"

    # Parse token — pode ser JSON com refresh_token ou só o refresh_token string
    try:
        token_data = _json.loads(token_raw)
        refresh_token = token_data.get("refresh_token", token_raw)
    except Exception:
        refresh_token = token_raw.strip()

    # Obter access_token via refresh
    r = req_lib.post("https://oauth2.googleapis.com/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=15)
    if not r.ok:
        return False, f"Erro ao obter access_token: {r.text[:200]}"
    access_token = r.json().get("access_token", "")
    if not access_token:
        return False, "access_token vazio"

    # Construir email MIME
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    msg = MIMEMultipart()
    msg["From"]     = "Beyond Madeira <booking@beyondmadeira.com>"
    msg["To"]       = to
    msg["Subject"]  = subject
    msg["Reply-To"] = "booking@beyondmadeira.com"

    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg.attach(MIMEText(body_text or "", "plain", "utf-8"))

    if pdf_b64 and pdf_filename:
        pdf_bytes = base64.b64decode(pdf_b64)
        att = MIMEApplication(pdf_bytes, _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(att)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    # Enviar via Gmail API
    gr = req_lib.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"raw": raw},
        timeout=30,
    )
    if gr.ok:
        return True, ""
    return False, f"Gmail API erro {gr.status_code}: {gr.text[:200]}"


@app.route("/enviar-extrato-email", methods=["POST"])
def enviar_extrato_email():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json() or {}
        to           = d.get("to", "").strip()
        subject      = d.get("subject", "").strip()
        body_text    = d.get("body", "").strip()
        parceiro     = d.get("parceiro", "").strip()
        mes_str      = d.get("mes", "").strip()
        pdf_b64      = d.get("pdf_base64", "")
        pdf_filename = d.get("pdf_filename") or f"Extrato_{re.sub('[^a-zA-Z0-9]','_',parceiro)}_{mes_str}.pdf"
        record_id    = d.get("record_id", "")
        if not to:
            return jsonify({"error": "Email destinatario obrigatorio"}), 400

        ok, err = gmail_send_oauth2(
            to=to,
            subject=subject or f"Extrato de Comissões — {mes_str} | Beyond Madeira",
            body_text=body_text,
            pdf_b64=pdf_b64 or None,
            pdf_filename=pdf_filename if pdf_b64 else None,
        )
        if not ok:
            return jsonify({"error": err}), 500

        if record_id and record_id.startswith("rec"):
            try:
                airtable_patch(BASE_EXTRATO, TAB_EXTRATO, record_id, {"Mail enviado / pedido?": True})
            except:
                pass
        return jsonify({"success": True, "to": to, "parceiro": parceiro, "mes": mes_str})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/airtable/despesas-fixas/<record_id>", methods=["PATCH"])
def patch_despesa_fixa(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = {}
        if "pago" in body: fields["Pago?"] = bool(body["pago"])
        if "valor" in body: fields["Valor (€)"] = float(body["valor"])
        if "notas" in body: fields["Notas"] = str(body["notas"])
        if not fields:
            return jsonify({"error": "Nenhum campo para actualizar"}), 400
        result = airtable_patch(BASE_FINANCEIRO, "Despesas Fixas", record_id, fields)
        cache_clear("despesas")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/despesas-variaveis/<record_id>", methods=["PATCH"])
def patch_despesa_variavel(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = {}
        if "pago" in body: fields["Pago?"] = bool(body["pago"])
        if "valor" in body: fields["Valor (€)"] = float(body["valor"])
        if "notas" in body: fields["Notas"] = str(body["notas"])
        if not fields:
            return jsonify({"error": "Nenhum campo para actualizar"}), 400
        result = airtable_patch(BASE_FINANCEIRO, "Despesas Variáveis", record_id, fields)
        cache_clear("despesas")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/extrato-parceiros/criar-mes", methods=["POST"])
def criar_extrato_mes():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        mes_str = body.get("mes", "").strip()
        if not mes_str:
            return jsonify({"error": "mes obrigatório"}), 400
        parts = mes_str.split(" ")
        if len(parts) != 2 or not parts[1].isdigit():
            return jsonify({"error": f"Formato inválido: {mes_str}"}), 400
        mes_nome, ano = parts[0], int(parts[1])
        mes_num = MESES_IDX.get(mes_nome)
        if not mes_num:
            return jsonify({"error": f"Mês inválido: {mes_nome}"}), 400
        import calendar
        from datetime import date
        first_day = date(ano, mes_num, 1)
        last_day  = date(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
        parceiros_com_reservas = {}
        rc_records = airtable_list_table(BASE_RESERVAS, TAB_RC_ID)
        for rec in rc_records:
            rf = rec.get("fields", {})
            if rf.get("Estado de Reserva", "") == "Cancelado": continue
            date_raw = rf.get("Data do Drop Off") or rf.get("Data de Drop-off") or rf.get("Data") or ""
            dt = parse_date_ext(str(date_raw))
            if not dt: continue
            if not (first_day <= dt.date() <= last_day): continue
            parceiro = get_text_f(fget_f(rf, "Fornecedor/Parceiro") or "")
            if parceiro and parceiro not in parceiros_com_reservas:
                parceiros_com_reservas[parceiro] = "Rent Car"
        at_records = airtable_list_table(BASE_RESERVAS, TAB_AT_ID)
        for rec in at_records:
            rf = rec.get("fields", {})
            if rf.get("Estado da Reserva", "") == "Cancelado": continue
            date_raw = rf.get("Data da Atividade") or rf.get("Data") or ""
            dt = parse_date_ext(str(date_raw))
            if not dt: continue
            if not (first_day <= dt.date() <= last_day): continue
            parceiro = get_text_f(fget_f(rf, "Fornecedor/Parceiro") or "")
            if parceiro and parceiro not in parceiros_com_reservas:
                ativ = rf.get("Atividade", "").lower()
                if any(k in ativ for k in ["jeep","tour","island","safari","drive"]): tipo = "Island Tours"
                elif any(k in ativ for k in ["boat","dolphin","whale","sea","swim","diving","surf","coast"]): tipo = "Water Experiences"
                elif any(k in ativ for k in ["hike","levada","walk","trail","mountain","dam"]): tipo = "Hikes"
                elif any(k in ativ for k in ["buggy","quad","zip","adventure","canyon","via ferrata"]): tipo = "Adventure"
                else: tipo = "Atividades"
                parceiros_com_reservas[parceiro] = tipo
        existing = airtable_list_table(BASE_EXTRATO, TAB_EXTRATO)
        existing_map = {}
        for rec in existing:
            f = rec.get("fields", {})
            mes_rec = f.get("Mês", "") or f.get("Mes", "")
            parc = get_text_f(f.get("Parceiro", ""))
            if mes_rec == mes_str and parc:
                existing_map[parc] = rec
        created = []
        skipped = []
        for parceiro, tipo in parceiros_com_reservas.items():
            if parceiro in existing_map:
                skipped.append(parceiro)
                continue
            rec = airtable_create(BASE_EXTRATO, TAB_EXTRATO, {"Parceiro": parceiro, "Mês": mes_str, "Tipo": tipo})
            if rec: created.append(parceiro)
        cache_clear("extrato")
        return jsonify({"success": True, "mes": mes_str, "parceiros_com_reservas": len(parceiros_com_reservas), "created": len(created), "parceiros_criados": created, "ja_existiam": len(skipped)})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/enviar-voucher-email", methods=["POST"])
def enviar_voucher_email():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        d = request.get_json() or {}
        to           = d.get("to", "").strip()
        cliente      = d.get("cliente", "Guest")
        atividade    = d.get("atividade", "Activity")
        data_str     = d.get("data", "")
        pdf_b64      = d.get("pdf_base64", "")
        pdf_filename = d.get("pdf_filename") or "Voucher_BeyondMadeira.pdf"
        record_id    = d.get("record_id", "")
        if not to:
            return jsonify({"error": "Email do cliente obrigatorio"}), 400

        first_name     = cliente.split()[0] if cliente else "Guest"
        custom_body    = (d.get("email_body") or "").strip()
        custom_subject = (d.get("email_subject") or "").strip()
        subject = custom_subject if custom_subject else f"Your Booking Confirmation – {atividade} | Beyond Madeira"
        body = custom_body if custom_body else (
            f"Dear {first_name},\n\nThank you for booking with Beyond Madeira!\n\n"
            f"Please find attached your booking confirmation voucher for:\n\n"
            f"  Activity: {atividade}\n  Date: {data_str}\n\n"
            f"If you have any questions, don't hesitate to contact us:\n"
            f"  WhatsApp: +351 939 566 415\n  Email: booking@beyondmadeira.com\n\n"
            f"We look forward to seeing you!\n\nBest regards,\nBeyond Madeira Team\nRNAVT 13020 · beyondmadeira.com\n"
        )

        ok, err = gmail_send_oauth2(
            to=to,
            subject=subject,
            body_text=body,
            pdf_b64=pdf_b64 or None,
            pdf_filename=pdf_filename if pdf_b64 else None,
        )
        if not ok:
            return jsonify({"error": err}), 500

        if record_id and record_id.startswith("rec"):
            try:
                airtable_patch(BASE_RESERVAS, "Atividades", record_id, {"Email Enviado": True})
                cache_clear("at")
            except: pass
        return jsonify({"success": True, "to": to, "cliente": cliente})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/airtable/despesas-variaveis", methods=["POST"])
def create_despesa_variavel():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields.get("Fornecedor") and not fields.get("Descrição"):
            return jsonify({"error": "Fornecedor obrigatório"}), 400
        result = airtable_create(BASE_FINANCEIRO, "Despesas Variáveis", fields)
        cache_clear("despesas")
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas", methods=["GET"])
def get_notas():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_RESERVAS, "Notas")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({"id": rec["id"], "titulo": f.get("Título", f.get("Title", "")), "conteudo": f.get("Conteúdo", f.get("Content", "")), "responsavel": f.get("Responsável", ""), "data": f.get("Data", ""), "categoria": f.get("Categoria", "")})
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas", methods=["POST"])
def create_nota():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_create(BASE_RESERVAS, "Notas", fields)
        cache_clear("notas")
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas/<record_id>", methods=["PATCH"])
def patch_nota(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_RESERVAS, "Notas", record_id, fields)
        cache_clear("notas")
        return jsonify({"success": True, "record": {"id": result.get("id",""), "fields": result.get("fields",{})}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/notas/<record_id>", methods=["DELETE"])
def delete_nota(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        url = f"https://api.airtable.com/v0/{BASE_RESERVAS}/Notas/{record_id}"
        resp = req_lib.delete(url, headers=AT_HEADERS(), timeout=15)
        cache_clear("notas")
        return jsonify({"success": resp.ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/wa-templates", methods=["GET"])
def get_wa_templates():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        records = airtable_list(BASE_CONHECIMENTO, "Templates Mensagens")
        out = []
        for rec in records:
            f = rec.get("fields", {})
            out.append({
                "id":         rec["id"],
                "name":       f.get("Name", ""),
                "label":      f.get("Name", ""),
                "categoria":  f.get("Categoria", ""),
                "empresa":    f.get("Empresa", ""),
                "topico":     f.get("Tópico", ""),
                "contexto":   f.get("Contexto", ""),
                "msg_en":     f.get("Message 🇬🇧", ""),
                "msg_pt":     f.get("Mensagem 🇵🇹", ""),
                "msg_fr":     f.get("Mensagem 🇫🇷", ""),
                "subj_en":    f.get("Subject 🇬🇧", ""),
                "subj_pt":    f.get("Assunto Email 🇵🇹", f.get("Assunto 🇵🇹", "")),
                "subj_fr":    f.get("Assunto 🇫🇷", ""),
                "com_cancel": f.get("Com cancelamento", ""),
                "vezes":      f.get("Vezes Enviado", 0),
                # legacy compat
                "text_pt":    f.get("Mensagem 🇵🇹", f.get("Message 🇬🇧", "")),
                "text_en":    f.get("Message 🇬🇧", ""),
                "subject_pt": f.get("Assunto Email 🇵🇹", f.get("Assunto 🇵🇹", "")),
                "subject_en": f.get("Subject 🇬🇧", ""),
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/airtable/wa-templates/<record_id>", methods=["PATCH"])
def patch_wa_template(record_id):
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        result = airtable_patch(BASE_CONHECIMENTO, "Templates Mensagens", record_id, fields)
        cache_clear("wa_templates")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/cache/clear", methods=["POST"])
def clear_cache_route():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    cache_clear()
    return jsonify({"success": True, "message": "Cache limpo"})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Beyond Madeira Voucher API", "endpoints": ["/gerar-voucher", "/gerar-voucher-atividade", "GET /airtable/rc", "POST /airtable/rc", "PATCH /airtable/rc/<id>", "GET /airtable/at", "POST /airtable/at", "PATCH /airtable/at/<id>", "/airtable/sitemap", "/airtable/biblioteca", "/airtable/guia", "/airtable/reviews", "/airtable/disponibilidade", "/airtable/frota", "/airtable/tarefas", "/airtable/diario", "/airtable/resumos-mensais", "/airtable/despesas-fixas", "/airtable/despesas-variaveis", "/airtable/objetivos", "/airtable/caixa-mensal", "/wazzup/chats", "/wazzup/messages", "/wazzup/message", "/wazzup/mark-as-read", "/wazzup/status"]})

# ═══════════════════════════════════════════════
# WAZZUP PROXY
# ═══════════════════════════════════════════════

WAZZUP_BASE    = "https://api.wazzup24.com/v3"
WAZZUP_API_KEY = os.environ.get("WAZZUP_API_KEY", "")
WAZZUP_CHANNEL = os.environ.get("WAZZUP_CHANNEL", "")

def wazzup_req(method, path, body=None):
    headers = {"Authorization": "Bearer " + WAZZUP_API_KEY, "Content-Type": "application/json"}
    url = WAZZUP_BASE + path
    r = req_lib.get(url, headers=headers) if method == "GET" else req_lib.post(url, headers=headers, json=body)
    try:
        d = r.json()
    except:
        d = {}
    return r.status_code, d

@app.route("/wazzup/chats")
def wz_chats():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    # Wazzup v3 uses /contacts to get contact list
    s, d = wazzup_req("GET", "/contacts")
    return jsonify(d), s

@app.route("/wazzup/messages")
def wz_messages():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    chat_id   = request.args.get("chatId", "")
    chat_type = request.args.get("chatType", "whatsapp")
    limit     = request.args.get("limit", 20)
    s, d = wazzup_req("GET", f"/messages?chatId={chat_id}&chatType={chat_type}&limit={limit}")
    return jsonify(d), s

@app.route("/wazzup/message", methods=["POST"])
def wz_send():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    b = request.get_json()
    s, d = wazzup_req("POST", "/message", {"channelId": WAZZUP_CHANNEL, "chatType": "whatsapp", "chatId": b["chatId"], "type": "text", "text": b["text"]})
    return jsonify({"success": s in (200, 201), "data": d})

@app.route("/wazzup/mark-as-read", methods=["POST"])
def wz_read():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    b = request.get_json()
    wazzup_req("POST", "/mark-as-read", {"chatId": b["chatId"], "channelId": WAZZUP_CHANNEL})
    return jsonify({"success": True})

@app.route("/wazzup/iframe", methods=["POST"])
def wz_iframe():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    try:
        b = request.get_json() or {}
        user_id   = b.get("userId", "milton")
        user_name = b.get("userName", "Milton")
        # Step 1: Register/update user in Wazzup
        wazzup_req("POST", "/users", [{"id": user_id, "name": user_name}])
        # Step 2: Get iframe URL with events enabled
        payload = {
            "user": {"id": user_id, "name": user_name},
            "scope": "global",
            "options": {
                "useDealsEvents": True,
                "useMessageEvents": True
            }
        }
        s, d = wazzup_req("POST", "/iframe", payload)
        return jsonify(d), s
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/wazzup/status")
def wz_status():
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    s, d = wazzup_req("GET", "/channels")
    return jsonify({"connected": s == 200, "data": d})


# ─────────────────────────────────────────────────────────────
# GMAIL OAUTH2 ENDPOINTS
# Requires Railway vars: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET
# GMAIL_REDIRECT_URI = https://beyond-madeira-voucher-api-production.up.railway.app/gmail/callback
# ─────────────────────────────────────────────────────────────

GMAIL_CLIENT_ID     = os.environ.get("GMAIL_CLIENT_ID", "184849359060-4tnm984gpiglun1pj0tc9vkqvpbumm4d.apps.googleusercontent.com")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "G0CSPX-YtETXvl01m3w99v90W55jMjCDy1p")
GMAIL_REDIRECT_URI  = os.environ.get("GMAIL_REDIRECT_URI", "https://beyond-madeira-voucher-api-production.up.railway.app/gmail/callback")
GMAIL_SCOPES        = "https://www.googleapis.com/auth/gmail.modify"

def gmail_token_store():
    """Use Railway env var GMAIL_TOKEN to persist tokens."""
    return os.environ.get("GMAIL_TOKEN", "")

_GMAIL_TOKEN_FILE = '/tmp/gmail_token.json'
_gmail_token_cache = {}

def gmail_save_token(token_json):
    """Save token to file and memory cache."""
    global _gmail_token_cache
    try:
        _gmail_token_cache = json.loads(token_json) if isinstance(token_json, str) else token_json
        with open(_GMAIL_TOKEN_FILE, 'w') as f:
            json.dump(_gmail_token_cache, f)
    except Exception as e:
        print("Error saving token:", e)
    print("GMAIL_TOKEN=", token_json)

def gmail_get_tokens():
    global _gmail_token_cache
    # 1. In-memory cache
    if _gmail_token_cache:
        return _gmail_token_cache
    # 2. File on disk
    try:
        with open(_GMAIL_TOKEN_FILE, 'r') as f:
            _gmail_token_cache = json.load(f)
            return _gmail_token_cache
    except:
        pass
    # 3. Railway env var (manually set)
    raw = os.environ.get("GMAIL_TOKEN", "")
    if raw:
        try:
            _gmail_token_cache = json.loads(raw)
            return _gmail_token_cache
        except:
            pass
    return None

def gmail_refresh(tokens):
    """Refresh access token using refresh token."""
    data = urllib.parse.urlencode({
        "client_id": GMAIL_CLIENT_ID,
        "client_secret": GMAIL_CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
        "grant_type": "refresh_token"
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as r:
        new = json.loads(r.read())
    tokens["access_token"] = new["access_token"]
    gmail_save_token(json.dumps(tokens))
    return tokens

def gmail_request(method, path, tokens, body=None):
    """Make authenticated Gmail API request."""
    url = f"https://gmail.googleapis.com/gmail/v1/users/me{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tokens['access_token']}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Try refresh
            tokens = gmail_refresh(tokens)
            req2 = urllib.request.Request(url, data=data, method=method)
            req2.add_header("Authorization", f"Bearer {tokens['access_token']}")
            req2.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req2) as r:
                return json.loads(r.read())
        raise

@app.route("/gmail/auth")
def gmail_auth():
    """Step 1: Show page with OAuth link."""
    try:
        params = urllib.parse.urlencode({
            "client_id": GMAIL_CLIENT_ID,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "response_type": "code",
            "scope": GMAIL_SCOPES,
            "access_type": "offline",
            "prompt": "consent"
        })
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + params
        return """<!DOCTYPE html><html><body style="font-family:sans-serif;padding:40px;max-width:500px;margin:auto">
        <h2 style="color:#0a8f82">Beyond Madeira — Ligar Gmail</h2>
        <p>Clica para autorizar o acesso ao Gmail:</p>
        <a href="""" + url + """" style="display:inline-block;padding:14px 28px;background:#0a8f82;color:white;border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold">
            Autorizar com Google
        </a>
        </body></html>"""
    except Exception as e:
        return "Erro: " + str(e), 500

@app.route("/gmail/callback")
def gmail_callback():
    """Step 2: Exchange code for tokens."""
    code = request.args.get("code")
    if not code:
        return "Erro: sem código de autorização", 400
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": GMAIL_CLIENT_ID,
        "client_secret": GMAIL_CLIENT_SECRET,
        "redirect_uri": GMAIL_REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as r:
            tokens = json.loads(r.read())
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        return f"""<html><body style="font-family:sans-serif;padding:40px">
        <h2 style="color:red">Erro {he.code} do Google</h2>
        <p>O código OAuth expirou ou já foi usado. Vai a <a href="/gmail/auth">/gmail/auth</a> e tenta de novo imediatamente.</p>
        <pre style="background:#f5f5f5;padding:12px;border-radius:8px;font-size:12px">{err_body}</pre>
        </body></html>""", 400
    token_json = json.dumps(tokens)
    gmail_save_token(token_json)
    return f"""<html><body style="font-family:sans-serif;padding:40px;max-width:600px;margin:auto">
    <h2 style="color:#0a8f82">✅ Gmail ligado com sucesso!</h2>
    <p>O token foi guardado automaticamente. Podes fechar esta janela e usar o Gmail no CRM.</p>
    <details><summary style="cursor:pointer;color:#666;font-size:12px">Ver token (para backup)</summary>
    <textarea rows="4" style="width:100%;font-size:11px;margin-top:8px">{token_json}</textarea></details>
    </body></html>"""

@app.route("/gmail/inbox")
def gmail_inbox():
    """Get inbox messages."""
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    tokens = gmail_get_tokens()
    if not tokens:
        return jsonify({"error": "Gmail não autenticado. Vai a /gmail/auth"}), 401
    try:
        tab   = request.args.get("tab", "INBOX")   # INBOX, SENT, UNREAD
        limit = int(request.args.get("limit", 20))
        q     = request.args.get("q", "")
        
        # Build query
        query = q if q else ""
        if tab == "UNREAD": query = "is:unread " + query
        elif tab == "SENT":  query = "in:sent " + query
        else:                query = "in:inbox " + query
        
        # List messages
        params = urllib.parse.urlencode({"q": query.strip(), "maxResults": limit})
        list_data = gmail_request("GET", f"/messages?{params}", tokens)
        messages = list_data.get("messages", [])
        
        # Fetch each message (snippet + headers)
        result = []
        for m in messages[:limit]:
            msg = gmail_request("GET", f"/messages/{m['id']}?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Date", tokens)
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            labels  = msg.get("labelIds", [])
            result.append({
                "id":       msg["id"],
                "threadId": msg["threadId"],
                "subject":  headers.get("Subject", "(sem assunto)"),
                "from":     headers.get("From", ""),
                "to":       headers.get("To", ""),
                "date":     headers.get("Date", ""),
                "snippet":  msg.get("snippet", ""),
                "unread":   "UNREAD" in labels,
                "starred":  "STARRED" in labels,
            })
        
        return jsonify({"messages": result, "total": list_data.get("resultSizeEstimate", 0)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/gmail/thread/<thread_id>")
def gmail_thread(thread_id):
    """Get full thread with all messages."""
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    tokens = gmail_get_tokens()
    if not tokens:
        return jsonify({"error": "Gmail não autenticado"}), 401
    try:
        thread = gmail_request("GET", f"/threads/{thread_id}?format=full", tokens)
        messages = []
        for msg in thread.get("messages", []):
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            body = _extract_gmail_body(msg.get("payload", {}))
            messages.append({
                "id":      msg["id"],
                "from":    headers.get("From", ""),
                "to":      headers.get("To", ""),
                "date":    headers.get("Date", ""),
                "subject": headers.get("Subject", ""),
                "body":    body,
                "unread":  "UNREAD" in msg.get("labelIds", []),
            })
        return jsonify({"threadId": thread_id, "messages": messages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _extract_gmail_body(payload):
    """Extract text/html or text/plain body from Gmail payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    # Multipart — recurse
    for part in payload.get("parts", []):
        body = _extract_gmail_body(part)
        if body:
            return body
    return ""

@app.route("/gmail/send", methods=["POST"])
def gmail_send_api():
    """Send email via Gmail API."""
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    tokens = gmail_get_tokens()
    if not tokens:
        return jsonify({"error": "Gmail não autenticado"}), 401
    try:
        b       = request.get_json()
        to      = b.get("to", "")
        subject = b.get("subject", "")
        body    = b.get("body", "")
        thread_id = b.get("threadId", "")   # for replies
        
        # Build RFC 2822 message
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart("alternative")
        msg["To"]      = to
        msg["Subject"] = subject
        if thread_id:
            msg["In-Reply-To"] = thread_id
        msg.attach(MIMEText(body, "html"))
        
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        
        result = gmail_request("POST", "/messages/send", tokens, payload)
        return jsonify({"success": True, "id": result.get("id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/gmail/star", methods=["POST"])
def gmail_star():
    """Star/unstar or mark read/unread."""
    if not check_key(): return jsonify({"error": "Unauthorized"}), 401
    tokens = gmail_get_tokens()
    if not tokens:
        return jsonify({"error": "Gmail não autenticado"}), 401
    try:
        b      = request.get_json()
        msg_id = b.get("id")
        action = b.get("action")  # star, unstar, read, unread
        add_labels    = []
        remove_labels = []
        if action == "star":   add_labels    = ["STARRED"]
        if action == "unstar": remove_labels = ["STARRED"]
        if action == "read":   remove_labels = ["UNREAD"]
        if action == "unread": add_labels    = ["UNREAD"]
        gmail_request("POST", f"/messages/{msg_id}/modify", tokens, {
            "addLabelIds": add_labels, "removeLabelIds": remove_labels
        })
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
