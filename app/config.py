import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/beyond"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    VOUCHER_API_KEY = os.environ.get("VOUCHER_API_KEY", "beyond-madeira-voucher-2026")

    # Airtable
    AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
    BASE_RESERVAS = "appR8ZKP5ygR8o8Q0"
    BASE_CONHECIMENTO = "appKhPwEBxolWaO9r"
    BASE_EXTRATO = "appRGJjirAzgEe46q"
    BASE_FINANCEIRO = "appOrdG5Fsr7N0RmH"

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    # Wazzup
    WAZZUP_API_KEY = os.environ.get(
        "WAZZUP_API_KEY", "3c681e9848a14ceaa6c6bb1f27d33880"
    )
    WAZZUP_CHANNEL = os.environ.get(
        "WAZZUP_CHANNEL", "c01da476-ab8e-4997-872b-599767c16fc9"
    )

    # SMTP
    SMTP_USER = os.environ.get("SMTP_USER", "booking@beyondmadeira.com")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

    # Sync intervals (seconds)
    SYNC_PULL_INTERVAL = 300  # 5 min
    SYNC_PUSH_INTERVAL = 30
