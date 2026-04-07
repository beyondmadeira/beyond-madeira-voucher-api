from flask import Blueprint, request, jsonify
from app.extensions import db
from app.utils.auth import require_api_key
from app.models.reservas import RentCar, Atividade, Parceiro, Tarefa, Nota

bp = Blueprint("reservas", __name__)


# ── Rent Car ──────────────────────────────────────────────────────────────

@bp.route("/airtable/rc", methods=["GET"])
@require_api_key
def get_rc():
    try:
        records = RentCar.query.all()
        out = [r.to_api() for r in records]
        return jsonify({"success": True, "records": out})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/airtable/rc/<record_id>", methods=["PATCH"])
@require_api_key
def patch_rc(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400

        rec = RentCar.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404

        _apply_rc_fields(rec, fields)
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _apply_rc_fields(rec, fields):
    """Apply Airtable-named fields to a RentCar model."""
    mapping = {
        "Referência": "ref", "Referencia": "ref",
        "Nome do cliente": "nome", "Nome do Cliente": "nome",
        "Número de Telemovel": "tel", "Telefone": "tel",
        "Email do cliente": "email", "Email": "email",
        "Idade": "idade",
        "Fornecedor/Parceiro": "parceiro", "Parceiro": "parceiro",
        "Carro": "carro", "Veículo": "carro",
        "Estado de Reserva": "estado", "Estado da Reserva": "estado",
        "Estado de Pagamento": "pagamento", "Pagamento": "pagamento",
        "Data da Pick-up": "pickup_data", "Data Pick-up": "pickup_data",
        "Localização Pick-up": "pickup_local", "Local Pick-up": "pickup_local",
        "Voo Pick-up": "pickup_voo",
        "Detalhes Pick Up": "pickup_detalhe",
        "Data do Drop Off": "dropoff_data", "Data Drop-off": "dropoff_data",
        "Localização Drop-off": "dropoff_local", "Local Drop-off": "dropoff_local",
        "Voo Drop-off": "dropoff_voo",
        "Detalhes Drop Off": "dropoff_detalhe",
        "Valor da Reserva (€)": "total", "Total": "total",
        "Comissão": "comissao", "Comissao": "comissao",
        "Duração": "duracao", "Duracao": "duracao",
        "Extras": "extras",
        "Observações": "observacoes", "Observacoes": "observacoes",
        "Referência Parceiro": "ref_parceiro",
        "Email Enviado": "email_enviado",
        "Review Enviado": "review_enviado",
    }
    for at_name, pg_col in mapping.items():
        if at_name in fields:
            val = fields[at_name]
            if isinstance(val, list) and val:
                val = val[0]
            setattr(rec, pg_col, val)


# ── Atividades ────────────────────────────────────────────────────────────

@bp.route("/airtable/at", methods=["GET"])
@require_api_key
def get_at():
    try:
        records = Atividade.query.all()
        out = [r.to_api() for r in records]
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/at/<record_id>", methods=["PATCH"])
@require_api_key
def patch_at(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        if not fields:
            return jsonify({"error": "No fields provided"}), 400

        rec = Atividade.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404

        _apply_at_fields(rec, fields)
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _apply_at_fields(rec, fields):
    mapping = {
        "Referência": "ref", "Referencia": "ref",
        "Nome do Cliente": "nome",
        "Contacto Telefonico": "tel", "Telefone": "tel",
        "Email Clientes": "email", "Email": "email",
        "Atividade": "atividade",
        "Categoria": "categoria",
        "Fornecedor/Parceiro": "parceiro", "Parceiro": "parceiro",
        "Nº Pessoas": "pax", "Pessoas": "pax",
        "Data da Atividade": "data", "Data": "data",
        "Hora": "hora",
        "Preço Total": "total", "Valor da Reserva (€)": "total", "Total": "total",
        "Comissão": "comissao", "Comissao": "comissao",
        "Estado da Reserva": "estado",
        "Estado de Pagamento": "pagamento", "Pagamento": "pagamento",
        "Observação": "observacoes", "Observacoes": "observacoes",
        "Pick-up local": "local_pickup", "Local": "local_pickup",
        "Stripe Link": "stripe_link",
        "Idiomas": "idiomas",
        "Email Enviado": "email_enviado",
        "Thank You Enviado": "thankyou_enviado",
        "Review Pedida": "review_pedida",
    }
    for at_name, pg_col in mapping.items():
        if at_name in fields:
            val = fields[at_name]
            if isinstance(val, list) and val:
                val = val[0]
            setattr(rec, pg_col, val)


# ── Parceiros ─────────────────────────────────────────────────────────────

@bp.route("/airtable/parceiros", methods=["GET"])
@require_api_key
def get_parceiros():
    try:
        records = Parceiro.query.all()
        out = [r.to_api() for r in records]
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/parceiros/<record_id>", methods=["PATCH"])
@require_api_key
def patch_parceiro(record_id):
    try:
        fields = (request.get_json() or {}).get("fields", {})
        row = Parceiro.query.filter(
            (Parceiro.airtable_id == record_id) | (Parceiro.id == int(record_id) if record_id.isdigit() else False)
        ).first()
        if not row:
            return jsonify({"error": "not found"}), 404
        field_map = {
            "Telefone": "telefone", "Email": "email", "Notas": "notas",
            "Comissão Valor": "comissao_valor", "Tipo Comissao": "comissao_tipo",
            "Instruções Aeroporto": "instrucoes_aeroporto", "Instruções Hotel": "instrucoes_hotel",
        }
        for airtable_name, col in field_map.items():
            if airtable_name in fields and hasattr(row, col):
                setattr(row, col, fields[airtable_name])
        row._dirty = True
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/frota", methods=["GET"])
@require_api_key
def get_frota():
    """Return fleet data — currently from Parceiro-linked data or empty."""
    return jsonify({"success": True, "records": []})


@bp.route("/airtable/disponibilidade", methods=["GET"])
@require_api_key
def get_disponibilidade():
    """Return availability blocks — currently empty."""
    return jsonify({"success": True, "records": []})


@bp.route("/airtable/clientes", methods=["GET"])
@require_api_key
def get_clientes():
    """Build client list from RC + AT reservations."""
    try:
        clients = {}
        for r in RentCar.query.all():
            api = r.to_api()
            key = (api.get("email") or api.get("nome") or "").lower()
            if not key:
                continue
            if key not in clients:
                clients[key] = {"nome": api.get("nome",""), "email": api.get("email",""),
                                "tel": api.get("tel",""), "n_rc": 0, "n_at": 0,
                                "total_gasto": 0, "vip": False}
            clients[key]["n_rc"] += 1
            clients[key]["total_gasto"] += float(api.get("total", 0) or 0)
        for r in Atividade.query.all():
            api = r.to_api()
            key = (api.get("email") or api.get("nome") or "").lower()
            if not key:
                continue
            if key not in clients:
                clients[key] = {"nome": api.get("nome",""), "email": api.get("email",""),
                                "tel": api.get("tel",""), "n_rc": 0, "n_at": 0,
                                "total_gasto": 0, "vip": False}
            clients[key]["n_at"] += 1
            clients[key]["total_gasto"] += float(api.get("total", 0) or 0)
        out = sorted(clients.values(), key=lambda x: x["total_gasto"], reverse=True)
        for c in out:
            if c["total_gasto"] >= 500 or (c["n_rc"] + c["n_at"]) >= 5:
                c["vip"] = True
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Tarefas ───────────────────────────────────────────────────────────────

@bp.route("/airtable/tarefas", methods=["GET", "POST"])
@require_api_key
def tarefas():
    try:
        if request.method == "GET":
            records = Tarefa.query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})
        else:
            body = request.get_json() or {}
            fields = body.get("fields", {})
            rec = Tarefa(
                descricao=fields.get("Descrição", fields.get("Descricao", fields.get("Tarefa", ""))),
                status=fields.get("Status", fields.get("Estado", "pendente")),
                prioridade=fields.get("Prioridade", fields.get("Priority", "media")),
                responsavel=fields.get("Responsável", fields.get("Responsavel", "")),
                data=fields.get("Data", ""),
                feita=bool(fields.get("Feita", fields.get("Done", False))),
                dirty=True,
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": {"id": rec.airtable_id or str(rec.id), "fields": fields}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/tarefas/<record_id>", methods=["PATCH"])
@require_api_key
def patch_tarefa(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        rec = Tarefa.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404
        for at_name, pg_col in {
            "Descrição": "descricao", "Descricao": "descricao",
            "Status": "status", "Estado": "status",
            "Prioridade": "prioridade",
            "Responsável": "responsavel",
            "Data": "data",
            "Feita": "feita", "Done": "feita",
        }.items():
            if at_name in fields:
                setattr(rec, pg_col, fields[at_name])
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Notas ─────────────────────────────────────────────────────────────────

@bp.route("/airtable/notas", methods=["GET", "POST"])
@require_api_key
def notas():
    try:
        if request.method == "GET":
            records = Nota.query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})
        else:
            body = request.get_json() or {}
            fields = body.get("fields", {})
            rec = Nota(
                titulo=fields.get("Título", fields.get("Titulo", fields.get("Nome", ""))),
                texto=fields.get("Texto", fields.get("Nota", fields.get("Conteúdo", ""))),
                data=fields.get("Data", ""),
                cor=fields.get("Cor", ""),
                dirty=True,
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": {"id": rec.airtable_id or str(rec.id), "fields": fields}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/notas/<record_id>", methods=["PATCH", "DELETE"])
@require_api_key
def patch_nota(record_id):
    try:
        rec = Nota.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404

        if request.method == "DELETE":
            db.session.delete(rec)
            db.session.commit()
            return jsonify({"success": True})

        body = request.get_json() or {}
        fields = body.get("fields", {})
        for at_name, pg_col in {
            "Título": "titulo", "Titulo": "titulo", "Nome": "titulo",
            "Texto": "texto", "Nota": "texto",
            "Data": "data",
            "Cor": "cor",
        }.items():
            if at_name in fields:
                setattr(rec, pg_col, fields[at_name])
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
