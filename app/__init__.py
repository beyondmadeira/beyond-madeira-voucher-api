import os
from flask import Flask
from app.config import Config
from app.extensions import db, migrate, cors


def create_app(config_class=Config):
    application = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    application.config.from_object(config_class)

    # Fix Railway DATABASE_URL (postgres:// -> postgresql://)
    uri = application.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        application.config["SQLALCHEMY_DATABASE_URI"] = uri.replace(
            "postgres://", "postgresql://", 1
        )

    # Extensions
    db.init_app(application)
    migrate.init_app(application, db)
    try:
        from flask_compress import Compress
        Compress(application)
    except ImportError:
        pass
    cors.init_app(
        application,
        origins=[
            "https://hub.beyondmadeira.com",
            "https://hub-crm.8vesjw.easypanel.host",
            "http://localhost",
            "file://",
        ],
    )

    # Import models so Alembic sees them
    from app import models  # noqa: F401

    # Register blueprints
    from app.blueprints.core import bp as core_bp
    from app.blueprints.reservas import bp as reservas_bp
    from app.blueprints.conhecimento import bp as conhecimento_bp
    from app.blueprints.financeiro import bp as financeiro_bp
    from app.blueprints.extratos import bp as extratos_bp
    from app.blueprints.vouchers import bp as vouchers_bp
    from app.blueprints.email import bp as email_bp
    from app.blueprints.whatsapp import bp as whatsapp_bp
    from app.blueprints.chat import bp as chat_bp
    from app.blueprints.site_bookings import bp as site_bookings_bp

    application.register_blueprint(core_bp)
    application.register_blueprint(reservas_bp)
    application.register_blueprint(conhecimento_bp)
    application.register_blueprint(financeiro_bp)
    application.register_blueprint(extratos_bp)
    application.register_blueprint(vouchers_bp)
    application.register_blueprint(email_bp)
    application.register_blueprint(whatsapp_bp)
    application.register_blueprint(chat_bp)
    application.register_blueprint(site_bookings_bp)

    # Register CLI commands
    from app.services.airtable_sync import register_commands
    register_commands(application)

    # Background sync scheduler (only in main process, not in flask CLI)
    if not application.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_scheduler(application)

    return application


def _start_scheduler(application):
    """Start APScheduler for background Airtable sync."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        def _pull_job():
            with application.app_context():
                from app.services.airtable_sync import pull_all
                try:
                    pull_all()
                except Exception as e:
                    print(f"[SCHEDULER] Pull error: {e}")

        def _push_job():
            with application.app_context():
                from app.services.airtable_sync import push_all_dirty
                try:
                    push_all_dirty()
                except Exception as e:
                    print(f"[SCHEDULER] Push error: {e}")

        def _sync_comissoes_job():
            with application.app_context():
                try:
                    from app.blueprints.extratos import _sync_all_comissoes
                    _sync_all_comissoes()
                except Exception as e:
                    print(f"[SCHEDULER] Comissoes sync error: {e}")

        pull_interval = application.config.get("SYNC_PULL_INTERVAL", 300)
        push_interval = application.config.get("SYNC_PUSH_INTERVAL", 30)

        scheduler.add_job(_pull_job, "interval", seconds=pull_interval, id="sync_pull")
        scheduler.add_job(_push_job, "interval", seconds=push_interval, id="sync_push")
        scheduler.add_job(_sync_comissoes_job, "interval", seconds=900, id="sync_comissoes")
        scheduler.start()
        print(f"[SCHEDULER] Started: pull every {pull_interval}s, push every {push_interval}s")
    except ImportError:
        print("[SCHEDULER] APScheduler not installed, background sync disabled")
    except Exception as e:
        print(f"[SCHEDULER] Failed to start: {e}")
