from datetime import datetime
from app.extensions import db


class ApiUsageLog(db.Model):
    """Registo de cada chamada à API da Anthropic (Claude).

    Serve para responder à pergunta "onde vai o dinheiro?": quem chamou,
    que modelo, quantos tokens e o custo estimado. Escrito em best-effort
    — nunca deve bloquear a resposta ao utilizador.
    """
    __tablename__ = "api_usage_log"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.Text)          # ex.: /api/chat, /ai/parse-reserva
    model = db.Column(db.Text)
    user_name = db.Column(db.Text)         # quem/que agente originou a chamada
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cache_read_tokens = db.Column(db.Integer, default=0)
    cache_write_tokens = db.Column(db.Integer, default=0)
    est_cost_usd = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_api(self):
        return {
            "id": self.id,
            "endpoint": self.endpoint or "",
            "model": self.model or "",
            "user_name": self.user_name or "",
            "input_tokens": self.input_tokens or 0,
            "output_tokens": self.output_tokens or 0,
            "cache_read_tokens": self.cache_read_tokens or 0,
            "cache_write_tokens": self.cache_write_tokens or 0,
            "est_cost_usd": round(self.est_cost_usd or 0.0, 5),
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }
