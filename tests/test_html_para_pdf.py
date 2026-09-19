"""/html-para-pdf: o PDF é o voucher web, convertido — nada é redesenhado aqui.

Porquê (17-19 Set 2026): o PDF era desenhado outra vez neste serviço a partir
de campos escolhidos à mão pelo Hub. Cada campo esquecido virou um bug no
voucher do cliente — "Payment: Cash Only" a quem já pagou, `{{tipo_tour}}`
cru, o logo do parceiro em falta.

E como o HTML vem de quem chama, o conversor não pode ir à rede: seria uma
porta para ler endereços internos (SSRF).
"""
import base64
import os
import sys
from unittest import mock

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.blueprints.vouchers import bp  # noqa: E402
from app.services import pdf as pdf_mod  # noqa: E402

CHAVE = "chave-de-teste"
# PNG 1x1 transparente
PNG_1PX = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["VOUCHER_API_KEY"] = CHAVE
    app.register_blueprint(bp)
    return app.test_client()


def _post(client, body, chave=CHAVE):
    return client.post("/html-para-pdf", json=body, headers={"X-API-Key": chave})


def test_sem_chave_nao_entra(client):
    r = _post(client, {"html": "<p>x</p>"}, chave="errada")
    assert r.status_code == 401


def test_html_vazio_e_400(client):
    assert _post(client, {"html": ""}).status_code == 400
    assert _post(client, {}).status_code == 400


def test_converte_o_html_que_recebe(client):
    html = "<html><body><h1>Payment Confirmed</h1><p>Hikes</p></body></html>"
    r = _post(client, {"html": html, "filename": "Voucher_AT_133.pdf"})
    assert r.status_code == 200
    j = r.get_json()
    pdf = base64.b64decode(j["pdf_base64"])
    assert pdf.startswith(b"%PDF")
    assert j["filename"] == "Voucher_AT_133.pdf"


def test_nome_do_ficheiro_e_higienizado(client):
    r = _post(client, {"html": "<p>x</p>", "filename": "../../etc/passwd"})
    nome = r.get_json()["filename"]
    assert "/" not in nome and nome.endswith(".pdf")


def test_nunca_vai_a_rede():
    """Nem imagens, nem CSS, nem fontes: nenhuma ligação de rede sai daqui."""
    import socket
    ligacoes = []
    real_connect = socket.socket.connect

    def espia(self, addr, *a, **k):
        ligacoes.append(addr)
        raise OSError("rede proibida no teste")

    html = (
        '<html><head><link rel="stylesheet" href="http://169.254.169.254/latest/meta-data">'
        "<style>@import url('https://fonts.googleapis.com/css2?family=Montserrat');</style>"
        '</head><body><img src="http://10.0.0.1/interno.png">'
        '<img src="file:///etc/passwd">'
        f'<img src="{PNG_1PX}"><p>ok</p></body></html>'
    )
    with mock.patch.object(socket.socket, "connect", espia), \
         mock.patch.object(socket, "create_connection", side_effect=espia):
        out = pdf_mod.html_para_pdf(html)
    assert out.startswith(b"%PDF")
    assert ligacoes == [], f"tentou ligar a {ligacoes}"


def test_fetcher_so_aceita_data():
    f = pdf_mod._fetcher_sem_rede()
    for url in ("http://10.0.0.1/x.png", "https://example.com/a.css", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            f.fetch(url)


def test_imagem_embutida_entra():
    out = pdf_mod.html_para_pdf(f'<img src="{PNG_1PX}" style="width:20px">')
    assert out.startswith(b"%PDF")


def test_html_gigante_e_recusado():
    with pytest.raises(ValueError):
        pdf_mod.html_para_pdf("x" * (pdf_mod.HTML_MAX_BYTES + 1))
