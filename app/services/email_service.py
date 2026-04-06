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
        part = MIMEBase("application", "octet-stream")
        part.set_payload(base64.b64decode(pdf_b64))
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{pdf_filename}"'
        )
        msg.attach(part)

    return msg


def _send_via_gmail_api(msg):
    """Send email via Gmail API using OAuth2 refresh token."""
    cfg = current_app.config
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


def _send_via_smtp(msg, sender):
    """Send email via SMTP (fallback)."""
    cfg = current_app.config
    smtp_pass = cfg["SMTP_PASS"]
    smtp_host = cfg["SMTP_HOST"]
    smtp_port = cfg["SMTP_PORT"]

    if not smtp_pass:
        raise ValueError("SMTP_PASS not configured")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ctx)
        s.login(sender, smtp_pass)
        s.sendmail(sender, msg["To"], msg.as_string())


def _send(msg, sender):
    """Try Gmail API first, fall back to SMTP."""
    cfg = current_app.config
    if cfg.get("GMAIL_CLIENT_ID") and cfg.get("GMAIL_REFRESH_TOKEN"):
        _send_via_gmail_api(msg)
    else:
        _send_via_smtp(msg, sender)


def send_html_email(to, subject, html_body, pdf_b64=None,
                    pdf_filename="attachment.pdf"):
    sender = current_app.config.get("GMAIL_SENDER",
                                     current_app.config["SMTP_USER"])
    msg = _build_message(sender, to, subject, html_body=html_body,
                         pdf_b64=pdf_b64, pdf_filename=pdf_filename)
    _send(msg, sender)


def send_plain_email(to, subject, body_text, pdf_b64=None,
                     pdf_filename="attachment.pdf"):
    sender = current_app.config.get("GMAIL_SENDER",
                                     current_app.config["SMTP_USER"])
    msg = _build_message(sender, to, subject, body_text=body_text,
                         pdf_b64=pdf_b64, pdf_filename=pdf_filename)
    _send(msg, sender)
