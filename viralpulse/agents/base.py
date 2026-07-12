"""Classe base dos agentes."""

from __future__ import annotations

from typing import Any

from ..core.config import Settings, get_config, get_settings
from ..core.logging_setup import get_logger


class BaseAgent:
    """Funcionalidade partilhada: acesso a settings, config e logger próprio."""

    name: str = "agent"

    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.config: dict[str, Any] = get_config()
        self.log = get_logger(self.name)

    @property
    def dry_run(self) -> bool:
        return self.settings.dry_run
