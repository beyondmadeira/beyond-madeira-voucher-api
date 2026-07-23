"""Utilitários de custo/consumo da API Anthropic (Claude).

Centraliza:
  - a tabela de preços por modelo,
  - a estimativa de custo a partir do bloco `usage` da resposta,
  - o registo best-effort do consumo na tabela api_usage_log.

Nada aqui pode levantar exceção para o chamador: se o registo falhar
(ex.: tabela ainda não migrada), apenas escreve no stdout e segue.
"""
import logging

log = logging.getLogger(__name__)

# Preço em USD por 1 milhão de tokens. (input, output, cache_read, cache_write)
# Valores aproximados — atualizar se a Anthropic mudar a tabela.
_PRICING = {
    "opus":   (15.0, 75.0, 1.50, 18.75),
    "sonnet": (3.0,  15.0, 0.30,  3.75),
    "haiku":  (1.0,   5.0, 0.10,  1.25),
}
# Fallback conservador (assume Sonnet) para modelos desconhecidos.
_DEFAULT_PRICE = _PRICING["sonnet"]


def _price_for(model):
    m = (model or "").lower()
    for key, price in _PRICING.items():
        if key in m:
            return price
    return _DEFAULT_PRICE


def parse_usage(usage):
    """Normaliza o bloco `usage` da resposta Anthropic para inteiros."""
    usage = usage or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "cache_read_tokens": int(usage.get("cache_read_input_tokens") or 0),
        "cache_write_tokens": int(usage.get("cache_creation_input_tokens") or 0),
    }


def estimate_cost(model, u):
    """u = dict devolvido por parse_usage(). Devolve custo estimado em USD."""
    p_in, p_out, p_cr, p_cw = _price_for(model)
    return (
        u["input_tokens"] / 1_000_000 * p_in
        + u["output_tokens"] / 1_000_000 * p_out
        + u["cache_read_tokens"] / 1_000_000 * p_cr
        + u["cache_write_tokens"] / 1_000_000 * p_cw
    )


def log_usage(endpoint, model, usage, user_name=""):
    """Regista uma chamada. Best-effort: nunca propaga exceções.

    `usage` é o bloco cru vindo da API Anthropic (dict).
    """
    try:
        u = parse_usage(usage)
        cost = estimate_cost(model, u)
        # Log sempre no stdout (aparece nos logs do Railway em tempo real).
        log.info(
            "[ANTHROPIC USAGE] endpoint=%s model=%s user=%s in=%d out=%d "
            "cache_read=%d cache_write=%d est_cost=$%.5f",
            endpoint, model, user_name or "-",
            u["input_tokens"], u["output_tokens"],
            u["cache_read_tokens"], u["cache_write_tokens"], cost,
        )
        # Persistir na BD (best-effort).
        try:
            from app.extensions import db
            from app.models.usage_log import ApiUsageLog
            row = ApiUsageLog(
                endpoint=endpoint,
                model=model or "",
                user_name=user_name or "",
                input_tokens=u["input_tokens"],
                output_tokens=u["output_tokens"],
                cache_read_tokens=u["cache_read_tokens"],
                cache_write_tokens=u["cache_write_tokens"],
                est_cost_usd=cost,
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            try:
                from app.extensions import db
                db.session.rollback()
            except Exception:
                pass
            log.exception("[ANTHROPIC USAGE] falha a persistir na BD (segue)")
        return cost
    except Exception:
        log.exception("[ANTHROPIC USAGE] falha inesperada no log (ignorado)")
        return 0.0
