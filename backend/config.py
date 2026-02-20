"""
Configuração centralizada da aplicação via variáveis de ambiente.

Usa ``pydantic-settings`` para carregar valores do ``.env`` com validação
e type-casting automático.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação."""

    app_password: str
    google_credentials_json: str
    sheets_id_default: str  # ID da planilha padrão
    google_drive_folder_id: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Retorna instância única de Settings (cached)."""
    return Settings()  # type: ignore[call-arg]
