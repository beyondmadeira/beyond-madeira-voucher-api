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


WAZZUP_IFRAME_URL = (
    "https://app.wazzup24.com/3024-2504/chat/whatsgroup"
    "/120363420181553197/c01da476-ab8e-4997-872b-599767c16fc9"
)


@bp.route("/wazzup/iframe", methods=["POST"])
@require_api_key
def wazzup_iframe():
    url = WAZZUP_IFRAME_URL
    return jsonify({"url": url, "iframeUrl": url})


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
            WAZZUP_BASE + "/messages/text",
            headers=_wazzup_headers(),
            json=body,
            timeout=15,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
