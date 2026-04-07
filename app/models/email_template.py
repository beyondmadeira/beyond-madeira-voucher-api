from datetime import datetime
from app.extensions import db


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.Text, unique=True, nullable=False)  # sunrise, dolphins, generic
    name = db.Column(db.Text)
    subject = db.Column(db.Text)
    body_html = db.Column(db.Text)  # Full HTML or template with {{placeholders}}
    no_payment_link = db.Column(db.Boolean, default=False)
    activities = db.Column(db.Text)  # comma-separated activity keywords
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_api(self):
        return {
            "id": self.id,
            "key": self.key or "",
            "name": self.name or "",
            "subject": self.subject or "",
            "body_html": self.body_html or "",
            "no_payment_link": self.no_payment_link or False,
            "activities": self.activities or "",
            "notes": self.notes or "",
        }
