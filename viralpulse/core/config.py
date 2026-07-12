"""
Carregamento de configuração.

Duas fontes, com responsabilidades separadas:
  - .env        → segredos e flags de runtime (credenciais, DRY_RUN).
  - config.yaml → parâmetros editáveis não-secretos (hashtags, limites, textos).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Segredos e flags de runtime, lidos do ambiente / .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_prefix="",
        extra="ignore",
    )

    # Modo de operação
    dry_run: bool = Field(default=True, alias="VIRALPULSE_DRY_RUN")
    require_approval: bool = Field(default=True, alias="VIRALPULSE_REQUIRE_APPROVAL")

    # Instagram Graph API
    ig_business_account_id: str = Field(default="", alias="IG_BUSINESS_ACCOUNT_ID")
    ig_access_token: str = Field(default="", alias="IG_ACCESS_TOKEN")

    # TikTok
    tiktok_client_key: str = Field(default="", alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str = Field(default="", alias="TIKTOK_CLIENT_SECRET")
    tiktok_access_token: str = Field(default="", alias="TIKTOK_ACCESS_TOKEN")

    # Dashboard
    dashboard_password: str = Field(default="muda-me", alias="VIRALPULSE_DASHBOARD_PASSWORD")

    # Base de dados
    database_url: str = Field(default="sqlite:///viralpulse.db", alias="VIRALPULSE_DATABASE_URL")


def load_yaml_config() -> dict[str, Any]:
    """Lê config.yaml (ou config.example.yaml como fallback seguro)."""
    for candidate in ("config.yaml", "config.example.yaml"):
        path = BASE_DIR / candidate
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
    return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_config() -> dict[str, Any]:
    return load_yaml_config()
