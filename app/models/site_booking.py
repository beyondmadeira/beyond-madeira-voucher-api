from datetime import datetime, timezone
from app.extensions import db


class SiteBooking(db.Model):
    __tablename__ = "site_bookings"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.Text, nullable=False)  # 'rc' or 'at'
    status = db.Column(db.Text, nullable=False, default="pending")  # pending/confirmed/ignored
    raw_email = db.Column(db.Text)
    parsed_data = db.Column(db.Text)  # JSON string
    nome = db.Column(db.Text)
    email = db.Column(db.Text)
    tel = db.Column(db.Text)
    ref = db.Column(db.Text, unique=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    confirmed_at = db.Column(db.DateTime, nullable=True)
    whatsapp_sent = db.Column(db.Boolean, default=False)
    email_sent = db.Column(db.Boolean, default=False)

    def to_api(self):
        import json
        parsed = {}
        if self.parsed_data:
            try:
                parsed = json.loads(self.parsed_data)
            except (json.JSONDecodeError, TypeError):
                parsed = {}
        return {
            "id": self.id,
            "tipo": self.tipo or "",
            "status": self.status or "pending",
            "raw_email": self.raw_email or "",
            "parsed_data": parsed,
            "nome": self.nome or "",
            "email": self.email or "",
            "tel": self.tel or "",
            "ref": self.ref or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else "",
            "whatsapp_sent": self.whatsapp_sent or False,
            "email_sent": self.email_sent or False,
        }
