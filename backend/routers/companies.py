"""
Router de empresas — preparação para multi-empresa.

Por enquanto suporta apenas uma empresa (configurada via env).
Estrutura preparada para expansão futura.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])

# ── Armazenamento em memória (futuro: banco de dados) ──
_companies: list[dict[str, Any]] = []
_initialized = False


def _ensure_default():
    """Garante que a empresa padrão (do .env) esteja na lista."""
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    _companies.append(
        {
            "id": 1,
            "nome": "Empresa Padrão",
            "cnpj": "",
            "sheets_id": settings.sheets_id_default,
            "active": True,
        }
    )
    _initialized = True


class CompanyCreate(BaseModel):
    """Corpo para criação de nova empresa."""
    nome: str
    cnpj: str = ""
    sheets_id: str


@router.get("")
async def list_companies():
    """Lista empresas configuradas."""
    _ensure_default()
    return {"companies": _companies}


@router.post("")
async def create_company(body: CompanyCreate):
    """Configura uma nova empresa."""
    _ensure_default()

    new_id = max(c["id"] for c in _companies) + 1 if _companies else 1

    company: dict[str, Any] = {
        "id": new_id,
        "nome": body.nome,
        "cnpj": body.cnpj,
        "sheets_id": body.sheets_id,
        "active": True,
    }
    _companies.append(company)

    logger.info("Nova empresa cadastrada: %s (ID %d)", body.nome, new_id)
    return {"company": company, "message": "Empresa criada com sucesso."}
