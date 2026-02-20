"""
Testes para o pacote classifier (DEPARA de contas contábeis).

Testes unitários com DataFrames sintéticos e Sheets client mockado.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from backend.classifier.default_mapping import (
    CLASSIFICATION_TO_DF,
    DEFAULT_MAPPING,
    SPECIFIC_ACCOUNT_MAPPING,
)
from backend.classifier.depara_manager import DEPARAManager, SheetsError


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_sheets(
    depara_data: list[list[str]] | None = None,
) -> MagicMock:
    """Cria um sheets_client mockado.

    Args:
        depara_data: Dados a retornar em read_sheet. Se None, retorna
            planilha vazia (só header).
    """
    client = MagicMock()
    header = ["codigo_conta", "titulo_original", "classificacao", "grupo_df", "status"]
    if depara_data is None:
        client.read_sheet.return_value = [header]
    else:
        client.read_sheet.return_value = [header] + depara_data
    return client


def _make_balancete_df(
    contas: list[dict[str, str]],
) -> pd.DataFrame:
    """Cria DataFrame de balancete sintético para testes."""
    records = []
    for c in contas:
        records.append(
            {
                "codigo_conta": c["codigo"],
                "titulo_conta": c.get("titulo", "CONTA TESTE"),
                "tipo": c.get("tipo", "Último Nível"),
                "nivel": c.get("nivel", 5),
                "saldo_atual": c.get("saldo", 100.0),
            }
        )
    return pd.DataFrame(records)


# ============================================================================
# Testes de DEFAULT_MAPPING
# ============================================================================


class TestDefaultMapping:
    """Validações de integridade dos dicionários de mapeamento."""

    def test_default_mapping_not_empty(self) -> None:
        """DEFAULT_MAPPING contém entradas."""
        assert len(DEFAULT_MAPPING) > 0

    def test_specific_mapping_not_empty(self) -> None:
        """SPECIFIC_ACCOUNT_MAPPING contém entradas."""
        assert len(SPECIFIC_ACCOUNT_MAPPING) > 0

    def test_classification_to_df_not_empty(self) -> None:
        """CLASSIFICATION_TO_DF contém entradas."""
        assert len(CLASSIFICATION_TO_DF) > 0

    def test_all_default_classifications_in_df(self) -> None:
        """Toda classificação de DEFAULT_MAPPING existe em CLASSIFICATION_TO_DF."""
        for code, classif in DEFAULT_MAPPING.items():
            assert classif in CLASSIFICATION_TO_DF, (
                f"Classificação '{classif}' (de {code}) "
                f"não encontrada em CLASSIFICATION_TO_DF"
            )

    def test_all_specific_classifications_in_df(self) -> None:
        """Toda classificação de SPECIFIC_ACCOUNT_MAPPING existe em CLASSIFICATION_TO_DF."""
        for code, classif in SPECIFIC_ACCOUNT_MAPPING.items():
            assert classif in CLASSIFICATION_TO_DF, (
                f"Classificação '{classif}' (de {code}) "
                f"não encontrada em CLASSIFICATION_TO_DF"
            )

    def test_classification_values_are_dre_or_bp(self) -> None:
        """CLASSIFICATION_TO_DF só mapeia para 'DRE' ou 'BP'."""
        for classif, grupo in CLASSIFICATION_TO_DF.items():
            assert grupo in ("DRE", "BP"), (
                f"Grupo '{grupo}' inválido para classificação '{classif}'"
            )

    def test_default_mapping_keys_are_level4(self) -> None:
        """Chaves de DEFAULT_MAPPING têm 3–4 partes separadas por ponto."""
        for code in DEFAULT_MAPPING:
            parts = code.split(".")
            assert 3 <= len(parts) <= 4, (
                f"Código '{code}' não é nível 3 ou 4 (tem {len(parts)} partes)"
            )

    def test_specific_mapping_keys_are_level5(self) -> None:
        """Chaves de SPECIFIC_ACCOUNT_MAPPING têm 5 partes (conta analítica)."""
        for code in SPECIFIC_ACCOUNT_MAPPING:
            parts = code.split(".")
            assert len(parts) == 5, (
                f"Código '{code}' não é nível 5 (tem {len(parts)} partes)"
            )


# ============================================================================
# Testes de DEPARAManager.classify_accounts
# ============================================================================


class TestClassifyAccounts:
    """Testes para o método classify_accounts."""

    def test_classify_via_depara_existente(self) -> None:
        """Conta já no DEPARA do Sheets é classificada por ele."""
        sheets = _make_mock_sheets(
            [["1.01.01.02.00004", "BANCO ITAU", "(+) Caixa e Equivalentes de Caixa", "BP", "Revisado"]]
        )
        manager = DEPARAManager(sheets)
        df = _make_balancete_df([{"codigo": "1.01.01.02.00004", "titulo": "BANCO ITAU"}])

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "(+) Caixa e Equivalentes de Caixa"
        assert result.at[0, "grupo_df"] == "BP"

    def test_classify_via_specific_mapping(self) -> None:
        """Conta com código exato em SPECIFIC_ACCOUNT_MAPPING."""
        sheets = _make_mock_sheets()  # DEPARA vazio
        manager = DEPARAManager(sheets)
        df = _make_balancete_df([{"codigo": "3.01.01.02.00004", "titulo": "PIS"}])

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "(-) PIS"
        assert result.at[0, "grupo_df"] == "DRE"

    def test_classify_via_default_mapping(self) -> None:
        """Conta com prefixo nível 4 no DEFAULT_MAPPING."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "1.01.01.02.00099", "titulo": "OUTRO BANCO"}]
        )

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "(+) Caixa e Equivalentes de Caixa"
        assert result.at[0, "grupo_df"] == "BP"

    def test_classify_pendente_ia(self) -> None:
        """Conta não mapeada é marcada como 'Pendente IA'."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "9.99.99.99.00001", "titulo": "CONTA ESTRANHA"}]
        )

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "Pendente IA"
        assert result.at[0, "grupo_df"] == ""

    def test_specific_has_priority_over_default(self) -> None:
        """SPECIFIC_ACCOUNT_MAPPING tem prioridade sobre DEFAULT_MAPPING."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        # 3.01.01.02.00005 está em SPECIFIC → "(-) COFINS"
        # 3.01.01.02 está em DEFAULT → "(-) Deduções da Receita"
        df = _make_balancete_df(
            [{"codigo": "3.01.01.02.00005", "titulo": "COFINS"}]
        )

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "(-) COFINS"

    def test_depara_has_priority_over_specific(self) -> None:
        """DEPARA existente no Sheets tem prioridade sobre SPECIFIC_ACCOUNT_MAPPING."""
        sheets = _make_mock_sheets(
            [["3.01.01.02.00005", "COFINS CUSTOM", "(-) Deduções da Receita", "DRE", "Revisado"]]
        )
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "3.01.01.02.00005", "titulo": "COFINS CUSTOM"}]
        )

        result = manager.classify_accounts(df)

        # DEPARA do Sheets prevalece
        assert result.at[0, "classificacao_depara"] == "(-) Deduções da Receita"

    def test_macro_accounts_not_classified(self) -> None:
        """Contas Macro não recebem classificação."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "1.01.01.02", "titulo": "BANCOS", "tipo": "Macro"}]
        )

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == ""

    def test_missing_columns_raises(self) -> None:
        """DataFrame sem colunas obrigatórias levanta ValueError."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = pd.DataFrame({"foo": [1]})

        with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
            manager.classify_accounts(df)

    def test_new_accounts_persisted(self) -> None:
        """Contas classificadas automaticamente são persistidas no Sheets."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "1.01.01.02.00099", "titulo": "NOVO BANCO"}]
        )

        manager.classify_accounts(df)

        sheets.append_rows.assert_called_once()
        args = sheets.append_rows.call_args
        rows = args[0][1]
        assert len(rows) == 1
        assert rows[0][0] == "1.01.01.02.00099"
        assert rows[0][2] == "(+) Caixa e Equivalentes de Caixa"

    def test_classify_impostos_short_prefix(self) -> None:
        """Contas de impostos com nível 3 (ex: 4.98.03) são mapeadas."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "4.98.03", "titulo": "CSLL", "tipo": "Último Nível"}]
        )

        result = manager.classify_accounts(df)

        assert result.at[0, "classificacao_depara"] == "(-) CSLL"

    def test_sheets_read_failure_uses_defaults(self) -> None:
        """Falha na leitura do Sheets não impede classificação."""
        sheets = MagicMock()
        sheets.read_sheet.side_effect = Exception("Connection error")
        sheets.append_rows.side_effect = Exception("Connection error")
        manager = DEPARAManager(sheets)
        df = _make_balancete_df(
            [{"codigo": "1.01.01.02.00004", "titulo": "BANCO"}]
        )

        result = manager.classify_accounts(df)

        # Cai no SPECIFIC ou DEFAULT normalmente
        assert result.at[0, "classificacao_depara"] == "(+) Caixa e Equivalentes de Caixa"


