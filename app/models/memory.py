from datetime import datetime
from app.extensions import db


class BeyondMemory(db.Model):
    __tablename__ = "beyond_memory"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Text, nullable=False)  # parceiro, regra, insight, padrao
    key = db.Column(db.Text)  # partner name or rule identifier
    content = db.Column(db.Text)  # the actual knowledge
    source = db.Column(db.Text)  # who/what added it: user, agent, system
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_api(self):
        return {
            "id": self.id,
            "category": self.category or "",
            "key": self.key or "",
            "content": self.content or "",
            "source": self.source or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }
