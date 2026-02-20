"""
Validador de integridade hierárquica de balancetes contábeis.

Verifica que cada conta "pai" (Macro) tem saldo igual à soma dos filhos
diretos, valida o equilíbrio patrimonial (Ativo + Passivo + PL = 0),
e confirma a classificação correta de tipo (Macro vs Último Nível).
"""

from __future__ import annotations

import pandas as pd

# Tolerância de R$0.02 para arredondamentos de centavos
_TOLERANCE = 0.02


def validate_hierarchy(df: pd.DataFrame) -> list[dict]:
    """Valida a integridade hierárquica de todas as contas Macro do balancete.

    Para cada conta de tipo "Macro", identifica seus filhos diretos
    (contas cujo código começa com ``codigo_pai + "."`` e tem exatamente
    1 nível a mais), soma os saldos dos filhos e compara com o saldo do pai.

    Quando a soma dos filhos diretos não cobre o saldo do pai, verifica se
    existem filhos "pulando" nível (hierarquia irregular) e reporta como
    WARNING em vez de ERROR.

    Args:
        df: DataFrame com colunas ``codigo_conta``, ``titulo_conta``,
            ``nivel``, ``tipo``, ``saldo_atual``.

    Returns:
        Lista de dicts com resultado da validação de cada conta Macro::

            {
                "conta_pai": str,
                "titulo_pai": str,
                "saldo_pai": float,
                "soma_filhos": float,
                "diferenca": float,
                "status": "OK" | "WARNING" | "ERROR",
                "filhos": list[str],
                "mensagem": str   # presente apenas em WARNING/ERROR
            }
    """
    _validate_required_columns(
        df, ["codigo_conta", "titulo_conta", "nivel", "tipo", "saldo_atual"]
    )

    results: list[dict] = []
    macros = df[df["tipo"] == "Macro"]

    # Indexar todas as contas por código para busca rápida
    all_codes = set(df["codigo_conta"].values)

    for _, row in macros.iterrows():
        codigo_pai: str = row["codigo_conta"]
        titulo_pai: str = row["titulo_conta"]
        saldo_pai: float = float(row["saldo_atual"])
        nivel_pai: int = int(row["nivel"])
        nivel_filho_direto = nivel_pai + 1

        # Encontrar filhos diretos: começam com "codigo_pai." e têm nível = pai + 1
        prefix = codigo_pai + "."
        filhos_diretos = df[
            (df["codigo_conta"].str.startswith(prefix))
            & (df["nivel"] == nivel_filho_direto)
        ]

        filhos_codes = filhos_diretos["codigo_conta"].tolist()
        soma_filhos = float(filhos_diretos["saldo_atual"].sum())
        diferenca = abs(saldo_pai - soma_filhos)

        result: dict = {
            "conta_pai": codigo_pai,
            "titulo_pai": titulo_pai,
            "saldo_pai": round(saldo_pai, 2),
            "soma_filhos": round(soma_filhos, 2),
            "diferenca": round(diferenca, 2),
            "filhos": filhos_codes,
        }

        if diferenca <= _TOLERANCE:
            result["status"] = "OK"
        else:
            # Verificar se há filhos "pulando" nível (hierarquia irregular)
            # Ex.: 4.03 → 4.03.01 (nível 3), mas 4.03.01.03 é nível 4
            # e 4.03.01.04.00000 é nível 5 — listados diretamente sob 4.03.01
            filhos_skip = df[
                (df["codigo_conta"].str.startswith(prefix))
                & (df["nivel"] > nivel_filho_direto)
            ]

            if not filhos_skip.empty:
                # Há descendentes além de filhos diretos — hierarquia irregular
                # Tentar somar TODOS os descendentes de último nível em vez apenas
                # dos filhos diretos, para ver se cobre
                all_descendants_leaf = df[
                    (df["codigo_conta"].str.startswith(prefix))
                    & (df["tipo"] == "Último Nível")
                ]
                soma_leaf = float(all_descendants_leaf["saldo_atual"].sum())
                diff_leaf = abs(saldo_pai - soma_leaf)

                if diff_leaf <= _TOLERANCE:
                    result["status"] = "WARNING"
                    result["mensagem"] = (
                        f"Hierarquia irregular detectada. Filhos diretos somam "
                        f"{round(soma_filhos, 2)}, mas soma dos últimos níveis "
                        f"({round(soma_leaf, 2)}) bate com o pai. "
                        f"Possível pulo de nível na estrutura."
                    )
                else:
                    result["status"] = "WARNING"
                    result["mensagem"] = (
                        f"Hierarquia irregular. Filhos diretos somam "
                        f"{round(soma_filhos, 2)}, últimos níveis somam "
                        f"{round(soma_leaf, 2)}, pai = {round(saldo_pai, 2)}. "
                        f"Diferença de {round(diferenca, 2)} nos filhos diretos."
                    )
            else:
                result["status"] = "ERROR"
                result["mensagem"] = (
                    f"Saldo do pai ({round(saldo_pai, 2)}) difere da soma dos "
                    f"filhos diretos ({round(soma_filhos, 2)}) em "
                    f"{round(diferenca, 2)}."
                )

        results.append(result)

    return results


