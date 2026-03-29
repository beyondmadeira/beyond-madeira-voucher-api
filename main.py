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
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --teal:#0a8f82;--teal-light:#edf7f6;--teal-mid:#c8e8e5;
  --amber:#b5720e;--amber-light:#fef6e8;--amber-border:#f0ce8a;
  --text:#171613;--text2:#635e58;--text3:#a8a39c;
  --border:#e6e2dc;--white:#fff;--bg:#f7f6f2;
}
body{font-family:'Montserrat',sans-serif;background:var(--white);color:var(--text);font-size:12px;-webkit-print-color-adjust:exact;print-color-adjust:exact;margin:0;padding:0;}
.page{padding:36px 44px;max-width:740px;margin:0 auto;}
.ref-band,.act-card,.guest-row,.extras-card,.cancel,.contacts-row,.thankyou,.legal-box{page-break-inside:avoid;break-inside:avoid;}
.hdr{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:22px;page-break-inside:avoid;break-inside:avoid;}
.logo-wrap img{height:54px;width:auto;}
.brand-legal{font-size:9px;color:var(--text3);margin-top:7px;}
.hdr-right{text-align:right;}
.doc-type{font-size:10px;font-weight:700;color:var(--text3);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px;}
.doc-title{font-size:30px;font-weight:900;color:var(--text);letter-spacing:-.8px;line-height:1;}
.hdr-rule{height:2px;background:var(--teal);border-radius:1px;margin-bottom:22px;}
.ref-band{background:var(--teal);border-radius:16px;padding:24px 30px;display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
.ref-label{font-size:9px;font-weight:700;color:rgba(255,255,255,.6);letter-spacing:1.2px;text-transform:uppercase;margin-bottom:7px;}
.ref-value{font-size:28px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1;}
.ref-issued{font-size:9px;color:rgba(255,255,255,.5);margin-top:5px;}
.ref-right{text-align:right;}
.ref-total-label{font-size:9px;font-weight:700;color:rgba(255,255,255,.6);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;}
.ref-total{font-size:28px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1;}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}
.info-card{background:var(--bg);border:1px solid var(--border);border-radius:16px;padding:20px 24px;}
.info-card.full{grid-column:1/-1;}
.cell-label{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px;}
.cell-value{font-size:14px;font-weight:800;color:var(--text);letter-spacing:-.2px;line-height:1.3;}
.cell-value.teal{color:var(--teal);}
.cell-value.sm{font-size:12px;}
.client-row{display:flex;gap:0;margin-bottom:20px;border:1px solid var(--border);border-radius:16px;overflow:hidden;page-break-inside:avoid;break-inside:avoid;}
.client-cell{flex:1;background:var(--white);padding:18px 22px;border-right:1px solid var(--border);}
.client-cell:last-child{border-right:none;}
.client-label{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px;}
.client-value{font-size:13px;font-weight:800;color:var(--text);}
.client-value.sm{font-size:11px;font-weight:500;color:var(--text2);}
.dates-row{display:flex;gap:0;margin-bottom:20px;border:1px solid var(--border);border-radius:16px;overflow:hidden;page-break-inside:avoid;break-inside:avoid;}
.date-cell{flex:1;background:var(--bg);padding:20px 24px;border-right:1px solid var(--border);}
.date-cell:last-child{border-right:none;}
.date-label{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px;}
.date-day{font-size:18px;font-weight:900;color:var(--text);letter-spacing:-.4px;margin-bottom:3px;}
.date-time{font-size:16px;font-weight:800;color:var(--teal);margin-bottom:3px;}
.date-loc{font-size:11px;color:var(--text2);font-weight:500;}
.extras-card{background:var(--amber-light);border:1px solid var(--amber-border);border-radius:16px;padding:16px 22px;display:flex;align-items:center;gap:14px;margin-bottom:16px;}
.extras-dot{width:32px;height:32px;min-width:32px;background:var(--amber);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;font-weight:900;color:#fff;}
.extras-label{font-size:9px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;}
.extras-value{font-size:12px;font-weight:600;color:#7a4d08;}
.cancel{background:var(--white);border:1px solid var(--border);border-radius:16px;padding:16px 22px;display:flex;align-items:flex-start;gap:13px;margin-bottom:16px;}
.cancel-dot{width:22px;height:22px;min-width:22px;border-radius:50%;border:2px solid var(--teal);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;font-size:11px;font-weight:900;color:var(--teal);}
.cancel-t{font-size:10px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}
.cancel-b{font-size:11px;color:var(--text2);line-height:1.65;}
.contacts-row{display:flex;gap:14px;margin-bottom:16px;}
.contact-card{flex:1;background:var(--white);border:1px solid var(--border);border-radius:16px;padding:16px 20px;}
.contact-lbl{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px;}
.contact-name{font-size:13px;font-weight:800;color:var(--text);margin-bottom:4px;}
.contact-det{font-size:11px;color:var(--text2);line-height:1.7;}
.thankyou{background:var(--teal);border-radius:16px;padding:22px 28px;margin-bottom:24px;}
.ty-title{font-size:14px;font-weight:900;color:#fff;margin-bottom:7px;letter-spacing:-.3px;}
.ty-text{font-size:11px;color:rgba(255,255,255,.87);line-height:1.75;}
.footer{border-top:1px solid var(--border);padding-top:14px;display:flex;justify-content:space-between;page-break-inside:avoid;break-inside:avoid;}
.ft-l,.ft-r{font-size:9px;color:var(--text3);line-height:1.8;}
.ft-r{text-align:right;}
.ft-teal{color:var(--teal);font-weight:600;}
.legal{font-size:8px;color:var(--text3);line-height:1.6;margin-top:11px;padding-top:11px;border-top:1px solid var(--border);}
</style>
</head>
<body>
<div class="page">
<div class="hdr">
  <div>
    <div class="logo-wrap"><img src="{{LOGO_SRC}}" alt="Beyond Madeira"/></div>
    <div class="brand-legal">RNAVT 13020 &middot; NIPC 518 827 119</div>
  </div>
  <div class="hdr-right">
    <div class="doc-type">Car Rental Voucher</div>
    <div class="doc-title">Rental<br>Confirmation</div>
  </div>
</div>
<div class="hdr-rule"></div>
<div class="ref-band">
  <div>
    <div class="ref-label">Booking Reference</div>
    <div class="ref-value">{{referencia}}</div>
    <div class="ref-issued">Issued by Beyond Madeira &middot; RNAVT 13020</div>
  </div>
  <div class="ref-right">
    <div class="ref-total-label">Total Amount</div>
    <div class="ref-total">{{total}}</div>
  </div>
</div>
<div class="info-grid">
  <div class="info-card">
    <div class="cell-label">Vehicle</div>
    <div class="cell-value">{{veiculo}} <span style="font-weight:500;font-size:11px;color:var(--text3);">or similar</span></div>
  </div>
  <div class="info-card">
    <div class="cell-label">Rental Company</div>
    <div class="cell-value teal">{{empresa}}</div>
  </div>
</div>
<div class="client-row">
  <div class="client-cell">
    <div class="client-label">Client</div>
    <div class="client-value">{{cliente}}</div>
  </div>
  <div class="client-cell">
    <div class="client-label">Phone</div>
    <div class="client-value sm">{{telefone}}</div>
  </div>
  <div class="client-cell" style="border-right:none;">
    <div class="client-label">Email</div>
    <div class="client-value sm">{{email}}</div>
  </div>
</div>
<div class="dates-row">
  <div class="date-cell">
    <div class="date-label">Pick-up</div>
    <div class="date-day">{{pickup_data}}</div>
    <div class="date-time">{{pickup_hora}}</div>
    <div class="date-loc">{{pickup_local}}</div>
    {{pickup_extra}}
  </div>
  <div class="date-cell">
    <div class="date-label">Drop-off</div>
    <div class="date-day">{{dropoff_data}}</div>
    <div class="date-time">{{dropoff_hora}}</div>
    <div class="date-loc">{{dropoff_local}}</div>
    {{dropoff_extra}}
  </div>
</div>
<div class="extras-card">
  <div class="extras-dot">+</div>
  <div>
    <div class="extras-label">Extras</div>
    <div class="extras-value">{{extras}}</div>
  </div>
</div>
<div class="cancel">
  <div class="cancel-dot">i</div>
  <div>
    <div class="cancel-t">Cancellation Policy</div>
    <div class="cancel-b">Free cancellation up to <strong>24 hours before</strong> pick-up. Late cancellations or no-shows may incur a fee.</div>
  </div>
</div>
<div style="page-break-inside:avoid;break-inside:avoid;">
{{contacts_row_html}}
<div class="thankyou">
  <div class="ty-title">Thank you for booking with Beyond Madeira!</div>
  <div class="ty-text">Your rental is confirmed. Please present this voucher at vehicle pick-up. All insurance terms and rental conditions are governed solely by the rental company&rsquo;s contract issued at pick-up.<br><br>Questions? <strong>WhatsApp +351 939 566 415</strong> &middot; <strong>booking@beyondmadeira.com</strong></div>
</div>
</div>
<div class="footer">
  <div class="ft-l">Beyond Madeira &middot; RNAVT 13020 &middot; NIPC 518 827 119<br>Head Office: Largo da Sa&uacute;de n1, 9000-221 Funchal, Madeira, Portugal</div>
  <div class="ft-r"><span class="ft-teal">beyondmadeira.com</span><br>+351 939 566 415 &middot; booking@beyondmadeira.com</div>
</div>
<div class="legal">Beyond Madeira (RNAVT 13020) acts exclusively as a booking intermediary pursuant to Decreto-Lei n.o 61/2011. Beyond Madeira is not a party to the rental agreement and assumes no liability for vehicle condition, insurance, accidents, or disputes. All rental terms are governed by the contract issued by the rental company at pick-up. Personal data processed under GDPR for booking fulfilment only.</div>
</div>
</body>
</html>'''

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
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --teal:#0a8f82;--teal-light:#edf7f6;--teal-mid:#c8e8e5;
  --amber:#b5720e;--amber-light:#fef6e8;--amber-border:#f0ce8a;
  --green:#186640;--green-light:#edf6f1;--green-border:#a7f3d0;
  --text:#171613;--text2:#635e58;--text3:#a8a39c;
  --border:#e6e2dc;--white:#fff;--bg:#f7f6f2;
}
body{font-family:'Montserrat',sans-serif;background:var(--white);color:var(--text);font-size:12px;-webkit-print-color-adjust:exact;print-color-adjust:exact;margin:0;padding:0;}
.page{padding:44px 48px;max-width:740px;margin:0 auto;}
.ref-band,.act-card,.guest-row,.pay-alert,.paymethod,.pickup-card,.special-req,.invoice,.inv-total-row,.cancel,.insurance,.contacts-row,.thankyou{page-break-inside:avoid;break-inside:avoid;}
.hdr{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px;page-break-inside:avoid;break-inside:avoid;}
.logo-wrap img{height:54px;width:auto;}
.brand-legal{font-size:9px;color:var(--text3);margin-top:7px;}
.hdr-right{text-align:right;}
.doc-type{font-size:10px;font-weight:700;color:var(--text3);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px;}
.doc-status{font-size:30px;font-weight:900;color:var(--text);letter-spacing:-.8px;line-height:1;}
.doc-status.awaiting{color:var(--amber);}
.doc-status.paid{color:var(--green);}
.hdr-rule{height:2px;background:var(--teal);border-radius:1px;margin-bottom:28px;}
.ref-band{background:var(--teal);border-radius:16px;padding:24px 30px;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;}
.ref-label{font-size:9px;font-weight:700;color:rgba(255,255,255,.6);letter-spacing:1.2px;text-transform:uppercase;margin-bottom:7px;}
.ref-value{font-size:28px;font-weight:900;color:#fff;letter-spacing:-.5px;line-height:1;}
.ref-bokun{font-size:10px;color:rgba(255,255,255,.5);margin-top:5px;}
.issued-by{font-size:9px;color:rgba(255,255,255,.5);margin-top:5px;}
.act-card{background:var(--bg);border:1px solid var(--border);border-radius:16px;padding:24px 28px;margin-bottom:20px;}
.act-name{font-size:21px;font-weight:900;color:var(--text);letter-spacing:-.5px;line-height:1.2;margin-bottom:4px;}
.act-date{font-size:14px;font-weight:700;color:var(--teal);margin-bottom:22px;}
.act-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;}
.cell-label{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;}
.cell-value{font-size:13px;font-weight:800;color:var(--text);line-height:1.3;}
.cell-value.accent{color:var(--teal);font-size:19px;}
.cell-value.tbc{color:var(--text3);font-size:13px;font-style:italic;}
.guest-row{display:flex;gap:0;margin-bottom:20px;border:1px solid var(--border);border-radius:16px;overflow:hidden;}
.guest-card{flex:1;background:var(--white);padding:20px 24px;border-right:1px solid var(--border);}
.price-card{padding:18px 22px;display:flex;flex-direction:column;align-items:center;justify-content:center;width:170px;flex-shrink:0;}
.price-card.cash{background:var(--teal);}
.price-card.awaiting{background:var(--amber);}
.price-card.paid{background:var(--green);}
.sect-lbl{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:5px;}
.sect-lbl.muted{color:var(--text3);}
.sect-lbl.inv{color:rgba(255,255,255,.65);}
.guest-name{font-size:16px;font-weight:900;color:var(--text);letter-spacing:-.3px;margin-bottom:4px;}
.guest-contacts{font-size:11px;color:var(--text2);line-height:1.7;}
.price-amount{font-size:32px;font-weight:900;color:#fff;letter-spacing:-.8px;line-height:1;text-align:center;}
.price-note{font-size:9px;color:rgba(255,255,255,.7);margin-top:6px;font-weight:600;text-align:center;}
.pay-alert{border-radius:14px;padding:16px 20px;display:flex;align-items:flex-start;gap:14px;margin-bottom:20px;}
.pay-alert.awaiting{background:var(--amber-light);border:1px solid var(--amber-border);}
.pay-alert.paid{background:var(--green-light);border:1px solid var(--green-border);}
.pa-dot{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:15px;font-weight:900;color:#fff;margin-top:1px;}
.pa-dot.awaiting{background:var(--amber);}
.pa-dot.paid{background:var(--green);}
.pa-title{font-size:12px;font-weight:800;margin-bottom:4px;}
.pa-title.awaiting{color:#7a4d08;}
.pa-title.paid{color:#0f4428;}
.pa-body{font-size:11px;line-height:1.65;}
.pa-body.awaiting{color:#7a4d08;}
.pa-body.paid{color:#0f4428;}
.paymethod{border-radius:14px;padding:14px 20px;display:flex;align-items:center;gap:14px;margin-bottom:20px;background:var(--teal-light);border:1px solid var(--teal-mid);}
.pm-dot{width:32px;height:32px;border-radius:50%;background:var(--teal);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:13px;font-weight:900;color:#fff;}
.pm-title{font-size:12px;font-weight:800;color:var(--teal);margin-bottom:3px;}
.pm-body{font-size:11px;color:var(--text2);line-height:1.5;}
.pickup-card{background:var(--amber-light);border:1px solid var(--amber-border);border-radius:16px;padding:18px 24px;display:flex;align-items:flex-start;gap:16px;margin-bottom:20px;}
.pickup-dot{width:36px;height:36px;min-width:36px;background:var(--amber);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:17px;color:#fff;font-weight:900;line-height:1;margin-top:1px;}
.pickup-lbl{font-size:9px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;}
.pickup-loc{font-size:15px;font-weight:800;color:var(--text);letter-spacing:-.2px;margin-bottom:3px;}
.pickup-sub{font-size:11px;font-weight:600;color:var(--text2);margin-bottom:3px;}
.pickup-note{font-size:10px;color:var(--text3);margin-top:2px;line-height:1.5;font-style:italic;}
.special-req{background:var(--white);border:1px solid var(--border);border-left:3px solid var(--teal);border-radius:0 14px 14px 0;padding:14px 20px;margin-bottom:20px;}
.sr-label{font-size:9px;font-weight:700;color:var(--teal);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px;}
.sr-text{font-size:11px;color:var(--text2);line-height:1.6;}
.invoice{border:1px solid var(--border);border-radius:16px;overflow:hidden;margin-bottom:6px;}
.inv-hdr{padding:11px 22px;background:var(--bg);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
.inv-hdr-t{font-size:10px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.8px;}
.inv-hdr-r{font-size:10px;color:var(--text3);}
.inv-row{padding:13px 22px;display:flex;align-items:center;gap:10px;background:var(--white);border-bottom:1px solid var(--border);}
.inv-row:last-child{border-bottom:none;}
.inv-prod{flex:1;}
.inv-name{font-size:12px;font-weight:700;color:var(--text);}
.inv-detail{font-size:10px;color:var(--text3);margin-top:2px;}
.inv-qty{font-size:11px;font-weight:600;color:var(--text2);width:30px;text-align:center;}
.inv-unit{font-size:11px;color:var(--text3);width:60px;text-align:right;}
.inv-sub{font-size:12px;font-weight:700;color:var(--text);width:60px;text-align:right;}
.inv-total-row{padding:13px 22px;display:flex;justify-content:space-between;align-items:center;background:var(--teal-light);border-top:2px solid var(--teal);border-radius:0 0 16px 16px;margin-bottom:20px;}
.inv-total-l{font-size:12px;font-weight:700;color:var(--text);}
.inv-total-r{font-size:21px;font-weight:900;color:var(--teal);}
.cancel{background:var(--white);border:1px solid var(--border);border-radius:16px;padding:16px 22px;display:flex;align-items:flex-start;gap:13px;margin-bottom:20px;}
.cancel-dot{width:22px;height:22px;min-width:22px;border-radius:50%;border:2px solid var(--teal);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;font-size:11px;font-weight:900;color:var(--teal);}
.cancel-t{font-size:10px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}
.cancel-b{font-size:11px;color:var(--text2);line-height:1.65;}
.insurance{background:var(--teal-light);border:1px solid var(--teal-mid);border-radius:16px;padding:16px 22px;display:flex;align-items:center;gap:13px;margin-bottom:20px;}
.ins-dot{width:32px;height:32px;min-width:32px;border-radius:50%;background:var(--teal);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;font-weight:900;color:#fff;}
.ins-title{font-size:12px;font-weight:800;color:var(--teal);margin-bottom:3px;}
.ins-body{font-size:11px;color:var(--text2);line-height:1.5;}
.contacts-row{display:flex;gap:14px;margin-bottom:20px;}
.contact-card{flex:1;background:var(--white);border:1px solid var(--border);border-radius:16px;padding:16px 20px;}
.contact-lbl{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px;}
.contact-name{font-size:13px;font-weight:800;color:var(--text);margin-bottom:4px;}
.contact-det{font-size:11px;color:var(--text2);line-height:1.7;}
.thankyou{background:var(--teal);border-radius:16px;padding:22px 28px;margin-bottom:24px;}
.ty-title{font-size:14px;font-weight:900;color:#fff;margin-bottom:7px;letter-spacing:-.3px;}
.ty-text{font-size:11px;color:rgba(255,255,255,.87);line-height:1.75;}
.footer{border-top:1px solid var(--border);padding-top:14px;display:flex;justify-content:space-between;page-break-inside:avoid;break-inside:avoid;}
.ft-l,.ft-r{font-size:9px;color:var(--text3);line-height:1.8;}
.ft-r{text-align:right;}
.ft-teal{color:var(--teal);font-weight:600;}
.legal{font-size:8px;color:var(--text3);line-height:1.6;margin-top:11px;padding-top:11px;border-top:1px solid var(--border);}
</style>
</head>
<body>
<div class="page">
<div class="hdr">
  <div>
    <div class="logo-wrap"><img src="{{LOGO_SRC}}" alt="Beyond Madeira"/></div>
    <div class="brand-legal">RNAVT 13020 &middot; NIPC 518 827 119</div>
  </div>
  <div class="hdr-right">
    <div class="doc-type">Voucher</div>
    <div class="doc-status {{status_class}}">{{status_label}}</div>
  </div>
</div>
<div class="hdr-rule"></div>
<div class="ref-band">
  <div>
    <div class="ref-label">Booking Reference</div>
    <div class="ref-value">{{referencia}}</div>
    <div class="ref-bokun">Bokun: {{bokun_ref}}</div>
  </div>
  <div style="text-align:right;">
    <div class="issued-by">Issued by Beyond Madeira</div>
  </div>
</div>
<div class="act-card">
  <div class="act-name">{{atividade}}</div>
  <div class="act-date">{{data}}</div>
  <div class="act-grid">
    <div><div class="cell-label">Start Time</div><div class="cell-value {{start_time_class}}">{{hora}}</div></div>
    <div><div class="cell-label">Participants</div><div class="cell-value">{{pax}}</div></div>
    <div><div class="cell-label">Tour Type</div><div class="cell-value">{{tipo_tour}}</div></div>
    <div><div class="cell-label">Operator</div><div class="cell-value" style="color:var(--teal);">{{operador}}</div></div>
  </div>
</div>
<div class="guest-row">
  <div class="guest-card">
    <div class="sect-lbl muted">Guest</div>
    <div class="guest-name">{{cliente}}</div>
    <div class="guest-contacts">{{email}}<br>{{telefone}}</div>
  </div>
  <div class="price-card {{price_class}}">
    <div class="sect-lbl inv">Total</div>
    <div class="price-amount">{{total}}&euro;</div>
    <div class="price-note">{{price_note}}</div>
  </div>
</div>
{{payment_alert_html}}
{{payment_method_html}}
{{pickup_html}}
{{special_requests_html}}
<div class="invoice">
  <div class="inv-hdr"><div class="inv-hdr-t">Invoice</div><div class="inv-hdr-r">{{bokun_ref}}</div></div>
  {{invoice_rows_html}}
</div>
<div class="inv-total-row">
  <div class="inv-total-l">Total Amount</div>
  <div class="inv-total-r">{{total}}&euro;</div>
</div>
<div class="cancel">
  <div class="cancel-dot">i</div>
  <div><div class="cancel-t">Cancellation Policy</div><div class="cancel-b">{{cancelamento}}</div></div>
</div>
<div class="insurance">
  <div class="ins-dot">&#10003;</div>
  <div>
    <div class="ins-title">Insurance Included</div>
    <div class="ins-body">This activity includes personal accident insurance provided by the operator. Coverage terms are governed solely by the operator&rsquo;s own insurance policy.</div>
  </div>
</div>
<div class="contacts-row">
  <div class="contact-card">
    <div class="contact-lbl">Operator Contact</div>
    <div class="contact-name">{{operador}}</div>
    <div class="contact-det">{{operador_telefone}}<br>{{operador_email}}</div>
  </div>
  <div class="contact-card">
    <div class="contact-lbl">Beyond Madeira</div>
    <div class="contact-name">Booking Support</div>
    <div class="contact-det">+351 939 566 415<br>booking@beyondmadeira.com</div>
  </div>
</div>
<div class="thankyou">
  <div class="ty-title">Thank you for booking with Beyond Madeira!</div>
  <div class="ty-text">{{mensagem_confirmacao}}<br><br>Questions? <strong>WhatsApp +351 939 566 415</strong> &middot; <strong>booking@beyondmadeira.com</strong></div>
</div>
<div class="footer">
  <div class="ft-l">Beyond Madeira &middot; RNAVT 13020 &middot; NIPC 518 827 119<br>Head Office: Largo da Sa&uacute;de n1, 9000-221 Funchal, Madeira, Portugal</div>
  <div class="ft-r"><span class="ft-teal">beyondmadeira.com</span><br>+351 939 566 415 &middot; booking@beyondmadeira.com</div>
</div>
<div class="legal">Beyond Madeira (RNAVT 13020) acts exclusively as a booking intermediary. Beyond Madeira is not a party to the activity agreement and assumes no liability for the activity, accidents, or disputes between the guest and the operator. Personal data processed under GDPR for booking fulfilment only.</div>
</div>
</body>
</html>'''

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
        mes_num  = int(d.get("mes", 0))
        ano      = int(d.get("ano", 0))
        upload   = d.get("upload", False)
        record_id= d.get("record_id", "")
        meses_pt = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
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
        return jsonify({"success": True, "filename": fname, "pdf_base64": b64})
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
