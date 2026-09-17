"""O silencio de quem chama nao pode virar "pague em dinheiro ao guia".

17 Set 2026, reserva 133 (Francesa Rosy, Private Guided Hikes, 500 EUR, paga).
O voucher web dizia "Paid / Payment Confirmed". O PDF gerado por este servico,
para a MESMA reserva, dizia "Cash on the day" e "Payment: Cash Only". A causa
estava aqui:

    status    = d.get("status", "confirmed").lower()
    pagamento = d.get("pagamento", "cash").lower()

O Hub nunca enviava `status` — logo, por omissao, toda a gente pagava em
dinheiro no dia. A jusante o operador le o PDF, assume que recebeu o dinheiro,
e factura-nos o valor cheio: foi assim que a Safari Madeira pediu 732,92 EUR
onde o correcto eram 136,98 EUR (4 Set 2026).

Regra desta casa: uma afirmacao sobre dinheiro exige que alguem a tenha
escrito. Sem `status`, o voucher cala-se.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pdf import build_at_html  # noqa: E402
from app.utils.formatting import strip_unfilled  # noqa: E402

BASE = {
    "referencia": "133",
    "atividade": "Private Guided Hikes",
    "data": "2026-09-29",
    "hora": "TBC",
    "cliente": "Francesa Rosy",
    "email": "cliente@example.com",
    "telefone": "+33 000000000",
    "pax": "2",
    "participantes": "2",
    "total": "500.0",
    "operador": "DamWalk",
    "tipo_tour": "Hikes",
}

# As frases que nunca podem aparecer num voucher que nao tenha sido
# explicitamente marcado como "confirmed" (paga-se no dia).
FRASES_DE_DINHEIRO = [
    "Cash Only",
    "Cash on the day",
    "Cash or card on the day",
    "paid in cash on the day",
    "to be paid in cash",
]


def _html(**extra):
    d = dict(BASE)
    d.update(extra)
    return build_at_html(d)


def _sem_frases_de_dinheiro(html):
    baixo = html.lower()
    return [f for f in FRASES_DE_DINHEIRO if f.lower() in baixo]


# ─── O bug exacto da reserva 133 ──────────────────────────────────────────
def test_reserva_paga_nao_manda_pagar_em_dinheiro():
    html = _html(status="paid")
    assert not _sem_frases_de_dinheiro(html), _sem_frases_de_dinheiro(html)
    assert "Payment Confirmed" in html


def test_payload_sem_status_nao_inventa_pagamento_em_dinheiro():
    """O caso que causou o incidente: o Hub nao mandava `status` nenhum."""
    html = _html()
    assert not _sem_frases_de_dinheiro(html), _sem_frases_de_dinheiro(html)


def test_payload_sem_status_tambem_nao_afirma_que_esta_pago():
    # Nem uma coisa nem outra. Um falso "pago" custa o tour (7 Jul 2026).
    html = _html()
    assert "Payment Confirmed" not in html
    assert "Payment received" not in html


def test_indeterminado_manda_perguntar_antes_de_pagar():
    html = _html(status="indeterminado")
    assert "Payment Being Confirmed" in html
    assert "before you pay the guide" in html
    assert not _sem_frases_de_dinheiro(html), _sem_frases_de_dinheiro(html)


def test_awaiting_pede_pagamento_sem_dizer_dinheiro_ao_guia():
    html = _html(status="awaiting")
    assert "Payment Required Before the Activity" in html
    assert not _sem_frases_de_dinheiro(html), _sem_frases_de_dinheiro(html)


# ─── "confirmed" continua a valer o que valia, mas tem de ser escrito ─────
def test_confirmed_explicito_continua_a_dizer_paga_no_dia():
    html = _html(status="confirmed", pagamento="cash")
    assert "Payment: Cash Only" in html


def test_confirmed_com_cartao():
    html = _html(status="confirmed", pagamento="cash_card")
    assert "Payment: Cash or Card" in html


# ─── Chavetas cruas ───────────────────────────────────────────────────────
def test_tipo_tour_em_falta_nao_sai_cru_no_pdf():
    d = dict(BASE)
    d.pop("tipo_tour")
    html = build_at_html(d)
    assert "{{tipo_tour}}" not in html


def test_nenhuma_chaveta_sobrevive_ao_render():
    import re
    html = _html(status="paid")
    sobras = re.findall(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}", html)
    assert not sobras, sobras


def test_strip_unfilled_nao_toca_no_resto():
    assert strip_unfilled("<b>Hikes</b> {{tipo_tour}}!") == "<b>Hikes</b> !"
    assert strip_unfilled("100% {ok} {{ }}") == "100% {ok} {{ }}"
