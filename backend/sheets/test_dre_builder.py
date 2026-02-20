"""
Testes unitários para DREBuilder.

Valida geração de fórmulas SUMIFS, subtotais, margens e formatação
sem chamadas reais à API.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from backend.sheets.dre_builder import (
    SHEET_NAME,
    DREBuilder,
    _DRE_STRUCTURE,
    _LAST_DATA_ROW,
    _col_letter,
    _period_to_header,
    _somases_formula,
    _subtotal_formula,
    _sumifs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> MagicMock:
    import pandas as pd
    client = MagicMock()
    client.read_sheet.return_value = pd.DataFrame()
    return client


PERIODS_3 = ["2025-01", "2025-02", "2025-03"]
PERIODS_12 = [f"2025-{m:02d}" for m in range(1, 13)]


# ---------------------------------------------------------------------------
# Testes de utilidades
# ---------------------------------------------------------------------------

class TestColLetter:
    def test_single_letters(self):
        assert _col_letter(1) == "A"
        assert _col_letter(2) == "B"
        assert _col_letter(26) == "Z"

    def test_double_letters(self):
        assert _col_letter(27) == "AA"
        assert _col_letter(28) == "AB"


class TestPeriodToHeader:
    def test_basic(self):
        assert _period_to_header("2025-01") == "Jan/25"
        assert _period_to_header("2025-12") == "Dez/25"


class TestSumifs:
    def test_sumifs_fragment(self):
        result = _sumifs("ISS", "2025-03")
        assert "SUMIFS" in result
        assert "'Base Balancete'" in result
        assert '"ISS"' in result
        assert '"2025-03"' in result
        assert '"Último Nível"' in result


class TestSomasesFormula:
    def test_first_month(self):
        f = _somases_formula("ISS", "2025-01", None)
        assert f.startswith("=-SUMIFS")
        assert '"2025-01"' in f

    def test_subsequent_month(self):
        f = _somases_formula("ISS", "2025-02", "2025-01")
        assert f.startswith("=-(SUMIFS")
        assert '"2025-02"' in f
        assert '"2025-01"' in f


class TestSubtotalFormula:
    def test_basic(self):
        assert _subtotal_formula("B", [3, 4]) == "=B3+B4"
        assert _subtotal_formula("C", [6, 7, 8, 9]) == "=C6+C7+C8+C9"


# ---------------------------------------------------------------------------
# Testes de estrutura
# ---------------------------------------------------------------------------

class TestDREStructure:
    def test_structure_length(self):
        assert len(_DRE_STRUCTURE) == 46

    def test_last_data_row(self):
        assert _LAST_DATA_ROW == 47

    def test_all_somases_have_classification(self):
        for line in _DRE_STRUCTURE:
            if line.line_type == "somases":
                assert line.classification, f"Linha '{line.label}' sem classificação"

    def test_all_subtotals_have_children(self):
        for line in _DRE_STRUCTURE:
            if line.line_type == "subtotal":
                assert line.children_rows, f"Subtotal '{line.label}' sem filhos"

    def test_children_rows_in_range(self):
        for line in _DRE_STRUCTURE:
            if line.line_type == "subtotal":
                for r in line.children_rows:
                    assert 2 <= r <= _LAST_DATA_ROW, (
                        f"Row {r} fora do range em '{line.label}'"
                    )

    def test_get_classifications(self):
        classifications = DREBuilder.get_classifications()
        assert "Receita de Serviços" in classifications
        assert "ISS" in classifications
        assert "CSLL" in classifications
        assert len(classifications) >= 20

    def test_get_structure(self):
        struct = DREBuilder.get_structure()
        assert len(struct) == 46
        assert struct[0]["row"] == 2
        assert struct[0]["label"] == "Receita Bruta"


# ---------------------------------------------------------------------------
# Testes do build_dre
# ---------------------------------------------------------------------------

class TestBuildDRE:
    def test_build_calls_sequence(self):
        """Verifica a sequência de chamadas ao SheetsClient."""
        client = _make_client()
        builder = DREBuilder(client)
        builder.build_dre(PERIODS_3)

        # Deve ter chamado ensure_sheet_exists, clear, update_range (2x),
        # batch_write_formulas, e format_range
        client.ensure_sheet_exists.assert_called_once_with(SHEET_NAME)
        client.clear_sheet.assert_called_once_with(SHEET_NAME, preserve_headers=False)
        assert client.update_range.call_count == 2  # headers + labels
        client.batch_write_formulas.assert_called_once()

    def test_headers_content(self):
        """Verifica headers gerados para 3 períodos."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        headers_call = client.update_range.call_args_list[0]
        headers = headers_call[0][2][0]  # terceiro arg posicional, primeira lista
        assert headers == ["", "Jan/25", "Fev/25", "Mar/25", "Total Ano"]

    def test_labels_written(self):
        """Verifica que todas as labels foram escritas."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        labels_call = client.update_range.call_args_list[1]
        labels = labels_call[0][2]
        assert len(labels) == 46
        assert labels[0] == ["Receita Bruta"]
        assert labels[-1] == ["Margem Líquida"]

    def test_formula_count(self):
        """Cada linha ativa gera 1 fórmula por período + 1 total."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        active_lines = sum(
            1 for l in _DRE_STRUCTURE if l.line_type not in ("blank", "label")
        )
        expected = active_lines * (3 + 1)  # 3 meses + total
        assert len(formulas) == expected

    def test_12_months_headers(self):
        """Verifica headers para ano completo."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_12)

        headers = client.update_range.call_args_list[0][0][2][0]
        assert len(headers) == 14  # "" + 12 meses + "Total Ano"
        assert headers[-1] == "Total Ano"

    def test_empty_periods_raises(self):
        client = _make_client()
        with pytest.raises(ValueError, match="vazia"):
            DREBuilder(client).build_dre([])

    def test_margin_total_uses_formula_not_sum(self):
        """Coluna Total de margens deve usar IFERROR, não SUM."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        total_col_idx = len(PERIODS_3) + 2  # 5 (E)

        margin_totals = [
            f for f in formulas
            if f["row"] in (45, 46, 47) and f["col"] == total_col_idx
        ]
        for mf in margin_totals:
            assert "IFERROR" in mf["formula"]
            assert "SUM" not in mf["formula"]

    def test_somases_first_month_no_subtraction(self):
        """Janeiro não deve ter subtração de mês anterior."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        # Row 3 (Receita de Serviços), col 2 (B = Janeiro)
        jan_formula = next(
            f for f in formulas if f["row"] == 3 and f["col"] == 2
        )
        assert jan_formula["formula"].startswith("=-SUMIFS")

    def test_somases_second_month_has_subtraction(self):
        """Fevereiro deve subtrair janeiro."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        feb_formula = next(
            f for f in formulas if f["row"] == 3 and f["col"] == 3
        )
        assert feb_formula["formula"].startswith("=-(SUMIFS")
        assert "2025-02" in feb_formula["formula"]
        assert "2025-01" in feb_formula["formula"]


# ---------------------------------------------------------------------------
# Testes de formatação
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_format_range_called(self):
        """Verifica que format_range é chamado para headers, bold e números."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)
        assert client.format_range.call_count > 0

    def test_bold_rows_formatted(self):
        """Cada linha bold deve ter format_range com bold=True."""
        client = _make_client()
        DREBuilder(client).build_dre(PERIODS_3)

        bold_calls = [
            c for c in client.format_range.call_args_list
            if c[0][2].get("textFormat", {}).get("bold") is True
        ]
        bold_rows_in_structure = sum(1 for l in _DRE_STRUCTURE if l.bold)
        # +1 para header row 1
        assert len(bold_calls) == bold_rows_in_structure + 1


# ---------------------------------------------------------------------------
# Testes de get_dre_data
# ---------------------------------------------------------------------------

class TestGetDREData:
    def test_returns_dataframe(self):
        import pandas as pd
        client = _make_client()
        client.read_sheet.return_value = pd.DataFrame({"A": [1]})
        builder = DREBuilder(client)
        df = builder.get_dre_data()
        assert len(df) == 1
        client.read_sheet.assert_called_with(SHEET_NAME)
