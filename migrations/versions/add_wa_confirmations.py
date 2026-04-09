"""Add wa_confirmations table for WhatsApp email confirmation tracking

Revision ID: add_wa_confirm_001
Revises: add_site_bookings_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_wa_confirm_001'
down_revision = 'add_site_bookings_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wa_confirmations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('replied', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('replied_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_wa_confirmations_chat_id', 'wa_confirmations', ['chat_id'])


def downgrade():
    op.drop_index('ix_wa_confirmations_chat_id', table_name='wa_confirmations')
    op.drop_table('wa_confirmations')