# ============================================================================
# Testes de DEPARAManager.add_new_accounts
# ============================================================================


class TestAddNewAccounts:
    """Testes para add_new_accounts."""

    def test_add_accounts(self) -> None:
        """Adiciona contas com sucesso."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)

        accounts = [
            {
                "codigo_conta": "1.01.01.02.00099",
                "titulo_original": "BANCO NOVO",
                "classificacao": "(+) Caixa e Equivalentes de Caixa",
                "grupo_df": "BP",
                "status": "Auto",
            }
        ]
        manager.add_new_accounts(accounts)

        sheets.append_rows.assert_called_once()

    def test_add_empty_does_nothing(self) -> None:
        """Lista vazia não faz chamada ao Sheets."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)

        manager.add_new_accounts([])

        sheets.append_rows.assert_not_called()

    def test_add_failure_raises(self) -> None:
        """Falha no Sheets levanta SheetsError."""
        sheets = _make_mock_sheets()
        sheets.append_rows.side_effect = Exception("API Error")
        manager = DEPARAManager(sheets)

        with pytest.raises(SheetsError, match="Falha ao adicionar contas"):
            manager.add_new_accounts(
                [{"codigo_conta": "x", "titulo_original": "t", "classificacao": "c", "grupo_df": "d", "status": "s"}]
            )


