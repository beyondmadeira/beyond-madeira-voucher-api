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


def _sync_all_comissoes():
    """Auto-sync commission records for all months that have reservations."""
    from app.services.airtable_client import airtable_create
    months_seen = set()
    for rc in RentCar.query.all():
        if not rc.dropoff_data or rc.estado == "Cancelado":
            continue
        try:
            dt = datetime.fromisoformat(str(rc.dropoff_data)[:10])
            months_seen.add((dt.month, dt.year))
        except (ValueError, TypeError):
            pass
    for at in Atividade.query.all():
        if (at.estado or "") == "Cancelado" or not at.data:
            continue
        try:
            dt = datetime.fromisoformat(str(at.data)[:10])
            months_seen.add((dt.month, dt.year))
        except (ValueError, TypeError):
            pass

    for mes_num, ano in sorted(months_seen):
        mes_label = f"{MESES_PT[mes_num] if 1 <= mes_num <= 12 else str(mes_num)} {ano}"
        partners = {}
        for rc in RentCar.query.all():
            if not rc.dropoff_data or rc.estado == "Cancelado":
                continue
            try:
                dt = datetime.fromisoformat(str(rc.dropoff_data)[:10])
                if dt.month != mes_num or dt.year != ano:
                    continue
            except (ValueError, TypeError):
                continue
            par = (rc.parceiro or "").strip()
            if par:
                partners[par] = partners.get(par, 0) + float(rc.comissao or 0)
        for at in Atividade.query.all():
            if (at.estado or "") == "Cancelado" or not at.data:
                continue
            try:
                dt = datetime.fromisoformat(str(at.data)[:10])
                if dt.month != mes_num or dt.year != ano:
                    continue
            except (ValueError, TypeError):
                continue
            par = (at.parceiro or "").strip()
            if par:
                partners[par] = partners.get(par, 0) + float(at.comissao or 0)

        for par_name, com_val in partners.items():
            com_val = round(com_val, 2)
            existing = ComissaoParceiro.query.filter_by(parceiro=par_name, mes=mes_label).first()
            if not existing:
                all_recs = ComissaoParceiro.query.filter_by(mes=mes_label).all()
                for r in all_recs:
                    if _names_match(r.parceiro, par_name):
                        existing = r
                        break
            if existing:
                if abs(float(existing.valor or 0) - com_val) > 0.01:
                    existing.valor = com_val
                    existing.total = com_val + float(existing.ajustes or 0)
                    existing.dirty = True
            else:
                at_id = None
                try:
                    at_result = airtable_create(
                        "appRGJjirAzgEe46q", "Comissões Parceiros",
                        {"Parceiro": par_name, "Mês": mes_label,
                         "Valor do mês (€)": com_val, "Total a Receber (€)": com_val}
                    )
                    at_id = at_result.get("id", "")
                except Exception:
                    pass
                rec = ComissaoParceiro(
                    parceiro=par_name, mes=mes_label,
                    valor=com_val, total=com_val,
                    airtable_id=at_id or None, dirty=not bool(at_id),
                )
                db.session.add(rec)
        db.session.commit()
    print(f"[COMISSOES SYNC] Synced {len(months_seen)} months")


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


