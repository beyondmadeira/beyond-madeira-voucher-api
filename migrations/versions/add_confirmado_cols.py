"""Add confirmado_parceiro and confirmado_beyond to comissao_parceiro

Revision ID: add_confirmado_001
Revises: 484d663b089c
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_confirmado_001'
down_revision = '484d663b089c'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('comissao_parceiro', sa.Column('confirmado_parceiro', sa.Boolean(), server_default='false'))
    op.add_column('comissao_parceiro', sa.Column('confirmado_beyond', sa.Boolean(), server_default='false'))

def downgrade():
    op.drop_column('comissao_parceiro', 'confirmado_beyond')
    op.drop_column('comissao_parceiro', 'confirmado_parceiro')
