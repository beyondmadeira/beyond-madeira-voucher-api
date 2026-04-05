from app.extensions import db
from app.models.mixins import AirtableSyncMixin


class RegistoDiario(AirtableSyncMixin, db.Model):
    __tablename__ = "registo_diario"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(50))
    faturacao = db.Column(db.Numeric(10, 2), default=0)
    faturacao_rc = db.Column(db.Numeric(10, 2), default=0)
    faturacao_at = db.Column(db.Numeric(10, 2), default=0)
    notas = db.Column(db.Text)
    responsavel = db.Column(db.String(100))

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "data": self.data or "",
            "fat": float(self.faturacao or 0),
            "fatRC": float(self.faturacao_rc or 0),
            "fatAT": float(self.faturacao_at or 0),
            "obs": self.notas or "",
            "resp": self.responsavel or "",
        }


class DespesaFixa(AirtableSyncMixin, db.Model):
    __tablename__ = "despesa_fixa"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    valor = db.Column(db.Numeric(10, 2), default=0)
    mes = db.Column(db.String(50))
    categoria = db.Column(db.String(100))
    pago = db.Column(db.Boolean, default=False)
    fatura = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "descricao": self.nome or "",
            "valor": float(self.valor or 0),
            "mes": self.mes or "",
            "categoria": self.categoria or "",
            "pago": self.pago or False,
            "fatura": self.fatura or False,
            "tipo": "fixa",
        }


class DespesaVariavel(AirtableSyncMixin, db.Model):
    __tablename__ = "despesa_variavel"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    valor = db.Column(db.Numeric(10, 2), default=0)
    mes = db.Column(db.String(50))
    categoria = db.Column(db.String(100))
    pago = db.Column(db.Boolean, default=False)
    fatura = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "descricao": self.nome or "",
            "valor": float(self.valor or 0),
            "mes": self.mes or "",
            "categoria": self.categoria or "",
            "pago": self.pago or False,
            "fatura": self.fatura or False,
            "tipo": "variavel",
        }


class Objetivo(AirtableSyncMixin, db.Model):
    __tablename__ = "objetivo"

    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer)
    ano = db.Column(db.Integer)
    faturacao = db.Column(db.Numeric(12, 2), default=0)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "mes": self.mes or 0,
            "ano": self.ano or 0,
            "fat": float(self.faturacao or 0),
        }


class ResumoMensal(AirtableSyncMixin, db.Model):
    __tablename__ = "resumo_mensal"

    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.String(50))
    faturacao = db.Column(db.Numeric(12, 2), default=0)
    comissoes = db.Column(db.Numeric(10, 2), default=0)
    despesas = db.Column(db.Numeric(10, 2), default=0)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "mes": self.mes or "",
            "fat": float(self.faturacao or 0),
            "com": float(self.comissoes or 0),
            "desp": float(self.despesas or 0),
        }


class CaixaMensal(AirtableSyncMixin, db.Model):
    __tablename__ = "caixa_mensal"

    id = db.Column(db.Integer, primary_key=True)
    raw_fields = db.Column(db.JSON, default=dict)

    def to_api(self):
        out = {"id": self.airtable_id or str(self.id)}
        if self.raw_fields:
            out.update(self.raw_fields)
        return out
