"""Add meeting_points table with seed data

Revision ID: add_meetpts_001
Revises: add_email_tpl_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_meetpts_001'
down_revision = 'add_email_tpl_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'meeting_points',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parceiro', sa.Text(), nullable=False),
        sa.Column('atividade', sa.Text()),
        sa.Column('local', sa.Text()),
        sa.Column('maps_link', sa.Text()),
        sa.Column('notas', sa.Text()),
        sa.Column('pickup_mode', sa.Text(), server_default='meeting_point'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.execute("""
        INSERT INTO meeting_points (parceiro, atividade, local, maps_link, notas, pickup_mode) VALUES
        ('WilderMadeira', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before via WhatsApp. Be ready 5 min early.', 'pickup_day_before'),
        ('Madeira Explorers', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before.', 'pickup_day_before'),
        ('Safari Madeira', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before via WhatsApp.', 'pickup_day_before'),
        ('Green Devil', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before.', 'pickup_day_before'),
        ('Warriors Adventure', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the day before.', 'pickup_day_before'),
        ('Be Local', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time sent the night before.', 'pickup_day_before'),
        ('Do it Madeira', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before.', 'pickup_day_before'),
        ('Seaborn', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 30 min before departure for check-in.', 'meeting_point'),
        ('VMT', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 30 min before departure. Payment at marina.', 'meeting_point'),
        ('VIP Dolphins', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 30 min before departure for check-in and payment.', 'meeting_point'),
        ('Nau Santa Maria', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 30 min before. Look for Nau Santa Maria boat.', 'meeting_point'),
        ('Bonita da Madeira', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 20 min before departure.', 'meeting_point'),
        ('Magic Dolphins', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 30 min before departure.', 'meeting_point'),
        ('Sea La Vie', NULL, 'Calheta Marina', 'https://maps.app.goo.gl/calheta-marina', 'Arrive 15 min before departure.', 'meeting_point'),
        ('Azul Diving', NULL, 'Porto do Funchal', '', 'Arrive 30 min before. All equipment provided.', 'meeting_point'),
        ('Surf Madeira', NULL, 'Jardim do Mar', '', 'Arrive 15 min early. All equipment provided.', 'meeting_point'),
        ('Quad Xperience', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the day before.', 'pickup_day_before'),
        ('E-Bike Madeira', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the day before.', 'pickup_day_before'),
        ('Trail4Fun', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time sent the night before.', 'pickup_day_before'),
        ('Fly Madeira', NULL, 'Arco da Calheta', '', 'Flights are weather dependent — confirmed on the morning.', 'meeting_point'),
        ('Fishing Family', NULL, 'Marina do Funchal', 'https://maps.app.goo.gl/funchal-marina', 'Arrive 15 min before departure.', 'meeting_point'),
        ('Epic Madeira', NULL, 'Pick-up at your hotel/accommodation', '', 'Pick-up time confirmed the night before.', 'pickup_day_before')
    """)


def downgrade():
    op.drop_table('meeting_points')
