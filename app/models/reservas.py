from app.extensions import db
from app.models.mixins import AirtableSyncMixin


class RentCar(AirtableSyncMixin, db.Model):
    __tablename__ = "rent_car"

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(50))
    nome = db.Column(db.String(200))
    tel = db.Column(db.String(50))
    email = db.Column(db.String(200))
    idade = db.Column(db.String(20))
    parceiro = db.Column(db.String(200))
    carro = db.Column(db.String(200))
    estado = db.Column(db.String(50))
    pagamento = db.Column(db.String(50))
    pickup_data = db.Column(db.String(50))
    pickup_local = db.Column(db.String(300))
    pickup_voo = db.Column(db.String(50))
    pickup_detalhe = db.Column(db.Text)
    dropoff_data = db.Column(db.String(50))
    dropoff_local = db.Column(db.String(300))
    dropoff_voo = db.Column(db.String(50))
    dropoff_detalhe = db.Column(db.Text)
    total = db.Column(db.Numeric(10, 2), default=0)
    comissao = db.Column(db.Numeric(10, 2), default=0)
    duracao = db.Column(db.Integer, default=0)
    extras = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    ref_parceiro = db.Column(db.String(100))
    email_enviado = db.Column(db.Boolean, default=False)
    review_enviado = db.Column(db.Boolean, default=False)
    data_feita = db.Column(db.String(50))

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "ref": self.ref or "",
            "nome": self.nome or "",
            "tel": self.tel or "",
            "email": self.email or "",
            "idade": self.idade or "",
            "parceiro": self.parceiro or "",
            "carro": self.carro or "",
            "estado": self.estado or "",
            "pagamento": self.pagamento or "",
            "pdt": self.pickup_data or "",
            "ploc": self.pickup_local or "",
            "pvoo": self.pickup_voo or "",
            "pdet": self.pickup_detalhe or "",
            "ddt": self.dropoff_data or "",
            "dloc": self.dropoff_local or "",
            "dvoo": self.dropoff_voo or "",
            "ddet": self.dropoff_detalhe or "",
            "total": float(self.total or 0),
            "com": float(self.comissao or 0),
            "dur": self.duracao or 0,
            "ext": self.extras or "",
            "obs": self.observacoes or "",
            "refp": self.ref_parceiro or "",
            "eEnv": self.email_enviado or False,
            "rEnv": self.review_enviado or False,
            "dataFeita": self.data_feita or "",
        }


class Atividade(AirtableSyncMixin, db.Model):
    __tablename__ = "atividade"

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(50))
    nome = db.Column(db.String(200))
    tel = db.Column(db.String(50))
    email = db.Column(db.String(200))
    atividade = db.Column(db.String(200))
    categoria = db.Column(db.String(100))
    parceiro = db.Column(db.String(200))
    pax = db.Column(db.String(20))
    data = db.Column(db.String(50))
    hora = db.Column(db.String(20))
    total = db.Column(db.Numeric(10, 2), default=0)
    comissao = db.Column(db.Numeric(10, 2), default=0)
    estado = db.Column(db.String(50))
    pagamento = db.Column(db.String(50))
    observacoes = db.Column(db.Text)
    local_pickup = db.Column(db.String(300))
    stripe_link = db.Column(db.String(500))
    idiomas = db.Column(db.String(100))
    email_enviado = db.Column(db.Boolean, default=False)
    thankyou_enviado = db.Column(db.Boolean, default=False)
    review_pedida = db.Column(db.Boolean, default=False)
    data_feita = db.Column(db.String(50))

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "ref": self.ref or "",
            "nome": self.nome or "",
            "tel": self.tel or "",
            "email": self.email or "",
            "atv": self.atividade or "",
            "cat": self.categoria or "",
            "par": self.parceiro or "",
            "pess": self.pax or "",
            "data": self.data or "",
            "hora": self.hora or "",
            "total": float(self.total or 0),
            "com": float(self.comissao or 0),
            "estado": self.estado or "",
            "estado_res": self.estado or "",
            "pagamento": self.pagamento or "",
            "obs": self.observacoes or "",
            "local": self.local_pickup or "",
            "stripe": self.stripe_link or "",
            "idiomas": self.idiomas or "",
            "eEnv": self.email_enviado or False,
            "tyEnv": self.thankyou_enviado or False,
            "rEnv": self.review_pedida or False,
            "dataFeita": self.data_feita or "",
        }


class Parceiro(AirtableSyncMixin, db.Model):
    __tablename__ = "parceiro"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    email = db.Column(db.String(200))
    telefone = db.Column(db.String(50))
    tipo = db.Column(db.String(100))
    ativo = db.Column(db.Boolean, default=True)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "email": self.email or "",
            "telefone": self.telefone or "",
            "tipo": self.tipo or "",
            "ativo": self.ativo if self.ativo is not None else True,
        }


class Tarefa(AirtableSyncMixin, db.Model):
    __tablename__ = "tarefa"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(50), default="pendente")
    prioridade = db.Column(db.String(20), default="media")
    responsavel = db.Column(db.String(100))
    data = db.Column(db.String(50))
    feita = db.Column(db.Boolean, default=False)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "desc": self.descricao or "",
            "status": self.status or "pendente",
            "pri": self.prioridade or "media",
            "resp": self.responsavel or "",
            "data": self.data or "",
            "feita": self.feita or False,
        }


class Nota(AirtableSyncMixin, db.Model):
    __tablename__ = "nota"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    texto = db.Column(db.Text)
    data = db.Column(db.String(50))
    cor = db.Column(db.String(30))

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "titulo": self.titulo or "",
            "texto": self.texto or "",
            "data": self.data or "",
            "cor": self.cor or "",
        }
