import json
import logging
import re
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import update
from app.extensions import db
from app.models.wa_confirmation import WaConfirmation
from app.models.wa_notification import WaNotification
from app.models.site_booking import SiteBooking
from app.utils.auth import require_api_key

bp = Blueprint("whatsapp", __name__)
log = logging.getLogger(__name__)

WAZZUP_BASE = "https://api.wazzup24.com/v3"

# ── Positive confirmation keywords (lowercase) ──────────────────────
POSITIVE_KEYWORDS = [
    "yes", "yeah", "yep", "received", "got it", "confirm", "confirmed", "ok",
    "si", "sim", "oui", "ja", "danke", "merci", "gracias", "ricevuto",
    "ontvangen", "perfect", "great", "sure", "of course", "claro",
    "bien sûr", "bien sur",
]

# ── Follow-up messages by language ──────────────────────────────────
FOLLOWUP_MESSAGES = {
    "en": (
        "Great, thank you for confirming! 😊\n\n"
        "If you need anything at all during your stay, we're always here to help.\n"
        "You can also find tips, our travel guide and webcams on our website anytime.\n\n"
        "Enjoy your time in Madeira! 😊"
    ),
    "fr": (
        "Parfait, merci d'avoir confirmé ! 😊\n\n"
        "Si vous avez besoin de quoi que ce soit pendant votre séjour, nous sommes là pour vous aider.\n"
        "Vous trouverez aussi des conseils et notre guide de voyage sur notre site.\n\n"
        "Profitez bien de Madère ! 😊"
    ),
    "pt": (
        "Ótimo, obrigado por confirmar! 😊\n\n"
        "Se precisar de alguma coisa durante a sua estadia, estamos sempre aqui.\n"
        "Pode encontrar dicas e o nosso guia de viagem no nosso site.\n\n"
        "Aproveite a Madeira! 😊"
    ),
    "es": (
        "Perfecto, gracias por confirmar! 😊\n\n"
        "Si necesitas algo durante tu estancia, estamos aquí para ayudarte.\n"
        "También puedes encontrar consejos y nuestra guía de viaje en nuestra web.\n\n"
        "¡Disfruta de Madeira! 😊"
    ),
    "de": (
        "Super, danke für die Bestätigung! 😊\n\n"
        "Wenn Sie während Ihres Aufenthalts etwas brauchen, sind wir immer für Sie da.\n"
        "Auf unserer Website finden Sie Tipps und unseren Reiseführer.\n\n"
        "Genießen Sie Madeira! 😊"
    ),
}

# ── Phone prefix to language mapping ────────────────────────────────
PREFIX_LANG = [
    ("351", "pt"),
    ("33", "fr"),
    ("34", "es"),
    ("49", "de"),
    ("39", "it"),
    ("31", "nl"),
]


def _detect_lang_from_phone(chat_id):
    """Detect language from phone number prefix. Default to English."""
    clean = re.sub(r"[^\d]", "", chat_id or "")
    for prefix, lang in PREFIX_LANG:
        if clean.startswith(prefix):
            return lang
    return "en"


def _is_positive_confirmation(text):
    """Check if text contains a positive confirmation keyword."""
    if not text:
        return False
    lower = text.strip().lower()
    for kw in POSITIVE_KEYWORDS:
        # Match whole word or the entire message is just the keyword
        pattern = r"(?:^|\s)" + re.escape(kw) + r"(?:\s|$|[!.,?])"
        if re.search(pattern, lower):
            return True
    return False


def _wazzup_headers():
    return {
        "Authorization": "Bearer " + current_app.config["WAZZUP_API_KEY"],
        "Content-Type": "application/json",
    }


def _ensure_wazzup_user(user_id, user_name):
    """Register the user in Wazzup via POST /v3/users (idempotent)."""
    requests.post(
        WAZZUP_BASE + "/users",
        headers=_wazzup_headers(),
        json=[{"id": user_id, "name": user_name}],
        timeout=10,
    )


