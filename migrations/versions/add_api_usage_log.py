"""Add api_usage_log table (registo de consumo Claude)

Revision ID: add_usage_log_001
Revises: add_wa_notif_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_usage_log_001'
down_revision = 'add_wa_notif_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_usage_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('endpoint', sa.Text()),
        sa.Column('model', sa.Text()),
        sa.Column('user_name', sa.Text()),
        sa.Column('input_tokens', sa.Integer(), server_default='0'),
        sa.Column('output_tokens', sa.Integer(), server_default='0'),
        sa.Column('cache_read_tokens', sa.Integer(), server_default='0'),
        sa.Column('cache_write_tokens', sa.Integer(), server_default='0'),
        sa.Column('est_cost_usd', sa.Float(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_api_usage_log_created_at', 'api_usage_log', ['created_at'])


def downgrade():
    op.drop_index('ix_api_usage_log_created_at', table_name='api_usage_log')
    op.drop_table('api_usage_log')
