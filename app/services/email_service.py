"""SMTP email sending service."""

import base64
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import current_app


def send_html_email(to, subject, html_body, pdf_b64=None, pdf_filename="attachment.pdf"):
    cfg = current_app.config
    smtp_user = cfg["SMTP_USER"]
    smtp_pass = cfg["SMTP_PASS"]
    smtp_host = cfg["SMTP_HOST"]
    smtp_port = cfg["SMTP_PORT"]

    if not smtp_pass:
        raise ValueError("SMTP_PASS not configured")

    msg = MIMEMultipart("mixed")
    msg["From"] = f"Beyond Madeira <{smtp_user}>"
    msg["To"] = to
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Please view this email in an HTML-capable client.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if pdf_b64:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(base64.b64decode(pdf_b64))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
        msg.attach(part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ctx)
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, to, msg.as_string())


def send_plain_email(to, subject, body_text, pdf_b64=None, pdf_filename="attachment.pdf"):
    cfg = current_app.config
    smtp_user = cfg["SMTP_USER"]
    smtp_pass = cfg["SMTP_PASS"]
    smtp_host = cfg["SMTP_HOST"]
    smtp_port = cfg["SMTP_PORT"]

    if not smtp_pass:
        raise ValueError("SMTP_PASS not configured")

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if pdf_b64:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(base64.b64decode(pdf_b64))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
        msg.attach(part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ctx)
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, to, msg.as_string())
