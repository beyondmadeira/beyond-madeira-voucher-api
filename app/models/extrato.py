from app.extensions import db
from app.models.mixins import AirtableSyncMixin


class ComissaoParceiro(AirtableSyncMixin, db.Model):
    __tablename__ = "comissao_parceiro"

    id = db.Column(db.Integer, primary_key=True)
    parceiro = db.Column(db.String(200))
    mes = db.Column(db.String(50))
    valor = db.Column(db.Numeric(10, 2), default=0)
    ajustes = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    recebido = db.Column(db.Boolean, default=False)
    data_recebimento = db.Column(db.String(50))
    mail_enviado = db.Column(db.Boolean, default=False)
    acumulado = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "parceiro": self.parceiro or "",
            "mes": self.mes or "",
            "valor": float(self.valor or 0),
            "ajustes": float(self.ajustes or 0),
            "total": float(self.total or 0),
            "recebido": self.recebido or False,
            "dataRecebimento": self.data_recebimento or "",
            "mailEnviado": self.mail_enviado or False,
            "acumulado": self.acumulado or False,
        }
