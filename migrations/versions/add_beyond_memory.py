"""Add beyond_memory table with seed data

Revision ID: add_memory_001
Revises: add_meetpts_001
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_memory_001'
down_revision = 'add_meetpts_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'beyond_memory',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('key', sa.Text()),
        sa.Column('content', sa.Text()),
        sa.Column('source', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    op.execute("""
        INSERT INTO beyond_memory (category, key, content, source) VALUES
        ('parceiro', 'WilderMadeira', 'Confirma hora de pick-up na vespera via WhatsApp. Especialista em levadas e sunrise. Contacto fiavel.', 'system'),
        ('parceiro', 'Safari Madeira', 'Jeep tours West e East. Pick-up no hotel. Confirma hora na vespera. Almoco incluido nos full day.', 'system'),
        ('parceiro', 'Green Devil', 'Jeep tours. Pick-up no hotel. Confirma hora na vespera.', 'system'),
        ('parceiro', 'VIP Dolphins', 'Meeting point: Marina do Funchal. Chegar 30min antes. Pagamento na marina. Cancelamento se mau tempo.', 'system'),
        ('parceiro', 'Seaborn', 'Meeting point: Marina do Funchal. Chegar 30min antes. Catamara e speedboat disponiveis.', 'system'),
        ('parceiro', 'VMT', 'Meeting point: Marina do Funchal. Barcos de observacao de cetaceos. Pagamento na marina.', 'system'),
        ('parceiro', 'Warriors Adventure', 'Canyoning e coasteering. Pick-up no hotel. Equipamento incluido. Informar condicoes de saude.', 'system'),
        ('parceiro', 'Be Local', 'Canyoning. Pick-up no hotel. Hora confirmada na vespera.', 'system'),
        ('parceiro', 'Do it Madeira', 'Tours variados. Pick-up no hotel. Confirma na vespera.', 'system'),
        ('parceiro', 'Atlantic Rent Car', 'Entrega so em hoteis (nao apartamentos). Dados do condutor obrigatorios antes do pick-up. Taxa aeroporto 15EUR unico.', 'system'),
        ('parceiro', 'Point Car', 'Minimo 2 dias. Fiat Panda exclusivo deste parceiro. Taxa aeroporto 20EUR por viagem. Comissao 15%.', 'system'),
        ('parceiro', 'RentCar Madeira', 'Comissao fixa 11EUR/dia. Entrega em qualquer alojamento. Seguro extra opcional +10EUR/dia.', 'system'),
        ('parceiro', 'AB4rent', 'Comissao 25% do total (excl extras e seguro). Reservar para reservas de valor alto.', 'system'),
        ('regra', 'sunrise_no_payment', 'Atividades Sunrise e Vereda do Larano: nunca pedir pagamento antecipado. Trail fee 3EUR pago no local via Simplifica.', 'system'),
        ('regra', 'dolphins_no_payment', 'Whale watching e dolphin watching: pagamento na marina no dia. Nunca pedir antecipado.', 'system'),
        ('regra', 'pickup_hora', 'Quando hora de pick-up e definida ou alterada, enviar email automatico ao cliente com a nova hora.', 'system'),
        ('regra', 'lingua_cliente', 'Responder SEMPRE na lingua do cliente. Nunca em portugues a cliente que escreveu noutra lingua.', 'system'),
        ('insight', 'best_sellers', 'Atividades mais vendidas: Jeep Tour West, Dolphins Catamaran, Levada 25 Fontes, Canyoning Level 1.', 'system'),
        ('insight', 'upsell', 'Clientes que reservam jeep tour frequentemente adicionam barco de golfinhos. Sugerir sempre.', 'system'),
        ('insight', 'fora_funchal', 'Pick-up fora de Funchal (Calheta, Porto Moniz, etc) tem extra de 25EUR. Sugerir automaticamente.', 'system'),
        ('padrao', 'confirmacao', 'Fluxo: criar reserva > confirmar > enviar voucher email > enviar WA parceiro > marcar pick-up hora > email pick-up ao cliente.', 'system')
    """)


def downgrade():
    op.drop_table('beyond_memory')
