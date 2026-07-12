"""Configuração de logging estruturado (structlog) + alertas simples."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configura logging legível na consola e estruturado."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def alert(message: str, **context) -> None:
    """
    Ponto único de alertas. Por agora escreve no log com nível de erro;
    trocar por Telegram/Slack/email quando quiseres notificações reais.
    """
    get_logger("alert").error("ALERTA", message=message, **context)
