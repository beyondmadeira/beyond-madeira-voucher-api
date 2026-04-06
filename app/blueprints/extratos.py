import re
import base64
from datetime import datetime
from collections import defaultdict
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.utils.auth import require_api_key
from app.utils.formatting import eur_val, norm_act
from app.models.reservas import RentCar, Atividade
from app.models.extrato import ComissaoParceiro
from app.services.pdf import build_extrato_html, calc_totais, generate_pdf

bp = Blueprint("extratos", __name__)

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _parse_mes_ano(mes_raw, ano_raw=None):
    mes_num = 0
    ano = 0
    if isinstance(mes_raw, str) and " " in mes_raw:
        parts = mes_raw.strip().split()
        if len(parts) == 2:
            for i, m in enumerate(MESES_PT):
                if m.lower() == parts[0].lower():
                    mes_num = i
                    break
            try:
                ano = int(parts[1])
            except (ValueError, TypeError):
                ano = datetime.now().year
    else:
        try:
            mes_num = int(mes_raw)
        except (ValueError, TypeError):
            mes_num = datetime.now().month
        try:
            ano = int(ano_raw) if ano_raw else datetime.now().year
        except (ValueError, TypeError):
            ano = datetime.now().year
    return mes_num, ano


def _normalize_status(status_raw):
    if status_raw in ("Cancelado", "Cancelada"):
        return "Cancelado"
    if status_raw == "Devemos":
        return "Devemos"
    if status_raw == "Pago":
        return "Pago"
    return "Por Pagar"


def _norm_name(s):
    """Normalize partner name for fuzzy matching (remove spaces, hyphens, lowercase)."""
    import re
    return re.sub(r'[\s\-_]+', '', (s or '')).lower()


def _names_match(a, b):
    """Fuzzy match two partner names (exact, or one contains the other)."""
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _build_rows_from_pg(parceiro, mes_num, ano):
    """Build extrato rows from PostgreSQL data."""
    rows = []

    # Rent Car records — fuzzy match on parceiro name
    for rec in RentCar.query.all():
        if not _names_match(rec.parceiro, parceiro):
            continue
        raw_date = rec.dropoff_data or ""
        if not raw_date:
            continue
        try:
            dt = datetime.fromisoformat(str(raw_date)[:10])
            if dt.month != mes_num or dt.year != ano:
                continue
        except (ValueError, TypeError):
            continue
        rows.append(dict(
            date=dt.strftime("%d/%m"),
            ref=rec.ref or rec.airtable_id or "",
            client=rec.nome or "",
            act=norm_act(rec.carro or ""),
            pax=str(rec.duracao or ""),
            total=float(rec.total or 0),
            comm=float(rec.comissao or 0),
            status=_normalize_status(rec.estado or ""),
            ddt=raw_date,
        ))

    # Activity records — fuzzy match on parceiro name
    for rec in Atividade.query.all():
        if not _names_match(rec.parceiro, parceiro):
            continue
        raw_date = rec.data or ""
        if not raw_date:
            continue
        try:
            dt = datetime.fromisoformat(str(raw_date)[:10])
            if dt.month != mes_num or dt.year != ano:
                continue
        except (ValueError, TypeError):
            continue
        rows.append(dict(
            date=dt.strftime("%d/%m"),
            ref=rec.ref or rec.airtable_id or "",
            client=rec.nome or "",
            act=norm_act(rec.atividade or ""),
            pax=str(rec.pax or ""),
            total=float(rec.total or 0),
            comm=float(rec.comissao or 0),
            status=_normalize_status(rec.estado or ""),
            ddt=raw_date,
        ))

    rows.sort(key=lambda x: x["date"])
    return rows


def _gerar_extrato_interno(parceiro, mes_str, tipo="", meses=None):
    """Generate extrato PDF internally. Supports multi-month (accumulated)."""
    all_months = meses or [mes_str]
    all_rows = []
    rows_by_month = {}
    for m in all_months:
        mn, yr = _parse_mes_ano(m, None)
        r = _build_rows_from_pg(parceiro, mn, yr)
        lbl = f"{MESES_PT[mn] if 1 <= mn <= 12 else str(mn)} {yr}"
        rows_by_month[lbl] = r
        all_rows.extend(r)

    mes_num, ano = _parse_mes_ano(mes_str, None)
    mes_nome = MESES_PT[mes_num] if 1 <= mes_num <= 12 else str(mes_num)
    tots = calc_totais(all_rows)
    sl = re.sub(r"[^a-zA-Z0-9]", "", parceiro)
    ref = f"EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}"
    fname = f"BeyondMadeira_{sl}_{mes_nome}{ano}.pdf"
    html_str = build_extrato_html(
        parceiro, all_rows, ref, mes_nome, ano, tots,
        rows_by_month=rows_by_month if len(all_months) > 1 else None,
    )
    pdf_bytes = generate_pdf(html_str)
    b64 = base64.b64encode(pdf_bytes).decode()
    return {
        "success": True,
        "filename": fname,
        "pdf_base64": b64,
        "reservas": all_rows,
        "total": tots["total_fim"],
        "total_fim": tots["total_fim"],
    }


