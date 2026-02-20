"""
Classificador de contas contábeis via IA (Gemini).

Usa a API do Google Gemini (modelo ``gemini-2.5-flash``) para sugerir
classificações de contas contábeis que não foram mapeadas pelo DEPARA
padrão nem pelo mapeamento específico.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.5-flash"
_BATCH_SIZE = 20
_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 30
_TEMPERATURE = 0.0

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
Você é um especialista em contabilidade brasileira.

Sua tarefa é classificar contas contábeis analíticas (último nível) em
classificações padronizadas para DRE (Demonstração do Resultado do
Exercício) ou BP (Balanço Patrimonial).

## Regras

1. **PREFIRA classificações existentes.** Só sugira uma nova se nenhuma
   das existentes se encaixa razoavelmente.
2. **Grupo da DF:**
   - Contas do grupo 1 (Ativo) e 2 (Passivo/PL) → **BP**
   - Contas do grupo 3 (Receita) e 4 (Despesa/Custo) → **DRE**
3. **Prefixo de sinal:**
   - Receitas e ativos: prefixo **(+)**
   - Despesas e custos: prefixo **(-)**
   - Passivo (grupo 2): usa **(+)** (a convenção é o sinal do item na DF)
4. Se sugerir uma classificação nova (que não está na lista), coloque
   ``is_new_classification: true``.
5. Nível de confiança:
   - **alta**: a conta se encaixa claramente numa classificação existente.
   - **media**: há ambiguidade, mas a sugestão é razoável.
   - **baixa**: classificação incerta, requer revisão humana.

## Formato de resposta

Responda APENAS com um array JSON. Cada elemento:

```json
{
  "codigo_conta": "<código da conta>",
  "classificacao_sugerida": "<classificação>",
  "confianca": "alta|media|baixa",
  "justificativa": "<breve justificativa>",
  "grupo_df": "DRE|BP",
  "is_new_classification": false
}
```

Não inclua markdown, explicações extras, nem blocos de código envolvendo
o JSON. Retorne SOMENTE o array JSON puro.
"""


def _build_user_prompt(
    accounts: list[dict[str, str]],
    existing_classifications: list[str],
) -> str:
    """Monta o prompt do usuário com contas e classificações existentes."""
    classif_list = "\n".join(f"- {c}" for c in existing_classifications)

    accounts_json = json.dumps(accounts, ensure_ascii=False, indent=2)

    return (
        "## Classificações existentes\n\n"
        f"{classif_list}\n\n"
        "## Contas para classificar\n\n"
        f"{accounts_json}\n\n"
        "Classifique cada conta acima seguindo as regras do sistema."
    )


# ---------------------------------------------------------------------------
# Parsing da resposta
# ---------------------------------------------------------------------------


