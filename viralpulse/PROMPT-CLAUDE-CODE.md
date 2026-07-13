# Prompt para o Claude Code (correr NO MAC, com Palmier Pro + MCP ativos)

> Copia tudo o que está no bloco abaixo e cola no Claude Code, no teu Mac, com o
> Palmier Pro aberto e o MCP do Palmier ligado. (Este prompt não corre a partir
> da sessão remota — o Palmier é uma app local de macOS.)

---

```
Estás no repositório beyond-madeira-voucher-api, subprojeto viralpulse/.
Marca: Madeira Daily. Vamos montar os primeiros vídeos no Palmier Pro, a partir
das referências guardadas e do MEU footage próprio.

CONTEXTO A LER PRIMEIRO
- viralpulse/IDEIAS.md      → 7 referências TikTok + 4 ideias de vídeo
- viralpulse/INSPIRACAO.md  → contas de inspiração
- viralpulse/MARCA.md       → cores da marca: True Pink #FD1843, Chill White
                              #FFF9FA, preto #0A0A0A

PASSO 1 — Organizar o hub (garantir que só há UM Madeira Daily)
- Lê os três ficheiros acima.
- Verifica se há conteúdo Madeira Daily duplicado entre content/madeiradaily/ e
  viralpulse/. NÃO dupliques: mantém viralpulse/ como "studio de produção" e
  content/madeiradaily/ como hub editorial, e cria uma nota/ligação entre os
  dois. Reporta-me o que encontraste.

PASSO 2 — Resolver as referências
- Para cada link vm.tiktok.com em IDEIAS.md, resolve o URL final e identifica o
  @criador original e o nº de likes/views.
- Atualiza a tabela em IDEIAS.md com: URL completo, @criador, likes. Isto é
  essencial para dar crédito e, se algum dia reutilizarmos o clip, pedir permissão.

PASSO 3 — Preparar o estúdio (pastas locais, FORA do git)
- Cria viralpulse/studio/ com três subpastas:
    references/  → clips de referência (só estudo)
    assets/      → o MEU footage (drone, Pico do Areeiro, etc.)
    output/      → vídeos finais exportados
- Acrescenta viralpulse/studio/ ao .gitignore (media não vai para o git).

PASSO 4 — Descarregar referências (SÓ como material de estudo / moodboard)
- Com yt-dlp, descarrega as referências de IDEIAS.md para studio/references/,
  apenas para estudar estrutura, ritmo e estilo de título. NÃO são para republicar.
- Os vídeos que vamos PUBLICAR são feitos com o MEU footage em studio/assets/.
  (Se um dia quisermos mesmo reutilizar um clip de terceiros, primeiro passa pelo
  fluxo de permissão do ViralPulse — não republicar sem o "sim" do criador.)

PASSO 5 — Montar os vídeos no Palmier Pro (via MCP)
Para cada ideia, cria um projeto no Palmier, monta a timeline e exporta MP4
(H.264) vertical 1080x1920 para studio/output/:

  • Ideia #4 — Drone + título à frente:
      abre com o shot de drone mais forte; título grande à frente nas cores da
      marca (Chill White sobre caixa True Pink); primeiros ~1s = gancho.

  • Ideia #2 — Montagem "uau":
      abre com sunrise no Pico do Areeiro, depois encadeia os clips mais épicos
      ao ritmo da música (ref TikTok #5, ~1.5M).

  • Ideia #3 — Conceito do TikTok #6, com outra música:
      mesma estrutura/ritmo do ref, local Pico do Areeiro, MÚSICA diferente
      (trend / livre de direitos).

  • Ideia #1 — Itinerário 5 dias:
      estrutura Dia 1 → Dia 5, 1–2 spots por dia, texto do dia nas cores da marca.

REGRAS DE MARCA E QUALIDADE (em todos os vídeos)
- Vertical 1080x1920. Títulos/legendas nas cores da marca (MARCA.md).
- Só o MEU footage nos vídeos a publicar; referências de terceiros ficam como estudo.
- Crédito ao criador quando aplicável.
- Música: preferir faixas em trend e livres de direitos.

PASSO 6 — Registar e parar para eu rever
- Cria/atualiza viralpulse/studio/OUTPUT.md com cada vídeo produzido: ideia,
  ficheiro final, referência usada, música, estado (rascunho / pronto a publicar).
- NÃO publiques automaticamente. Deixa os finais em studio/output/ para eu rever.

No fim, diz-me:
  1) o que resolveste das referências (criadores + likes),
  2) que vídeos ficaram em studio/output/,
  3) que footage meu falta para completar as ideias.
```

---

## Notas de uso

- **Pré-requisitos no Mac:** Palmier Pro instalado + MCP ligado no Claude Code;
  `yt-dlp` e `ffmpeg` instalados; este repositório clonado.
- **O teu footage:** mete os teus vídeos em `viralpulse/studio/assets/` antes de
  correres o Passo 5 (é o material dos vídeos finais).
- **Porquê "estudo" e não republicar:** descarregar as referências para estudar
  é moodboard; os vídeos publicados usam footage teu. Reutilizar um clip de
  terceiros só depois de permissão (fluxo do ViralPulse). É o que protege a marca.
