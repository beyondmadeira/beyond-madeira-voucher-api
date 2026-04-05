"""
Bidirectional Airtable sync engine.

PG is source of truth. Push local changes to Airtable, pull remote changes back.
"""

import click
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.services.airtable_client import airtable_list, airtable_patch, airtable_create
from app.services.airtable_field_maps import FIELD_MAPS
from app.models.reservas import RentCar, Atividade, Parceiro, Tarefa, Nota
from app.models.conhecimento import Sitemap, Biblioteca, MadeiraGuide, TemplateMensagem
from app.models.financeiro import (
    RegistoDiario, DespesaFixa, DespesaVariavel,
    Objetivo, ResumoMensal, CaixaMensal,
)
from app.models.extrato import ComissaoParceiro


MODEL_REGISTRY = {
    "RentCar": RentCar,
    "Atividade": Atividade,
    "Parceiro": Parceiro,
    "Tarefa": Tarefa,
    "Nota": Nota,
    "Sitemap": Sitemap,
    "Biblioteca": Biblioteca,
    "MadeiraGuide": MadeiraGuide,
    "TemplateMensagem": TemplateMensagem,
    "ComissaoParceiro": ComissaoParceiro,
    "RegistoDiario": RegistoDiario,
    "DespesaFixa": DespesaFixa,
    "DespesaVariavel": DespesaVariavel,
    "Objetivo": Objetivo,
    "ResumoMensal": ResumoMensal,
    "CaixaMensal": CaixaMensal,
}


def _read_at_field(fields, at_field_names):
    """Read a value from Airtable fields dict, trying multiple field names."""
    for name in at_field_names:
        if name in fields and fields[name] not in (None, "", []):
            val = fields[name]
            # Handle linked record arrays (take first element)
            if isinstance(val, list) and len(val) > 0:
                val = val[0]
            return val
    return None


def _coerce_value(val, column):
    """Coerce an Airtable value to the expected Python/PG type."""
    if val is None:
        return None
    col_type = str(column.type)
    if "NUMERIC" in col_type:
        try:
            s = str(val).replace("\u20ac", "").replace(",", ".").strip()
            return float(s) if s else 0
        except (ValueError, TypeError):
            return 0
    if "INTEGER" in col_type:
        try:
            return int(float(str(val)))
        except (ValueError, TypeError):
            return 0
    if "BOOLEAN" in col_type:
        if isinstance(val, bool):
            return val
        return val in (True, "checked", "true", "True", 1, "1")
    return str(val) if val is not None else None


def pull_table(model_name):
    """Pull all records from Airtable into PG for a given model."""
    fmap = FIELD_MAPS.get(model_name)
    if not fmap:
        return 0
    Model = MODEL_REGISTRY[model_name]
    base_id = fmap["airtable_base"]
    table = fmap["airtable_table"]
    field_defs = fmap["fields"]

    records = airtable_list(base_id, table, max_records=10000)
    count = 0

    for rec in records:
        at_id = rec["id"]
        f = rec.get("fields", {})

        existing = Model.query.filter_by(airtable_id=at_id).first()

        if existing and existing.dirty:
            continue  # local change takes precedence

        if not existing:
            existing = Model(airtable_id=at_id)
            db.session.add(existing)

        # Special handling for CaixaMensal (raw pass-through)
        if model_name == "CaixaMensal":
            existing.raw_fields = f
        else:
            for pg_col, at_names in field_defs.items():
                val = _read_at_field(f, at_names)
                column = Model.__table__.columns.get(pg_col)
                if column is not None:
                    setattr(existing, pg_col, _coerce_value(val, column))

        existing.synced_at = datetime.now(timezone.utc)
        existing.dirty = False
        count += 1

    db.session.commit()
    return count


def push_dirty(model_name):
    """Push all dirty records from PG to Airtable."""
    fmap = FIELD_MAPS.get(model_name)
    if not fmap:
        return 0
    Model = MODEL_REGISTRY[model_name]
    base_id = fmap["airtable_base"]
    table = fmap["airtable_table"]
    field_defs = fmap["fields"]

    dirty_records = Model.query.filter_by(dirty=True).all()
    count = 0

    for record in dirty_records:
        at_fields = {}

        if model_name == "CaixaMensal":
            at_fields = record.raw_fields or {}
        else:
            for pg_col, at_names in field_defs.items():
                val = getattr(record, pg_col, None)
                if val is not None:
                    at_fields[at_names[0]] = val  # write to first field name

        try:
            if record.airtable_id:
                airtable_patch(base_id, table, record.airtable_id, at_fields)
            else:
                result = airtable_create(base_id, table, at_fields)
                record.airtable_id = result["id"]

            record.dirty = False
            record.synced_at = datetime.now(timezone.utc)
            count += 1
        except Exception as e:
            print(f"[SYNC PUSH ERROR] {model_name} id={record.id}: {e}")

    db.session.commit()
    return count


def pull_all():
    """Pull all tables from Airtable."""
    total = 0
    for name in MODEL_REGISTRY:
        try:
            n = pull_table(name)
            print(f"[SYNC PULL] {name}: {n} records")
            total += n
        except Exception as e:
            print(f"[SYNC PULL ERROR] {name}: {e}")
    return total


def push_all_dirty():
    """Push all dirty records across all tables."""
    total = 0
    for name in MODEL_REGISTRY:
        try:
            n = push_dirty(name)
            if n:
                print(f"[SYNC PUSH] {name}: {n} records")
            total += n
        except Exception as e:
            print(f"[SYNC PUSH ERROR] {name}: {e}")
    return total


def register_commands(app):
    @app.cli.command("sync-initial")
    def sync_initial():
        """Pull all data from Airtable into PostgreSQL (initial load)."""
        click.echo("Starting initial Airtable -> PostgreSQL sync...")
        total = pull_all()
        click.echo(f"Done. {total} records synced.")

    @app.cli.command("sync-pull")
    def sync_pull():
        """Pull latest data from Airtable."""
        total = pull_all()
        click.echo(f"Pulled {total} records.")

    @app.cli.command("sync-push")
    def sync_push():
        """Push dirty records to Airtable."""
        total = push_all_dirty()
        click.echo(f"Pushed {total} records.")
