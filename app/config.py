import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/beyond"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    VOUCHER_API_KEY = os.environ.get("VOUCHER_API_KEY", "beyond-madeira-voucher-2026")

    # Sessões (login do hub Madeira Daily)
    SECRET_KEY = os.environ.get("SECRET_KEY", "beyond-madeira-hub-secret")

    # Madeira Daily hub — password de acesso (vazio = acesso aberto)
    MADEIRADAILY_PASSWORD = os.environ.get("MADEIRADAILY_PASSWORD", "madeira2026")

    # Airtable
    AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
    BASE_RESERVAS = "appR8ZKP5ygR8o8Q0"
    BASE_CONHECIMENTO = "appKhPwEBxolWaO9r"
    BASE_EXTRATO = "appRGJjirAzgEe46q"
    BASE_FINANCEIRO = "appOrdG5Fsr7N0RmH"

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    # Wazzup (env vars — never hardcode API keys in source)
    WAZZUP_API_KEY = os.environ.get("WAZZUP_API_KEY", "")
    WAZZUP_CHANNEL = os.environ.get("WAZZUP_CHANNEL", "")
    WAZZUP_WEBHOOK_SECRET = os.environ.get("WAZZUP_WEBHOOK_SECRET", "")

    # SMTP (legacy fallback — usado se as vars per-kind não estiverem definidas)
    SMTP_USER = os.environ.get("SMTP_USER", "booking@beyondmadeira.com")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

    # Gmail API (OAuth2) — legacy shared (fallback)
    GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "")
    GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "booking@beyondmadeira.com")

    # ── Per-sender credentials ────────────────────────────────────────
    # HELLO: vouchers, confirmações, pickup updates, emails ao cliente
    GMAIL_SENDER_HELLO = os.environ.get("GMAIL_SENDER_HELLO", "")
    GMAIL_REFRESH_TOKEN_HELLO = os.environ.get("GMAIL_REFRESH_TOKEN_HELLO", "")
    SMTP_USER_HELLO = os.environ.get("SMTP_USER_HELLO", "")
    SMTP_PASS_HELLO = os.environ.get("SMTP_PASS_HELLO", "")

    # INFO: extratos para parceiros
    GMAIL_SENDER_INFO = os.environ.get("GMAIL_SENDER_INFO", "")
    GMAIL_REFRESH_TOKEN_INFO = os.environ.get("GMAIL_REFRESH_TOKEN_INFO", "")
    SMTP_USER_INFO = os.environ.get("SMTP_USER_INFO", "")
    SMTP_PASS_INFO = os.environ.get("SMTP_PASS_INFO", "")

    # Sync intervals (seconds)
    SYNC_PULL_INTERVAL = 300  # 5 min
    SYNC_PUSH_INTERVAL = 30
