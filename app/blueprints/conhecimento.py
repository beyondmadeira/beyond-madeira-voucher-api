from flask import Blueprint, request, jsonify
from app.extensions import db
from app.utils.auth import require_api_key
from app.models.conhecimento import Sitemap, Biblioteca, MadeiraGuide, TemplateMensagem

bp = Blueprint("conhecimento", __name__)


# ── Sitemap ───────────────────────────────────────────────────────────────

@bp.route("/airtable/sitemap", methods=["GET"])
@require_api_key
def get_sitemap():
    try:
        records = Sitemap.query.all()
        return jsonify({"success": True, "records": [r.to_api() for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/sitemap/<record_id>", methods=["PATCH"])
@require_api_key
def patch_sitemap(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        rec = Sitemap.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404
        for at_name, pg_col in {
            "Nome de Página": "nome", "Nome de Pagina": "nome",
            "Estado": "estado",
            "Categoria Principal": "categoria_principal",
            "URL": "url",
            "Categoria": "categoria",
            "Conteúdo": "conteudo", "Conteudo": "conteudo",
        }.items():
            if at_name in fields:
                setattr(rec, pg_col, fields[at_name])
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Biblioteca ────────────────────────────────────────────────────────────

@bp.route("/airtable/biblioteca", methods=["GET"])
@require_api_key
def get_biblioteca():
    try:
        records = Biblioteca.query.all()
        return jsonify({"success": True, "records": [r.to_api() for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/biblioteca/<record_id>", methods=["PATCH"])
@require_api_key
def patch_biblioteca(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        rec = Biblioteca.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404
        for at_name, pg_col in {
            "Answer Title": "titulo",
            "Trigger": "gatilho", "Customer Question": "gatilho",
            "Answer": "resposta",
            "Category": "categoria",
            "Status": "estado",
            "Observação": "observacoes", "Observacao": "observacoes",
        }.items():
            if at_name in fields:
                setattr(rec, pg_col, fields[at_name])
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Guia Madeira ──────────────────────────────────────────────────────────

@bp.route("/airtable/guia", methods=["GET"])
@require_api_key
def get_guia():
    try:
        records = MadeiraGuide.query.all()
        return jsonify({"success": True, "records": [r.to_api() for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/guia/<record_id>", methods=["PATCH"])
@require_api_key
def patch_guia(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        rec = MadeiraGuide.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404
        for at_name, pg_col in {
            "Nome": "titulo",
            "Categoria": "categoria",
            "Descrição": "descricao", "Descricao": "descricao",
            "Localização": "localizacao", "Localizacao": "localizacao",
            "Estado": "estado",
            "Prioridade": "prioridade",
            "Tags": "tags",
            "Notas Internas": "notas",
            "Recomendado?": "recomendado",
            "Preço Nível": "preco_nivel",
            "Horário": "horario", "Horario": "horario",
            "Distância": "distancia", "Distancia": "distancia",
            "Dificuldade": "dificuldade",
            "Website": "website",
            "Contacto": "contacto",
        }.items():
            if at_name in fields:
                setattr(rec, pg_col, fields[at_name])
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── WA Templates ──────────────────────────────────────────────────────────

@bp.route("/airtable/wa-templates", methods=["GET"])
@require_api_key
def get_wa_templates():
    try:
        records = TemplateMensagem.query.all()
        return jsonify({"success": True, "records": [r.to_api() for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
