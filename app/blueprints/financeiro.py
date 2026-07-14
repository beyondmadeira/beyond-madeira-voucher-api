from flask import Blueprint, request, jsonify
from app.extensions import db
from app.utils.auth import require_api_key
from app.models.financeiro import (
    RegistoDiario, DespesaFixa, DespesaVariavel,
    Objetivo, ResumoMensal, CaixaMensal,
)
from app.models.reservas import Parceiro

bp = Blueprint("financeiro", __name__)


def _parceiro_names():
    """Nomes de parceiros/fornecedores já registados no sistema (não são despesas próprias)."""
    return [
        p.nome.strip().lower()
        for p in Parceiro.query.filter(Parceiro.nome.isnot(None)).all()
        if p.nome and len(p.nome.strip()) >= 4
    ]


def _is_parceiro_despesa(nome, parceiro_names):
    if not nome:
        return False
    n = nome.lower()
    return any(pn in n for pn in parceiro_names)


# ── Registos Diários ──────────────────────────────────────────────────────

@bp.route("/airtable/diario", methods=["GET", "POST", "PATCH"])
@require_api_key
def airtable_diario():
    try:
        if request.method == "GET":
            records = RegistoDiario.query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})
        elif request.method == "POST":
            body = request.get_json() or {}
            fields = body.get("fields", {})
            fat_val = fields.get("Faturação Diária", fields.get("Faturacao Diaria", 0))
            try:
                fat_val = float(str(fat_val).replace("€", "").replace(",", ".").strip() or 0)
            except (ValueError, TypeError):
                fat_val = 0
            rec = RegistoDiario(
                data=fields.get("Data", fields.get("Date", "")),
                faturacao=fat_val,
                faturacao_rc=float(fields.get("Faturação RC", 0) or 0),
                faturacao_at=float(fields.get("Faturação AT", 0) or 0),
                notas=fields.get("Notas do Dia", ""),
                responsavel=fields.get("Responsável", ""),
                dirty=True,
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})
        else:
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/airtable/diario/<record_id>", methods=["PATCH"])
@require_api_key
def patch_diario(record_id):
    try:
        body = request.get_json() or {}
        fields = body.get("fields", {})
        rec = RegistoDiario.query.filter_by(airtable_id=record_id).first()
        if not rec:
            return jsonify({"error": "Record not found"}), 404
        if "Faturação Diária" in fields:
            try:
                rec.faturacao = float(str(fields["Faturação Diária"]).replace("€", "").replace(",", ".").strip() or 0)
            except (ValueError, TypeError):
                pass
        if "Faturação RC" in fields:
            rec.faturacao_rc = float(fields["Faturação RC"] or 0)
        if "Faturação AT" in fields:
            rec.faturacao_at = float(fields["Faturação AT"] or 0)
        if "Notas do Dia" in fields:
            rec.notas = fields["Notas do Dia"]
        if "Responsável" in fields:
            rec.responsavel = fields["Responsável"]
        rec.dirty = True
        db.session.commit()
        return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Despesas Fixas ────────────────────────────────────────────────────────

@bp.route("/airtable/despesas-fixas", methods=["GET", "POST"])
@bp.route("/airtable/despesas-fixas/<record_id>", methods=["PATCH", "DELETE"])
@require_api_key
def despesas_fixas(**kwargs):
    return _handle_despesa(DespesaFixa, kwargs.get("record_id", ""))


# ── Despesas Variáveis ────────────────────────────────────────────────────

@bp.route("/airtable/despesas-variaveis", methods=["GET", "POST"])
@bp.route("/airtable/despesas-variaveis/<record_id>", methods=["PATCH", "DELETE"])
@bp.route("/airtable/financeiro/despesas", methods=["GET", "POST"])
@bp.route("/airtable/financeiro/despesas/<record_id>", methods=["PATCH", "DELETE"])
@require_api_key
def despesas_variaveis(**kwargs):
    return _handle_despesa(DespesaVariavel, kwargs.get("record_id", ""))


