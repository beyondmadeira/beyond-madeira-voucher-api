TIPS_TEXT = {
    "warm":       "Dress very warmly \u2014 it can be very cold at high altitude.",
    "jacket":     "Bring a light jacket \u2014 temperatures change quickly in the mountains.",
    "jacket_sea": "Bring a light jacket \u2014 temperatures at sea can drop quickly, especially on the way back.",
    "swimsuit":   "Bring swimsuit and towel.",
    "sunscreen":  "Don't forget sunscreen.",
    "water":      "Bring water.",
    "snack":      "Bring a snack.",
    "shoes":      "Wear comfortable walking shoes.",
    "flashlight": "Bring a flashlight/torch \u2014 essential for tunnel sections.",
}

ACTIVITY_RULES = [
    {"kw": ["sunrise", "pico areeiro"],
     "payment": "cash", "pickup": "pickup_day_before",
     "no_payment_link": True, "email_template": "sunrise",
     "tips": ["warm", "water", "snack", "shoes"],
     "note": "Dress very warmly \u2014 Pico Areeiro can be below 0\u00b0C at sunrise."},

    {"kw": ["vereda", "larano"],
     "payment": "cash", "pickup": "pickup_day_before",
     "no_payment_link": True, "email_template": "sunrise",
     "tips": ["jacket", "water", "snack", "shoes"],
     "note": "Trail fee \u20ac3 per person \u2014 paid on site via Simplifica app."},

    {"kw": ["caldeirao verde", "caldeir\u00e3o verde"],
     "payment": "cash", "pickup": "pickup_hotel",
     "tips": ["jacket", "water", "flashlight", "snack", "shoes"],
     "note": "A flashlight is essential for the tunnel section of the trail."},

    {"kw": ["west", "jeep"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "swimsuit", "water", "snack"],
     "note": "The tour may include a swim stop \u2014 bring swimwear just in case."},

    {"kw": ["west", "minivan"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "swimsuit", "water", "snack"],
     "note": "The tour may include a swim stop \u2014 bring swimwear just in case."},

    {"kw": ["east", "jeep"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "water", "snack"], "note": ""},

    {"kw": ["east", "minivan"],
     "payment": "cash", "pickup": "pickup_day_before",
     "tips": ["jacket", "water", "snack"], "note": ""},

    {"kw": ["whale", "dolphin"],
     "payment": "cash_card", "pickup": "meeting_point",
     "no_payment_link": True, "email_template": "dolphins",
     "tips": ["jacket_sea", "swimsuit", "sunscreen", "water"],
     "note": "Please arrive at the marina 30 minutes before departure for check-in."},

    {"kw": ["vip dolphin"],
     "payment": "cash_card", "pickup": "meeting_point",
     "no_payment_link": True, "email_template": "dolphins",
     "tips": ["jacket", "sunscreen", "water"],
     "note": "Please arrive at the marina 30 minutes before departure."},

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

ACTIVITY_TIPS = {
    "hike": {
        "bring": ["Comfortable hiking shoes", "Water (min 1.5L)", "Sunscreen & sunglasses", "Light rain jacket", "Snacks", "Small backpack"],
        "not_included": [],
        "tips": ["Wear layers \u2014 mornings can be cool", "Start well-rested and hydrated"],
    },
    "sunrise": {
        "bring": ["Warm layers (near 0\u00b0C at altitude)", "Headlamp or phone torch", "Water & snacks", "Phone torch"],
        "not_included": [],
        "tips": ["Set multiple alarms \u2014 departure is very early", "Dress warmer than you think"],
    },
    "cabo girao": {
        "bring": ["Comfortable shoes"],
        "not_included": ["Cabo Gir\u00e3o skywalk entry \u2014 \u20ac5 per person (cash or card on site)"],
        "tips": ["Entry paid on site \u2014 card or cash accepted"],
    },
    "queimadas": {
        "bring": ["Warm layers", "Waterproof jacket \u2014 often misty", "Water 1.5L"],
        "not_included": [],
        "tips": ["Waterproof shoes recommended \u2014 path can be muddy"],
    },
    "caldeir\u00e3o verde": {
        "bring": ["Headlamp (MANDATORY \u2014 tunnel sections)", "Waterproof jacket", "Water 1.5L"],
        "not_included": [],
        "tips": ["You MUST bring a headlamp \u2014 tunnels are pitch dark", "Trail shoes strongly recommended"],
    },
    "pico ruivo": {
        "bring": ["Warm layers \u2014 summit above 1800m", "Sunscreen", "Water 2L", "Energy snacks"],
        "not_included": [],
        "tips": ["Weather changes fast at altitude \u2014 always bring a jacket", "No water points on trail"],
    },
    "island tour": {
        "bring": ["Sunscreen", "Light jacket", "Water", "Comfortable walking shoes"],
        "not_included": ["Lunch", "Entry fees (if applicable)"],
        "tips": ["We stop for lunch — cards accepted almost everywhere", "Confirm pick-up point the day before"],
    },
    "jeep": {
        "bring": ["Sunscreen", "Light jacket", "Water"],
        "not_included": ["Lunch"],
        "tips": ["Off-road sections can be bumpy \u2014 avoid if back issues", "We stop for lunch — cards accepted at most places"],
    },
    "mini van": {
        "bring": ["Sunscreen", "Comfortable shoes", "Water"],
        "not_included": ["Lunch", "Entry fees (if applicable)"],
        "tips": ["Confirm pick-up location the night before"],
    },
    "boat": {
        "bring": ["Swimwear", "Towel", "Waterproof sunscreen", "Change of clothes", "Seasickness tablets if needed"],
        "not_included": [],
        "tips": ["Take seasickness medication 30min before if prone", "Bring a waterproof bag for your phone"],
    },
    "dolphin": {
        "bring": ["Sunscreen", "Warm layer for sea breeze", "Seasickness tablets if needed"],
        "not_included": [],
        "tips": ["Sightings are very likely but not 100% guaranteed \u2014 it's nature", "Confirm departure marina"],
    },
    "whale": {
        "bring": ["Warm windproof layer", "Sunscreen", "Seasickness tablets (strongly recommended)", "Binoculars"],
        "not_included": [],
        "tips": ["Boats go further offshore \u2014 sea can be rough", "Sightings not guaranteed but likelihood high"],
    },
    "canyoning": {
        "bring": ["Swimwear (worn under wetsuit)", "Old trainers or water shoes", "Towel & change of clothes"],
        "not_included": ["Wetsuit and all equipment are provided"],
        "tips": ["Do not eat heavy 2h before", "Inform operator of any health issues"],
    },
    "surf": {
        "bring": ["Swimwear", "Towel", "Waterproof sunscreen", "Change of clothes"],
        "not_included": ["Surfboard and wetsuit included"],
        "tips": ["No experience needed for beginner lessons", "Arrive 15min early for briefing"],
    },
    "paragliding": {
        "bring": ["Comfortable clothes (no skirts)", "Closed-toe shoes", "Sunglasses"],
        "not_included": ["Photos/video package (optional \u2014 ask on the day)"],
        "tips": ["Weight limit ~100-110kg \u2014 confirm with operator", "Flights are weather dependent \u2014 confirmed morning of"],
    },
    "quad": {
        "bring": ["Clothes you don't mind getting dusty", "Closed-toe shoes", "Sunglasses", "Sunscreen"],
        "not_included": ["Helmet provided"],
        "tips": ["Minimum age may apply \u2014 confirm with operator"],
    },
    "via ferrata": {
        "bring": ["Sport clothing", "Trail shoes or hiking boots", "Water 1.5L", "Sunscreen"],
        "not_included": ["Harness, helmet and via ferrata kit all provided"],
        "tips": ["Some upper body strength required", "Not suitable for severe fear of heights"],
    },
    "default": {
        "bring": ["Comfortable clothes", "Sunscreen & sunglasses", "Water"],
        "not_included": [],
        "tips": ["Confirm meeting point the day before", "Arrive 10 minutes early"],
    },
}


def detect_activity(nome):
    n = nome.lower()
    for rule in ACTIVITY_RULES:
        if all(kw in n for kw in rule["kw"]):
            return rule
    return None


def is_no_payment_activity(nome):
    """Returns True if this activity should NOT show payment link in email."""
    rule = detect_activity(nome or "")
    return bool(rule and rule.get("no_payment_link"))


def get_email_template_key(nome):
    """Returns template key (sunrise/dolphins/generic) for this activity."""
    rule = detect_activity(nome or "")
    return (rule.get("email_template") if rule else None) or "generic"


def get_activity_tips(atividade_str, categoria_str=""):
    search = (atividade_str + " " + categoria_str).lower()
    for key in ["caldeir\u00e3o verde", "cabo girao", "queimadas", "pico ruivo",
                "via ferrata", "island tour", "mini van",
                "dolphin", "canyoning", "paragliding", "sunrise",
                "whale", "boat", "surf", "hike", "jeep", "quad"]:
        if key in search:
            return ACTIVITY_TIPS[key]
    return ACTIVITY_TIPS["default"]


def build_tips_html(tips):
    if not tips:
        return ""
    sections = []
    if tips.get("bring"):
        items = "".join(f"<li>{b}</li>" for b in tips["bring"])
        sections.append(
            f'<div style="background:#f0f7ff;border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
            f'<p style="margin:0 0 6px;font-weight:700;font-size:13px;color:#1a5276;">\U0001f392 What to Bring</p>'
            f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#2a2a2a;line-height:1.8;">{items}</ul></div>'
        )
    if tips.get("not_included"):
        items = "".join(f"<li>{n}</li>" for n in tips["not_included"])
        sections.append(
            f'<div style="background:#fff8f0;border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
            f'<p style="margin:0 0 6px;font-weight:700;font-size:13px;color:#c0392b;">\u26a0\ufe0f Not Included</p>'
            f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#2a2a2a;line-height:1.8;">{items}</ul></div>'
        )
    if tips.get("tips"):
        items = "".join(f"<li>{t}</li>" for t in tips["tips"])
        sections.append(
            f'<div style="background:#f0faf7;border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
            f'<p style="margin:0 0 6px;font-weight:700;font-size:13px;color:#0d6e7a;">\U0001f4a1 Tips</p>'
            f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#2a2a2a;line-height:1.8;">{items}</ul></div>'
        )
    return "\n".join(sections)