@bp.route("/gerar-extrato-parceiro", methods=["POST"])
@require_api_key
def gerar_extrato_parceiro():
    try:
        d = request.get_json() or {}
        result = _gerar_extrato_interno(
            d.get("parceiro", ""), d.get("mes", ""), d.get("tipo", ""),
            meses=d.get("meses"),
        )
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/gerar-extratos-mes", methods=["POST"])
@require_api_key
def gerar_extratos_mes():
    try:
        d = request.get_json() or {}
        mes_str = d.get("mes", "")
        mes_num, ano = _parse_mes_ano(mes_str)
        if not mes_num:
            return jsonify({"error": "Invalid mes format. Use 'Março 2026'"}), 400
        mes_nome = MESES_PT[mes_num]

        # Get all partners from both RC and AT tables
        partners = set()
        for rec in RentCar.query.all():
            if rec.parceiro:
                # Check date matches
                raw = rec.dropoff_data or ""
                try:
                    dt = datetime.fromisoformat(str(raw)[:10])
                    if dt.month == mes_num and dt.year == ano:
                        partners.add(rec.parceiro)
                except (ValueError, TypeError):
                    pass
        for rec in Atividade.query.all():
            if rec.parceiro:
                raw = rec.data or ""
                try:
                    dt = datetime.fromisoformat(str(raw)[:10])
                    if dt.month == mes_num and dt.year == ano:
                        partners.add(rec.parceiro)
                except (ValueError, TypeError):
                    pass

        results = []
        total_geral = 0

        for par in sorted(partners):
            try:
                rows = _build_rows_from_pg(par, mes_num, ano)
                tots = calc_totais(rows)
                sl = re.sub(r"[^a-zA-Z0-9]", "", par)
                ref = f"EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}"
                fname = f"BeyondMadeira_{sl}_{mes_nome}{ano}.pdf"
                html_str = build_extrato_html(par, rows, ref, mes_nome, ano, tots)
                pdf_bytes = generate_pdf(html_str)
                b64 = base64.b64encode(pdf_bytes).decode()
                total_geral += abs(tots["total_fim"])
                results.append({
                    "parceiro": par,
                    "success": True,
                    "filename": fname,
                    "pdf_base64": b64,
                    "total": tots["total_fim"],
                })
            except Exception as ep:
                results.append({"parceiro": par, "success": False, "error": str(ep)})

        return jsonify({"success": True, "results": results, "total_geral": total_geral})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Extrato Parceiros (comissões) ─────────────────────────────────────────

@bp.route("/airtable/extrato-parceiros", methods=["GET"])
@bp.route("/airtable/extrato-parceiros/<record_id>", methods=["GET", "PATCH"])
@bp.route("/airtable/extrato-parceiros/criar-mes", methods=["POST"])
@require_api_key
def extrato_parceiros(**kwargs):
    try:
        if request.method == "GET":
            mes = request.args.get("mes", "")
            ano = request.args.get("ano", "")
            query = ComissaoParceiro.query
            if mes:
                query = query.filter(ComissaoParceiro.mes == mes)
            elif ano:
                query = query.filter(ComissaoParceiro.mes.contains(ano))
            records = query.all()
            return jsonify({"success": True, "records": [r.to_api() for r in records]})

        elif request.method == "PATCH":
            record_id = kwargs.get("record_id", "")
            rec = ComissaoParceiro.query.filter_by(airtable_id=record_id).first()
            if not rec:
                return jsonify({"error": "Record not found"}), 404
            body = request.get_json() or {}
            fields = body.get("fields", {})
            for at_name, pg_col in {
                "Parceiro": "parceiro",
                "Mês": "mes", "Mes": "mes",
                "Valor do mês (€)": "valor", "Valor": "valor",
                "Ajustes / Atrasos (€)": "ajustes",
                "Total a Receber (€)": "total", "Total": "total",
                "Recebido?": "recebido",
                "Data de Recebimento": "data_recebimento",
                "Mail enviado / pedido?": "mail_enviado",
                "Acumulado": "acumulado",
            }.items():
                if at_name in fields:
                    val = fields[at_name]
                    if pg_col in ("recebido", "mail_enviado", "acumulado"):
                        val = val in (True, "checked", "true")
                    elif pg_col in ("valor", "ajustes", "total"):
                        try:
                            val = float(val or 0)
                        except (ValueError, TypeError):
                            val = 0
                    setattr(rec, pg_col, val)
            rec.dirty = True
            db.session.commit()
            return jsonify({"success": True, "record": rec.to_api()})

        else:
            return jsonify({"success": True, "records": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