def _handle_despesa(Model, record_id):
    try:
        if request.method == "GET":
            records = Model.query.all()
            incluir_parceiros = request.args.get("incluir_parceiros", "").lower() in ("1", "true", "yes")
            if incluir_parceiros:
                return jsonify({"success": True, "records": [r.to_api() for r in records]})

            parceiro_names = _parceiro_names()
            proprios, excluidos = [], []
            for r in records:
                api = r.to_api()
                if _is_parceiro_despesa(api.get("nome"), parceiro_names):
                    excluidos.append(api)
                else:
                    proprios.append(api)
            return jsonify({
                "success": True,
                "records": proprios,
                "parceiros_excluidos": len(excluidos),
            })

        elif request.method == "POST":
            body = request.get_json() or {}
            fields = body.get("fields", body)
            rec = Model(
                nome=fields.get("Fornecedor", fields.get("nome", fields.get("descricao", ""))),
                valor=float(fields.get("Valor", fields.get("valor", 0)) or 0),
                categoria=fields.get("Categoria", fields.get("categoria", "")),
                pago=bool(fields.get("Pago?", fields.get("pago", False))),
                mes=fields.get("Notas", fields.get("mes", "")),
                dirty=True,
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})

        elif request.method == "PATCH":
            rec = Model.query.filter_by(airtable_id=record_id).first()
            if not rec:
                try:
                    rec = Model.query.get(int(record_id))
                except (ValueError, TypeError):
                    pass
            if not rec:
                return jsonify({"error": "Record not found"}), 404
            body = request.get_json() or {}
            fields = body.get("fields", body)
            if "pago" in fields or "Pago?" in fields:
                rec.pago = bool(fields.get("Pago?", fields.get("pago", False)))
            if "valor" in fields or "Valor" in fields:
                rec.valor = float(fields.get("Valor", fields.get("valor", 0)) or 0)
            if "nome" in fields or "Fornecedor" in fields:
                rec.nome = fields.get("Fornecedor", fields.get("nome", ""))
            if "mes" in fields or "Notas" in fields:
                rec.mes = fields.get("Notas", fields.get("mes", rec.mes))
            if "categoria" in fields or "Categoria" in fields:
                rec.categoria = fields.get("Categoria", fields.get("categoria", rec.categoria))
            if "fatura" in fields or "Fatura Guardada" in fields:
                rec.fatura = bool(fields.get("Fatura Guardada", fields.get("fatura", False)))
            rec.dirty = True
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})

        elif request.method == "DELETE":
            rec = Model.query.filter_by(airtable_id=record_id).first()
            if not rec:
                try:
                    rec = Model.query.get(int(record_id))
                except (ValueError, TypeError):
                    pass
            if not rec:
                return jsonify({"error": "Record not found"}), 404
            db.session.delete(rec)
            db.session.commit()
            return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Objetivos ─────────────────────────────────────────────────────────────

@bp.route("/airtable/objetivos", methods=["GET", "POST"])
@require_api_key
def objetivos():
    try:
        if request.method == "GET":
            records = Objetivo.query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})
        else:
            body = request.get_json() or {}
            fields = body.get("fields", {})
            rec = Objetivo(
                mes=fields.get("Mês", fields.get("Mes", 0)),
                ano=fields.get("Ano", 0),
                faturacao=float(fields.get("Faturação", fields.get("Faturacao", fields.get("Objetivo", 0))) or 0),
                dirty=True,
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Resumos Mensais ───────────────────────────────────────────────────────

@bp.route("/airtable/resumos-mensais", methods=["GET"])
@require_api_key
def resumos_mensais():
    try:
        records = ResumoMensal.query.all()
        return jsonify({"success": True, "records": [r.to_api() for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Caixa Mensal ──────────────────────────────────────────────────────────

@bp.route("/airtable/caixa-mensal", methods=["GET", "POST"])
@bp.route("/airtable/caixa-mensal/<record_id>", methods=["PATCH"])
@require_api_key
def caixa_mensal(**kwargs):
    try:
        if request.method == "GET":
            records = CaixaMensal.query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})
        elif request.method == "POST":
            body = request.get_json() or {}
            fields = body.get("fields", {})
            rec = CaixaMensal(raw_fields=fields, dirty=True)
            db.session.add(rec)
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})
        else:
            record_id = kwargs.get("record_id", "")
            rec = CaixaMensal.query.filter_by(airtable_id=record_id).first()
            if not rec:
                try:
                    rec = CaixaMensal.query.get(int(record_id))
                except (ValueError, TypeError):
                    pass
            if not rec:
                return jsonify({"error": "Record not found"}), 404
            body = request.get_json() or {}
            fields = body.get("fields", body)
            raw = rec.raw_fields or {}
            raw.update(fields)
            rec.raw_fields = raw
            rec.dirty = True
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