@bp.route("/wazzup/iframe", methods=["POST"])
@require_api_key
def wazzup_iframe():
    try:
        body = request.get_json(silent=True) or {}
        user_id = body.get("userId", "Milton")
        user_name = body.get("userName", "Milton")
        scope = body.get("scope", "global")

        _ensure_wazzup_user(user_id, user_name)

        channel_id = current_app.config["WAZZUP_CHANNEL"]

        payload = {
            "user": {"id": user_id, "name": user_name},
            "scope": scope,
            "channels": [channel_id],
            "options": {"hideAvatars": True},
        }
        chat_type = body.get("chatType")
        chat_id = body.get("chatId")
        if chat_type and chat_id:
            payload["filter"] = [{"chatType": chat_type, "chatId": chat_id}]
            payload["activeChat"] = {"chatType": chat_type, "chatId": chat_id}
            if scope == "global":
                payload["scope"] = "card"

        r = requests.post(
            WAZZUP_BASE + "/iframe",
            headers=_wazzup_headers(),
            json=payload,
            timeout=15,
        )
        if not r.ok:
            detail = r.text
            log.error("Wazzup iframe %s: %s", r.status_code, detail)
            return jsonify({"error": f"Wazzup {r.status_code}", "detail": detail}), 502

        data = r.json()
        if "error" in data:
            log.error("Wazzup iframe error: %s", data)
            return jsonify({"error": data["error"]}), 502

        url = data.get("url", "")
        if not url:
            log.error("Wazzup iframe empty url: %s", data)
            return jsonify({"error": "Wazzup returned empty URL"}), 502

        return jsonify({"url": url, "iframeUrl": url})
    except Exception as e:
        log.exception("wazzup_iframe failed")
        return jsonify({"error": str(e)}), 500


