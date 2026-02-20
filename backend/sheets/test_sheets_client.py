"""
Testes unitários para SheetsClient.

Usa mocks do gspread e google-auth para validar a lógica sem chamadas
reais à API.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.sheets.sheets_client import SheetsClient
from backend.sheets.exceptions import (
    AuthenticationError,
    QuotaExceededError,
    SheetNotFoundError,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
FAKE_CREDS = {"type": "service_account", "project_id": "test"}
SPREADSHEET_ID = "fake-spreadsheet-id"

# Caminho dos patches
_PATCH_AUTHORIZE = "backend.sheets.sheets_client.gspread.authorize"
_PATCH_CREDENTIALS = "backend.sheets.sheets_client.Credentials.from_service_account_info"
_PATCH_SLEEP = "backend.sheets.sheets_client.time.sleep"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_gc():
    """Mocka gspread.authorize e Credentials para isolar testes da API."""
    with (
        patch(_PATCH_AUTHORIZE) as mock_auth,
        patch(_PATCH_CREDENTIALS) as mock_creds,
    ):
        mock_creds.return_value = MagicMock()  # Credentials mockadas
        mock_client = MagicMock()
        mock_auth.return_value = mock_client

        # Spreadsheet mock
        mock_spreadsheet = MagicMock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        # Default worksheet mock
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        mock_ws.id = 0
        mock_ws.row_count = 100
        mock_ws.col_count = 26
        mock_spreadsheet.worksheets.return_value = [mock_ws]
        mock_spreadsheet.worksheet.return_value = mock_ws

        yield mock_client, mock_spreadsheet, mock_ws


@pytest.fixture()
def client(mock_gc):
    """Constrói SheetsClient com mocks injetados."""
    return SheetsClient(FAKE_CREDS, SPREADSHEET_ID)


# ---------------------------------------------------------------------------
# Testes de inicialização
# ---------------------------------------------------------------------------

class TestInit:
    def test_auth_with_dict(self, client):
        assert client is not None

    def test_auth_with_json_string(self, mock_gc):
        c = SheetsClient(json.dumps(FAKE_CREDS), SPREADSHEET_ID)
        assert c is not None

    def test_auth_failure(self):
        with patch(_PATCH_CREDENTIALS, side_effect=Exception("bad creds")):
            with pytest.raises(AuthenticationError):
                SheetsClient({"bad": "creds"}, SPREADSHEET_ID)


# ---------------------------------------------------------------------------
# ensure_sheet_exists
# ---------------------------------------------------------------------------

class TestEnsureSheetExists:
    def test_creates_new_sheet(self, client, mock_gc):
        _, spreadsheet, _ = mock_gc
        new_ws = MagicMock()
        new_ws.id = 99
        spreadsheet.add_worksheet.return_value = new_ws

        client.ensure_sheet_exists("NovaAba", headers=["A", "B", "C"])
        spreadsheet.add_worksheet.assert_called_once()
        new_ws.update.assert_called_once_with([["A", "B", "C"]], "A1")

    def test_existing_sheet_no_headers(self, client, mock_gc):
        _, spreadsheet, _ = mock_gc
        # "Sheet1" já está no cache
        client.ensure_sheet_exists("Sheet1")
        spreadsheet.add_worksheet.assert_not_called()


# ---------------------------------------------------------------------------
# read_sheet
# ---------------------------------------------------------------------------

class TestReadSheet:
    def test_returns_dataframe(self, client, mock_gc):
        _, _, ws = mock_gc
        ws.get_all_records.return_value = [
            {"col1": "a", "col2": 1},
            {"col1": "b", "col2": 2},
        ]
        df = client.read_sheet("Sheet1")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["col1", "col2"]


# ---------------------------------------------------------------------------
# write_dataframe
# ---------------------------------------------------------------------------

class TestWriteDataframe:
    def test_writes_values(self, client, mock_gc):
        _, _, ws = mock_gc
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        client.write_dataframe("Sheet1", df, start_row=2)
        ws.update.assert_called_once()

    def test_empty_dataframe(self, client, mock_gc):
        _, _, ws = mock_gc
        df = pd.DataFrame()
        client.write_dataframe("Sheet1", df)
        ws.update.assert_not_called()


# ---------------------------------------------------------------------------
# append_rows
# ---------------------------------------------------------------------------

class TestAppendRows:
    def test_appends(self, client, mock_gc):
        _, _, ws = mock_gc
        client.append_rows("Sheet1", [["a", "b"], ["c", "d"]])
        ws.append_rows.assert_called_once()

    def test_empty_list(self, client, mock_gc):
        _, _, ws = mock_gc
        client.append_rows("Sheet1", [])
        ws.append_rows.assert_not_called()


# ---------------------------------------------------------------------------
# update_cell / update_range
# ---------------------------------------------------------------------------

class TestUpdates:
    def test_update_cell(self, client, mock_gc):
        _, _, ws = mock_gc
        client.update_cell("Sheet1", 2, 3, "valor")
        ws.update_cell.assert_called_once_with(2, 3, "valor")

    def test_update_range(self, client, mock_gc):
        _, _, ws = mock_gc
        client.update_range("Sheet1", "A1:B2", [["a", "b"], ["c", "d"]])
        ws.update.assert_called_once()


# ---------------------------------------------------------------------------
# Fórmulas
# ---------------------------------------------------------------------------

class TestFormulas:
    def test_write_formula(self, client, mock_gc):
        _, _, ws = mock_gc
        client.write_formula("Sheet1", 1, 1, "=SOMA(A1:A10)")
        ws.update_cell.assert_called_once_with(1, 1, "=SOMA(A1:A10)")

    def test_write_formula_no_equals(self, client):
        with pytest.raises(ValueError, match="deve começar com '='"):
            client.write_formula("Sheet1", 1, 1, "SOMA(A1:A10)")

    def test_batch_write_formulas(self, client, mock_gc):
        _, _, ws = mock_gc
        formulas = [
            {"row": 1, "col": 1, "formula": "=A1+B1"},
            {"row": 2, "col": 1, "formula": "=A2+B2"},
        ]
        client.batch_write_formulas("Sheet1", formulas)
        ws.update_cells.assert_called_once()

    def test_batch_write_invalid_formula(self, client):
        with pytest.raises(ValueError):
            client.batch_write_formulas(
                "Sheet1", [{"row": 1, "col": 1, "formula": "NO_EQUALS"}]
            )


# ---------------------------------------------------------------------------
# clear_sheet
# ---------------------------------------------------------------------------

class TestClearSheet:
    def test_clear_preserve_headers(self, client, mock_gc):
        _, _, ws = mock_gc
        ws.row_count = 50
        ws.col_count = 5
        client.clear_sheet("Sheet1", preserve_headers=True)
        ws.batch_clear.assert_called_once()

    def test_clear_all(self, client, mock_gc):
        _, _, ws = mock_gc
        client.clear_sheet("Sheet1", preserve_headers=False)
        ws.clear.assert_called_once()


# ---------------------------------------------------------------------------
# get_sheet_id
# ---------------------------------------------------------------------------

class TestGetSheetId:
    def test_cached(self, client):
        assert client.get_sheet_id("Sheet1") == 0

    def test_not_found(self, client, mock_gc):
        _, spreadsheet, _ = mock_gc
        spreadsheet.worksheets.return_value = []  # vazio no refresh
        with pytest.raises(SheetNotFoundError):
            client.get_sheet_id("Inexistente")


# ---------------------------------------------------------------------------
# format_range
# ---------------------------------------------------------------------------

class TestFormatRange:
    def test_format(self, client, mock_gc):
        _, _, ws = mock_gc
        fmt = {"textFormat": {"bold": True}}
        client.format_range("Sheet1", "A1:F1", fmt)
        ws.format.assert_called_once_with("A1:F1", fmt)


# ---------------------------------------------------------------------------
# Retry / Rate limiting
# ---------------------------------------------------------------------------

class TestRetry:
    def test_retry_on_429(self, client, mock_gc):
        _, _, ws = mock_gc
        resp = MagicMock()
        resp.status_code = 429
        api_err = __import__("gspread").exceptions.APIError(resp)

        # Falha 2x com 429, depois sucesso
        ws.get_all_records.side_effect = [api_err, api_err, [{"a": 1}]]

        with patch(_PATCH_SLEEP):
            df = client.read_sheet("Sheet1")
        assert len(df) == 1

    def test_quota_exceeded_after_max_retries(self, client, mock_gc):
        _, _, ws = mock_gc
        resp = MagicMock()
        resp.status_code = 429
        api_err = __import__("gspread").exceptions.APIError(resp)
        ws.get_all_records.side_effect = [api_err] * 10

        with patch(_PATCH_SLEEP):
            with pytest.raises(QuotaExceededError):
                client.read_sheet("Sheet1")


# ---------------------------------------------------------------------------
# SheetNotFoundError
# ---------------------------------------------------------------------------

class TestSheetNotFound:
    def test_worksheet_not_found(self, client, mock_gc):
        _, spreadsheet, _ = mock_gc
        spreadsheet.worksheet.side_effect = (
            __import__("gspread").exceptions.WorksheetNotFound("X")
        )
        with pytest.raises(SheetNotFoundError):
            client.read_sheet("X")
