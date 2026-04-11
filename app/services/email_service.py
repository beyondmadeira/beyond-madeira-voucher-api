"""Email sending service — Gmail API (OAuth2) with SMTP fallback."""

import base64
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import current_app


def _resolve_sender(kind):
    """Resolve sender credentials by kind ('hello' or 'info').

    Returns dict with: sender, gmail_client_id, gmail_client_secret,
    gmail_refresh_token, smtp_user, smtp_pass.

    Falls back to legacy shared GMAIL_SENDER / SMTP_USER if per-kind
    vars are not set, so the system keeps working until both mailboxes
    are configured in Railway.
    """
    cfg = current_app.config
    suffix = (kind or "").upper()

    sender = (
        cfg.get(f"GMAIL_SENDER_{suffix}")
        or cfg.get(f"SMTP_USER_{suffix}")
        or cfg.get("GMAIL_SENDER")
        or cfg.get("SMTP_USER", "")
    )

    refresh_token = (
        cfg.get(f"GMAIL_REFRESH_TOKEN_{suffix}")
        or cfg.get("GMAIL_REFRESH_TOKEN", "")
    )

    smtp_user = (
        cfg.get(f"SMTP_USER_{suffix}")
        or cfg.get(f"GMAIL_SENDER_{suffix}")
        or cfg.get("SMTP_USER", "")
    )

    smtp_pass = (
        cfg.get(f"SMTP_PASS_{suffix}")
        or cfg.get("SMTP_PASS", "")
    )

    return {
        "sender": sender,
        "gmail_client_id": cfg.get("GMAIL_CLIENT_ID", ""),
        "gmail_client_secret": cfg.get("GMAIL_CLIENT_SECRET", ""),
        "gmail_refresh_token": refresh_token,
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
    }


def _build_message(sender, to, subject, body_text=None, html_body=None,
                   pdf_b64=None, pdf_filename="attachment.pdf"):
    """Build a MIME message with optional PDF attachment."""
    msg = MIMEMultipart("mixed")
    msg["From"] = f"Beyond Madeira <{sender}>"
    msg["To"] = to
    msg["Subject"] = subject

    if html_body:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text or "Please view in HTML.", "plain"))
        alt.attach(MIMEText(html_body, "html"))
        msg.attach(alt)
    elif body_text:
        msg.attach(MIMEText(body_text, "plain"))

    if pdf_b64:
        import unicodedata, re
        raw = pdf_filename or "extrato.pdf"
        # Convert to ASCII-safe name: ã→a, ç→c, spaces→_
        safe = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
        safe = re.sub(r'[^\w.\-]', '_', safe)
        if not safe.endswith('.pdf'):
            safe += '.pdf'
        part = MIMEBase("application", "pdf", name=safe)
        part.set_payload(base64.b64decode(pdf_b64))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=safe)
        msg.attach(part)

    return msg


def _send_via_gmail_api(msg, creds=None):
    """Send email via Gmail API using OAuth2 refresh token.

    `creds` is the dict from _resolve_sender(); if None, falls back to
    the legacy shared config (backwards compat for any caller that
    didn't migrate yet).
    """
    cfg = current_app.config
    if creds:
        client_id = creds.get("gmail_client_id", "")
        client_secret = creds.get("gmail_client_secret", "")
        refresh_token = creds.get("gmail_refresh_token", "")
    else:
        client_id = cfg.get("GMAIL_CLIENT_ID", "")
        client_secret = cfg.get("GMAIL_CLIENT_SECRET", "")
        refresh_token = cfg.get("GMAIL_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Gmail API credentials not configured")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()


def _send_via_smtp(msg, creds=None):
    """Send email via SMTP (fallback). Tries SSL (465) then STARTTLS (587)."""
    cfg = current_app.config
    if creds:
        smtp_user = creds.get("smtp_user", "")
        smtp_pass = creds.get("smtp_pass", "")
    else:
        smtp_user = cfg.get("SMTP_USER", "")
        smtp_pass = cfg.get("SMTP_PASS", "")
    smtp_host = cfg.get("SMTP_HOST", "smtp.gmail.com")

    if not smtp_pass:
        raise ValueError("SMTP_PASS not configured")

    ctx = ssl.create_default_context()

    # Try SSL on 465 first (works on Railway and most cloud hosts)
    try:
        with smtplib.SMTP_SSL(smtp_host, 465, context=ctx, timeout=15) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, msg["To"], msg.as_string())
            return
    except Exception:
        pass

    # Fallback to STARTTLS on 587
    smtp_port = int(cfg.get("SMTP_PORT", 587))
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
        s.starttls(context=ctx)
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, msg["To"], msg.as_string())


def _send(msg, creds=None):
    """Try Gmail API first, fall back to SMTP."""
    has_gmail = bool(
        (creds and creds.get("gmail_refresh_token") and creds.get("gmail_client_id"))
        or (not creds and current_app.config.get("GMAIL_CLIENT_ID") and current_app.config.get("GMAIL_REFRESH_TOKEN"))
    )
    if has_gmail:
        _send_via_gmail_api(msg, creds=creds)
    else:
        _send_via_smtp(msg, creds=creds)


def send_html_email(to, subject, html_body, pdf_b64=None,
                    pdf_filename="attachment.pdf", sender_kind="hello"):
    """Send an HTML email.

    `sender_kind`: 'hello' (default — vouchers, confirmations, client
    emails) or 'info' (extratos for partners). Falls back to legacy
    shared GMAIL_SENDER if the per-kind env vars are not set yet.
    """
    creds = _resolve_sender(sender_kind)
    sender = creds["sender"]
    msg = _build_message(sender, to, subject, html_body=html_body,
                         pdf_b64=pdf_b64, pdf_filename=pdf_filename)
    _send(msg, creds=creds)


def send_plain_email(to, subject, body_text, pdf_b64=None,
                     pdf_filename="attachment.pdf", sender_kind="hello"):
    creds = _resolve_sender(sender_kind)
    sender = creds["sender"]
    msg = _build_message(sender, to, subject, body_text=body_text,
                         pdf_b64=pdf_b64, pdf_filename=pdf_filename)
    _send(msg, creds=creds)
