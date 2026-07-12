# ViralPulse

Sistema 24/7 de curadoria viral para o **Madeira Daily** — descobre conteúdo
viral no nicho da Madeira, pede autorização ao criador, edita com crédito e
publica automaticamente no Instagram e TikTok.

> **Filosofia:** fazer como as páginas grandes fazem *a sério* — descoberta por
> **APIs oficiais** (não scraping) e republicação **só com permissão** (não
> apropriação). É o que protege a marca Beyond Madeira e o que faz a página
> durar em vez de arder.

---

## O que este sistema **faz** e **não faz**

| Faz ✅ | Não faz ❌ |
|--------|-----------|
| Descobre virais via Instagram Graph API + TikTok Research API | Scraping do Explore / stealth / proxies para fugir a bans |
| Pede autorização ao criador e regista o consentimento | Republicar conteúdo sem permissão |
| Acrescenta crédito visível ao autor original | Remover watermark do autor |
| Publica via APIs oficiais, com limite diário | Contas falsas ou automação que viole os ToS |

Se te pediram um scraper anti-ban, a resposta honesta é: é isso mesmo que faz
banir contas e expõe a marca a queixas de copyright. Esta versão entrega o
mesmo objetivo (uma página viral que cresce 24/7) pelo caminho que se aguenta.

---

## Arquitetura (multi-agente)

```
viralpulse/
├── main.py              # CLI + scheduler 24/7 (APScheduler)
├── dashboard.py         # painel web FastAPI (controlo, aprovações, stats)
├── pipeline.py          # orquestra os agentes por estados
├── config.example.yaml  # fontes, hashtags, limites (copiar p/ config.yaml)
├── .env.example         # segredos e flags (copiar p/ .env)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── core/
│   ├── config.py        # carrega .env + config.yaml
│   ├── db.py            # sessão SQLAlchemy
│   ├── models.py        # Candidate → PermissionRequest → Post (máquina de estados)
│   └── logging_setup.py # logs estruturados + alertas
└── agents/
    ├── discovery.py     # 🔍 descoberta via APIs oficiais
    ├── permission.py    # 🤝 pedido + registo de autorização (o "gate")
    ├── editor.py        # ✂️ download autorizado + FFmpeg (crédito, vertical, news)
    └── publisher.py     # 📤 publicação via IG Graph + TikTok Content Posting
```

O fluxo é uma máquina de estados que **impede** publicar sem permissão:

```
Candidate(DISCOVERED) ─▶ pedido ─▶ PermissionRequest(PENDING)
                                        ├─ GRANTED ─▶ Post(QUEUED→EDITED→PUBLISHED)
                                        └─ DENIED/EXPIRED ─▶ descartado
```

---

## Correr localmente

Requisitos: **Python 3.11+** e **FFmpeg** instalado no sistema
(`sudo apt install ffmpeg` ou `brew install ffmpeg`).

```bash
cd viralpulse
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env               # deixa VIRALPULSE_DRY_RUN=true para começar
cp config.example.yaml config.yaml # edita hashtags/limites à vontade

python -m viralpulse.main initdb   # cria a base de dados
python -m viralpulse.main once     # corre UM ciclo (com dados de exemplo)
```

Abre o dashboard:

```bash
uvicorn viralpulse.dashboard:app --host 0.0.0.0 --port 8090
# → http://localhost:8090  (password = VIRALPULSE_DASHBOARD_PASSWORD do .env)
```

No dashboard vês os candidatos, autorizas os pedidos (o passo humano) e podes
correr um ciclo à mão. Enquanto `DRY_RUN=true`, nada é publicado — o sistema
simula tudo para poderes ver o pipeline completo sem credenciais.

Correr 24/7 localmente:

```bash
python -m viralpulse.main run      # ciclos a cada `cycle_minutes` (config.yaml)
```

---

## Ligar as APIs oficiais (sair do DRY-RUN)

1. **Instagram Graph API** — precisas de uma conta **Business/Creator** ligada a
   uma Página do Facebook e a uma App em <https://developers.facebook.com>.
   Permissões: `instagram_basic`, `instagram_content_publish`,
   `instagram_manage_insights`. Preenche `IG_BUSINESS_ACCOUNT_ID` e
   `IG_ACCESS_TOKEN` (token de longa duração) no `.env`.
2. **TikTok** — regista a app em <https://developers.tiktok.com>, pede acesso à
   **Research API** (descoberta) e à **Content Posting API** (publicação).
   Preenche `TIKTOK_*` no `.env`.
3. Muda `VIRALPULSE_DRY_RUN=false`. Mantém `VIRALPULSE_REQUIRE_APPROVAL=true`.

> A publicação no Instagram exige que o vídeo editado esteja acessível por **URL
> público** (o container `video_url`). Serve a pasta `processed/` por HTTPS
> (ex.: um bucket S3/Cloudflare R2) e passa esse URL ao publisher.

---

## Deploy num VPS (Hetzner / DigitalOcean)

```bash
# 1) Provisiona um VPS pequeno (2 vCPU / 4 GB chega). Ubuntu 22.04+.
# 2) Instala Docker + compose plugin:
curl -fsSL https://get.docker.com | sh

# 3) Clona o repo e entra na pasta do subprojeto:
git clone <repo> && cd beyond-madeira-voucher-api/viralpulse

# 4) Configura:
cp .env.example .env && nano .env             # credenciais + DRY_RUN=false
cp config.example.yaml config.yaml && nano config.yaml

# 5) Arranca worker + dashboard:
docker compose up -d --build

# 6) Expõe o dashboard com TLS (recomendado): coloca um Caddy/Nginx à frente
#    do porto 8090 com o teu domínio. Nunca deixes o dashboard aberto sem HTTPS.
```

Logs: `docker compose logs -f worker`.

---

## Boas práticas (maximizar resultados, sem levar ban)

- **Autorização primeiro, sempre.** O crédito visível + o "sim" do criador é a
  tua licença. Guarda a prova (o dashboard regista-a no `PermissionRequest`).
- **Limite diário conservador** (`daily_limit`) e **janela horária** humana
  (`active_hours`) — publicar 40x/dia às 4h da manhã é sinal de bot.
- **Prioriza viralidade real:** o `virality_score` pondera comentários acima de
  likes; ajusta `min_engagement` por hashtag.
- **Modo "news":** liga `news_overlay` para dar contexto editorial ao clip.
- **Nunca** removas watermarks nem uses proxies para contornar deteção. Não está
  neste código de propósito.
- **Fontes licenciadas** como alternativa/escala: agências como Storyful ou
  Jukin licenciam clips virais legalmente — é assim que a CNN "partilha momentos".

---

## Estado atual

Pronto a correr em **DRY-RUN** (simulação ponta-a-ponta). Para ir a *live*, liga
as credenciais das APIs conforme acima. O gate de aprovação humana está ativo
por defeito — desliga-o só quando tiveres um processo de permissão automatizado
e legalmente sólido.
