"""Add email_templates table with seed data

Revision ID: add_email_tpl_001
Revises: add_chat_notes_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_email_tpl_001'
down_revision = 'add_chat_notes_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.Text(), unique=True, nullable=False),
        sa.Column('name', sa.Text()),
        sa.Column('subject', sa.Text()),
        sa.Column('body_html', sa.Text()),
        sa.Column('no_payment_link', sa.Boolean(), server_default='false'),
        sa.Column('activities', sa.Text()),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # Seed default templates
    op.execute("""
        INSERT INTO email_templates (key, name, subject, no_payment_link, activities, notes) VALUES
        ('sunrise', 'Sunrise / Vereda do Larano', 'Your Sunrise Hike is Confirmed — Beyond Madeira', true, 'sunrise,pico areeiro,vereda,larano', 'WilderMadeira partner. Pick-up time sent night before. Trail fee €3 via Simplifica. No payment link.'),
        ('dolphins', 'Whale & Dolphin Watching', 'Your Boat Trip is Confirmed — Beyond Madeira', true, 'whale,dolphin,vip dolphin,catamaran', 'Payment at marina on the day. Arrive 30min before departure. No payment link.'),
        ('generic', 'Generic Activity', 'Your Activity is Confirmed — Beyond Madeira', false, '', 'Default template with payment link.')
    """)


def downgrade():
    op.drop_table('email_templates')