# ============================================================================
# Testes de DEPARAManager.update_classification
# ============================================================================


class TestUpdateClassification:
    """Testes para update_classification."""

    def test_update_existing_account(self) -> None:
        """Atualização bem-sucedida retorna propagated=True."""
        sheets = _make_mock_sheets(
            [["1.01.01.02.00004", "BANCO ITAU", "(+) Caixa", "BP", "Auto"]]
        )
        manager = DEPARAManager(sheets)

        result = manager.update_classification(
            "1.01.01.02.00004", "(-) Equipe"
        )

        assert result["propagated"] is True
        assert result["classification"] == "(-) Equipe"
        assert result["grupo_df"] == "DRE"
        assert result["new_df_line_needed"] is False

    def test_update_nonexistent_account(self) -> None:
        """Conta não encontrada retorna propagated=False."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)

        result = manager.update_classification("9.99.99.99.00001", "(-) Equipe")

        assert result["propagated"] is False

    def test_update_with_new_classification(self) -> None:
        """Classificação nova sinaliza new_df_line_needed=True."""
        sheets = _make_mock_sheets(
            [["1.01.01.02.00004", "BANCO", "(+) Caixa", "BP", "Auto"]]
        )
        manager = DEPARAManager(sheets)

        result = manager.update_classification(
            "1.01.01.02.00004", "(+) Classificação Nova Inventada"
        )

        assert result["propagated"] is True
        assert result["new_df_line_needed"] is True
        assert result["grupo_df"] == ""

    def test_update_sheets_failure_raises(self) -> None:
        """Falha no Sheets durante update levanta SheetsError."""
        sheets = _make_mock_sheets(
            [["1.01.01.02.00004", "BANCO", "(+) Caixa", "BP", "Auto"]]
        )
        sheets.update_cell.side_effect = Exception("API Error")
        manager = DEPARAManager(sheets)

        with pytest.raises(SheetsError, match="Falha ao atualizar"):
            manager.update_classification("1.01.01.02.00004", "(-) Equipe")


# ============================================================================
# Testes de DEPARAManager.get_pending_reviews
# ============================================================================


class TestGetPendingReviews:
    """Testes para get_pending_reviews."""

    def test_returns_pending_only(self) -> None:
        """Retorna apenas contas com status Pendente."""
        sheets = _make_mock_sheets(
            [
                ["1.01.01.02.00004", "BANCO ITAU", "(+) Caixa", "BP", "Revisado"],
                ["9.99.99.99.00001", "DESCONHECIDA", "Pendente IA", "", "Pendente"],
            ]
        )
        manager = DEPARAManager(sheets)

        pending = manager.get_pending_reviews()

        assert len(pending) == 1
        assert pending[0]["codigo_conta"] == "9.99.99.99.00001"

    def test_no_pending(self) -> None:
        """Sem pendentes retorna lista vazia."""
        sheets = _make_mock_sheets(
            [["1.01.01.02.00004", "BANCO ITAU", "(+) Caixa", "BP", "Revisado"]]
        )
        manager = DEPARAManager(sheets)

        pending = manager.get_pending_reviews()

        assert pending == []


# ============================================================================
# Testes de DEPARAManager.get_all_classifications
# ============================================================================


class TestGetAllClassifications:
    """Testes para get_all_classifications."""

    def test_includes_standard_classifications(self) -> None:
        """Resultado inclui todas as classificações de CLASSIFICATION_TO_DF."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)

        result = manager.get_all_classifications()

        for classif in CLASSIFICATION_TO_DF:
            assert classif in result

    def test_includes_sheets_classifications(self) -> None:
        """Resultado inclui classificações customizadas do Sheets."""
        sheets = _make_mock_sheets(
            [["x", "t", "(+) Custom Nova", "DRE", "Revisado"]]
        )
        manager = DEPARAManager(sheets)

        result = manager.get_all_classifications()

        assert "(+) Custom Nova" in result

    def test_excludes_pendente_ia(self) -> None:
        """Pendente IA não aparece na lista de classificações."""
        sheets = _make_mock_sheets(
            [["x", "t", "Pendente IA", "", "Pendente"]]
        )
        manager = DEPARAManager(sheets)

        result = manager.get_all_classifications()

        assert "Pendente IA" not in result

    def test_result_is_sorted(self) -> None:
        """Lista retornada está ordenada."""
        sheets = _make_mock_sheets()
        manager = DEPARAManager(sheets)

        result = manager.get_all_classifications()

        assert result == sorted(result)

    def test_sheets_failure_returns_defaults(self) -> None:
        """Falha no Sheets retorna apenas classificações padrão."""
        sheets = MagicMock()
        sheets.read_sheet.side_effect = Exception("Connection error")
        manager = DEPARAManager(sheets)

        result = manager.get_all_classifications()

        assert len(result) == len(CLASSIFICATION_TO_DF)


# ============================================================================
# Testes de _get_level4_prefix
# ============================================================================


class TestGetLevel4Prefix:
    """Testes para o helper _get_level4_prefix."""

    def test_level5_account(self) -> None:
        """Conta nível 5 retorna 4 primeiras partes."""
        assert DEPARAManager._get_level4_prefix("1.01.01.02.00004") == "1.01.01.02"

    def test_level4_account(self) -> None:
        """Conta nível 4 retorna ela mesma."""
        assert DEPARAManager._get_level4_prefix("1.01.01.02") == "1.01.01.02"

    def test_level3_account(self) -> None:
        """Conta nível 3 (ex: impostos) retorna ela mesma."""
        assert DEPARAManager._get_level4_prefix("4.98.03") == "4.98.03"

    def test_empty_string(self) -> None:
        """String vazia retorna string vazia."""
        assert DEPARAManager._get_level4_prefix("") == ""
