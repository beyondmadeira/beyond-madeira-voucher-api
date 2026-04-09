"""Add parceiro extra fields"""
from alembic import op
import sqlalchemy as sa

revision = "add_parceiro_fields_001"
down_revision = "add_wa_confirmations_001"
branch_labels = None
depends_on = None


def upgrade():
    cols = [
        "categoria", "website", "morada_office", "comissao_tipo",
        "comissao_valor", "comissao_notas", "instrucoes_aeroporto",
        "instrucoes_hotel", "instrucoes_office", "logo_url", "notas", "atividades",
    ]
    for col in cols:
        try:
            op.add_column("parceiro", sa.Column(col, sa.Text(), nullable=True))
        except Exception:
            pass


def downgrade():
    pass
