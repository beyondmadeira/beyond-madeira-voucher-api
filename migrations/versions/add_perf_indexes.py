"""Add performance indexes"""
from alembic import op

revision = "add_perf_indexes_001"
down_revision = "add_wa_notif_001"
branch_labels = None
depends_on = None


def upgrade():
    indexes = [
        ("ix_rent_car_dropoff_data", "rent_car", ["dropoff_data"]),
        ("ix_rent_car_parceiro", "rent_car", ["parceiro"]),
        ("ix_rent_car_estado", "rent_car", ["estado"]),
        ("ix_atividade_data", "atividade", ["data"]),
        ("ix_atividade_parceiro", "atividade", ["parceiro"]),
        ("ix_atividade_estado", "atividade", ["estado"]),
        ("ix_site_bookings_status", "site_bookings", ["status"]),
        ("ix_site_bookings_created_at", "site_bookings", ["created_at"]),
        ("ix_wa_notifications_read_received", "wa_notifications", ["read", "received_at"]),
        ("ix_wa_notifications_chat_id", "wa_notifications", ["chat_id"]),
        ("ix_wa_confirmations_chat_replied", "wa_confirmations", ["chat_id", "replied"]),
        ("ix_comissao_parceiro_mes", "comissao_parceiro", ["parceiro", "mes"]),
    ]
    for name, table, cols in indexes:
        try:
            op.create_index(name, table, cols)
        except Exception:
            pass


def downgrade():
    pass
