"""
Beyond Madeira — Car Rental Voucher API
"""

import os
import io
import base64
import uuid
from flask import Flask, request, jsonify, send_file

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, Flowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

app = Flask(__name__)

PDF_STORE = {}

OCEAN    = colors.HexColor("#0A616B")
INK      = colors.HexColor("#111827")
INK_MED  = colors.HexColor("#374151")
INK_S    = colors.HexColor("#6B7280")
INK_XS   = colors.HexColor("#9CA3AF")
RULE     = colors.HexColor("#D1D5DB")
BG       = colors.HexColor("#F8FAFC")
WHITE    = colors.white
AMBER    = colors.HexColor("#92400E")
AMBER_LT = colors.HexColor("#FEF3C7")
AMBER_BD = colors.HexColor("#D97706")

P = 9; GAP = 0.45*cm; R = 6
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo_clean.png")

def tx(text, sz=8, bold=False, color=INK, align=TA_LEFT, italic=False, lead=None):
    fn = 'Helvetica-Bold' if bold else 'Helvetica-
cat > ~/voucher-api/main.py << 'PYEOF'
"""
Beyond Madeira — Car Rental Voucher API
"""

import os
import io
import base64
import uuid
from flask import Flask, request, jsonify, send_file

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, Flowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

app = Flask(__name__)

PDF_STORE = {}

OCEAN    = colors.HexColor("#0A616B")
INK      = colors.HexColor("#111827")
INK_MED  = colors.HexColor("#374151")
INK_S    = colors.HexColor("#6B7280")
INK_XS   = colors.HexColor("#9CA3AF")
RULE     = colors.HexColor("#D1D5DB")
BG       = colors.HexColor("#F8FAFC")
WHITE    = colors.white
AMBER    = colors.HexColor("#92400E")
AMBER_LT = colors.HexColor("#FEF3C7")
AMBER_BD = colors.HexColor("#D97706")

P = 9; GAP = 0.45*cm; R = 6
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo_clean.png")

def tx(text, sz=8, bold=False, color=INK, align=TA_LEFT, italic=False, lead=None):
    fn = 'Helvetica-Bold' if bold else 'Helvetica-Oblique' if italic else 'Helvetica'
    return Paragraph(str(text), ParagraphStyle('_', fontSize=sz, fontName=fn,
        textColor=color, alignment=align, leading=lead or sz*1.5, spaceBefore=0, spaceAfter=0))

def lbl(t): return tx(t, 6, bold=True, color=INK_XS)

class RoundedCard(Flowable):
    def __init__(self, inner, radius=6, bg=BG, border_color=RULE, border_width=0.8):
        super().__init__()
        self._inner = inner; self.r = radius
        self.bg = bg; self.bc = border_color; self.bw = border_width
    def wrap(self, aw, ah):
        self._w, self._h = self._inner.wrap(aw, ah); return self._w, self._h
    def draw(self):
        cv = self.canv
        cv.setFillColor(self.bg); cv.setStrokeColor(self.bc); cv.setLineWidth(self.bw)
        cv.roundRect(0, 0, self._w, self._h, self.r, fill=1, stroke=1)
        self._inner.drawOn(cv, 0, 0)

def card(data, col_widths, extra_styles=[]):
    inner = Table(data, colWidths=col_widths)
    inner.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), colors.transparent),
        ('TOPPADDING',   (0,0), (-1,-1), P),
        ('BOTTOMPADDING',(0,0), (-1,-1), P),
        ('LEFTPADDING',  (0,0), (-1,-1), P),
        ('RIGHTPADDING', (0,0), (-1,-1), P),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
    ] + extra_styles))
    return RoundedCard(inner, radius=R)

PW, PH = A4
ML = MR = 1.6*cm; MT = 1.3*cm; MB = 1.3*cm
UW = PW - ML - MR
W2 = UW/2; W3 = UW/3; W6 = UW*0.58; W4 = UW*0.42; WL = UW*0.27; WR = UW*0.73

class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, **kw)
        fr = Frame(ML, MB, UW, PH-MT-MB, id='body')
        self.addPageTemplates([PageTemplate(id='p', frames=fr, onPage=self._bg)])
    def _bg(self, cv, doc):
        cv.setFillColor(WHITE); cv.rect(0,0,PW,PH,fill=1,stroke=0)
        cv.setFillColor(OCEAN); cv.rect(0,PH-4*mm,PW,4*mm,fill=1,stroke=0)
        cv.setStrokeColor(RULE); cv.setLineWidth(0.5)
        cv.line(ML, 1.0*cm, PW-MR, 1.0*cm)
        cv.setFillColor(INK_XS); cv.setFont("Helvetica", 6)
        cv.drawString(ML, 0.65*cm, "Beyond Madeira  ·  RNAVT 13020  ·  NIPC 518 827 119  ·  Funchal, Madeira, Portugal")
        cv.drawRightString(PW-MR, 0.65*cm, "beyondmadeira.com  ·  +351 939 566 415")

def gerar_voucher_bytes(d):
    buf = io.BytesIO()
    doc = Doc(buf, pagesize=A4, rightMargin=MR, leftMargin=ML, topMargin=MT, bottomMargin=MB)
    s = []
    logo = RLImage(LOGO_PATH, width=2.7*cm, height=1.55*cm)
    rh = Table([
        [tx("CAR RENTAL VOUCHER", 7, bold=True, color=INK_S, align=TA_RIGHT)],
        [tx("Rental Confirmation", 15, bold=True, color=INK, align=TA_RIGHT)],
        [tx("Present this document at vehicle pick-up.", 7, color=INK_S, align=TA_RIGHT, italic=True)],
    ], colWidths=[UW-3.8*cm])
    rh.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),1),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    hdr = Table([[logo, rh]], colWidths=[3.8*cm, UW-3.8*cm])
    hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    s.append(hdr); s.append(Spacer(1, 0.3*cm))
    s.append(HRFlowable(width="100%", thickness=1.5, color=OCEAN, spaceAfter=0.35*cm))
    s.append(card([
        [lbl("BOOKING REFERENCE"), lbl("TOTAL AMOUNT")],
        [tx(d["referencia"], 19, bold=True, color=OCEAN), tx(d["total"], 19, bold=True, color=INK)],
        [tx("Issued by Beyond Madeira · RNAVT 13020", 6.5, color=INK_XS, italic=True), tx(" ", 6.5)],
    ], [W2, W2], [('LINEAFTER',(0,0),(0,-1),0.5,RULE)]))
    s.append(Spacer(1, GAP))
    s.append(card([
        [lbl("VEHICLE"), lbl("RENTAL COMPANY")],
        [tx(d["veiculo"], 9, bold=True, color=INK), tx(d["empresa"], 9, bold=True, color=OCEAN)],
    ], [W6, W4], [('LINEAFTER',(0,0),(0,-1),0.5,RULE)]))
    s.append(Spacer(1, GAP))
    s.append(card([
        [lbl("CLIENT"), lbl("PHONE"), lbl("EMAIL")],
        [tx(d["cliente"], 9, bold=True, color=INK),
         tx(d["telefone"], 9, bold=True, color=INK),
         tx(d["email"], 8.5, color=INK)],
    ], [W3, W3, W3], [('LINEAFTER',(0,0),(0,-1),0.5,RULE),('LINEAFTER',(1,0),(1,-1),0.5,RULE)]))
    s.append(Spacer(1, GAP))
    s.append(card([
        [lbl("PICK-UP"),                                      lbl("DROP-OFF")],
        [tx(d["pickup_data"], 12, bold=True, color=INK),      tx(d["dropoff_data"], 12, bold=True, color=INK)],
        [tx(d["pickup_hora"], 10, bold=True, color=OCEAN),    tx(d["dropoff_hora"], 10, bold=True, color=OCEAN)],
        [tx(d["pickup_local"], 8, color=INK_S),               tx(d["dropoff_local"], 8, color=INK_S)],
    ], [W2, W2], [('LINEAFTER',(0,0),(0,-1),0.5,RULE)]))
    s.append(Spacer(1, GAP))
    extras_inner = Table([[
        tx("EXTRAS", 7, bold=True, color=AMBER),
        tx(d.get("extras", "Extra driver, child seat, GPS and other add-ons are available and paid directly at pick-up."), 8, color=AMBER),
    ]], colWidths=[WL, WR])
    extras_inner.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), colors.transparent),
        ('LINEAFTER',(0,0),(0,-1),0.5,AMBER_BD),
        ('TOPPADDING',(0,0),(-1,-1),P),('BOTTOMPADDING',(0,0),(-1,-1),P),
        ('LEFTPADDING',(0,0),(-1,-1),P),('RIGHTPADDING',(0,0),(-1,-1),P),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    s.append(RoundedCard(extras_inner, radius=R, bg=AMBER_LT, border_color=AMBER_BD))
    s.append(Spacer(1, GAP))
    s.append(card([
        [tx("CANCELLATION POLICY", 7, bold=True, color=OCEAN),
         tx("Free cancellation up to <b>24 hours before</b> pick-up. Late cancellations or no-shows may incur a fee.", 8, color=INK_MED)],
    ], [WL, WR], [('LINEAFTER',(0,0),(0,-1),0.5,RULE)]))
    s.append(Spacer(1, 0.35*cm))
    s.append(tx("* Insurance coverage, terms and conditions are governed solely by the rental company's own contract.",
        7, color=INK_XS, italic=True))
    s.append(Spacer(1, 0.25*cm))
    s.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=0.15*cm))
    s.append(tx(
        "Beyond Madeira (RNAVT 13020) acts exclusively as a booking intermediary pursuant to Decreto-Lei n.o 61/2011. "
        "Beyond Madeira is not a party to the rental agreement and assumes no liability for vehicle condition, insurance, "
        "accidents, or disputes. All rental terms are governed by the contract issued by the rental company at pick-up. "
        "Personal data processed under GDPR for booking fulfilment only.",
        6.5, color=INK_XS, italic=True, lead=9.5))
    doc.build(s)
    buf.seek(0)
    return buf.read()


@app.route("/gerar-voucher", methods=["POST"])
def gerar_voucher_endpoint():
    try:
        d = request.get_json()
        if not d:
            return jsonify({"error": "JSON body required"}), 400
        required = ["referencia", "total", "veiculo", "empresa", "cliente",
                    "telefone", "email", "pickup_data", "pickup_hora",
                    "pickup_local", "dropoff_data", "dropoff_hora", "dropoff_local"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return jsonify({"error": f"Campos em falta: {missing}"}), 400

        pdf_bytes = gerar_voucher_bytes(d)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        filename = f"Voucher_{d['referencia']}_{d['cliente'].replace(' ', '_')}.pdf"

        token = str(uuid.uuid4())
        PDF_STORE[token] = {"bytes": pdf_bytes, "filename": filename}

        base_url = request.host_url.rstrip("/")
        pdf_url = f"{base_url}/download/{token}"

        return jsonify({
            "success": True,
            "filename": filename,
            "pdf_base64": pdf_b64,
            "pdf_url": pdf_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<token>", methods=["GET"])
def download_pdf(token):
    entry = PDF_STORE.get(token)
    if not entry:
        return jsonify({"error": "Not found or expired"}), 404
    return send_file(
        io.BytesIO(entry["bytes"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=entry["filename"]
    )


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Beyond Madeira Voucher API"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
