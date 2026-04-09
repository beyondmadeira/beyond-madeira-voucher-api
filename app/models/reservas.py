from app.extensions import db
from app.models.mixins import AirtableSyncMixin


class RentCar(AirtableSyncMixin, db.Model):
    __tablename__ = "rent_car"

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.Text)
    nome = db.Column(db.Text)
    tel = db.Column(db.Text)
    email = db.Column(db.Text)
    idade = db.Column(db.Text)
    parceiro = db.Column(db.Text)
    carro = db.Column(db.Text)
    estado = db.Column(db.Text)
    pagamento = db.Column(db.Text)
    pickup_data = db.Column(db.Text)
    pickup_local = db.Column(db.Text)
    pickup_voo = db.Column(db.Text)
    pickup_detalhe = db.Column(db.Text)
    dropoff_data = db.Column(db.Text)
    dropoff_local = db.Column(db.Text)
    dropoff_voo = db.Column(db.Text)
    dropoff_detalhe = db.Column(db.Text)
    total = db.Column(db.Numeric(10, 2), default=0)
    comissao = db.Column(db.Numeric(10, 2), default=0)
    duracao = db.Column(db.Integer, default=0)
    extras = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    ref_parceiro = db.Column(db.Text)
    email_enviado = db.Column(db.Boolean, default=False)
    review_enviado = db.Column(db.Boolean, default=False)
    data_feita = db.Column(db.Text)

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
    ref = db.Column(db.Text)
    nome = db.Column(db.Text)
    tel = db.Column(db.Text)
    email = db.Column(db.Text)
    atividade = db.Column(db.Text)
    categoria = db.Column(db.Text)
    parceiro = db.Column(db.Text)
    pax = db.Column(db.Text)
    data = db.Column(db.Text)
    hora = db.Column(db.Text)
    total = db.Column(db.Numeric(10, 2), default=0)
    comissao = db.Column(db.Numeric(10, 2), default=0)
    estado = db.Column(db.Text)
    pagamento = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    local_pickup = db.Column(db.Text)
    stripe_link = db.Column(db.Text)
    idiomas = db.Column(db.Text)
    email_enviado = db.Column(db.Boolean, default=False)
    thankyou_enviado = db.Column(db.Boolean, default=False)
    review_pedida = db.Column(db.Boolean, default=False)
    data_feita = db.Column(db.Text)

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
    nome = db.Column(db.Text)
    categoria = db.Column(db.Text)
    email = db.Column(db.Text)
    telefone = db.Column(db.Text)
    website = db.Column(db.Text)
    morada_office = db.Column(db.Text)
    comissao_tipo = db.Column(db.Text)
    comissao_valor = db.Column(db.Text)
    comissao_notas = db.Column(db.Text)
    instrucoes_aeroporto = db.Column(db.Text)
    instrucoes_hotel = db.Column(db.Text)
    instrucoes_office = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    notas = db.Column(db.Text)
    atividades = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    # Legacy
    tipo = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "categoria": self.categoria or self.tipo or "",
            "email": self.email or "",
            "tel": self.telefone or "",
            "website": self.website or "",
            "morada_office": self.morada_office or "",
            "comissao_tipo": self.comissao_tipo or "",
            "comissao_valor": self.comissao_valor or "",
            "comissao_notas": self.comissao_notas or "",
            "instrucoes_aeroporto": self.instrucoes_aeroporto or "",
            "instrucoes_hotel": self.instrucoes_hotel or "",
            "instrucoes_office": self.instrucoes_office or "",
            "logo_url": self.logo_url or "",
            "notas": self.notas or "",
            "atividades": self.atividades or "",
            "ativo": self.ativo if self.ativo is not None else True,
        }


class Tarefa(AirtableSyncMixin, db.Model):
    __tablename__ = "tarefa"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.Text)
    status = db.Column(db.Text, default="pendente")
    prioridade = db.Column(db.Text, default="media")
    responsavel = db.Column(db.Text)
    data = db.Column(db.Text)
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
    titulo = db.Column(db.Text)
    texto = db.Column(db.Text)
    data = db.Column(db.Text)
    cor = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "titulo": self.titulo or "",
            "texto": self.texto or "",
            "data": self.data or "",
            "cor": self.cor or "",
        }
