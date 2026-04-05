import requests
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app.utils.auth import require_api_key

bp = Blueprint("chat", __name__)


@bp.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    api_key = current_app.config["ANTHROPIC_API_KEY"]
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    try:
        body = request.get_json() or {}
        messages = body.get("messages", [])
        model = body.get("model", "claude-sonnet-4-20250514")
        max_tokens = body.get("max_tokens", 1024)
        system = body.get("system", "")
        stream = body.get("stream", False)

        payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        if stream:
            payload["stream"] = True

            def generate():
                with requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=60,
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                yield decoded + "\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
