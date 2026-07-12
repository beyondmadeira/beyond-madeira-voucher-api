"""
ViralPulse — ponto de entrada / CLI.

Comandos:
  python -m viralpulse.main run       → corre o scheduler 24/7 (ciclos periódicos)
  python -m viralpulse.main once      → corre um único ciclo e sai
  python -m viralpulse.main approve   → aprova/nega pedidos de permissão (CLI)
  python -m viralpulse.main initdb    → cria as tabelas

Nota: o dashboard web arranca com  `uvicorn viralpulse.dashboard:app`.
"""

from __future__ import annotations

import argparse

from apscheduler.schedulers.blocking import BlockingScheduler

from .core.config import get_config, get_settings
from .core.db import init_db, session_scope
from .core.logging_setup import get_logger, setup_logging
from .core.models import PermissionRequest, PermissionStatus
from .agents.permission import PermissionAgent
from .pipeline import Pipeline

log = get_logger("main")


def cmd_once() -> None:
    init_db()
    Pipeline().run_cycle()


def cmd_run() -> None:
    init_db()
    cfg = get_config().get("publishing", {})
    minutes = cfg.get("cycle_minutes", 45)
    pipeline = Pipeline()

    settings = get_settings()
    log.info("boot", dry_run=settings.dry_run, require_approval=settings.require_approval,
             cycle_minutes=minutes)

    pipeline.run_cycle()  # ciclo imediato ao arrancar
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(pipeline.run_cycle, "interval", minutes=minutes, max_instances=1,
                      coalesce=True)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("shutdown")


def cmd_approve() -> None:
    """Lista pedidos pendentes e permite resolvê-los interativamente."""
    init_db()
    with session_scope() as s:
        pending = s.query(PermissionRequest).filter_by(status=PermissionStatus.PENDING).all()
        rows = [(r.id, r.candidate.creator, r.candidate.permalink) for r in pending]

    if not rows:
        print("Sem pedidos pendentes.")
        return

    for rid, creator, link in rows:
        print(f"\n[#{rid}] @{creator} — {link}")
        ans = input("Autorizado? (s/n/skip): ").strip().lower()
        if ans == "s":
            PermissionAgent.resolve(rid, granted=True, proof=input("Prova (opcional): ").strip())
        elif ans == "n":
            PermissionAgent.resolve(rid, granted=False)


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(prog="viralpulse")
    parser.add_argument("command", choices=["run", "once", "approve", "initdb"])
    args = parser.parse_args()

    if args.command == "initdb":
        init_db()
        print("Base de dados inicializada.")
    elif args.command == "once":
        cmd_once()
    elif args.command == "run":
        cmd_run()
    elif args.command == "approve":
        cmd_approve()


if __name__ == "__main__":
    main()
