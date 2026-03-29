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
RC_TEMPLATE = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@page { size: A4; margin: 1.6cm 1.8cm 1.5cm 1.8cm; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Helvetica, Arial, sans-serif; color:#111827; font-size:9pt; }
.header { background:#0A616B; color:white; padding:18px 22px 16px; margin:-1.6cm -1.8cm 0; }
.header-inner { display:table; width:100%; }
.header-l { display:table-cell; vertical-align:middle; }
.header-r { display:table-cell; vertical-align:middle; text-align:right; }
.brand { font-size:8pt; font-weight:700; color:rgba(255,255,255,0.7); text-transform:uppercase; letter-spacing:1pt; }
.voucher-type { font-size:18pt; font-weight:800; color:white; line-height:1.1; margin-top:2pt; }
.ref-tag { display:inline-block; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3); border-radius:4pt; padding:3px 8px; font-size:7.5pt; font-weight:700; color:white; margin-top:6pt; }
.logo-img { height:36pt; }
.section { margin-top:14pt; }
.section-title { font-size:6.5pt; font-weight:800; color:#6B7280; text-transform:uppercase; letter-spacing:1pt; margin-bottom:6pt; border-bottom:0.5pt solid #E5E7EB; padding-bottom:4pt; }
.grid2 { display:table; width:100%; border-collapse:collapse; }
.col { display:table-cell; width:50%; vertical-align:top; padding-right:12pt; }
.col:last-child { padding-right:0; }
.info-card { background:#F9FAFB; border:0.5pt solid #E5E7EB; border-radius:6pt; padding:10px 12px; }
.info-lbl { font-size:6.5pt; font-weight:700; color:#6B7280; text-transform:uppercase; letter-spacing:.5pt; margin-bottom:3pt; }
.info-val { font-size:9.5pt; font-weight:700; color:#111827; }
.info-sub { font-size:8pt; color:#6B7280; margin-top:2pt; }
.date-sub { font-size:7.5pt; color:#6B7280; margin-top:1pt; }
.client-block { background:#F0FAF9; border:1pt solid #A7F3D0; border-radius:6pt; padding:10px 14px; margin-top:14pt; }
.client-table { display:table; width:100%; }
.client-col { display:table-cell; vertical-align:top; width:50%; }
.client-name { font-size:13pt; font-weight:800; color:#0A616B; }
.client-lbl { font-size:6.5pt; color:#6B7280; font-weight:700; text-transform:uppercase; letter-spacing:.5pt; margin-bottom:2pt; }
.client-contact { font-size:8pt; color:#374151; margin-top:2pt; }
.vehicle-block { background:#111827; border-radius:6pt; padding:12px 16px; margin-top:14pt; }
.vehicle-name { font-size:14pt; font-weight:800; color:white; }
.vehicle-co { font-size:8pt; color:rgba(255,255,255,0.6); margin-top:2pt; }
.vehicle-extras { font-size:8pt; color:rgba(255,255,255,0.75); margin-top:6pt; }
.price-badge { display:inline-block; background:#0A616B; color:white; font-size:14pt; font-weight:800; padding:6px 14px; border-radius:5pt; margin-top:6pt; }
.itinerary { margin-top:14pt; }
.itin-table { display:table; width:100%; border-collapse:collapse; }
.itin-col { display:table-cell; width:50%; vertical-align:top; padding-right:12pt; }
.itin-col:last-child { padding-right:0; }
.itin-card { border:0.5pt solid #E5E7EB; border-radius:6pt; overflow:hidden; }
.itin-head { background:#0A616B; padding:7px 12px; }
.itin-head-lbl { font-size:6.5pt; font-weight:800; color:rgba(255,255,255,0.7); text-transform:uppercase; letter-spacing:.5pt; }
.itin-head-date { font-size:11pt; font-weight:800; color:white; margin-top:1pt; }
.itin-head-time { font-size:9pt; color:rgba(255,255,255,0.85); font-weight:600; }
.itin-body { padding:8px 12px; background:#F9FAFB; }
.itin-loc-lbl { font-size:6.5pt; color:#6B7280; font-weight:700; text-transform:uppercase; letter-spacing:.5pt; }
.itin-loc { font-size:9pt; font-weight:700; color:#111827; margin-top:2pt; }
.contacts-row { display:table; width:100%; border-collapse:separate; border-spacing:8pt 0; margin-top:14pt; }
.contact-card { display:table-cell; border:0.5pt solid #E5E7EB; border-radius:6pt; padding:8px 12px; }
.contact-lbl { font-size:6.5pt; color:#6B7280; font-weight:700; text-transform:uppercase; letter-spacing:.5pt; }
.contact-name { font-size:9pt; font-weight:700; color:#111827; margin-top:2pt; }
.contact-det { font-size:8pt; color:#6B7280; margin-top:2pt; }
.footer { position:fixed; bottom:-1.5cm; left:-1.8cm; right:-1.8cm; border-top:0.5pt solid #E5E7EB; padding:4pt 1.8cm; display:table; }
.footer-l { display:table-cell; font-size:6.5pt; color:#9CA3AF; }
.footer-r { display:table-cell; font-size:6.5pt; color:#9CA3AF; text-align:right; }
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div class="header-l">
      <div class="brand">Beyond Madeira</div>
      <div class="voucher-type">Car Rental<br>Voucher</div>
      <div class="ref-tag">Ref: {{referencia}}</div>
    </div>
    <div class="header-r">
      <img src="{{LOGO_SRC}}" class="logo-img" alt="Beyond Madeira">
    </div>
  </div>
</div>

<div class="client-block">
  <div class="client-table">
    <div class="client-col">
      <div class="client-lbl">Guest</div>
      <div class="client-name">{{cliente}}</div>
    </div>
    <div class="client-col">
      <div class="client-lbl">Contact</div>
      <div class="client-contact">{{telefone}}<br>{{email}}</div>
    </div>
  </div>
</div>

<div class="vehicle-block">
  <div style="display:table;width:100%">
    <div style="display:table-cell;vertical-align:middle">
      <div class="vehicle-name">{{veiculo}}</div>
      <div class="vehicle-co">{{empresa}}</div>
      <div class="vehicle-extras">{{extras}}</div>
    </div>
    <div style="display:table-cell;vertical-align:middle;text-align:right">
      <div class="price-badge">&euro;{{total}}</div>
    </div>
  </div>
</div>

<div class="itinerary">
  <div class="section-title">Rental Period</div>
  <div class="itin-table">
    <div class="itin-col">
      <div class="itin-card">
        <div class="itin-head">
          <div class="itin-head-lbl">Pick-Up</div>
          <div class="itin-head-date">{{pickup_data}}</div>
          <div class="itin-head-time">{{pickup_hora}}</div>
        </div>
        <div class="itin-body">
          <div class="itin-loc-lbl">Location</div>
          <div class="itin-loc">{{pickup_local}}</div>
          {{pickup_extra}}
        </div>
      </div>
    </div>
    <div class="itin-col">
      <div class="itin-card">
        <div class="itin-head">
          <div class="itin-head-lbl">Drop-Off</div>
          <div class="itin-head-date">{{dropoff_data}}</div>
          <div class="itin-head-time">{{dropoff_hora}}</div>
        </div>
        <div class="itin-body">
          <div class="itin-loc-lbl">Location</div>
          <div class="itin-loc">{{dropoff_local}}</div>
          {{dropoff_extra}}
        </div>
      </div>
    </div>
  </div>
</div>

{{contacts_row_html}}

<div style="margin-top:14pt;background:#FEF9C3;border:0.5pt solid #FDE047;border-radius:6pt;padding:8px 12px;">
  <div style="font-size:7pt;font-weight:800;color:#854D0E;text-transform:uppercase;letter-spacing:.5pt;margin-bottom:3pt;">Required Documents</div>
  <div style="font-size:8pt;color:#713F12;">Passport or ID card &middot; Driving licence &middot; Credit card (for deposit)</div>
</div>

<div class="footer">
  <span class="footer-l">Beyond Madeira &middot; RNAVT 13020 &middot; +351 939 566 415 &middot; booking@beyondmadeira.com</span>
  <span class="footer-r">Ref. {{referencia}}</span>
</div>
</body></html>'''

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
AT_TEMPLATE = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@page { size: A4; margin: 1.6cm 1.8cm 1.5cm 1.8cm; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Helvetica, Arial, sans-serif; color:#111827; font-size:9pt; }
.header { background:#1a3c6e; color:white; padding:18px 22px 16px; margin:-1.6cm -1.8cm 0; }
.header-inner { display:table; width:100%; }
.header-l { display:table-cell; vertical-align:middle; }
.header-r { display:table-cell; vertical-align:middle; text-align:right; }
.brand { font-size:8pt; font-weight:700; color:rgba(255,255,255,0.7); text-transform:uppercase; letter-spacing:1pt; }
.voucher-type { font-size:18pt; font-weight:800; color:white; line-height:1.1; margin-top:2pt; }
.ref-tag { display:inline-block; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3); border-radius:4pt; padding:3px 8px; font-size:7.5pt; font-weight:700; color:white; margin-top:6pt; }
.logo-img { height:36pt; }
.section-title { font-size:6.5pt; font-weight:800; color:#6B7280; text-transform:uppercase; letter-spacing:1pt; margin-bottom:6pt; border-bottom:0.5pt solid #E5E7EB; padding-bottom:4pt; margin-top:14pt; }
.status-bar { display:table; width:100%; background:#F9FAFB; border:0.5pt solid #E5E7EB; border-radius:6pt; padding:10px 14px; margin-top:14pt; border-collapse:collapse; }
.status-col { display:table-cell; vertical-align:middle; }
.status-badge { display:inline-block; background:#15803D; color:white; font-size:7pt; font-weight:800; padding:3px 10px; border-radius:20pt; text-transform:uppercase; letter-spacing:.5pt; }
.status-badge.awaiting { background:#B45309; }
.status-badge.paid { background:#15803D; }
.activity-block { background:#1a3c6e; border-radius:6pt; padding:14px 18px; margin-top:14pt; }
.activity-name { font-size:14pt; font-weight:800; color:white; }
.activity-op { font-size:8pt; color:rgba(255,255,255,0.65); margin-top:2pt; }
.activity-details { display:table; width:100%; margin-top:10pt; border-collapse:collapse; }
.activity-det-col { display:table-cell; vertical-align:top; padding-right:16pt; }
.activity-det-col:last-child { padding-right:0; }
.det-lbl { font-size:6.5pt; color:rgba(255,255,255,0.6); font-weight:700; text-transform:uppercase; letter-spacing:.5pt; }
.det-val { font-size:11pt; font-weight:800; color:white; margin-top:2pt; }
.det-val.accent { color:#60D0FF; }
.det-val.tbc { color:rgba(255,255,255,0.5); font-style:italic; }
.price-right { text-align:right; }
.price-val { font-size:18pt; font-weight:800; color:white; }
.price-note-txt { font-size:7pt; color:rgba(255,255,255,0.6); margin-top:2pt; }
.price-note-txt.cash { color:#86EFAC; }
.price-note-txt.awaiting { color:#FCD34D; }
.price-note-txt.paid { color:#86EFAC; }
.pay-alert { display:table; width:100%; border-radius:6pt; padding:10px 14px; margin-top:14pt; border-collapse:collapse; }
.pay-alert.awaiting { background:#FEF3C7; border:0.5pt solid #FCD34D; }
.pay-alert.paid { background:#DCFCE7; border:0.5pt solid #86EFAC; }
.pa-dot { display:table-cell; width:20pt; font-size:14pt; font-weight:900; vertical-align:middle; }
.pa-dot.awaiting { color:#B45309; }
.pa-dot.paid { color:#15803D; }
.pa-title { font-size:8.5pt; font-weight:800; }
.pa-title.awaiting { color:#92400E; }
.pa-title.paid { color:#14532D; }
.pa-body { font-size:8pt; margin-top:2pt; }
.pa-body.awaiting { color:#78350F; }
.pa-body.paid { color:#166534; }
.paymethod { display:table; width:100%; border:0.5pt solid #E5E7EB; border-radius:6pt; padding:10px 14px; margin-top:14pt; background:#F9FAFB; border-collapse:collapse; }
.pm-dot { display:table-cell; font-size:14pt; width:22pt; color:#1a3c6e; vertical-align:middle; font-weight:900; }
.pm-title { font-size:8.5pt; font-weight:800; color:#1a3c6e; }
.pm-body { font-size:8pt; color:#6B7280; margin-top:2pt; }
.pickup-card { display:table; width:100%; border:0.5pt solid #BFDBFE; background:#EFF6FF; border-radius:6pt; padding:10px 14px; margin-top:14pt; border-collapse:collapse; }
.pickup-dot { display:table-cell; width:16pt; font-size:10pt; color:#1D4ED8; vertical-align:top; padding-top:2pt; }
.pickup-lbl { font-size:6.5pt; font-weight:800; color:#1E40AF; text-transform:uppercase; letter-spacing:.5pt; }
.pickup-loc { font-size:9.5pt; font-weight:700; color:#1E3A8A; margin-top:2pt; }
.pickup-sub { font-size:8pt; color:#3B82F6; margin-top:1pt; }
.pickup-note { font-size:7.5pt; color:#60A5FA; margin-top:4pt; }
.inv-row { display:table; width:100%; border-bottom:0.5pt solid #F3F4F6; padding:7px 0; border-collapse:collapse; }
.inv-prod { display:table-cell; vertical-align:middle; }
.inv-name { font-size:9pt; font-weight:700; color:#111827; }
.inv-detail { font-size:7.5pt; color:#6B7280; margin-top:1pt; }
.inv-qty { display:table-cell; width:40pt; text-align:center; font-size:8.5pt; color:#6B7280; vertical-align:middle; }
.inv-unit { display:table-cell; width:55pt; text-align:right; font-size:8.5pt; color:#6B7280; vertical-align:middle; }
.inv-sub { display:table-cell; width:60pt; text-align:right; font-size:9pt; font-weight:700; color:#111827; vertical-align:middle; }
.inv-total { display:table; width:100%; border-collapse:collapse; padding:8px 0; }
.inv-total-lbl { display:table-cell; font-size:9pt; font-weight:800; color:#111827; }
.inv-total-val { display:table-cell; text-align:right; font-size:11pt; font-weight:800; color:#1a3c6e; }
.special-req { background:#F9FAFB; border:0.5pt solid #E5E7EB; border-radius:6pt; padding:8px 12px; margin-top:8pt; }
.sr-label { font-size:6.5pt; font-weight:800; color:#6B7280; text-transform:uppercase; letter-spacing:.5pt; margin-bottom:3pt; }
.sr-text { font-size:8pt; color:#374151; line-height:1.5; }
.msg-box { background:#F0F9FF; border:0.5pt solid #BAE6FD; border-radius:6pt; padding:8px 12px; margin-top:14pt; }
.cancel-box { background:#FFF7ED; border:0.5pt solid #FED7AA; border-radius:6pt; padding:8px 12px; margin-top:8pt; }
.box-lbl { font-size:6.5pt; font-weight:800; color:#6B7280; text-transform:uppercase; letter-spacing:.5pt; margin-bottom:3pt; }
.box-txt { font-size:8pt; color:#374151; line-height:1.5; }
.footer { position:fixed; bottom:-1.5cm; left:-1.8cm; right:-1.8cm; border-top:0.5pt solid #E5E7EB; padding:4pt 1.8cm; display:table; }
.footer-l { display:table-cell; font-size:6.5pt; color:#9CA3AF; }
.footer-r { display:table-cell; font-size:6.5pt; color:#9CA3AF; text-align:right; }
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div class="header-l">
      <div class="brand">Beyond Madeira</div>
      <div class="voucher-type">Activity<br>Voucher</div>
      <div class="ref-tag">Ref: {{referencia}}</div>
    </div>
    <div class="header-r">
      <img src="{{LOGO_SRC}}" class="logo-img" alt="Beyond Madeira">
    </div>
  </div>
</div>

<div class="status-bar">
  <div class="status-col">
    <span class="status-badge {{status_class}}">{{status_label}}</span>
  </div>
  <div class="status-col" style="text-align:right">
    <span style="font-size:8pt;color:#6B7280;">Guest: <strong>{{cliente}}</strong></span>
  </div>
</div>

<div class="activity-block">
  <div class="activity-name">{{atividade}}</div>
  <div class="activity-op">{{operador}}</div>
  <div class="activity-details">
    <div class="activity-det-col">
      <div class="det-lbl">Date</div>
      <div class="det-val">{{data}}</div>
    </div>
    <div class="activity-det-col">
      <div class="det-lbl">Time</div>
      <div class="det-val {{start_time_class}}">{{hora}}</div>
    </div>
    <div class="activity-det-col">
      <div class="det-lbl">Guests</div>
      <div class="det-val">{{pax}}</div>
    </div>
    <div class="activity-det-col price-right">
      <div class="det-lbl">Total</div>
      <div class="price-val">&euro;{{total}}</div>
      <div class="price-note-txt {{price_class}}">{{price_note}}</div>
    </div>
  </div>
</div>

{{payment_alert_html}}
{{payment_method_html}}
{{pickup_html}}

<div class="section-title">Booking Details</div>
{{invoice_rows_html}}
<div class="inv-total">
  <div class="inv-total-lbl">Total</div>
  <div class="inv-total-val">&euro;{{total}}</div>
</div>

{{special_requests_html}}

<div class="msg-box">
  <div class="box-lbl">Confirmation Message</div>
  <div class="box-txt">{{mensagem_confirmacao}}</div>
</div>

<div class="cancel-box">
  <div class="box-lbl">Cancellation Policy</div>
  <div class="box-txt">{{cancelamento}}</div>
</div>

<div class="footer">
  <span class="footer-l">Beyond Madeira &middot; RNAVT 13020 &middot; +351 939 566 415 &middot; booking@beyondmadeira.com</span>
  <span class="footer-r">Ref. {{referencia}}</span>
</div>
</body></html>'''

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
WAZZUP_API_KEY  = os.environ.get("WAZZUP_API_KEY", "9b4f7530810243d387df6c6837568b43")
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
