"""Auto-import reservations from Gmail (Bokun activities + Web3Forms rent car)."""

import base64
import json
import logging
import re
from datetime import datetime, timezone

import requests
from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.utils.auth import require_api_key
from app.models.site_booking import SiteBooking

bp = Blueprint("site_bookings", __name__)
log = logging.getLogger(__name__)

WAZZUP_BASE = "https://api.wazzup24.com/v3"

# ---------------------------------------------------------------------------
# Gmail helpers
# ---------------------------------------------------------------------------

def _gmail_service():
    """Build an authenticated Gmail API service using OAuth2 refresh token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    cfg = current_app.config
    creds = Credentials(
        token=None,
        refresh_token=cfg["GMAIL_REFRESH_TOKEN"],
        client_id=cfg["GMAIL_CLIENT_ID"],
        client_secret=cfg["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_body_text(payload):
    """Recursively extract the plain-text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _get_body_text(part)
        if result:
            return result

    # Fallback: try HTML and strip tags
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        html = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", "", html)

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", "", html)

    return ""


# ---------------------------------------------------------------------------
# Parsers (regex-based)
# ---------------------------------------------------------------------------

def _parse_bokun(body):
    """Parse a Bokun activity booking email and return a dict."""

    def _extract(pattern, text, default=""):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    ref = _extract(r"Booking\s+ref\.\s+(BYD-\S+)", body)
    product = _extract(r"Product\s+(?!booking)(\S.+?)(?:\n|$)", body)
    # Customer line: "Customer    LastName, FirstName"
    customer_raw = _extract(r"Customer\s+(?!email|phone)(\S.+?)(?:\n|$)", body)
    # Flip "LastName, FirstName" -> "FirstName LastName"
    if "," in customer_raw:
        parts = [p.strip() for p in customer_raw.split(",", 1)]
        customer = f"{parts[1]} {parts[0]}" if len(parts) == 2 else customer_raw
    else:
        customer = customer_raw
    email_addr = _extract(r"Customer\s+email\s+(\S+)", body)
    phone = _extract(r"Customer\s+phone\s+(\+?\S+)", body)
    date_str = _extract(r"Date\s+(.+?)(?:\n|$)", body)
    pax = _extract(r"PAX\s+(.+?)(?:\n|$)", body)
    pickup = _extract(r"Pick-up\s+(.+?)(?:\n|$)", body)

    return {
        "ref": ref,
        "atividade": product,
        "nome": customer,
        "email": email_addr,
        "tel": phone,
        "data": date_str,
        "pax": pax,
        "pickup": pickup,
    }


def _parse_web3forms(body):
    """Parse a Web3Forms rent-car booking email and return a dict."""

    def _extract(pattern, text, default=""):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    ref = _extract(r"Ref:\s*(\S+)", body)
    driver = _extract(r"Driver:\s*(.+?)(?:\n|$)", body)
    age = _extract(r"Age:\s*(\d+)", body)
    phone = _extract(r"Phone:\s*(\+?\S+)", body)
    email_addr = _extract(r"Email:\s*(\S+)", body)
    pickup_raw = _extract(r"Pick-up:\s*(.+?)(?:\n|$)", body)
    dropoff_raw = _extract(r"Drop-off:\s*(.+?)(?:\n|$)", body)
    car = _extract(r"Car:\s*(.+?)(?:\n|$)", body)
    extras = _extract(r"Extras:\s*(.+?)(?:\n|$)", body)
    total_line = _extract(r"Total:\s*(.+?)(?:\n|$)", body)
    empresa = _extract(r"Empresa:\s*(.+?)(?:\n|$)", body)
    comissao_line = _extract(r"Comiss[aã]o:\s*(.+?)(?:\n|$)", body)
    total_num = _extract(r"Total\s*num:\s*(\S+)", body)
    comissao_num = _extract(r"Comiss?[aã]o\s*num:\s*(\S+)", body)

    # Parse pickup details: "Sat, 16 May 2026 17:30 — Airport (20€) — SK2901"
    pickup_dt = ""
    pickup_loc = ""
    pickup_flight = ""
    if pickup_raw:
        parts = re.split(r"\s*[—–-]\s*", pickup_raw, maxsplit=2)
        if len(parts) >= 1:
            pickup_dt = parts[0].strip()
        if len(parts) >= 2:
            pickup_loc = parts[1].strip()
        if len(parts) >= 3:
            pickup_flight = parts[2].strip()

    return {
        "ref": ref,
        "nome": driver,
        "idade": age,
        "tel": phone,
        "email": email_addr,
        "pickup_raw": pickup_raw,
        "pickup_dt": pickup_dt,
        "pickup_loc": pickup_loc,
        "pickup_flight": pickup_flight,
        "dropoff": dropoff_raw,
        "carro": car,
        "extras": extras,
        "total_line": total_line,
        "total": total_num,
        "comissao": comissao_num,
        "parceiro": empresa,
        "comissao_line": comissao_line,
        "observacoes": f"Age: {age}" if age else "",
    }


