"""
Router de upload de balancetes.

Pipeline síncrono completo:
  1. Recebe arquivo .xls/.xlsx
  2. Parseia via ``balancete_parser``
  3. Valida hierarquia e balanço
  4. Classifica contas (DEPARA + IA)
  5. Escreve na Base Balancete
  6. Atualiza DRE, BP, DFC
  7. Roda validações finais
  8. Retorna resultado JSON
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, UploadFile, File, HTTPException

from backend.parsers.balancete_parser import parse_balancete
from backend.validators.hierarchy_validator import (
    validate_hierarchy,
    validate_balance_sheet,
    validate_level_classification,
)
from backend.classifier.depara_manager import DEPARAManager
from backend.classifier.ai_classifier import classify_new_accounts
from backend.sheets.base_writer import BaseWriter
from backend.sheets.dre_builder import DREBuilder
from backend.sheets.bp_builder import BPBuilder
from backend.sheets.dfc_builder import DFCBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

# Cache de processamentos recentes (em memória)
_recent_processings: list[dict[str, Any]] = []
_MAX_RECENT = 20


def _get_sheets_client(request: Request):
    client = getattr(request.app.state, "sheets_client", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="SheetsClient não inicializado. Verifique credenciais.",
        )
    return client


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload e processamento completo de um balancete.

    Aceita arquivos .xls ou .xlsx. Executa todo o pipeline de forma
    síncrona e retorna resultado detalhado.
    """
    start = time.time()
    warnings: list[str] = []
    errors: list[str] = []

    # ── 1. Validar extensão e salvar arquivo temporário ──
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo ausente.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{ext}'. Use .xls ou .xlsx.",
        )

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        logger.info("Arquivo salvo: %s (%d bytes)", tmp_path, len(content))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao salvar arquivo: {exc}"
        )

    try:
        # ── 2. Parse do balancete ──
        logger.info("Parseando balancete...")
        header, df = parse_balancete(tmp_path)
        periodo = header.get("mes_referencia", "desconhecido")
        logger.info(
            "Parseado: %s | %d linhas | período %s",
            header.get("empresa", "?"),
            len(df),
            periodo,
        )

        # ── 3. Validações de hierarquia e balanço ──
        logger.info("Validando hierarquia...")
        hierarchy_results = validate_hierarchy(df)
        hierarchy_errors = [
            r for r in hierarchy_results if r.get("status") == "ERROR"
        ]
        hierarchy_warnings = [
            r for r in hierarchy_results if r.get("status") == "WARNING"
        ]
        if hierarchy_errors:
            errors.extend(
                [f"Hierarquia: {r['mensagem']}" for r in hierarchy_errors]
            )
        if hierarchy_warnings:
            warnings.extend(
                [f"Hierarquia: {r['mensagem']}" for r in hierarchy_warnings]
            )

        balance_result = validate_balance_sheet(df)
        if balance_result.get("status") == "ERROR":
            errors.append(f"Balanço: {balance_result.get('mensagem', '')}")
        elif balance_result.get("status") == "WARNING":
            warnings.append(f"Balanço: {balance_result.get('mensagem', '')}")

        level_errors = validate_level_classification(df)
        if level_errors:
            warnings.extend(
                [f"Classificação nível: {e['mensagem']}" for e in level_errors]
            )

        # ── 4. Classificar contas (DEPARA) ──
        sheets_client = _get_sheets_client(request)
        depara_mgr = DEPARAManager(sheets_client)

        logger.info("Classificando contas via DEPARA...")
        df = depara_mgr.classify_accounts(df)

        # ── 5. Contas não classificadas → IA ──
        new_accounts_info: list[dict] = []
        unclassified = df[
            (df["tipo"] == "Último Nível")
            & (
                df["classificacao_depara"].isna()
                | (df["classificacao_depara"] == "")
            )
        ]

        if not unclassified.empty:
            logger.info(
                "%d contas sem classificação — consultando IA...",
                len(unclassified),
            )
            accounts_for_ai = [
                {
                    "codigo_conta": str(row["codigo_conta"]),
                    "titulo_conta": str(row["titulo_conta"]),
                    "grupo": str(row.get("grupo", "")),
                }
                for _, row in unclassified.iterrows()
            ]

            existing_cls = depara_mgr.get_all_classifications()

            try:
                import asyncio
                ai_results = asyncio.get_event_loop().run_until_complete(
                    classify_new_accounts(accounts_for_ai, existing_cls)
                )
            except RuntimeError:
                # Já dentro de um event loop (FastAPI async)
                ai_results = await classify_new_accounts(
                    accounts_for_ai, existing_cls
                )

            # Aplicar classificações da IA no DataFrame
            ai_map = {r["codigo_conta"]: r for r in ai_results}
            for idx, row in df.iterrows():
                code = str(row["codigo_conta"])
                if code in ai_map and ai_map[code].get("classificacao"):
                    df.at[idx, "classificacao_depara"] = ai_map[code][
                        "classificacao"
                    ]

            # Adicionar novas contas ao DEPARA no Sheets
            new_depara_entries = [
                {
                    "codigo_conta": r["codigo_conta"],
                    "titulo_original": r.get(
                        "titulo_conta",
                        accounts_for_ai[i].get("titulo_conta", ""),
                    ),
                    "classificacao": r.get("classificacao", ""),
                    "grupo_df": r.get("grupo_df", ""),
                    "status": "IA" if r.get("classificacao") else "Pendente",
                }
                for i, r in enumerate(ai_results)
                if r.get("classificacao")
            ]
            if new_depara_entries:
                depara_mgr.add_new_accounts(new_depara_entries)

            new_accounts_info = ai_results
            warnings.append(
                f"{len(ai_results)} contas classificadas por IA — revisar."
            )

        # ── 6. Escrever na Base Balancete ──
        logger.info("Escrevendo na Base Balancete...")
        base_writer = BaseWriter(sheets_client)
        write_result = base_writer.write_month(header, df)

        # ── 7. Atualizar/Criar DRE, BP, DFC ──
        logger.info("Atualizando demonstrativos financeiros...")
        periods = sorted(base_writer.get_existing_periods())

        dre_builder = DREBuilder(sheets_client)
        dre_builder.build_dre(periods)

        bp_builder = BPBuilder(sheets_client)
        bp_builder.build_bp(periods)

        dfc_builder = DFCBuilder(sheets_client)
        dfc_builder.build_dfc(periods)

        # ── 8. Validações finais ──
        final_validations: dict[str, Any] = {
            "hierarchy_errors": len(hierarchy_errors),
            "hierarchy_warnings": len(hierarchy_warnings),
            "balance_ok": balance_result.get("status") != "ERROR",
            "periods_available": periods,
        }

        # ── 9. Resultado ──
        elapsed = round(time.time() - start, 2)
        result: dict[str, Any] = {
            "status": "error" if errors else "success",
            "periodo": periodo,
            "empresa": header.get("empresa", ""),
            "rows_written": write_result.get("rows_written", 0),
            "replaced": write_result.get("replaced", False),
            "warnings": warnings,
            "errors": errors,
            "new_accounts": new_accounts_info,
            "validations": final_validations,
            "elapsed_seconds": elapsed,
        }

        # Salvar no cache de processamentos recentes
        _recent_processings.insert(
            0,
            {
                **result,
                "filename": file.filename,
                "timestamp": datetime.now().isoformat(),
            },
        )
        if len(_recent_processings) > _MAX_RECENT:
            _recent_processings.pop()

        logger.info("Upload concluído em %.2fs — %s", elapsed, result["status"])
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro no processamento do upload")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # Limpeza do arquivo temporário
        try:
            os.unlink(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


@router.get("/upload/status")
async def upload_status():
    """Retorna processamentos recentes."""
    return {"processings": _recent_processings}
