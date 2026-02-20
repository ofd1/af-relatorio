"""
Testes para o classificador de contas contábeis via IA (Gemini).

Testes unitários com client mockado — sem chamadas reais à API.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.classifier.ai_classifier import (
    _build_user_prompt,
    _infer_grupo_df,
    _make_error_results,
    _parse_response,
    classify_new_accounts,
)


# ============================================================================
# Fixtures: contas de teste
# ============================================================================


def _sample_accounts() -> list[dict[str, str]]:
    """Contas fictícias para classificação."""
    return [
        {
            "codigo_conta": "4.01.01.04.00099",
            "titulo_conta": "DESPESAS COM VIAGENS",
            "grupo": "DESPESA",
            "grupo_nivel4": "4.01.01.04",
            "titulo_nivel4": "DESPESAS ADMINISTRATIVAS",
        },
        {
            "codigo_conta": "1.01.03.08.00055",
            "titulo_conta": "CREDITOS DIVERSOS",
            "grupo": "ATIVO",
            "grupo_nivel4": "1.01.03.08",
            "titulo_nivel4": "CREDITOS A RECUPERAR",
        },
    ]


def _sample_classifications() -> list[str]:
    return [
        "(+) Receita de Serviços",
        "(-) Equipe",
        "(-) Despesas Gerais e Administrativas",
        "(-) Viagens e Estadias",
        "(+) Outros Créditos",
    ]


def _gemini_response_json(accounts: list[dict[str, str]]) -> str:
    """Gera resposta JSON simulando o Gemini."""
    results = []
    for acc in accounts:
        codigo = acc["codigo_conta"]
        first = codigo[0] if codigo else "4"
        grupo_df = "BP" if first in ("1", "2") else "DRE"
        results.append(
            {
                "codigo_conta": codigo,
                "classificacao_sugerida": "(-) Despesas Gerais e Administrativas"
                if first in ("3", "4")
                else "(+) Outros Créditos",
                "confianca": "alta",
                "justificativa": "Classificação baseada no grupo contábil",
                "grupo_df": grupo_df,
                "is_new_classification": False,
            }
        )
    return json.dumps(results, ensure_ascii=False)


# ============================================================================
# Testes de _build_user_prompt
# ============================================================================


class TestBuildUserPrompt:
    """Testes para a construção do prompt."""

    def test_contains_classifications(self) -> None:
        """Prompt inclui classificações existentes."""
        prompt = _build_user_prompt(
            _sample_accounts(), _sample_classifications()
        )
        for c in _sample_classifications():
            assert c in prompt

    def test_contains_account_codes(self) -> None:
        """Prompt inclui códigos das contas."""
        accounts = _sample_accounts()
        prompt = _build_user_prompt(accounts, _sample_classifications())
        for acc in accounts:
            assert acc["codigo_conta"] in prompt

    def test_contains_account_titles(self) -> None:
        """Prompt inclui títulos das contas."""
        accounts = _sample_accounts()
        prompt = _build_user_prompt(accounts, _sample_classifications())
        for acc in accounts:
            assert acc["titulo_conta"] in prompt


# ============================================================================
# Testes de _parse_response
# ============================================================================


class TestParseResponse:
    """Testes para o parsing da resposta do Gemini."""

    def test_parse_clean_json(self) -> None:
        """Parseia JSON limpo sem fences."""
        accounts = _sample_accounts()
        raw = _gemini_response_json(accounts)

        results = _parse_response(raw, accounts)

        assert len(results) == 2
        assert results[0]["codigo_conta"] == "4.01.01.04.00099"

    def test_parse_json_with_fences(self) -> None:
        """Parseia JSON envolvido em markdown fences."""
        accounts = _sample_accounts()
        raw_json = _gemini_response_json(accounts)
        fenced = f"```json\n{raw_json}\n```"

        results = _parse_response(fenced, accounts)

        assert len(results) == 2

    def test_parse_normalizes_fields(self) -> None:
        """Campos ausentes são preenchidos com valores padrão."""
        raw = json.dumps([{"codigo_conta": "1.01.01.01.00001"}])

        results = _parse_response(raw, [])

        assert results[0]["classificacao_sugerida"] == "Não Classificada"
        assert results[0]["confianca"] == "baixa"
        assert results[0]["is_new_classification"] is False

    def test_parse_invalid_json_raises(self) -> None:
        """JSON inválido levanta ValueError."""
        with pytest.raises((json.JSONDecodeError, ValueError)):
            _parse_response("not json at all", [])

    def test_parse_non_array_raises(self) -> None:
        """Objeto JSON (não array) levanta ValueError."""
        with pytest.raises(ValueError, match="array JSON"):
            _parse_response('{"key": "value"}', [])


# ============================================================================
# Testes de _make_error_results
# ============================================================================


class TestMakeErrorResults:
    """Testes para geração de resultados de erro."""

    def test_error_results_structure(self) -> None:
        """Resultados de erro têm a estrutura esperada."""
        accounts = _sample_accounts()
        results = _make_error_results(accounts, "Timeout")

        assert len(results) == 2
        for r in results:
            assert r["classificacao_sugerida"] == "Não Classificada"
            assert "Timeout" in r["justificativa"]
            assert r["confianca"] == "baixa"
            assert r["is_new_classification"] is False

    def test_error_infers_grupo_df(self) -> None:
        """grupo_df é inferido pelo primeiro dígito da conta."""
        results = _make_error_results(
            [{"codigo_conta": "1.01.01.02.00001"}], "err"
        )
        assert results[0]["grupo_df"] == "BP"

        results = _make_error_results(
            [{"codigo_conta": "4.01.01.01.00001"}], "err"
        )
        assert results[0]["grupo_df"] == "DRE"


# ============================================================================
# Testes de _infer_grupo_df
# ============================================================================


class TestInferGrupoDf:
    """Testes para inferência do grupo DF."""

    @pytest.mark.parametrize(
        "codigo, expected",
        [
            ("1.01.01.02.00004", "BP"),
            ("2.01.01.01.00001", "BP"),
            ("3.01.01.01.00005", "DRE"),
            ("4.01.01.04.00099", "DRE"),
            ("", ""),
            ("9.99.99.99.00001", ""),
        ],
    )
    def test_infer(self, codigo: str, expected: str) -> None:
        assert _infer_grupo_df(codigo) == expected


# ============================================================================
# Testes de classify_new_accounts (integração com mock)
# ============================================================================


class TestClassifyNewAccounts:
    """Testes para a função principal classify_new_accounts."""

    def test_empty_accounts_returns_empty(self) -> None:
        """Lista vazia retorna lista vazia sem chamar API."""
        result = asyncio.run(classify_new_accounts([], []))
        assert result == []

    def test_missing_api_key_raises(self) -> None:
        """Sem GEMINI_API_KEY levanta ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                asyncio.run(
                    classify_new_accounts(
                        _sample_accounts(), _sample_classifications()
                    )
                )

    def test_successful_classification(self) -> None:
        """Classificação bem-sucedida retorna resultados corretos."""
        accounts = _sample_accounts()
        response_json = _gemini_response_json(accounts)

        mock_response = MagicMock()
        mock_response.text = response_json

        mock_client = MagicMock()
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.return_value = mock_response
        mock_client.aio.models = mock_aio_models

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("backend.classifier.ai_classifier.genai") as mock_genai:
                mock_genai.Client.return_value = mock_client
                results = asyncio.run(
                    classify_new_accounts(accounts, _sample_classifications())
                )

        assert len(results) == 2
        assert results[0]["codigo_conta"] == "4.01.01.04.00099"
        assert results[0]["confianca"] == "alta"

    def test_api_failure_returns_error_results(self) -> None:
        """Falha na API retorna resultados de erro para todas as contas."""
        accounts = _sample_accounts()

        mock_client = MagicMock()
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.side_effect = Exception("API Error")
        mock_client.aio.models = mock_aio_models

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("backend.classifier.ai_classifier.genai") as mock_genai:
                mock_genai.Client.return_value = mock_client
                results = asyncio.run(
                    classify_new_accounts(accounts, _sample_classifications())
                )

        assert len(results) == 2
        for r in results:
            assert r["classificacao_sugerida"] == "Não Classificada"
            assert "API Error" in r["justificativa"]

    def test_batching_splits_large_input(self) -> None:
        """Mais de 20 contas gera múltiplos batches."""
        # Cria 25 contas
        accounts = [
            {
                "codigo_conta": f"4.01.01.04.{i:05d}",
                "titulo_conta": f"CONTA {i}",
                "grupo": "DESPESA",
                "grupo_nivel4": "4.01.01.04",
                "titulo_nivel4": "DESPESAS ADMINISTRATIVAS",
            }
            for i in range(25)
        ]

        response_json_batch1 = _gemini_response_json(accounts[:20])
        response_json_batch2 = _gemini_response_json(accounts[20:])

        mock_response_1 = MagicMock()
        mock_response_1.text = response_json_batch1
        mock_response_2 = MagicMock()
        mock_response_2.text = response_json_batch2

        mock_client = MagicMock()
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.side_effect = [
            mock_response_1,
            mock_response_2,
        ]
        mock_client.aio.models = mock_aio_models

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("backend.classifier.ai_classifier.genai") as mock_genai:
                mock_genai.Client.return_value = mock_client
                results = asyncio.run(
                    classify_new_accounts(
                        accounts, _sample_classifications()
                    )
                )

        assert len(results) == 25
        assert mock_aio_models.generate_content.call_count == 2

    def test_empty_response_triggers_retry(self) -> None:
        """Resposta vazia do Gemini aciona retry."""
        accounts = [_sample_accounts()[0]]
        good_response = MagicMock()
        good_response.text = _gemini_response_json(accounts)

        empty_response = MagicMock()
        empty_response.text = ""

        mock_client = MagicMock()
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.side_effect = [
            empty_response,
            good_response,
        ]
        mock_client.aio.models = mock_aio_models

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("backend.classifier.ai_classifier.genai") as mock_genai:
                mock_genai.Client.return_value = mock_client
                # Patch sleep to avoid waiting
                with patch("backend.classifier.ai_classifier.asyncio.sleep", new_callable=AsyncMock):
                    results = asyncio.run(
                        classify_new_accounts(
                            accounts, _sample_classifications()
                        )
                    )

        assert len(results) == 1
        assert results[0]["classificacao_sugerida"] != "Não Classificada"
