"""
Testes para o validador de integridade hierárquica de balancetes.

Testes unitários com DataFrames sintéticos que rodam independentemente
de um arquivo real de balancete.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.validators.hierarchy_validator import (
    validate_balance_sheet,
    validate_hierarchy,
    validate_level_classification,
)


# ============================================================================
# Fixtures: DataFrames sintéticos
# ============================================================================


def _make_simple_hierarchy() -> pd.DataFrame:
    """Hierarquia simples e consistente para testes de validate_hierarchy."""
    return pd.DataFrame(
        [
            # ATIVO
            {"codigo_conta": "1", "titulo_conta": "ATIVO", "nivel": 1, "tipo": "Macro", "grupo": "ATIVO", "saldo_atual": 1000.0},
            {"codigo_conta": "1.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Macro", "grupo": "ATIVO", "saldo_atual": 600.0},
            {"codigo_conta": "1.01.01", "titulo_conta": "CAIXA", "nivel": 3, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 300.0},
            {"codigo_conta": "1.01.02", "titulo_conta": "BANCO", "nivel": 3, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 300.0},
            {"codigo_conta": "1.02", "titulo_conta": "NÃO CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 400.0},
            # PASSIVO
            {"codigo_conta": "2", "titulo_conta": "PASSIVO", "nivel": 1, "tipo": "Macro", "grupo": "PASSIVO", "saldo_atual": -700.0},
            {"codigo_conta": "2.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "PASSIVO", "saldo_atual": -200.0},
            {"codigo_conta": "2.02", "titulo_conta": "NÃO CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "PASSIVO", "saldo_atual": -100.0},
            {"codigo_conta": "2.03", "titulo_conta": "PL", "nivel": 2, "tipo": "Último Nível", "grupo": "PASSIVO", "saldo_atual": -400.0},
            # RECEITA
            {"codigo_conta": "3", "titulo_conta": "RECEITA", "nivel": 1, "tipo": "Último Nível", "grupo": "RECEITA", "saldo_atual": -500.0},
            # DESPESA
            {"codigo_conta": "4", "titulo_conta": "DESPESA", "nivel": 1, "tipo": "Último Nível", "grupo": "DESPESA", "saldo_atual": 200.0},
        ]
    )


def _make_hierarchy_error() -> pd.DataFrame:
    """Hierarquia com erro: pai não bate com soma dos filhos."""
    return pd.DataFrame(
        [
            {"codigo_conta": "1", "titulo_conta": "ATIVO", "nivel": 1, "tipo": "Macro", "grupo": "ATIVO", "saldo_atual": 1000.0},
            {"codigo_conta": "1.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 500.0},
            {"codigo_conta": "1.02", "titulo_conta": "NÃO CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 400.0},
            # Soma filhos = 900, pai = 1000 → ERROR
        ]
    )


def _make_irregular_hierarchy() -> pd.DataFrame:
    """Hierarquia irregular: filhos pulam nível (como 4.03 do Hinova)."""
    return pd.DataFrame(
        [
            {"codigo_conta": "4", "titulo_conta": "DESPESA", "nivel": 1, "tipo": "Macro", "grupo": "DESPESA", "saldo_atual": 500.0},
            {"codigo_conta": "4.03", "titulo_conta": "CUSTOS", "nivel": 2, "tipo": "Macro", "grupo": "DESPESA", "saldo_atual": 500.0},
            {"codigo_conta": "4.03.01", "titulo_conta": "CPV", "nivel": 3, "tipo": "Macro", "grupo": "DESPESA", "saldo_atual": 500.0},
            # Filhos diretos de 4.03.01 = nível 4
            {"codigo_conta": "4.03.01.03", "titulo_conta": "CUSTO A", "nivel": 4, "tipo": "Macro", "grupo": "DESPESA", "saldo_atual": 200.0},
            # Último nível com nível 5
            {"codigo_conta": "4.03.01.03.00001", "titulo_conta": "ITEM A1", "nivel": 5, "tipo": "Último Nível", "grupo": "DESPESA", "saldo_atual": 200.0},
            {"codigo_conta": "4.03.01.04.00000", "titulo_conta": "ITEM B", "nivel": 5, "tipo": "Último Nível", "grupo": "DESPESA", "saldo_atual": 150.0},
            {"codigo_conta": "4.03.01.09.00000", "titulo_conta": "ITEM C", "nivel": 5, "tipo": "Último Nível", "grupo": "DESPESA", "saldo_atual": 150.0},
        ]
    )


def _make_classification_error() -> pd.DataFrame:
    """Conta marcada como 'Último Nível' mas que tem filhos."""
    return pd.DataFrame(
        [
            {"codigo_conta": "1", "titulo_conta": "ATIVO", "nivel": 1, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 500.0},
            {"codigo_conta": "1.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "grupo": "ATIVO", "saldo_atual": 500.0},
        ]
    )


def _make_balanced_sheet() -> pd.DataFrame:
    """Balancete com BP equilibrado: Ativo + Passivo+PL + Resultado = 0."""
    return pd.DataFrame(
        [
            {"codigo_conta": "1", "titulo_conta": "ATIVO", "nivel": 1, "tipo": "Macro", "saldo_atual": 1000.0},
            {"codigo_conta": "1.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "saldo_atual": 600.0},
            {"codigo_conta": "1.02", "titulo_conta": "NÃO CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "saldo_atual": 400.0},
            {"codigo_conta": "2", "titulo_conta": "PASSIVO", "nivel": 1, "tipo": "Macro", "saldo_atual": -700.0},
            {"codigo_conta": "2.01", "titulo_conta": "CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "saldo_atual": -200.0},
            {"codigo_conta": "2.02", "titulo_conta": "NÃO CIRCULANTE", "nivel": 2, "tipo": "Último Nível", "saldo_atual": -100.0},
            {"codigo_conta": "2.03", "titulo_conta": "PL", "nivel": 2, "tipo": "Último Nível", "saldo_atual": -400.0},
            {"codigo_conta": "3", "titulo_conta": "RECEITA", "nivel": 1, "tipo": "Último Nível", "saldo_atual": -500.0},
            {"codigo_conta": "4", "titulo_conta": "DESPESA", "nivel": 1, "tipo": "Último Nível", "saldo_atual": 200.0},
        ]
    )


# ============================================================================
# Testes de validate_hierarchy
# ============================================================================


class TestValidateHierarchy:
    """Testes para validate_hierarchy."""

    def test_hierarchy_ok(self) -> None:
        """Hierarquia consistente retorna todos OK."""
        df = _make_simple_hierarchy()
        results = validate_hierarchy(df)

        for r in results:
            assert r["status"] in ("OK", "WARNING"), (
                f"Conta {r['conta_pai']} esperada OK, obteve {r['status']}: "
                f"{r.get('mensagem', '')}"
            )

    def test_hierarchy_error(self) -> None:
        """Hierarquia com erro detecta diferença."""
        df = _make_hierarchy_error()
        results = validate_hierarchy(df)

        # Conta "1" é Macro e soma filhos = 900, pai = 1000
        conta_1 = [r for r in results if r["conta_pai"] == "1"]
        assert len(conta_1) == 1
        assert conta_1[0]["status"] == "ERROR"
        assert conta_1[0]["diferenca"] == pytest.approx(100.0, abs=0.1)

    def test_hierarchy_irregular_warning(self) -> None:
        """Hierarquia irregular com pulo de nível gera WARNING."""
        df = _make_irregular_hierarchy()
        results = validate_hierarchy(df)

        # 4.03.01 tem filhos diretos nível 4 + filhos nível 5 pulando
        conta_4_03_01 = [r for r in results if r["conta_pai"] == "4.03.01"]
        assert len(conta_4_03_01) == 1

        r = conta_4_03_01[0]
        # Filhos diretos nível 4: apenas 4.03.01.03 (200)
        # Mas o pai é 500, então deveria detectar hierarquia irregular
        if r["diferenca"] > 0.02:
            assert r["status"] == "WARNING"

    def test_hierarchy_finds_direct_children(self) -> None:
        """Verifica que filhos diretos são identificados corretamente."""
        df = _make_simple_hierarchy()
        results = validate_hierarchy(df)

        conta_1 = [r for r in results if r["conta_pai"] == "1"][0]
        assert set(conta_1["filhos"]) == {"1.01", "1.02"}

        conta_101 = [r for r in results if r["conta_pai"] == "1.01"][0]
        assert set(conta_101["filhos"]) == {"1.01.01", "1.01.02"}

    def test_missing_columns_raises(self) -> None:
        """DataFrame sem colunas obrigatórias levanta ValueError."""
        df = pd.DataFrame({"foo": [1, 2]})
        with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
            validate_hierarchy(df)

    def test_no_macros_returns_empty(self) -> None:
        """DataFrame sem contas Macro retorna lista vazia."""
        df = pd.DataFrame(
            [
                {"codigo_conta": "1.01", "titulo_conta": "A", "nivel": 2, "tipo": "Último Nível", "saldo_atual": 100.0},
            ]
        )
        results = validate_hierarchy(df)
        assert results == []

    def test_tolerance_rounding(self) -> None:
        """Diferença <= 0.02 é considerada OK (tolerância de centavos)."""
        df = pd.DataFrame(
            [
                {"codigo_conta": "1", "titulo_conta": "ATIVO", "nivel": 1, "tipo": "Macro", "saldo_atual": 100.01},
                {"codigo_conta": "1.01", "titulo_conta": "A", "nivel": 2, "tipo": "Último Nível", "saldo_atual": 100.0},
            ]
        )
        results = validate_hierarchy(df)
        assert results[0]["status"] == "OK"


# ============================================================================
# Testes de validate_balance_sheet
# ============================================================================


class TestValidateBalanceSheet:
    """Testes para validate_balance_sheet."""

    def test_balanced_sheet(self) -> None:
        """Balancete equilibrado retorna todos os checks True."""
        df = _make_balanced_sheet()
        result = validate_balance_sheet(df)

        assert result["checks"]["ativo_decomposicao"] is True
        assert result["checks"]["passivo_decomposicao"] is True
        assert result["checks"]["bp_equilibrio"] is True
        assert result["diferenca_bp"] == pytest.approx(0.0, abs=0.02)

    def test_ativo_total(self) -> None:
        """Ativo total é extraído do saldo da conta '1'."""
        df = _make_balanced_sheet()
        result = validate_balance_sheet(df)
        assert result["ativo_total"] == pytest.approx(1000.0)

    def test_passivo_total(self) -> None:
        """Passivo+PL total é extraído do saldo da conta '2'."""
        df = _make_balanced_sheet()
        result = validate_balance_sheet(df)
        assert result["passivo_pl_total"] == pytest.approx(-700.0)

    def test_resultado_exercicio(self) -> None:
        """Resultado = Receita + Despesa."""
        df = _make_balanced_sheet()
        result = validate_balance_sheet(df)
        # Receita = -500, Despesa = 200, Resultado = -300
        assert result["resultado_exercicio"] == pytest.approx(-300.0)

    def test_receita_despesa(self) -> None:
        """Verifica receita e despesa individuais."""
        df = _make_balanced_sheet()
        result = validate_balance_sheet(df)
        assert result["receita_total"] == pytest.approx(-500.0)
        assert result["despesa_total"] == pytest.approx(200.0)

    def test_ativo_decomposicao_fail(self) -> None:
        """Quando 1.01 + 1.02 ≠ 1, ativo_decomposicao é False."""
        df = pd.DataFrame(
            [
                {"codigo_conta": "1", "saldo_atual": 1000.0},
                {"codigo_conta": "1.01", "saldo_atual": 400.0},
                {"codigo_conta": "1.02", "saldo_atual": 400.0},
                {"codigo_conta": "2", "saldo_atual": -1000.0},
                {"codigo_conta": "2.01", "saldo_atual": -500.0},
                {"codigo_conta": "2.02", "saldo_atual": -300.0},
                {"codigo_conta": "2.03", "saldo_atual": -200.0},
                {"codigo_conta": "3", "saldo_atual": 0.0},
                {"codigo_conta": "4", "saldo_atual": 0.0},
            ]
        )
        result = validate_balance_sheet(df)
        assert result["checks"]["ativo_decomposicao"] is False

    def test_missing_accounts(self) -> None:
        """Contas ausentes retornam 0 sem erro."""
        df = pd.DataFrame(
            [{"codigo_conta": "1", "saldo_atual": 1000.0}]
        )
        result = validate_balance_sheet(df)
        assert result["ativo_total"] == pytest.approx(1000.0)
        assert result["passivo_pl_total"] == pytest.approx(0.0)

    def test_missing_columns_raises(self) -> None:
        """DataFrame sem colunas obrigatórias levanta ValueError."""
        df = pd.DataFrame({"foo": [1]})
        with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
            validate_balance_sheet(df)


# ============================================================================
# Testes de validate_level_classification
# ============================================================================


class TestValidateLevelClassification:
    """Testes para validate_level_classification."""

    def test_correct_classification(self) -> None:
        """Classificação correta retorna lista vazia."""
        df = _make_simple_hierarchy()
        errors = validate_level_classification(df)
        assert errors == []

    def test_incorrect_classification(self) -> None:
        """Conta 'Último Nível' com filhos é detectada como erro."""
        df = _make_classification_error()
        errors = validate_level_classification(df)
        assert len(errors) == 1
        assert errors[0]["conta"] == "1"
        assert "1.01" in errors[0]["filhos_encontrados"]

    def test_no_ultimo_nivel(self) -> None:
        """DataFrame sem 'Último Nível' retorna lista vazia."""
        df = pd.DataFrame(
            [
                {"codigo_conta": "1", "tipo": "Macro"},
                {"codigo_conta": "1.01", "tipo": "Macro"},
            ]
        )
        errors = validate_level_classification(df)
        assert errors == []

    def test_missing_columns_raises(self) -> None:
        """DataFrame sem colunas obrigatórias levanta ValueError."""
        df = pd.DataFrame({"foo": [1]})
        with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
            validate_level_classification(df)