@bp.route("/gerar-extrato-manual", methods=["POST"])
@require_api_key
def gerar_extrato_manual():
    """Generate extrato PDF from manually provided rows (no DB lookup)."""
    try:
        d = request.get_json() or {}
        parceiro = d.get("parceiro", "")
        mes_str = d.get("mes", "")
        rows_raw = d.get("rows", [])
        if not parceiro or not rows_raw:
            return jsonify({"error": "parceiro and rows required"}), 400

        mes_num, ano = _parse_mes_ano(mes_str)
        if not mes_num:
            return jsonify({"error": "Invalid mes"}), 400
        mes_nome = MESES_PT[mes_num]

        rows = []
        for r in rows_raw:
            rows.append(dict(
                date=r.get("date", ""),
                ref=r.get("ref", ""),
                client=r.get("client", ""),
                act=r.get("act", ""),
                pax=str(r.get("pax", "")),
                total=float(r.get("total", 0)),
                comm=float(r.get("comm", 0)),
                status=r.get("status", "Confirmado"),
                ddt=r.get("date", ""),
            ))

        tots = calc_totais(rows)
        sl = re.sub(r"[^a-zA-Z0-9]", "", parceiro)
        ref = f"EXT-{ano}-{str(mes_num).zfill(2)}-{sl[:10].upper()}"
        fname = f"BeyondMadeira_{sl}_{mes_nome}{ano}.pdf"
        html_str = build_extrato_html(parceiro, rows, ref, mes_nome, ano, tots)
        pdf_bytes = generate_pdf(html_str)
        b64 = base64.b64encode(pdf_bytes).decode()
        return jsonify({
            "success": True, "filename": fname, "pdf_base64": b64,
            "total": tots["total_fim"],
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


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
@bp.route("/airtable/extrato-parceiros/<record_id>", methods=["GET", "PATCH", "DELETE"])
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
                # Fallback: try by numeric PG id
                try:
                    rec = ComissaoParceiro.query.get(int(record_id))
                except (ValueError, TypeError):
                    pass
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
                "Confirmado pelo parceiro?": "confirmado_parceiro",
                "Confirmado pela Beyond Madeira?": "confirmado_beyond",
                "Acumulado": "acumulado",
            }.items():
                if at_name in fields:
                    val = fields[at_name]
                    if pg_col in ("recebido", "mail_enviado", "acumulado", "confirmado_parceiro", "confirmado_beyond"):
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

        elif request.method == "DELETE":
            record_id = kwargs.get("record_id", "")
            rec = ComissaoParceiro.query.filter_by(airtable_id=record_id).first()
            if not rec:
                try:
                    rec = ComissaoParceiro.query.get(int(record_id))
                except (ValueError, TypeError):
                    pass
            if rec:
                # Also delete from Airtable if has airtable_id
                if rec.airtable_id:
                    try:
                        from app.services.airtable_client import airtable_delete
                        airtable_delete("appRGJjirAzgEe46q", "Comissões Parceiros", rec.airtable_id)
                    except Exception:
                        pass
                db.session.delete(rec)
                db.session.commit()
                return jsonify({"success": True})
            else:
                # Try delete from Airtable directly even if not in PG
                if record_id.startswith("rec"):
                    try:
                        from app.services.airtable_client import airtable_delete
                        airtable_delete("appRGJjirAzgEe46q", "Comissões Parceiros", record_id)
                        return jsonify({"success": True})
                    except Exception as e:
                        return jsonify({"error": str(e)}), 500
                return jsonify({"error": "Record not found"}), 404

        elif request.method == "POST":
            # criar-mes: auto-create/update extrato records for all partners in a month
            body = request.get_json() or {}
            mes_str = body.get("mes", "")
            if not mes_str:
                return jsonify({"error": "mes required"}), 400

            mes_num, ano = _parse_mes_ano(mes_str, None)
            mes_label = f"{MESES_PT[mes_num] if 1 <= mes_num <= 12 else str(mes_num)} {ano}"

            # Gather all partners from RC and AT for this month
            partners = {}
            for rc in RentCar.query.all():
                if not rc.dropoff_data or rc.estado == "Cancelado":
                    continue
                try:
                    dt = datetime.fromisoformat(str(rc.dropoff_data)[:10])
                    if dt.month != mes_num or dt.year != ano:
                        continue
                except (ValueError, TypeError):
                    continue
                par = (rc.parceiro or "").strip()
                if not par:
                    continue
                if par not in partners:
                    partners[par] = {"valor": 0, "total": 0}
                partners[par]["valor"] += float(rc.comissao or 0)

            for at in Atividade.query.all():
                est = (at.estado or "").strip()
                if est == "Cancelado":
                    continue
                if not at.data:
                    continue
                try:
                    dt = datetime.fromisoformat(str(at.data)[:10])
                    if dt.month != mes_num or dt.year != ano:
                        continue
                except (ValueError, TypeError):
                    continue
                par = (at.parceiro or "").strip()
                if not par:
                    continue
                if par not in partners:
                    partners[par] = {"valor": 0, "total": 0}
                partners[par]["valor"] += float(at.comissao or 0)

            created = 0
            updated = 0
            for par_name, vals in partners.items():
                com_val = round(vals["valor"], 2)
                # Find existing record
                existing = ComissaoParceiro.query.filter_by(
                    parceiro=par_name, mes=mes_label
                ).first()
                if not existing:
                    # Try fuzzy match
                    all_recs = ComissaoParceiro.query.filter_by(mes=mes_label).all()
                    for r in all_recs:
                        if _names_match(r.parceiro, par_name):
                            existing = r
                            break

                if existing:
                    if abs(float(existing.valor or 0) - com_val) > 0.01:
                        existing.valor = com_val
                        existing.total = com_val + float(existing.ajustes or 0)
                        existing.dirty = True
                        updated += 1
                else:
                    # Create in Airtable first, then save with airtable_id
                    at_id = None
                    try:
                        from app.services.airtable_client import airtable_create
                        at_result = airtable_create(
                            "appRGJjirAzgEe46q",
                            "Comissões Parceiros",
                            {
                                "Parceiro": par_name,
                                "Mês": mes_label,
                                "Valor do mês (€)": com_val,
                                "Total a Receber (€)": com_val,
                            }
                        )
                        at_id = at_result.get("id", "")
                    except Exception as at_err:
                        print(f"[CRIAR-MES] Airtable create failed for {par_name}: {at_err}")

                    rec = ComissaoParceiro(
                        parceiro=par_name,
                        mes=mes_label,
                        valor=com_val,
                        total=com_val,
                        airtable_id=at_id or None,
                        dirty=not bool(at_id),
                    )
                    db.session.add(rec)
                    created += 1

            db.session.commit()
            return jsonify({
                "success": True,
                "mes": mes_label,
                "created": created,
                "updated": updated,
                "partners": len(partners),
            })

        else:
            return jsonify({"success": True, "records": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
