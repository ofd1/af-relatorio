"""
Testes unitários para BaseWriter.

Mocka o SheetsClient para validar a lógica de escrita, substituição
por período, consultas e atualização de classificações.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pandas as pd
import pytest

from backend.sheets.base_writer import HEADERS, SHEET_NAME, BaseWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_mock(existing_data: pd.DataFrame | None = None) -> MagicMock:
    """Cria SheetsClient mock com dados existentes opcionais."""
    client = MagicMock()
    if existing_data is not None:
        client.read_sheet.return_value = existing_data
    else:
        client.read_sheet.return_value = pd.DataFrame(columns=HEADERS)
    return client


def _sample_parser_df(periodo: str = "2025-01", n: int = 3) -> pd.DataFrame:
    """Retorna DataFrame no formato de saída do parser."""
    records = []
    for i in range(1, n + 1):
        records.append(
            {
                "codigo_conta": f"1.0{i}",
                "titulo_conta": f"Conta {i}",
                "nivel": 2,
                "tipo": "Último Nível",
                "grupo": "ATIVO",
                "periodo": periodo,
                "saldo_anterior": 100.0 * i,
                "debitos": 50.0,
                "creditos": 30.0,
                "saldo_atual": 120.0 * i,
                "indicador_dc": "D",
            }
        )
    return pd.DataFrame(records)


def _sample_header(periodo: str = "2025-01") -> dict:
    return {"mes_referencia": periodo, "cnpj": "00.000.000/0001-00"}


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestInit:
    def test_ensures_sheet_exists_on_init(self):
        client = _make_client_mock()
        BaseWriter(client)
        client.ensure_sheet_exists.assert_called_once_with(
            SHEET_NAME, headers=HEADERS
        )


class TestWriteMonth:
    def test_write_new_period(self):
        """Período novo → append, replaced=False."""
        client = _make_client_mock()
        writer = BaseWriter(client)

        result = writer.write_month(_sample_header("2025-03"), _sample_parser_df("2025-03"))

        assert result["periodo"] == "2025-03"
        assert result["replaced"] is False
        assert result["rows_written"] == 3
        client.append_rows.assert_called_once()

    def test_replace_existing_period(self):
        """Período já existe → dados antigos removidos, replaced=True."""
        # Dados existentes: 2 linhas de "2025-01"
        existing = pd.DataFrame(
            {
                "codigo_conta": ["1.01", "1.02"],
                "titulo_conta": ["A", "B"],
                "nivel": [2, 2],
                "tipo": ["Último Nível", "Último Nível"],
                "grupo": ["ATIVO", "ATIVO"],
                "periodo": ["2025-01", "2025-01"],
                "saldo_original": [100.0, 200.0],
                "indicador_dc": ["D", "D"],
                "saldo_sinalizado": [100.0, 200.0],
                "classificacao_depara": ["CL1", "CL2"],
            }
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)

        result = writer.write_month(
            _sample_header("2025-01"), _sample_parser_df("2025-01", n=2)
        )

        assert result["replaced"] is True
        assert result["rows_written"] == 2
        client.clear_sheet.assert_called()

    def test_keeps_other_periods_when_replacing(self):
        """Ao substituir um período, dados de outros períodos devem permanecer."""
        existing = pd.DataFrame(
            {
                "codigo_conta": ["1.01", "2.01"],
                "titulo_conta": ["A", "B"],
                "nivel": [2, 2],
                "tipo": ["Último Nível", "Último Nível"],
                "grupo": ["ATIVO", "PASSIVO"],
                "periodo": ["2025-01", "2025-02"],
                "saldo_original": [100.0, 200.0],
                "indicador_dc": ["D", "C"],
                "saldo_sinalizado": [100.0, -200.0],
                "classificacao_depara": ["", ""],
            }
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)

        writer.write_month(
            _sample_header("2025-01"), _sample_parser_df("2025-01", n=1)
        )

        # Verifica que append_rows foi chamado com linhas de ambos os períodos
        append_call = client.append_rows.call_args
        rows_written = append_call[0][1]  # segundo argumento posicional
        periodos_escritos = {r[5] for r in rows_written}  # col F = periodo
        assert "2025-01" in periodos_escritos
        assert "2025-02" in periodos_escritos


class TestGetExistingPeriods:
    def test_empty_base(self):
        client = _make_client_mock()
        writer = BaseWriter(client)
        assert writer.get_existing_periods() == []

    def test_returns_sorted(self):
        existing = pd.DataFrame(
            {"periodo": ["2025-03", "2025-01", "2025-02"], **{
                h: [""] * 3 for h in HEADERS if h != "periodo"
            }}
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)
        assert writer.get_existing_periods() == ["2025-01", "2025-02", "2025-03"]


class TestGetDataForPeriod:
    def test_filters_correctly(self):
        existing = pd.DataFrame(
            {
                "codigo_conta": ["1.01", "2.01", "1.02"],
                "titulo_conta": ["A", "B", "C"],
                "nivel": [2, 2, 2],
                "tipo": ["Último Nível"] * 3,
                "grupo": ["ATIVO", "PASSIVO", "ATIVO"],
                "periodo": ["2025-01", "2025-02", "2025-01"],
                "saldo_original": [100.0, 200.0, 300.0],
                "indicador_dc": ["D", "C", "D"],
                "saldo_sinalizado": [100.0, -200.0, 300.0],
                "classificacao_depara": ["", "", ""],
            }
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)
        df = writer.get_data_for_period("2025-01")
        assert len(df) == 2

    def test_period_not_found(self):
        client = _make_client_mock()
        writer = BaseWriter(client)
        df = writer.get_data_for_period("2099-12")
        assert df.empty


class TestGetAllData:
    def test_returns_full_data(self):
        existing = pd.DataFrame(
            {"periodo": ["2025-01"], **{
                h: ["x"] for h in HEADERS if h != "periodo"
            }}
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)
        df = writer.get_all_data()
        assert len(df) == 1


class TestUpdateClassifications:
    def test_updates_matching_rows(self):
        existing = pd.DataFrame(
            {
                "codigo_conta": ["1.01", "1.01", "2.01"],
                "titulo_conta": ["A", "A", "B"],
                "nivel": [2, 2, 2],
                "tipo": ["Último Nível"] * 3,
                "grupo": ["ATIVO", "ATIVO", "PASSIVO"],
                "periodo": ["2025-01", "2025-02", "2025-01"],
                "saldo_original": [100.0, 150.0, 200.0],
                "indicador_dc": ["D", "D", "C"],
                "saldo_sinalizado": [100.0, 150.0, -200.0],
                "classificacao_depara": ["", "", ""],
            }
        )
        client = _make_client_mock(existing)
        writer = BaseWriter(client)
        count = writer.update_classifications("1.01", "Disponibilidades")
        assert count == 2
        client.clear_sheet.assert_called()

    def test_no_match_returns_zero(self):
        client = _make_client_mock()
        writer = BaseWriter(client)
        assert writer.update_classifications("9.99", "X") == 0


class TestPrepareDF:
    def test_column_mapping(self):
        """Verifica que saldo_atual vira saldo_sinalizado e saldo_original."""
        header = _sample_header("2025-06")
        df = _sample_parser_df("2025-06", n=1)
        result = BaseWriter._prepare_df(header, df)

        assert "saldo_sinalizado" in result.columns
        assert "saldo_original" in result.columns
        assert result.iloc[0]["saldo_sinalizado"] == 120.0
        assert result.iloc[0]["saldo_original"] == 120.0  # abs(120)

    def test_output_is_sorted(self):
        """Verifica ordenação por periodo + codigo_conta."""
        header = _sample_header("2025-01")
        df = pd.DataFrame(
            {
                "codigo_conta": ["2.01", "1.01"],
                "titulo_conta": ["B", "A"],
                "nivel": [2, 2],
                "tipo": ["Último Nível", "Último Nível"],
                "grupo": ["PASSIVO", "ATIVO"],
                "periodo": ["2025-01", "2025-01"],
                "saldo_atual": [-200.0, 100.0],
                "indicador_dc": ["C", "D"],
            }
        )
        result = BaseWriter._prepare_df(header, df)
        assert result.iloc[0]["codigo_conta"] == "1.01"
        assert result.iloc[1]["codigo_conta"] == "2.01"
