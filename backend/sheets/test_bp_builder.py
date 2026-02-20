"""
Testes unitários para BPBuilder.

Valida geração de fórmulas SUMIFS (acumuladas), subtotais,
referência cruzada com DRE e validação.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from backend.sheets.bp_builder import (
    SHEET_NAME,
    BPBuilder,
    _BP_STRUCTURE,
    _LAST_DATA_ROW,
    _col_letter,
    _dre_lucro_acumulado_formula,
    _period_to_header,
    _somases_formula,
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

class TestColLetter:
    def test_basic(self):
        assert _col_letter(1) == "A"
        assert _col_letter(2) == "B"
        assert _col_letter(14) == "N"


class TestPeriodHeader:
    def test_basic(self):
        assert _period_to_header("2025-06") == "Jun/25"


class TestSomasesFormula:
    def test_no_subtraction(self):
        """BP usa saldo acumulado direto, sem subtrair mês anterior."""
        f = _somases_formula("Clientes", "2025-03")
        assert f.startswith("=SUMIFS")
        assert '"Clientes"' in f
        assert '"2025-03"' in f
        # NÃO deve ter duplo SUMIFS ou subtração
        assert f.count("SUMIFS") == 1

    def test_always_same_regardless_of_month(self):
        """Janeiro e dezembro produzem a mesma estrutura (só acumulado)."""
        f_jan = _somases_formula("Clientes", "2025-01")
        f_dez = _somases_formula("Clientes", "2025-12")
        assert f_jan.count("SUMIFS") == 1
        assert f_dez.count("SUMIFS") == 1


class TestDRELucroAcumulado:
    def test_first_month(self):
        f = _dre_lucro_acumulado_formula("B", "B")
        assert f == "='DRE'!B42"

    def test_third_month(self):
        f = _dre_lucro_acumulado_formula("B", "D")
        assert f == "=SUM('DRE'!B42:D42)"

    def test_last_month_12(self):
        f = _dre_lucro_acumulado_formula("B", "M")
        assert f == "=SUM('DRE'!B42:M42)"


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------

class TestBPStructure:
    def test_structure_length(self):
        assert len(_BP_STRUCTURE) == 36

    def test_last_data_row(self):
        assert _LAST_DATA_ROW == 37

    def test_all_somases_have_classification(self):
        for line in _BP_STRUCTURE:
            if line.line_type == "somases":
                assert line.classification, f"'{line.label}' sem classificação"

    def test_all_subtotals_have_children(self):
        for line in _BP_STRUCTURE:
            if line.line_type == "subtotal":
                assert line.children_rows, f"'{line.label}' sem filhos"

    def test_children_rows_in_range(self):
        for line in _BP_STRUCTURE:
            if line.line_type == "subtotal":
                for r in line.children_rows:
                    assert 2 <= r <= _LAST_DATA_ROW, (
                        f"Row {r} fora do range em '{line.label}'"
                    )

    def test_has_validation_row(self):
        labels = [l.label for l in _BP_STRUCTURE]
        assert "Check" in labels

    def test_has_dre_ref(self):
        dre_refs = [l for l in _BP_STRUCTURE if l.line_type == "dre_ref"]
        assert len(dre_refs) == 1
        assert "Resultado do Exercício" in dre_refs[0].label

    def test_get_classifications(self):
        classifications = BPBuilder.get_classifications()
        assert "Clientes" in classifications
        assert "Capital Social" in classifications
        assert len(classifications) >= 15

    def test_get_structure(self):
        struct = BPBuilder.get_structure()
        assert struct[0]["row"] == 2
        assert struct[0]["label"] == "ATIVO"


# ---------------------------------------------------------------------------
# build_bp
# ---------------------------------------------------------------------------

class TestBuildBP:
    def test_build_calls_sequence(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        client.ensure_sheet_exists.assert_called_once_with(SHEET_NAME)
        client.clear_sheet.assert_called_once()
        assert client.update_range.call_count == 2  # headers + labels
        client.batch_write_formulas.assert_called_once()

    def test_headers_content(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        headers = client.update_range.call_args_list[0][0][2][0]
        assert headers == ["", "Jan/25", "Fev/25", "Mar/25", "Último Período"]

    def test_labels_written(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        labels = client.update_range.call_args_list[1][0][2]
        assert len(labels) == 36
        assert labels[0] == ["ATIVO"]

    def test_formula_count(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        active_lines = sum(
            1 for l in _BP_STRUCTURE if l.line_type not in ("blank", "label")
        )
        expected = active_lines * (3 + 1)  # 3 meses + último período
        assert len(formulas) == expected

    def test_empty_periods_raises(self):
        client = _make_client()
        with pytest.raises(ValueError, match="vazia"):
            BPBuilder(client).build_bp([])

    def test_somases_no_monthly_variation(self):
        """Cada SUMIFS deve ter apenas 1 chamada SUMIFS (sem subtração)."""
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        somases_formulas = [
            f for f in formulas if "SUMIFS" in f["formula"]
        ]
        for sf in somases_formulas:
            assert sf["formula"].count("SUMIFS") == 1, (
                f"Fórmula com múltiplos SUMIFS: {sf}"
            )

    def test_dre_ref_january_single(self):
        """Janeiro: referência direta ao lucro líquido da DRE."""
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        # Row 32 (Resultado do Exercício), col B (jan)
        dre_jan = next(
            f for f in formulas if f["row"] == 32 and f["col"] == 2
        )
        assert "'DRE'!" in dre_jan["formula"]
        assert "SUM" not in dre_jan["formula"]

    def test_dre_ref_march_cumulative(self):
        """Março: soma acumulada do lucro líquido Jan-Mar."""
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        dre_mar = next(
            f for f in formulas if f["row"] == 32 and f["col"] == 4
        )
        assert "SUM('DRE'!B42:D42)" in dre_mar["formula"]

    def test_validation_row_present(self):
        """A fórmula de validação (Check) deve conter IF e ABS."""
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        check_formulas = [f for f in formulas if f["row"] == 37]
        assert len(check_formulas) > 0
        assert all("IF" in f["formula"] and "ABS" in f["formula"]
                    for f in check_formulas)

    def test_ultimo_periodo_uses_last_month_for_somases(self):
        """Coluna 'Último Período' de SOMASES deve referenciar o último mês."""
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        formulas = client.batch_write_formulas.call_args[0][1]
        total_col_idx = len(PERIODS_3) + 2  # col 5 = E

        # Row 4 = Caixa e Equivalentes (somases)
        total_caixa = next(
            f for f in formulas if f["row"] == 4 and f["col"] == total_col_idx
        )
        assert '"2025-03"' in total_caixa["formula"]  # último período


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_format_range_called(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)
        assert client.format_range.call_count > 0

    def test_bold_count(self):
        client = _make_client()
        BPBuilder(client).build_bp(PERIODS_3)

        bold_calls = [
            c for c in client.format_range.call_args_list
            if c[0][2].get("textFormat", {}).get("bold") is True
        ]
        bold_in_structure = sum(1 for l in _BP_STRUCTURE if l.bold)
        assert len(bold_calls) == bold_in_structure + 1  # +1 header


# ---------------------------------------------------------------------------
# get_bp_data
# ---------------------------------------------------------------------------

class TestGetBPData:
    def test_returns_dataframe(self):
        client = _make_client()
        client.read_sheet.return_value = pd.DataFrame({"A": [1]})
        df = BPBuilder(client).get_bp_data()
        assert len(df) == 1
        client.read_sheet.assert_called_with(SHEET_NAME)