@bp.route("/wazzup/chats", methods=["GET"])
@require_api_key
def wazzup_chats():
    try:
        r = requests.get(
            WAZZUP_BASE + "/chats",
            headers=_wazzup_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/wazzup/messages", methods=["GET"])
@require_api_key
def wazzup_messages():
    try:
        chat_id = request.args.get("chatId", "")
        params = {"chatId": chat_id} if chat_id else {}
        r = requests.get(
            WAZZUP_BASE + "/messages",
            headers=_wazzup_headers(),
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/wazzup/send", methods=["POST"])
@require_api_key
def wazzup_send():
    """
    Envia mensagem WhatsApp via Wazzup API.
    Aceita campos opcionais para auto-ack lock atómico:
      - booking_id: int — id da SiteBooking
      - mark_whatsapp_sent: bool — se True, marca whatsapp_sent=True
        ATOMICAMENTE antes do POST. Se já estava True, devolve 409 e
        NÃO envia. Isto impede duplicação multi-user (Hugo+Paulo no
        mesmo segundo).
    """
    try:
        body = request.get_json() or {}
        booking_id = body.pop("booking_id", None)
        mark_wa = body.pop("mark_whatsapp_sent", False)

        # ── LOCK ATÓMICO antes do POST ──
        # UPDATE ... WHERE whatsapp_sent=False — devolve rowcount=1 só
        # se ninguém marcou ainda. Race-safe.
        if booking_id and mark_wa:
            try:
                bid = int(booking_id)
                stmt = (
                    update(SiteBooking)
                    .where(SiteBooking.id == bid)
                    .where(SiteBooking.whatsapp_sent.is_(False))
                    .values(whatsapp_sent=True)
                )
                result = db.session.execute(stmt)
                db.session.commit()
                if result.rowcount == 0:
                    # rowcount=0 pode ser:
                    #   (a) booking não existe → ignora lock e envia normal
                    #   (b) booking já tem whatsapp_sent=True → skip
                    existing = db.session.get(SiteBooking, bid)
                    if existing is None:
                        log.info("wazzup_send: booking %s não existe, envia sem lock", bid)
                        # Continua para enviar
                    elif existing.whatsapp_sent:
                        log.info("wazzup_send: booking %s já marcado, skip", bid)
                        return jsonify({
                            "success": False,
                            "skipped": True,
                            "reason": "already_sent",
                            "booking_id": bid
                        }), 409
                    # else: race condition estranha — segue para enviar
                else:
                    log.info("wazzup_send: booking %s lock acquired (whatsapp_sent=True)", bid)
            except (ValueError, TypeError) as e:
                log.warning("wazzup_send: booking_id inválido: %s", e)
                # Continua sem lock — comportamento legacy
            except Exception as e:
                log.exception("wazzup_send: falha no lock atómico")
                db.session.rollback()
                # Continua sem lock — não bloquear envio por erro DB

        # Se body NÃO trouxe channelId, usa o default
        if not body.get("channelId"):
            body["channelId"] = current_app.config["WAZZUP_CHANNEL"]
        # Auto-detectar group vs chat individual pelo formato do chatId
        # Grupos WhatsApp têm chatId que termina em @g.us ou começa por 1203...
        cid = str(body.get("chatId", ""))
        if "@g.us" in cid or cid.startswith("120363"):
            if not body.get("chatType") or body.get("chatType") == "whatsapp":
                body["chatType"] = "whatsappgroup"
            # Strip @g.us do chatId — Wazzup espera só o ID puro
            if "@g.us" in cid:
                body["chatId"] = cid.replace("@g.us", "")
        log.info("wazzup_send → body: %s", json.dumps(body)[:300])
        r = requests.post(
            WAZZUP_BASE + "/message",
            headers=_wazzup_headers(),
            json=body,
            timeout=15,
        )
        if not r.ok:
            log.warning("wazzup_send ← HTTP %s body: %s", r.status_code, r.text[:300])
        if not r.ok:
            # Wazzup falhou — REVERTER o lock para permitir retry
            if booking_id and mark_wa:
                try:
                    bid = int(booking_id)
                    db.session.execute(
                        update(SiteBooking)
                        .where(SiteBooking.id == bid)
                        .values(whatsapp_sent=False)
                    )
                    db.session.commit()
                    log.warning("wazzup_send: Wazzup HTTP %s, lock revertido para booking %s", r.status_code, bid)
                except Exception:
                    db.session.rollback()
            r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/wazzup/mark-as-read", methods=["POST"])
@require_api_key
def wazzup_mark_as_read():
    try:
        body = request.get_json()
        chat_id = body.get("chatId")
        if not chat_id:
            return jsonify({"error": "chatId is required"}), 400
        payload = {
            "chatId": chat_id,
            "channelId": current_app.config["WAZZUP_CHANNEL"],
        }
        r = requests.post(
            WAZZUP_BASE + "/mark-as-read",
            headers=_wazzup_headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return jsonify(r.json() if r.text else {"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Register a confirmation request (called by frontend) ───────────
@bp.route("/api/wa-confirmations", methods=["POST"])
@require_api_key
def create_wa_confirmation():
    """Frontend calls this after sending a 'did you receive the email?' WhatsApp."""
    try:
        body = request.get_json(silent=True) or {}
        chat_id = body.get("chatId", "").strip()
        if not chat_id:
            return jsonify({"error": "chatId is required"}), 400

        conf = WaConfirmation(chat_id=chat_id)
        db.session.add(conf)
        db.session.commit()
        log.info("wa_confirmation created for chat_id=%s id=%s", chat_id, conf.id)
        return jsonify(conf.to_api()), 201
    except Exception as e:
        db.session.rollback()
        log.exception("create_wa_confirmation failed")
        return jsonify({"error": str(e)}), 500


# ── Wazzup Webhook (no auth — Wazzup doesn't send API keys) ────────
@bp.route("/wazzup/webhook", methods=["POST"])
def wazzup_webhook():
    """
    Receives incoming messages from Wazzup.
    If the message is a positive confirmation to a recent 'confirm email'
    request, auto-sends a follow-up message in the client's language.
    """
    try:
        payload = request.get_json(silent=True) or {}
        messages = payload.get("messages", [])

        # Build a map of chatId -> contact_name from the contacts array, if present
        contacts_by_chat = {}
        try:
            for c in (payload.get("contacts") or []):
                cid = c.get("chatId") or c.get("id") or ""
                name = c.get("name") or c.get("username") or ""
                if cid:
                    contacts_by_chat[cid] = name
        except Exception:
            contacts_by_chat = {}

        for msg in messages:
            # Only process incoming WhatsApp text messages
            if msg.get("type") != "incoming":
                continue
            # Aceitar chats individuais E grupos (whatsapp + whatsappgroup)
            chat_type = msg.get("chatType", "")
            if chat_type not in ("whatsapp", "whatsappgroup"):
                continue

            text = msg.get("text", "")
            chat_id = msg.get("chatId", "")
            if not chat_id or not text:
                continue

            # ── Store as bell notification ─────────────────────────
            try:
                contact_name = contacts_by_chat.get(chat_id) or ""
                if not contact_name and isinstance(msg.get("contact"), dict):
                    contact_name = msg.get("contact", {}).get("name") or ""
                if not contact_name:
                    contact_name = msg.get("authorName") or ""
                notif = WaNotification(
                    chat_id=chat_id,
                    contact_name=contact_name or "",
                    text=text[:2000],
                    received_at=datetime.utcnow(),
                    read=False,
                    replied=False,
                )
                db.session.add(notif)
                db.session.commit()
            except Exception:
                db.session.rollback()
                log.exception("failed to store wa_notification")

            # Auto-confirm follow-up: APENAS para chats individuais (não grupos)
            if chat_type != "whatsapp":
                continue

            # Check if we have an unreplied confirmation for this chatId
            # sent within the last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            conf = (
                WaConfirmation.query
                .filter_by(chat_id=chat_id, replied=False)
                .filter(WaConfirmation.sent_at >= cutoff)
                .order_by(WaConfirmation.sent_at.desc())
                .first()
            )

            if not conf:
                continue

            if not _is_positive_confirmation(text):
                continue

            # Detect language and send follow-up
            lang = _detect_lang_from_phone(chat_id)
            followup = FOLLOWUP_MESSAGES.get(lang, FOLLOWUP_MESSAGES["en"])

            channel_id = (
                msg.get("channelId")
                or current_app.config.get("WAZZUP_CHANNEL", "")
            )
            send_payload = {
                "chatType": "whatsapp",
                "chatId": chat_id,
                "channelId": channel_id,
                "text": followup,
            }

            r = requests.post(
                WAZZUP_BASE + "/message",
                headers=_wazzup_headers(),
                json=send_payload,
                timeout=15,
            )

            if r.ok:
                conf.replied = True
                conf.replied_at = datetime.utcnow()
                # Mark the just-stored notification (and any other unreplied
                # ones for this chat) as replied so they won't nag in the bell.
                try:
                    (WaNotification.query
                     .filter_by(chat_id=chat_id, replied=False)
                     .update({"replied": True}))
                except Exception:
                    log.exception("failed to mark notifications replied")
                db.session.commit()
                log.info(
                    "Auto-replied confirmation for chat_id=%s lang=%s",
                    chat_id, lang,
                )
            else:
                log.error(
                    "Failed to send follow-up to chat_id=%s: %s %s",
                    chat_id, r.status_code, r.text,
                )

        return jsonify({"ok": True}), 200

    except Exception as e:
        db.session.rollback()
        log.exception("wazzup_webhook failed")
        # Always return 200 to Wazzup so it doesn't retry endlessly
        return jsonify({"ok": False, "error": str(e)}), 200


# ── Bell notifications API ─────────────────────────────────────────
@bp.route("/api/wa-notifications", methods=["GET"])
@require_api_key
def list_wa_notifications():
    """Return up to 20 most recent UNREAD WhatsApp notifications."""
    try:
        q = (
            WaNotification.query
            .filter_by(read=False)
            .order_by(WaNotification.received_at.desc())
            .limit(20)
            .all()
        )
        return jsonify({"items": [n.to_api() for n in q], "count": len(q)})
    except Exception as e:
        log.exception("list_wa_notifications failed")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/wa-notifications/<int:notif_id>/read", methods=["POST"])
@require_api_key
def mark_wa_notification_read(notif_id):
    """Mark a single WhatsApp bell notification as read."""
    try:
        n = WaNotification.query.get(notif_id)
        if not n:
            return jsonify({"error": "not found"}), 404
        n.read = True
        db.session.commit()
        return jsonify(n.to_api())
    except Exception as e:
        db.session.rollback()
        log.exception("mark_wa_notification_read failed")
        return jsonify({"error": str(e)}), 500
