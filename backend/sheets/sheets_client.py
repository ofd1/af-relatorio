"""
Wrapper para a Google Sheets API.

Usa gspread + google-auth para interação simplificada com planilhas Google.
Inclui retry automático, rate limiting, cache de metadados e logging.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from .exceptions import AuthenticationError, QuotaExceededError, SheetNotFoundError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_MAX_RETRIES = 5
_INITIAL_BACKOFF_S = 2.0
_RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_MAX_REQUESTS = 60


class SheetsClient:
    """Cliente para leitura/escrita em Google Sheets via gspread."""

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------
    def __init__(self, credentials_json: str | dict, spreadsheet_id: str) -> None:
        """
        Inicializa o cliente.

        Args:
            credentials_json: JSON string ou dict com credenciais de service account.
            spreadsheet_id: ID da planilha Google Sheets.
        """
        self._spreadsheet_id = spreadsheet_id

        # Cache de metadados
        self._sheet_id_cache: dict[str, int] = {}

        # Rate limiting simples (token-bucket por janela de 60 s)
        self._request_timestamps: list[float] = []

        try:
            creds_info = (
                json.loads(credentials_json)
                if isinstance(credentials_json, str)
                else credentials_json
            )
            creds = Credentials.from_service_account_info(creds_info, scopes=_SCOPES)
            self._gc = gspread.authorize(creds)
            logger.info("Autenticação bem-sucedida com Google Sheets API.")
        except Exception as exc:
            logger.error("Falha na autenticação: %s", exc)
            raise AuthenticationError(str(exc)) from exc

        self._spreadsheet = self._call_with_retry(
            lambda: self._gc.open_by_key(self._spreadsheet_id)
        )
        self._refresh_sheet_id_cache()

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _enforce_rate_limit(self) -> None:
        """Aguarda se necessário para respeitar o limite de 60 req/min."""
        now = time.monotonic()
        # Remove timestamps fora da janela
        self._request_timestamps = [
            t for t in self._request_timestamps if now - t < _RATE_LIMIT_WINDOW_S
        ]
        if len(self._request_timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            wait = _RATE_LIMIT_WINDOW_S - (now - self._request_timestamps[0])
            if wait > 0:
                logger.warning("Rate limit atingido. Aguardando %.1f s…", wait)
                time.sleep(wait)
        self._request_timestamps.append(time.monotonic())

    def _call_with_retry(self, fn, *args, **kwargs) -> Any:
        """
        Executa *fn* com retry automático em erros de quota (HTTP 429)
        usando backoff exponencial.
        """
        backoff = _INITIAL_BACKOFF_S
        for attempt in range(1, _MAX_RETRIES + 1):
            self._enforce_rate_limit()
            try:
                return fn(*args, **kwargs)
            except gspread.exceptions.APIError as exc:
                status = exc.response.status_code  # type: ignore[union-attr]
                if status == 429:
                    if attempt == _MAX_RETRIES:
                        logger.error("Quota excedida após %d tentativas.", _MAX_RETRIES)
                        raise QuotaExceededError() from exc
                    logger.warning(
                        "HTTP 429 – tentativa %d/%d, aguardando %.1f s…",
                        attempt,
                        _MAX_RETRIES,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise
        # Nunca deveria chegar aqui, mas por segurança:
        raise QuotaExceededError()  # pragma: no cover

    def _refresh_sheet_id_cache(self) -> None:
        """Atualiza o cache de sheet IDs a partir dos metadados da planilha."""
        for ws in self._spreadsheet.worksheets():
            self._sheet_id_cache[ws.title] = ws.id
        logger.debug("Cache de sheet IDs atualizado: %s", self._sheet_id_cache)

    def _get_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Retorna o worksheet pelo nome, com erro amigável."""
        try:
            return self._call_with_retry(
                lambda: self._spreadsheet.worksheet(sheet_name)
            )
        except gspread.exceptions.WorksheetNotFound as exc:
            raise SheetNotFoundError(sheet_name) from exc

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def ensure_sheet_exists(
        self, sheet_name: str, headers: list[str] | None = None
    ) -> None:
        """
        Cria a aba se não existir. Se *headers* fornecido, escreve na linha 1.
        """
        if sheet_name in self._sheet_id_cache:
            logger.info("Aba '%s' já existe.", sheet_name)
            ws = self._get_worksheet(sheet_name)
        else:
            rows = max(1000, len(headers) if headers else 1000)
            cols = max(26, len(headers) if headers else 26)
            ws = self._call_with_retry(
                lambda: self._spreadsheet.add_worksheet(
                    title=sheet_name, rows=rows, cols=cols
                )
            )
            self._sheet_id_cache[sheet_name] = ws.id
            logger.info("Aba '%s' criada com sucesso.", sheet_name)

        if headers:
            self._call_with_retry(
                lambda: ws.update([headers], "A1")
            )
            logger.info("Headers escritos na aba '%s': %s", sheet_name, headers)

    def read_sheet(self, sheet_name: str) -> pd.DataFrame:
        """Lê toda a aba e retorna um DataFrame (primeira linha = cabeçalho)."""
        ws = self._get_worksheet(sheet_name)
        records = self._call_with_retry(lambda: ws.get_all_records())
        df = pd.DataFrame(records)
        logger.info(
            "Leitura da aba '%s': %d linhas × %d colunas.",
            sheet_name,
            len(df),
            len(df.columns),
        )
        return df

    def write_dataframe(
        self, sheet_name: str, df: pd.DataFrame, start_row: int = 2
    ) -> None:
        """
        Escreve um DataFrame na aba a partir de *start_row*.
        Preserva o cabeçalho existente (linha 1).
        """
        ws = self._get_worksheet(sheet_name)
        values = df.astype(str).values.tolist()
        if not values:
            logger.warning("DataFrame vazio — nada a escrever na aba '%s'.", sheet_name)
            return

        cell_range = f"A{start_row}"
        self._call_with_retry(lambda: ws.update(values, cell_range))
        logger.info(
            "Escrita de %d linhas na aba '%s' a partir de %s.",
            len(values),
            sheet_name,
            cell_range,
        )

    def append_rows(self, sheet_name: str, rows: list[list]) -> None:
        """Adiciona linhas ao final da aba."""
        if not rows:
            return
        ws = self._get_worksheet(sheet_name)
        self._call_with_retry(
            lambda: ws.append_rows(rows, value_input_option="USER_ENTERED")
        )
        logger.info(
            "%d linhas adicionadas ao final da aba '%s'.", len(rows), sheet_name
        )

    def update_cell(self, sheet_name: str, row: int, col: int, value: Any) -> None:
        """Atualiza uma célula específica (row e col são 1-indexed)."""
        ws = self._get_worksheet(sheet_name)
        self._call_with_retry(lambda: ws.update_cell(row, col, value))
        logger.info(
            "Célula (%d, %d) da aba '%s' atualizada para '%s'.",
            row,
            col,
            sheet_name,
            value,
        )

    def update_range(
        self, sheet_name: str, range_str: str, values: list[list]
    ) -> None:
        """Atualiza um range (ex: ``"A1:F10"``)."""
        ws = self._get_worksheet(sheet_name)
        self._call_with_retry(lambda: ws.update(values, range_str))
        logger.info(
            "Range '%s' da aba '%s' atualizado (%d linhas).",
            range_str,
            sheet_name,
            len(values),
        )

    def write_formula(
        self, sheet_name: str, row: int, col: int, formula: str
    ) -> None:
        """
        Escreve uma fórmula numa célula.

        Args:
            formula: Deve começar com ``=``.
        """
        if not formula.startswith("="):
            raise ValueError(f"Fórmula deve começar com '=': {formula!r}")
        ws = self._get_worksheet(sheet_name)
        self._call_with_retry(lambda: ws.update_cell(row, col, formula))
        logger.info(
            "Fórmula escrita em (%d, %d) da aba '%s': %s",
            row,
            col,
            sheet_name,
            formula,
        )

    def batch_write_formulas(
        self, sheet_name: str, formulas: list[dict]
    ) -> None:
        """
        Escreve múltiplas fórmulas de uma vez via batch update.

        Args:
            formulas: Lista de dicts ``{"row": int, "col": int, "formula": str}``.
        """
        if not formulas:
            return

        ws = self._get_worksheet(sheet_name)
        cells: list[gspread.Cell] = []

        for entry in formulas:
            formula = entry["formula"]
            if not formula.startswith("="):
                raise ValueError(f"Fórmula deve começar com '=': {formula!r}")
            cells.append(gspread.Cell(entry["row"], entry["col"], value=formula))

        self._call_with_retry(
            lambda: ws.update_cells(cells, value_input_option="USER_ENTERED")
        )
        logger.info(
            "%d fórmulas escritas em batch na aba '%s'.", len(cells), sheet_name
        )

    def clear_sheet(
        self, sheet_name: str, preserve_headers: bool = True
    ) -> None:
        """
        Limpa dados da aba. Se *preserve_headers* for ``True``, mantém a linha 1.
        """
        ws = self._get_worksheet(sheet_name)

        if preserve_headers:
            # Limpa a partir da linha 2 até o final
            row_count = ws.row_count
            if row_count > 1:
                end_col = gspread.utils.rowcol_to_a1(1, ws.col_count).replace("1", "")
                clear_range = f"A2:{end_col}{row_count}"
                self._call_with_retry(lambda: ws.batch_clear([clear_range]))
                logger.info(
                    "Aba '%s' limpa (headers preservados). Range: %s",
                    sheet_name,
                    clear_range,
                )
        else:
            self._call_with_retry(lambda: ws.clear())
            logger.info("Aba '%s' completamente limpa.", sheet_name)

    def get_sheet_id(self, sheet_name: str) -> int:
        """Retorna o sheetId numérico (útil para chamadas de formatação)."""
        if sheet_name in self._sheet_id_cache:
            return self._sheet_id_cache[sheet_name]

        # Força refresh caso a aba tenha sido criada externamente
        self._refresh_sheet_id_cache()
        if sheet_name in self._sheet_id_cache:
            return self._sheet_id_cache[sheet_name]

        raise SheetNotFoundError(sheet_name)

    def format_range(
        self, sheet_name: str, range_str: str, format_dict: dict
    ) -> None:
        """
        Aplica formatação a um range.

        Args:
            range_str: ex ``"A1:F1"``
            format_dict: dicionário no formato aceito por ``gspread.worksheet.format``.

                Exemplos de chaves aceitas:

                - ``textFormat``: ``{"bold": True, "fontSize": 12}``
                - ``backgroundColor``: ``{"red": 0.9, "green": 0.9, "blue": 0.9}``
                - ``numberFormat``: ``{"type": "NUMBER", "pattern": "#,##0.00"}``
                - ``horizontalAlignment``: ``"CENTER"``
        """
        ws = self._get_worksheet(sheet_name)
        self._call_with_retry(lambda: ws.format(range_str, format_dict))
        logger.info(
            "Formatação aplicada em '%s' da aba '%s': %s",
            range_str,
            sheet_name,
            format_dict,
        )
