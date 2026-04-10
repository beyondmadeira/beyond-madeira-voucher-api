from app.extensions import db
from app.models.mixins import AirtableSyncMixin


def _safe_float(v):
    """Convert any value to float, tolerantly stripping €, spaces and converting , to ."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace("€", "").replace("\u20ac", "").replace(",", ".").strip()
        return float(s) if s else 0.0
    except (ValueError, TypeError):
        return 0.0


class RegistoDiario(AirtableSyncMixin, db.Model):
    __tablename__ = "registo_diario"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text)
    faturacao = db.Column(db.Numeric(10, 2), default=0)
    faturacao_rc = db.Column(db.Numeric(10, 2), default=0)
    faturacao_at = db.Column(db.Numeric(10, 2), default=0)
    notas = db.Column(db.Text)
    responsavel = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "data": self.data or "",
            "fat": _safe_float(self.faturacao),
            "fatRC": _safe_float(self.faturacao_rc),
            "fatAT": _safe_float(self.faturacao_at),
            "obs": self.notas or "",
            "resp": self.responsavel or "",
        }


class DespesaFixa(AirtableSyncMixin, db.Model):
    __tablename__ = "despesa_fixa"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text)
    valor = db.Column(db.Numeric(10, 2), default=0)
    mes = db.Column(db.Text)
    categoria = db.Column(db.Text)
    pago = db.Column(db.Boolean, default=False)
    fatura = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "descricao": self.nome or "",
            "valor": _safe_float(self.valor),
            "mes": self.mes or "",
            "categoria": self.categoria or "",
            "pago": self.pago or False,
            "fatura": self.fatura or False,
            "tipo": "fixa",
        }


class DespesaVariavel(AirtableSyncMixin, db.Model):
    __tablename__ = "despesa_variavel"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text)
    valor = db.Column(db.Numeric(10, 2), default=0)
    mes = db.Column(db.Text)
    categoria = db.Column(db.Text)
    pago = db.Column(db.Boolean, default=False)
    fatura = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "descricao": self.nome or "",
            "valor": _safe_float(self.valor),
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
            "fat": _safe_float(self.faturacao),
        }


class ResumoMensal(AirtableSyncMixin, db.Model):
    __tablename__ = "resumo_mensal"

    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Text)
    faturacao = db.Column(db.Numeric(12, 2), default=0)
    comissoes = db.Column(db.Numeric(10, 2), default=0)
    despesas = db.Column(db.Numeric(10, 2), default=0)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "mes": self.mes or "",
            "fat": _safe_float(self.faturacao),
            "com": _safe_float(self.comissoes),
            "desp": _safe_float(self.despesas),
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
