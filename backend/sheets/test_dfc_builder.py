"""
Testes unitários para DFCBuilder.

Valida fórmulas de variação do BP, referências à DRE,
subtotais, saldo de caixa e validação.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from backend.sheets.dfc_builder import (
    SHEET_NAME,
    DFCBuilder,
    _DFC_STRUCTURE,
    _LAST_DATA_ROW,
    _bp_ref,
    _bp_var_formula,
    _check_formula,
    _col_letter,
    _dre_ref,
    _period_to_header,
    _subtotal_formula,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> MagicMock:
    client = MagicMock()
    client.read_sheet.return_value = pd.DataFrame()
    return client


PERIODS_3 = ["2025-01", "2025-02", "2025-03"]
PERIODS_12 = [f"2025-{m:02d}" for m in range(1, 13)]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

class TestBPRef:
    def test_basic(self):
        assert _bp_ref("C", 5) == "'Balanço Patrimonial'!C5"


class TestDRERef:
    def test_basic(self):
        assert _dre_ref("B", 42) == "'DRE'!B42"


class TestBPVarFormula:
    def test_first_month_single(self):
        """Janeiro: variação a partir de zero = -BP_atual."""
        f = _bp_var_formula("B", None, [5])
        assert f == "=-('Balanço Patrimonial'!B5)"

    def test_subsequent_month_single(self):
        """Fev: -(BP_fev - BP_jan)."""
        f = _bp_var_formula("C", "B", [5])
        assert f == "=-('Balanço Patrimonial'!C5-('Balanço Patrimonial'!B5))"

    def test_first_month_multi(self):
        """Janeiro com múltiplos BP rows (empréstimos CP+LP)."""
        f = _bp_var_formula("B", None, [20, 27])
        assert "'Balanço Patrimonial'!B20" in f
        assert "'Balanço Patrimonial'!B27" in f
        assert f.startswith("=-(")

    def test_subsequent_month_multi(self):
        """Fev com múltiplos BP rows."""
        f = _bp_var_formula("C", "B", [20, 27])
        assert "'Balanço Patrimonial'!C20" in f
        assert "'Balanço Patrimonial'!C27" in f
        assert "'Balanço Patrimonial'!B20" in f
        assert "'Balanço Patrimonial'!B27" in f


class TestCheckFormula:
    def test_has_if_and_abs(self):
        f = _check_formula("B")
        assert "IF" in f
        assert "ABS" in f
        assert "B27" in f
        assert "B29" in f
        assert "B28" in f
        assert "✓" in f


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------

class TestDFCStructure:
    def test_structure_length(self):
        assert len(_DFC_STRUCTURE) == 31

    def test_last_data_row(self):
        assert _LAST_DATA_ROW == 32

    def test_has_three_sections(self):
        labels = [l.label for l in _DFC_STRUCTURE]
        assert "ATIVIDADES OPERACIONAIS" in labels
        assert "ATIVIDADES DE INVESTIMENTO" in labels
        assert "ATIVIDADES DE FINANCIAMENTO" in labels

    def test_has_validation(self):
        labels = [l.label for l in _DFC_STRUCTURE]
        assert "Check" in labels

    def test_has_cash_balance_rows(self):
        labels = [l.label for l in _DFC_STRUCTURE]
        assert "Saldo Inicial de Caixa" in labels
        assert "Saldo Final de Caixa" in labels

    def test_all_subtotals_have_children(self):
        for line in _DFC_STRUCTURE:
            if line.line_type == "subtotal":
                assert line.children_rows, f"'{line.label}' sem filhos"

    def test_all_bp_var_have_rows(self):
        for line in _DFC_STRUCTURE:
            if line.line_type in ("bp_var", "bp_var_multi"):
                assert line.bp_rows, f"'{line.label}' sem bp_rows"

    def test_get_structure(self):
        struct = DFCBuilder.get_structure()
        assert len(struct) == 31
        assert struct[0]["row"] == 2


# ---------------------------------------------------------------------------
# build_dfc
# ---------------------------------------------------------------------------

class TestBuildDFC:
    def test_build_calls_sequence(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        client.ensure_sheet_exists.assert_called_once_with(SHEET_NAME)
        client.clear_sheet.assert_called_once()
        assert client.update_range.call_count == 2
        client.batch_write_formulas.assert_called_once()

    def test_headers(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        headers = client.update_range.call_args_list[0][0][2][0]
        assert headers == ["", "Jan/25", "Fev/25", "Mar/25", "Total Ano"]

    def test_labels_written(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        labels = client.update_range.call_args_list[1][0][2]
        assert len(labels) == 31
        assert labels[0] == ["ATIVIDADES OPERACIONAIS"]

    def test_empty_periods_raises(self):
        client = _make_client()
        with pytest.raises(ValueError, match="vazia"):
            DFCBuilder(client).build_dfc([])

    def test_formula_count(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        active_lines = sum(
            1 for l in _DFC_STRUCTURE if l.line_type not in ("blank", "label")
        )
        expected = active_lines * (3 + 1)  # 3 meses + total
        assert len(formulas) == expected

    def test_lucro_liquido_from_dre(self):
        """Lucro Líquido deve referenciar DRE row 42."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        # Row 3 (Lucro Líquido), col B (Jan)
        ll = next(f for f in formulas if f["row"] == 3 and f["col"] == 2)
        assert "'DRE'!B42" in ll["formula"]
        assert ll["formula"].startswith("=")

    def test_da_addback_negated(self):
        """D&A add-back deve negar o DRE row 19."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        da = next(f for f in formulas if f["row"] == 4 and f["col"] == 2)
        assert "=-'DRE'!B19" == da["formula"]

    def test_bp_var_jan_no_prev(self):
        """Janeiro: variação a partir de zero."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        # Row 5 (Clientes), col B (Jan)
        clientes_jan = next(
            f for f in formulas if f["row"] == 5 and f["col"] == 2
        )
        # Should be =-(BP!B5) without subtraction
        assert clientes_jan["formula"].count("Balanço Patrimonial") == 1

    def test_bp_var_feb_has_prev(self):
        """Fevereiro: variação com subtração do mês anterior."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        clientes_feb = next(
            f for f in formulas if f["row"] == 5 and f["col"] == 3
        )
        # Should reference both C and B
        assert "'Balanço Patrimonial'!C5" in clientes_feb["formula"]
        assert "'Balanço Patrimonial'!B5" in clientes_feb["formula"]

    def test_emprestimos_multi_row(self):
        """Empréstimos CP+LP: referencia dois BP rows."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        emp_jan = next(
            f for f in formulas if f["row"] == 21 and f["col"] == 2
        )
        assert "'Balanço Patrimonial'!B20" in emp_jan["formula"]
        assert "'Balanço Patrimonial'!B27" in emp_jan["formula"]

    def test_saldo_inicial_jan_zero(self):
        """Saldo Inicial de Janeiro = 0."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        si_jan = next(
            f for f in formulas if f["row"] == 28 and f["col"] == 2
        )
        assert si_jan["formula"] == "=0"

    def test_saldo_inicial_feb_prev_month(self):
        """Saldo Inicial de Fevereiro = BP Caixa de Janeiro."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        si_feb = next(
            f for f in formulas if f["row"] == 28 and f["col"] == 3
        )
        assert "'Balanço Patrimonial'!B4" in si_feb["formula"]

    def test_saldo_final_current_month(self):
        """Saldo Final = BP Caixa do mês atual."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        sf_jan = next(
            f for f in formulas if f["row"] == 29 and f["col"] == 2
        )
        assert "'Balanço Patrimonial'!B4" in sf_jan["formula"]

    def test_variacao_caixa_sum_of_sections(self):
        """Variação de Caixa = Oper + Invest + Financ."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        var = next(
            f for f in formulas if f["row"] == 27 and f["col"] == 2
        )
        assert "B12" in var["formula"]
        assert "B18" in var["formula"]
        assert "B25" in var["formula"]

    def test_total_col_uses_sum(self):
        """Total Ano de linhas normais usa SUM."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        total_col_idx = len(PERIODS_3) + 2
        # Row 3 (Lucro Líquido), total column
        ll_total = next(
            f for f in formulas
            if f["row"] == 3 and f["col"] == total_col_idx
        )
        assert "SUM" in ll_total["formula"]

    def test_total_saldo_final_uses_last_month(self):
        """Total do Saldo Final = BP Caixa do último mês."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        total_col_idx = len(PERIODS_3) + 2
        sf_total = next(
            f for f in formulas
            if f["row"] == 29 and f["col"] == total_col_idx
        )
        assert "'Balanço Patrimonial'!D4" in sf_total["formula"]

    def test_total_saldo_inicial_zero(self):
        """Total do Saldo Inicial = 0."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        total_col_idx = len(PERIODS_3) + 2
        si_total = next(
            f for f in formulas
            if f["row"] == 28 and f["col"] == total_col_idx
        )
        assert si_total["formula"] == "=0"

    def test_check_row_has_validation(self):
        """Linha Check deve ter IF e ABS."""
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        checks = [f for f in formulas if f["row"] == 32]
        assert len(checks) > 0
        assert all("IF" in f["formula"] and "ABS" in f["formula"]
                    for f in checks)


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_format_called(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)
        assert client.format_range.call_count > 0

    def test_bold_count(self):
        client = _make_client()
        DFCBuilder(client).build_dfc(PERIODS_3)

        bold_calls = [
            c for c in client.format_range.call_args_list
            if c[0][2].get("textFormat", {}).get("bold") is True
        ]
        bold_in_structure = sum(1 for l in _DFC_STRUCTURE if l.bold)
        assert len(bold_calls) == bold_in_structure + 1  # +1 header


# ---------------------------------------------------------------------------
# get_dfc_data
# ---------------------------------------------------------------------------

class TestGetDFCData:
    def test_returns_dataframe(self):
        client = _make_client()
        client.read_sheet.return_value = pd.DataFrame({"A": [1]})
        df = DFCBuilder(client).get_dfc_data()
        assert len(df) == 1
        client.read_sheet.assert_called_with(SHEET_NAME)
