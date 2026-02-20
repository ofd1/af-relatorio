"""
Router de dados do dashboard.

Lê dados das abas DRE, BP e DFC do Google Sheets e retorna JSON
formatado para o frontend. Cache de 5 minutos via ``cachetools.TTLCache``.
"""

from __future__ import annotations

import logging
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter, Query, Request, HTTPException

from backend.sheets.sheets_client import SheetsClient
from backend.sheets.base_writer import BaseWriter
from backend.sheets.dre_builder import DREBuilder
from backend.sheets.bp_builder import BPBuilder
from backend.sheets.dfc_builder import DFCBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["dashboard"])

# Cache com TTL de 5 minutos, até 50 entradas
_cache: TTLCache = TTLCache(maxsize=50, ttl=300)


def _get_sheets_client(request: Request) -> SheetsClient:
    client = getattr(request.app.state, "sheets_client", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="SheetsClient não inicializado.",
        )
    return client


def _df_to_records(df) -> list[dict[str, Any]]:
    """Converte DataFrame para lista de dicts, tratando NaN."""
    if df.empty:
        return []
    return df.fillna("").to_dict(orient="records")


def _filter_by_year(records: list[dict], year: str) -> list[dict]:
    """Filtra registros cujas colunas de período contenham o ano."""
    # Os dados vêm das abas DRE/BP/DFC com colunas como Jan/25, Fev/25 etc.
    # Não filtramos aqui — retornamos tudo e o frontend filtra
    return records


@router.get("/dre")
async def get_dre(request: Request, year: str = Query(default="2025")):
    """Retorna a DRE completa em formato JSON."""
    cache_key = f"dre_{year}"
    if cache_key in _cache:
        return _cache[cache_key]

    sheets_client = _get_sheets_client(request)
    dre = DREBuilder(sheets_client)

    try:
        df = dre.get_dre_data()
        data = _df_to_records(df)
        result = {
            "statement": "DRE",
            "year": year,
            "rows": data,
            "structure": DREBuilder.get_structure(),
        }
        _cache[cache_key] = result
        return result
    except Exception as exc:
        logger.exception("Erro ao ler DRE")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/bp")
async def get_bp(request: Request, year: str = Query(default="2025")):
    """Retorna o Balanço Patrimonial completo em formato JSON."""
    cache_key = f"bp_{year}"
    if cache_key in _cache:
        return _cache[cache_key]

    sheets_client = _get_sheets_client(request)
    bp = BPBuilder(sheets_client)

    try:
        df = bp.get_bp_data()
        data = _df_to_records(df)
        result = {
            "statement": "BP",
            "year": year,
            "rows": data,
            "structure": BPBuilder.get_structure(),
        }
        _cache[cache_key] = result
        return result
    except Exception as exc:
        logger.exception("Erro ao ler BP")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dfc")
async def get_dfc(request: Request, year: str = Query(default="2025")):
    """Retorna a DFC completa em formato JSON."""
    cache_key = f"dfc_{year}"
    if cache_key in _cache:
        return _cache[cache_key]

    sheets_client = _get_sheets_client(request)
    dfc = DFCBuilder(sheets_client)

    try:
        df = dfc.get_dfc_data()
        data = _df_to_records(df)
        result = {
            "statement": "DFC",
            "year": year,
            "rows": data,
            "structure": DFCBuilder.get_structure(),
        }
        _cache[cache_key] = result
        return result
    except Exception as exc:
        logger.exception("Erro ao ler DFC")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/indicators")
async def get_indicators(request: Request, year: str = Query(default="2025")):
    """Calcula e retorna indicadores financeiros baseados na DRE."""
    cache_key = f"indicators_{year}"
    if cache_key in _cache:
        return _cache[cache_key]

    sheets_client = _get_sheets_client(request)
    dre = DREBuilder(sheets_client)

    try:
        df = dre.get_dre_data()
        if df.empty:
            return {"year": year, "indicators": {}}

        # Tentar extrair indicadores das linhas da DRE
        # As linhas são indexadas pela coluna A (label)
        indicators: dict[str, Any] = {"year": year}

        # Converter para dict por label para acesso rápido
        records = _df_to_records(df)
        by_label: dict[str, dict] = {}
        for row in records:
            label = str(row.get(df.columns[0], "")).strip() if df.columns[0] in row else ""
            if not label:
                # Tentar primeira coluna
                first_col = list(row.keys())[0] if row else ""
                label = str(row.get(first_col, "")).strip()
            if label:
                by_label[label] = row

        # Extrair valores numéricos das colunas de meses
        def _get_total(label_name: str) -> float:
            """Obtém o valor da coluna Total ou da última coluna numérica."""
            row_data = by_label.get(label_name, {})
            for key in ["Total", "TOTAL", "Acumulado"]:
                if key in row_data:
                    try:
                        return float(row_data[key])
                    except (ValueError, TypeError):
                        pass
            # Fallback: última coluna numérica
            for val in reversed(list(row_data.values())):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
            return 0.0

        receita_bruta = _get_total("Receita Bruta de Serviços")
        receita_liquida = _get_total("Receita Líquida")
        lucro_bruto = _get_total("Lucro Bruto")
        ebitda = _get_total("EBITDA")
        lucro_operacional = _get_total("Lucro Operacional (EBIT)")
        lucro_liquido = _get_total("Lucro Líquido")

        indicators["margins"] = {
            "margem_bruta": (
                round(lucro_bruto / receita_liquida * 100, 2)
                if receita_liquida
                else 0
            ),
            "margem_ebitda": (
                round(ebitda / receita_liquida * 100, 2)
                if receita_liquida
                else 0
            ),
            "margem_operacional": (
                round(lucro_operacional / receita_liquida * 100, 2)
                if receita_liquida
                else 0
            ),
            "margem_liquida": (
                round(lucro_liquido / receita_liquida * 100, 2)
                if receita_liquida
                else 0
            ),
        }

        indicators["absolute"] = {
            "receita_bruta": receita_bruta,
            "receita_liquida": receita_liquida,
            "lucro_bruto": lucro_bruto,
            "ebitda": ebitda,
            "lucro_operacional": lucro_operacional,
            "lucro_liquido": lucro_liquido,
        }

        _cache[cache_key] = indicators
        return indicators

    except Exception as exc:
        logger.exception("Erro ao calcular indicadores")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary")
async def get_summary(request: Request):
    """Resumo geral: períodos disponíveis, empresa, última atualização."""
    cache_key = "summary"
    if cache_key in _cache:
        return _cache[cache_key]

    sheets_client = _get_sheets_client(request)
    base_writer = BaseWriter(sheets_client)

    try:
        periods = base_writer.get_existing_periods()
        all_data = base_writer.get_all_data()

        empresa = ""
        if not all_data.empty and "titulo_conta" in all_data.columns:
            # Empresa pode estar nos metadados ou no header original
            pass

        result: dict[str, Any] = {
            "periods": periods,
            "empresa": empresa,
            "total_rows": len(all_data),
            "years": sorted(set(p[:4] for p in periods)) if periods else [],
        }

        _cache[cache_key] = result
        return result

    except Exception as exc:
        logger.exception("Erro ao gerar resumo")
        raise HTTPException(status_code=500, detail=str(exc))