def _parse_response(
    raw_text: str, accounts: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Parseia a resposta JSON do Gemini.

    Trata possíveis markdown fences envolvendo o JSON.

    Args:
        raw_text: Texto bruto da resposta do Gemini.
        accounts: Lista original de contas (para fallback em caso de erro).

    Returns:
        Lista de dicts com as classificações sugeridas.

    Raises:
        ValueError: Se o JSON não puder ser parseado.
    """
    text = raw_text.strip()

    # Remove possíveis fences ```json ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove primeira e última linhas (```json e ```)
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    parsed = json.loads(text)

    if not isinstance(parsed, list):
        raise ValueError(f"Resposta esperada é array JSON, recebeu: {type(parsed)}")

    # Valida e normaliza cada item
    results: list[dict[str, Any]] = []
    for item in parsed:
        results.append(
            {
                "codigo_conta": str(item.get("codigo_conta", "")),
                "classificacao_sugerida": str(
                    item.get("classificacao_sugerida", "Não Classificada")
                ),
                "confianca": str(item.get("confianca", "baixa")),
                "justificativa": str(item.get("justificativa", "")),
                "grupo_df": str(item.get("grupo_df", "")),
                "is_new_classification": bool(
                    item.get("is_new_classification", False)
                ),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Erro fallback
# ---------------------------------------------------------------------------


def _make_error_results(
    accounts: list[dict[str, str]], error_msg: str
) -> list[dict[str, Any]]:
    """Gera resultados de erro para contas que não puderam ser classificadas."""
    return [
        {
            "codigo_conta": acc.get("codigo_conta", ""),
            "classificacao_sugerida": "Não Classificada",
            "confianca": "baixa",
            "justificativa": f"Erro IA: {error_msg}",
            "grupo_df": _infer_grupo_df(acc.get("codigo_conta", "")),
            "is_new_classification": False,
        }
        for acc in accounts
    ]


def _infer_grupo_df(codigo_conta: str) -> str:
    """Infere o grupo DF pelo primeiro dígito da conta."""
    if not codigo_conta:
        return ""
    first = codigo_conta[0]
    if first in ("1", "2"):
        return "BP"
    if first in ("3", "4"):
        return "DRE"
    return ""


# ---------------------------------------------------------------------------
# API call (async)
# ---------------------------------------------------------------------------


async def _call_gemini(
    client: genai.Client,
    accounts: list[dict[str, str]],
    existing_classifications: list[str],
) -> list[dict[str, Any]]:
    """Faz uma chamada ao Gemini para classificar um batch de contas.

    Implementa retry com backoff exponencial.

    Args:
        client: Client do google-genai.
        accounts: Batch de contas (até _BATCH_SIZE).
        existing_classifications: Lista de classificações existentes.

    Returns:
        Lista de dicts com classificações sugeridas.
    """
    user_prompt = _build_user_prompt(accounts, existing_classifications)

    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        temperature=_TEMPERATURE,
        response_mime_type="application/json",
    )

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            logger.info(
                "Chamando Gemini (tentativa %d/%d) com %d contas...",
                attempt + 1,
                _MAX_RETRIES + 1,
                len(accounts),
            )

            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=_MODEL,
                    contents=user_prompt,
                    config=config,
                ),
                timeout=_TIMEOUT_SECONDS,
            )

            raw_text = response.text
            if not raw_text:
                raise ValueError("Resposta vazia do Gemini.")

            logger.debug("Resposta bruta do Gemini: %s", raw_text[:500])

            results = _parse_response(raw_text, accounts)

            logger.info(
                "Gemini classificou %d contas com sucesso.", len(results)
            )
            return results

        except asyncio.TimeoutError:
            last_error = TimeoutError(
                f"Timeout de {_TIMEOUT_SECONDS}s excedido."
            )
            logger.warning(
                "Timeout na tentativa %d/%d.",
                attempt + 1,
                _MAX_RETRIES + 1,
            )
        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning(
                "Erro ao parsear JSON na tentativa %d/%d: %s",
                attempt + 1,
                _MAX_RETRIES + 1,
                exc,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Erro na tentativa %d/%d: %s",
                attempt + 1,
                _MAX_RETRIES + 1,
                exc,
            )

        # Backoff exponencial entre retries
        if attempt < _MAX_RETRIES:
            wait = 2 ** attempt
            logger.info("Aguardando %ds antes de retry...", wait)
            await asyncio.sleep(wait)

    # Todas as tentativas falharam
    error_msg = str(last_error) if last_error else "Erro desconhecido"
    logger.error(
        "Todas as %d tentativas falharam: %s",
        _MAX_RETRIES + 1,
        error_msg,
    )
    return _make_error_results(accounts, error_msg)


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------


async def classify_new_accounts(
    accounts: list[dict[str, str]],
    existing_classifications: list[str],
) -> list[dict[str, Any]]:
    """Classifica contas contábeis não mapeadas usando a API do Gemini.

    Divide as contas em batches de até 20 contas por chamada e processa
    todos os batches em paralelo.

    Args:
        accounts: Lista de dicts com chaves:
            - ``codigo_conta``: código completo da conta.
            - ``titulo_conta``: título/descrição da conta.
            - ``grupo``: grupo contábil (ATIVO, PASSIVO, RECEITA, DESPESA).
            - ``grupo_nivel4``: código do sub-grupo nível 4.
            - ``titulo_nivel4``: título do sub-grupo nível 4.
        existing_classifications: Lista de classificações existentes na
            DRE/BP que devem ser preferidas.

    Returns:
        Lista de dicts com chaves:
            - ``codigo_conta`` (str)
            - ``classificacao_sugerida`` (str)
            - ``confianca`` (str): "alta", "media" ou "baixa"
            - ``justificativa`` (str)
            - ``grupo_df`` (str): "DRE" ou "BP"
            - ``is_new_classification`` (bool)

    Raises:
        ValueError: Se ``GEMINI_API_KEY`` não estiver configurada.
    """
    if not accounts:
        logger.info("Nenhuma conta para classificar.")
        return []

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "Variável de ambiente GEMINI_API_KEY não configurada. "
            "Defina-a antes de usar o classificador por IA."
        )

    client = genai.Client(api_key=api_key)

    # Divide em batches
    batches: list[list[dict[str, str]]] = [
        accounts[i : i + _BATCH_SIZE]
        for i in range(0, len(accounts), _BATCH_SIZE)
    ]

    logger.info(
        "Classificando %d contas em %d batch(es)...",
        len(accounts),
        len(batches),
    )

    # Processa batches em paralelo
    tasks = [
        _call_gemini(client, batch, existing_classifications)
        for batch in batches
    ]
    batch_results = await asyncio.gather(*tasks)

    # Concatena resultados
    all_results: list[dict[str, Any]] = []
    for batch_result in batch_results:
        all_results.extend(batch_result)

    classified = sum(
        1 for r in all_results if r["classificacao_sugerida"] != "Não Classificada"
    )
    logger.info(
        "Classificação IA concluída: %d/%d contas classificadas.",
        classified,
        len(all_results),
    )

    return all_results
