from app.extensions import db
from app.models.mixins import AirtableSyncMixin


class Sitemap(AirtableSyncMixin, db.Model):
    __tablename__ = "sitemap"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text)
    estado = db.Column(db.Text)
    categoria_principal = db.Column(db.Text)
    url = db.Column(db.Text)
    categoria = db.Column(db.Text)
    conteudo = db.Column(db.Text)
    modified = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "nome": self.nome or "",
            "estado": self.estado or "",
            "categoria": self.categoria_principal or "",
            "url": self.url or "",
            "cat": self.categoria or "",
            "conteudo": self.conteudo or "",
            "modified": self.modified or "",
        }


class Biblioteca(AirtableSyncMixin, db.Model):
    __tablename__ = "biblioteca"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text)
    gatilho = db.Column(db.Text)
    resposta = db.Column(db.Text)
    categoria = db.Column(db.Text)
    estado = db.Column(db.Text)
    observacoes = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "titulo": self.titulo or "",
            "gatilho": self.gatilho or "",
            "resposta": self.resposta or "",
            "categoria": self.categoria or "",
            "estado": self.estado or "",
            "obs": self.observacoes or "",
        }


class MadeiraGuide(AirtableSyncMixin, db.Model):
    __tablename__ = "madeira_guide"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text)
    categoria = db.Column(db.Text)
    descricao = db.Column(db.Text)
    localizacao = db.Column(db.Text)
    estado = db.Column(db.Text)
    prioridade = db.Column(db.Text)
    tags = db.Column(db.Text)
    notas = db.Column(db.Text)
    recomendado = db.Column(db.Boolean, default=False)
    preco_nivel = db.Column(db.Text)
    horario = db.Column(db.Text)
    distancia = db.Column(db.Text)
    dificuldade = db.Column(db.Text)
    website = db.Column(db.Text)
    contacto = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "titulo": self.titulo or "",
            "categoria": self.categoria or "",
            "descricao": self.descricao or "",
            "localizacao": self.localizacao or "",
            "estado": self.estado or "",
            "prioridade": self.prioridade or "",
            "tags": self.tags or "",
            "notas": self.notas or "",
            "recomendado": self.recomendado or False,
            "preco": self.preco_nivel or "",
            "horario": self.horario or "",
            "distancia": self.distancia or "",
            "dificuldade": self.dificuldade or "",
            "website": self.website or "",
            "contacto": self.contacto or "",
        }


class TemplateMensagem(AirtableSyncMixin, db.Model):
    __tablename__ = "template_mensagem"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    empresa = db.Column(db.Text)
    categoria = db.Column(db.Text)
    contexto = db.Column(db.Text)
    msg_en = db.Column(db.Text)
    msg_pt = db.Column(db.Text)
    msg_fr = db.Column(db.Text)
    subj_en = db.Column(db.Text)
    subj_pt = db.Column(db.Text)
    idioma = db.Column(db.Text)

    def to_api(self):
        return {
            "id": self.airtable_id or str(self.id),
            "name": self.name or "",
            "nome": self.name or "",
            "label": self.name or "",
            "empresa": self.empresa or "",
            "categoria": self.categoria or "",
            "contexto": self.contexto or "",
            "msg_en": self.msg_en or "",
            "msg_pt": self.msg_pt or "",
            "msg_fr": self.msg_fr or "",
            "subj_en": self.subj_en or "",
            "subj_pt": self.subj_pt or "",
            "text_en": self.msg_en or "",
            "text_pt": self.msg_pt or "",
            "text": self.msg_pt or self.msg_en or "",
            "subject": self.subj_pt or self.subj_en or "",
            "idioma": self.idioma or "EN",
        }
