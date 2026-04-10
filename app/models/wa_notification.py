from datetime import datetime
from app.extensions import db


class WaNotification(db.Model):
    __tablename__ = "wa_notifications"

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Text, nullable=False, index=True)
    contact_name = db.Column(db.Text, nullable=True)
    text = db.Column(db.Text, nullable=True)
    received_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read = db.Column(db.Boolean, default=False, index=True)
    replied = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id or "",
            "contact_name": self.contact_name or "",
            "text": self.text or "",
            "received_at": self.received_at.isoformat() if self.received_at else "",
            "read": bool(self.read),
            "replied": bool(self.replied),
        }
