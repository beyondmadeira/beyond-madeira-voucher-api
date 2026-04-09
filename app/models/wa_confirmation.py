from datetime import datetime
from app.extensions import db


class WaConfirmation(db.Model):
    __tablename__ = "wa_confirmations"

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Text, nullable=False, index=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied = db.Column(db.Boolean, default=False)
    replied_at = db.Column(db.DateTime, nullable=True)

    def to_api(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id or "",
            "sent_at": self.sent_at.isoformat() if self.sent_at else "",
            "replied": self.replied,
            "replied_at": self.replied_at.isoformat() if self.replied_at else "",
        }
