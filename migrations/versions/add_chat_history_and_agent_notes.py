"""Add chat_history and agent_notes tables

Revision ID: add_chat_notes_001
Revises: add_confirmado_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_chat_notes_001'
down_revision = 'add_confirmado_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'chat_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.Text()),
        sa.Column('title', sa.Text()),
        sa.Column('messages', sa.JSON(), server_default='[]'),
        sa.Column('user_name', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.create_table(
        'agent_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), server_default=''),
        sa.Column('user_name', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade():
    op.drop_table('agent_notes')
    op.drop_table('chat_history')