# ---------------------------------------------------------------------------
# WhatsApp notification via Wazzup
# ---------------------------------------------------------------------------

def _send_whatsapp(phone, name, product_or_car, tipo):
    """Send a WhatsApp greeting via Wazzup API."""
    if not phone:
        return False

    cfg = current_app.config
    api_key = cfg.get("WAZZUP_API_KEY", "")
    channel_id = cfg.get("WAZZUP_CHANNEL", "")
    if not api_key or not channel_id:
        log.warning("Wazzup not configured, skipping WhatsApp for %s", name)
        return False

    # Clean phone: keep only digits and leading +
    clean_phone = re.sub(r"[^\d+]", "", phone)
    if clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]

    if tipo == "at":
        item_label = product_or_car
    else:
        item_label = f"a rental car ({product_or_car})" if product_or_car else "a car rental"

    first_name = name.split()[0] if name else "there"

    message = (
        f"Hello {first_name}! \U0001f60a We received your booking request for "
        f"{item_label}. We're checking availability and will get back to you "
        f"shortly! \u2014 Beyond Madeira Team"
    )

    try:
        resp = requests.post(
            f"{WAZZUP_BASE}/message",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "channelId": channel_id,
                "chatType": "whatsapp",
                "chatId": clean_phone,
                "text": message,
            },
            timeout=15,
        )
        if resp.ok:
            log.info("WhatsApp sent to %s (%s)", name, clean_phone)
            return True
        else:
            log.error("Wazzup send failed %s: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        log.error("Wazzup send error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Gmail poll logic
# ---------------------------------------------------------------------------

def _poll_gmail():
    """Search Gmail for unread booking emails, parse, store, and notify."""
    service = _gmail_service()
    results = []

    queries = [
        ("from:no-reply@bokun.io newer_than:30d", "at"),
        ("from:notify@web3forms.com newer_than:30d", "rc"),
    ]

    for query, tipo in queries:
        try:
            resp = service.users().messages().list(
                userId="me", q=query, maxResults=100
            ).execute()
            messages = resp.get("messages", [])
        except Exception as e:
            log.error("Gmail list error for %s: %s", tipo, e)
            continue

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            try:
                msg = service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()

                body = _get_body_text(msg.get("payload", {}))
                if not body:
                    log.warning("Empty body for message %s", msg_id)
                    # Mark as read anyway to avoid reprocessing
                    service.users().messages().modify(
                        userId="me", id=msg_id,
                        body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                    continue

                if tipo == "at":
                    parsed = _parse_bokun(body)
                else:
                    parsed = _parse_web3forms(body)

                ref = parsed.get("ref", "")

                # Skip if already imported (by ref)
                if ref and SiteBooking.query.filter_by(ref=ref).first():
                    log.info("Skipping duplicate ref %s", ref)
                    service.users().messages().modify(
                        userId="me", id=msg_id,
                        body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                    continue

                # Determine product/car label for WhatsApp
                if tipo == "at":
                    product_label = parsed.get("atividade", "an activity")
                else:
                    product_label = parsed.get("carro", "")

                booking = SiteBooking(
                    tipo=tipo,
                    status="pending",
                    raw_email=body,
                    parsed_data=json.dumps(parsed, ensure_ascii=False),
                    nome=parsed.get("nome", ""),
                    email=parsed.get("email", ""),
                    tel=parsed.get("tel", ""),
                    ref=ref or None,
                )
                db.session.add(booking)
                db.session.flush()  # get the id

                # Send WhatsApp only for recent emails (< 2 hours old)
                wa_sent = False
                internal_date = int(msg.get("internalDate", "0")) / 1000
                email_age_hours = (datetime.now(timezone.utc).timestamp() - internal_date) / 3600
                if email_age_hours < 2:
                    wa_sent = _send_whatsapp(
                        parsed.get("tel", ""),
                        parsed.get("nome", ""),
                        product_label,
                        tipo,
                    )
                booking.whatsapp_sent = wa_sent

                db.session.commit()

                results.append({
                    "id": booking.id,
                    "tipo": tipo,
                    "ref": ref,
                    "nome": parsed.get("nome", ""),
                    "whatsapp_sent": wa_sent,
                })

                # Mark email as read
                service.users().messages().modify(
                    userId="me", id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()

            except Exception as e:
                log.exception("Error processing message %s: %s", msg_id, e)
                db.session.rollback()
                continue

    return results


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@bp.route("/api/site-bookings", methods=["GET"])
@require_api_key
def list_site_bookings():
    """List site bookings, optionally filtered by status."""
    try:
        status = request.args.get("status", "pending")
        q = SiteBooking.query
        if status and status != "all":
            q = q.filter_by(status=status)
        q = q.order_by(SiteBooking.created_at.desc())
        rows = q.all()
        return jsonify({"success": True, "records": [r.to_api() for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/site-bookings/<int:booking_id>/confirm", methods=["POST"])
@require_api_key
def confirm_site_booking(booking_id):
    """Confirm a pending site booking — creates a RentCar or Atividade record."""
    try:
        booking = SiteBooking.query.get(booking_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        if booking.status != "pending":
            return jsonify({"error": f"Booking already {booking.status}"}), 400

        parsed = {}
        if booking.parsed_data:
            try:
                parsed = json.loads(booking.parsed_data)
            except (json.JSONDecodeError, TypeError):
                pass

        created_record = None

        if booking.tipo == "rc":
            from app.models.reservas import RentCar
            rc = RentCar(
                ref=parsed.get("ref", ""),
                nome=parsed.get("nome", ""),
                tel=parsed.get("tel", ""),
                email=parsed.get("email", ""),
                idade=parsed.get("idade", ""),
                parceiro=parsed.get("parceiro", ""),
                carro=parsed.get("carro", ""),
                estado="Confirmada",
                pagamento="Por Pagar",
                pickup_data=parsed.get("pickup_dt", ""),
                pickup_local=parsed.get("pickup_loc", ""),
                pickup_voo=parsed.get("pickup_flight", ""),
                dropoff_data=parsed.get("dropoff", ""),
                total=float(parsed.get("total", 0) or 0),
                comissao=float(parsed.get("comissao", 0) or 0),
                extras=parsed.get("extras", ""),
                observacoes=parsed.get("observacoes", ""),
                dirty=True,
            )
            db.session.add(rc)
            db.session.flush()
            created_record = {"tipo": "rc", "id": rc.airtable_id or str(rc.id)}

        elif booking.tipo == "at":
            from app.models.reservas import Atividade
            at = Atividade(
                ref=parsed.get("ref", ""),
                nome=parsed.get("nome", ""),
                tel=parsed.get("tel", ""),
                email=parsed.get("email", ""),
                atividade=parsed.get("atividade", ""),
                pax=parsed.get("pax", ""),
                data=parsed.get("data", ""),
                local_pickup=parsed.get("pickup", ""),
                estado="Confirmada",
                pagamento="Por Pagar",
                dirty=True,
            )
            db.session.add(at)
            db.session.flush()
            created_record = {"tipo": "at", "id": at.airtable_id or str(at.id)}

        booking.status = "confirmed"
        booking.confirmed_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            "success": True,
            "booking": booking.to_api(),
            "created_record": created_record,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/site-bookings/<int:booking_id>/ignore", methods=["POST"])
@require_api_key
def ignore_site_booking(booking_id):
    """Mark a pending site booking as ignored."""
    try:
        booking = SiteBooking.query.get(booking_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404

        booking.status = "ignored"
        db.session.commit()
        return jsonify({"success": True, "booking": booking.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/site-bookings/debug", methods=["GET"])
@require_api_key
def debug_gmail():
    """Debug: test Gmail connection and show what emails exist."""
    try:
        service = _gmail_service()
        # Test 1: any recent email
        r1 = service.users().messages().list(userId="me", maxResults=3).execute()
        total = r1.get("resultSizeEstimate", 0)
        # Test 2: unread from bokun
        r2 = service.users().messages().list(userId="me", q="from:no-reply@bokun.io is:unread", maxResults=5).execute()
        bokun_unread = len(r2.get("messages", []))
        # Test 3: unread from web3forms
        r3 = service.users().messages().list(userId="me", q="from:notify@web3forms.com is:unread", maxResults=5).execute()
        web3_unread = len(r3.get("messages", []))
        # Test 4: ALL from bokun (last 30 days, read or unread)
        r4 = service.users().messages().list(userId="me", q="from:no-reply@bokun.io newer_than:30d", maxResults=5).execute()
        bokun_all = len(r4.get("messages", []))
        # Test 5: ALL from web3forms (last 30 days)
        r5 = service.users().messages().list(userId="me", q="from:notify@web3forms.com newer_than:30d", maxResults=5).execute()
        web3_all = len(r5.get("messages", []))
        return jsonify({
            "success": True,
            "gmail_connected": True,
            "total_emails": total,
            "bokun_unread": bokun_unread,
            "bokun_last_30d": bokun_all,
            "web3forms_unread": web3_unread,
            "web3forms_last_30d": web3_all,
        })
    except Exception as e:
        return jsonify({"success": False, "gmail_connected": False, "error": str(e)}), 500


@bp.route("/api/site-bookings/poll", methods=["POST"])
@require_api_key
def poll_site_bookings():
    """Manually trigger a Gmail poll for new booking emails."""
    try:
        results = _poll_gmail()
        return jsonify({
            "success": True,
            "imported": len(results),
            "bookings": results,
        })
    except Exception as e:
        log.exception("Poll failed")
        return jsonify({"error": str(e)}), 500