def validate_balance_sheet(df: pd.DataFrame) -> dict:
    """Verifica o equilíbrio patrimonial do balancete.

    Validações:
        1. Ativo ("1") = Circulante ("1.01") + Não Circulante ("1.02")
        2. Passivo ("2") = Circulante ("2.01") + Não Circ. ("2.02") + PL ("2.03")
        3. Ativo + Passivo+PL = 0 (quando inclui resultado do exercício)
        4. Receita ("3") + Despesa ("4") = resultado do exercício

    Convenções de sinal:
        - Ativo: positivo
        - Passivo+PL: negativo
        - Receita: negativa
        - Despesa: positiva

    Args:
        df: DataFrame com colunas ``codigo_conta``, ``saldo_atual``.

    Returns:
        Dicionário com totais, diferenças e checks booleanos::

            {
                "ativo_total": float,
                "passivo_pl_total": float,
                "diferenca_bp": float,
                "resultado_exercicio": float,
                "receita_total": float,
                "despesa_total": float,
                "checks": {
                    "ativo_decomposicao": bool,
                    "passivo_decomposicao": bool,
                    "bp_equilibrio": bool
                }
            }
    """
    _validate_required_columns(df, ["codigo_conta", "saldo_atual"])

    def _get_saldo(codigo: str) -> float:
        """Obtém o saldo_atual de uma conta pelo código."""
        row = df[df["codigo_conta"] == codigo]
        if row.empty:
            return 0.0
        return float(row.iloc[0]["saldo_atual"])

    # Totais principais
    ativo_total = _get_saldo("1")
    passivo_pl_total = _get_saldo("2")
    receita_total = _get_saldo("3")
    despesa_total = _get_saldo("4")

    # Subgrupos do Ativo
    ativo_circ = _get_saldo("1.01")
    ativo_nao_circ = _get_saldo("1.02")

    # Subgrupos do Passivo
    passivo_circ = _get_saldo("2.01")
    passivo_nao_circ = _get_saldo("2.02")
    patrimonio_liq = _get_saldo("2.03")

    # Check 1: Decomposição do Ativo
    soma_ativo = ativo_circ + ativo_nao_circ
    ativo_decomposicao = abs(ativo_total - soma_ativo) <= _TOLERANCE

    # Check 2: Decomposição do Passivo
    soma_passivo = passivo_circ + passivo_nao_circ + patrimonio_liq
    passivo_decomposicao = abs(passivo_pl_total - soma_passivo) <= _TOLERANCE

    # Check 3: Equilíbrio patrimonial
    # Ativo + Passivo+PL + Resultado = 0
    resultado_exercicio = receita_total + despesa_total
    bp_total = ativo_total + passivo_pl_total + resultado_exercicio
    bp_equilibrio = abs(bp_total) <= _TOLERANCE

    return {
        "ativo_total": round(ativo_total, 2),
        "passivo_pl_total": round(passivo_pl_total, 2),
        "diferenca_bp": round(bp_total, 2),
        "resultado_exercicio": round(resultado_exercicio, 2),
        "receita_total": round(receita_total, 2),
        "despesa_total": round(despesa_total, 2),
        "checks": {
            "ativo_decomposicao": ativo_decomposicao,
            "passivo_decomposicao": passivo_decomposicao,
            "bp_equilibrio": bp_equilibrio,
        },
    }


def validate_level_classification(df: pd.DataFrame) -> list[dict]:
    """Valida que contas de "Último Nível" não possuem filhos no DataFrame.

    Para cada conta marcada como "Último Nível", verifica que não existe
    nenhuma outra conta cujo código comece com ``codigo + "."``.

    Args:
        df: DataFrame com colunas ``codigo_conta``, ``tipo``.

    Returns:
        Lista de dicts com erros encontrados::

            {
                "conta": str,
                "titulo": str,
                "tipo_atual": "Último Nível",
                "filhos_encontrados": list[str],
                "mensagem": str
            }

        Lista vazia se não houver erros.
    """
    _validate_required_columns(df, ["codigo_conta", "tipo"])

    errors: list[dict] = []
    ultimo_nivel = df[df["tipo"] == "Último Nível"]
    all_codes = df["codigo_conta"].values

    for _, row in ultimo_nivel.iterrows():
        codigo: str = row["codigo_conta"]
        prefix = codigo + "."

        # Buscar contas que começam com este prefix
        filhos = df[df["codigo_conta"].str.startswith(prefix)]

        if not filhos.empty:
            titulo = row.get("titulo_conta", "")
            filhos_codes = filhos["codigo_conta"].tolist()
            errors.append(
                {
                    "conta": codigo,
                    "titulo": titulo if titulo else "",
                    "tipo_atual": "Último Nível",
                    "filhos_encontrados": filhos_codes,
                    "mensagem": (
                        f"Conta '{codigo}' está classificada como 'Último Nível' "
                        f"mas possui {len(filhos_codes)} filho(s): {filhos_codes}"
                    ),
                }
            )

    return errors


def _validate_required_columns(df: pd.DataFrame, required: list[str]) -> None:
    """Verifica se o DataFrame possui todas as colunas obrigatórias.

    Args:
        df: DataFrame a validar.
        required: Lista de nomes de coluna obrigatórios.

    Raises:
        ValueError: Se alguma coluna obrigatória estiver ausente.
    """
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"Colunas obrigatórias ausentes no DataFrame: {missing}. "
            f"Colunas presentes: {list(df.columns)}"
        )
