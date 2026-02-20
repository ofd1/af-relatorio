"""
Router do DEPARA — gestão do mapeamento de contas contábeis.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from backend.classifier.depara_manager import DEPARAManager
from backend.sheets.base_writer import BaseWriter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/depara", tags=["depara"])


class UpdateClassificationBody(BaseModel):
    """Corpo para atualização de classificação."""
    classificacao: str


def _get_sheets_client(request: Request):
    client = getattr(request.app.state, "sheets_client", None)
    if client is None:
        raise HTTPException(
            status_code=503, detail="SheetsClient não inicializado."
        )
    return client


@router.get("")
async def get_depara(request: Request):
    """Retorna lista completa do DEPARA."""
    sheets_client = _get_sheets_client(request)
    depara_mgr = DEPARAManager(sheets_client)

    try:
        df = depara_mgr.get_full_depara()
        records = df.fillna("").to_dict(orient="records") if not df.empty else []
        return {"depara": records, "total": len(records)}
    except Exception as exc:
        logger.exception("Erro ao ler DEPARA")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{codigo_conta}")
async def update_depara(
    codigo_conta: str,
    body: UpdateClassificationBody,
    request: Request,
):
    """
    Atualiza classificação de uma conta.

    Propaga a atualização para a Base Balancete. Se a classificação
    for nova, ela será usada nos próximos builds de DRE/BP.
    """
    sheets_client = _get_sheets_client(request)
    depara_mgr = DEPARAManager(sheets_client)
    base_writer = BaseWriter(sheets_client)

    try:
        # Atualizar no DEPARA
        depara_result = depara_mgr.update_classification(
            codigo_conta, body.classificacao
        )

        # Propagar para Base Balancete
        updated_rows = base_writer.update_classifications(
            codigo_conta, body.classificacao
        )

        result: dict[str, Any] = {
            "codigo_conta": codigo_conta,
            "classificacao": body.classificacao,
            "updated_rows": updated_rows,
            "depara_update": depara_result,
        }

        logger.info(
            "DEPARA atualizado: %s → '%s' (%d linhas na base)",
            codigo_conta,
            body.classificacao,
            updated_rows,
        )

        return result

    except Exception as exc:
        logger.exception("Erro ao atualizar DEPARA")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pending")
async def get_pending(request: Request):
    """Retorna contas pendentes de revisão."""
    sheets_client = _get_sheets_client(request)
    depara_mgr = DEPARAManager(sheets_client)

    try:
        pending = depara_mgr.get_pending_reviews()
        return {"pending": pending, "total": len(pending)}
    except Exception as exc:
        logger.exception("Erro ao buscar pendentes")
        raise HTTPException(status_code=500, detail=str(exc))
