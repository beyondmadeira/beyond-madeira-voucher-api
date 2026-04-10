"""Add wa_notifications table for WhatsApp bell notifications

Revision ID: add_wa_notif_001
Revises: add_wa_confirm_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_wa_notif_001'
down_revision = 'add_wa_confirm_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wa_notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.Text(), nullable=False),
        sa.Column('contact_name', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('read', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('replied', sa.Boolean(), server_default=sa.text('false')),
    )
    op.create_index('ix_wa_notifications_chat_id', 'wa_notifications', ['chat_id'])
    op.create_index('ix_wa_notifications_received_at', 'wa_notifications', ['received_at'])
    op.create_index('ix_wa_notifications_read', 'wa_notifications', ['read'])


def downgrade():
    op.drop_index('ix_wa_notifications_read', table_name='wa_notifications')
    op.drop_index('ix_wa_notifications_received_at', table_name='wa_notifications')
    op.drop_index('ix_wa_notifications_chat_id', table_name='wa_notifications')
    op.drop_table('wa_notifications')
