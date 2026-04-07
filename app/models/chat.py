from datetime import datetime
from app.extensions import db


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, nullable=False)
    agent_name = db.Column(db.Text)
    title = db.Column(db.Text)
    messages = db.Column(db.JSON, default=list)
    user_name = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_api(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name or "",
            "title": self.title or "",
            "messages": self.messages or [],
            "user_name": self.user_name or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


class AgentNote(db.Model):
    __tablename__ = "agent_notes"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Text, nullable=False)  # RC, AT, Geral, Parceiros
    content = db.Column(db.Text, default="")
    user_name = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_api(self):
        return {
            "id": self.id,
            "category": self.category or "",
            "content": self.content or "",
            "user_name": self.user_name or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }
