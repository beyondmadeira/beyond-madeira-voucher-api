import os
import re
import base64
from datetime import datetime


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def logo_b64():
    try:
        p = os.path.join(_BASE_DIR, "static", "logo_clean.png")
        with open(p, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return "https://res.cloudinary.com/dvrzzxu5b/image/upload/v1772828506/logo-beyond-madeira-_rvh6zt.png"


def fill(tmpl, data):
    for k, v in data.items():
        tmpl = tmpl.replace("{{" + k + "}}", str(v) if v is not None else "")
    return tmpl


def fmt_date(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%-d %b %Y")
    except Exception:
        return s


def fmt_time(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%H:%M")
    except Exception:
        return s


def eur_val(v):
    try:
        return float(str(v).replace("\u20ac", "").replace(",", ".").strip())
    except Exception:
        return 0.0


def get_text_f(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v) if v else ""


def norm_act(v):
    s = get_text_f(v)
    if len(s) > 35:
        s = s[:33] + "\u2026"
    return s


def fget_f(rec, *keys):
    for k in keys:
        if k in rec and rec[k] not in (None, "", []):
            return rec[k]
    return None


def load_template(fname):
    p = os.path.join(_BASE_DIR, "templates", fname)
    try:
        with open(p, encoding="utf-8") as f:
            html = f.read()
        html = re.sub(
            r"@import url\('https://fonts\.googleapis\.com/[^']*'\);?", "", html
        )
        html = re.sub(r"<link[^>]*fonts\.googleapis\.com[^>]*>", "", html)
        html = html.replace("'Montserrat',", "'Liberation Sans',")
        html = html.replace('"Montserrat",', '"Liberation Sans",')
        return html
    except Exception as e:
        print(f"[WARN] Could not load {fname}: {e}")
        return ""
