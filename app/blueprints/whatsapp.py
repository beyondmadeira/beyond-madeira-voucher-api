import logging
import requests
from flask import Blueprint, request, jsonify, current_app
from app.utils.auth import require_api_key

bp = Blueprint("whatsapp", __name__)
log = logging.getLogger(__name__)

WAZZUP_BASE = "https://api.wazzup24.com/v3"


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

        payload = {
            "user": {"id": user_id, "name": user_name},
            "scope": scope,
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
    try:
        body = request.get_json()
        body["channelId"] = current_app.config["WAZZUP_CHANNEL"]
        r = requests.post(
            WAZZUP_BASE + "/message",
            headers=_wazzup_headers(),
            json=body,
            timeout=15,
        )
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
