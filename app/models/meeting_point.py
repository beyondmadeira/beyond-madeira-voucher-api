from datetime import datetime
from app.extensions import db


class MeetingPoint(db.Model):
    __tablename__ = "meeting_points"

    id = db.Column(db.Integer, primary_key=True)
    parceiro = db.Column(db.Text, nullable=False)
    atividade = db.Column(db.Text)  # optional — specific activity
    local = db.Column(db.Text)  # name/description
    maps_link = db.Column(db.Text)  # Google Maps link
    notas = db.Column(db.Text)  # partner-specific notes
    pickup_mode = db.Column(db.Text, default="meeting_point")  # meeting_point / pickup_day_before
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_api(self):
        return {
            "id": self.id,
            "parceiro": self.parceiro or "",
            "atividade": self.atividade or "",
            "local": self.local or "",
            "maps_link": self.maps_link or "",
            "notas": self.notas or "",
            "pickup_mode": self.pickup_mode or "meeting_point",
        }
