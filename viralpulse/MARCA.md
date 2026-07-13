# Marca — paleta de cores (entretenimento)

Cores oficiais da marca de entretenimento (Madeira Daily / ViralPulse).
Fonte: referência de design partilhada (Combo 02, @design.deb).

| Nome | Uso | Hex | FFmpeg |
|------|-----|-----|--------|
| **True Pink** | Cor primária / destaque, títulos, botões, banner "news" | `#FD1843` | `0xFD1843` |
| **Chill White** | Fundo claro, texto sobre fundo escuro | `#FFF9FA` | `0xFFF9FA` |
| **Black** | Fundo escuro / caixas de contraste atrás do texto | `#0A0A0A` | `0x0A0A0A` |

## Onde estão aplicadas

- **Editor de vídeo** (`agents/editor.py`) — lê estas cores de `config.yaml`
  (`brand.colors`) para o crédito, a watermark e o banner do modo "news".
- **Dashboard / futuros templates** — usar True Pink como cor de destaque e
  Chill White como base clara.

## Regras rápidas de uso

- **True Pink** é a estrela: usa em títulos, destaques e chamadas de atenção —
  com moderação para não cansar.
- **Chill White** como respiro/fundo; nunca branco puro (#FFFFFF), é sempre o
  #FFF9FA para dar o toque quente da marca.
- Texto sobre True Pink → usa Chill White. Texto sobre Chill White → True Pink
  ou preto.
- Manter forte contraste (acessibilidade): evitar True Pink sobre preto para
  texto pequeno.
