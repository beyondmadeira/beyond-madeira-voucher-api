"""Add site_bookings table for Gmail auto-import

Revision ID: add_site_bookings_001
Revises: add_memory_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_site_bookings_001'
down_revision = 'add_memory_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'site_bookings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('raw_email', sa.Text()),
        sa.Column('parsed_data', sa.Text()),
        sa.Column('nome', sa.Text()),
        sa.Column('email', sa.Text()),
        sa.Column('tel', sa.Text()),
        sa.Column('ref', sa.Text(), unique=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('whatsapp_sent', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('email_sent', sa.Boolean(), server_default=sa.text('false')),
    )
    op.create_index('ix_site_bookings_status', 'site_bookings', ['status'])
    op.create_index('ix_site_bookings_ref', 'site_bookings', ['ref'], unique=True)


def downgrade():
    op.drop_index('ix_site_bookings_ref', table_name='site_bookings')
    op.drop_index('ix_site_bookings_status', table_name='site_bookings')
    op.drop_table('site_bookings')
