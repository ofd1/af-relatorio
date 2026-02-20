"""
Módulo de conversão de valores contábeis no formato brasileiro.

Trata valores como "1.234.567,89D" ou "0,00", convertendo para float
e aplicando sinais conforme o grupo contábil (ATIVO, PASSIVO, RECEITA, DESPESA).
"""

from __future__ import annotations

import math
import re


def parse_brazilian_value(value_str: str | None) -> tuple[float, str]:
    """Converte um valor contábil no formato brasileiro para (float, indicador).

    Formato de entrada:
        - "1.234.567,89D" → (1234567.89, "D")
        - "1.234.567,89C" → (1234567.89, "C")
        - "0,00"          → (0.0, "")
        - None / NaN       → (0.0, "")

    Args:
        value_str: String do valor no formato brasileiro, ou None/NaN.

    Returns:
        Tupla (valor_absoluto, indicador) onde indicador é "D", "C" ou "".

    Examples:
        >>> parse_brazilian_value("18.623.655,70D")
        (18623655.7, 'D')
        >>> parse_brazilian_value("0,00")
        (0.0, '')
        >>> parse_brazilian_value(None)
        (0.0, '')
    """
    # Tratar None, NaN e tipos não-string
    if value_str is None:
        return (0.0, "")

    if isinstance(value_str, float) and math.isnan(value_str):
        return (0.0, "")

    if not isinstance(value_str, str):
        try:
            return (float(value_str), "")
        except (ValueError, TypeError):
            return (0.0, "")

    # Limpar espaços e caracteres invisíveis
    cleaned = value_str.strip()

    if not cleaned:
        return (0.0, "")

    # Extrair indicador D/C do final
    indicator = ""
    if cleaned.upper().endswith("D"):
        indicator = "D"
        cleaned = cleaned[:-1].strip()
    elif cleaned.upper().endswith("C"):
        indicator = "C"
        cleaned = cleaned[:-1].strip()

    # Remover pontos (separador de milhar)
    cleaned = cleaned.replace(".", "")

    # Substituir vírgula (separador decimal) por ponto
    cleaned = cleaned.replace(",", ".")

    # Remover caracteres estranhos restantes (exceto dígitos, ponto, sinal)
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)

    if not cleaned:
        return (0.0, "")

    try:
        value = float(cleaned)
    except ValueError:
        return (0.0, "")

    return (value, indicator)


def apply_sign(value: float, indicator: str, account_group: int) -> float:
    """Aplica sinal ao valor conforme o grupo contábil e o indicador D/C.

    Convenções de sinal:
        - Grupo 1 (ATIVO):   D = +positivo,  C = -negativo
        - Grupo 2 (PASSIVO): C = -negativo,   D = +positivo
        - Grupo 3 (RECEITA): C = -negativo,   D = +positivo
        - Grupo 4 (DESPESA): D = +positivo,   C = -negativo

    Args:
        value: Valor absoluto (sempre >= 0).
        indicator: "D", "C" ou "" (vazio = zero).
        account_group: Número do grupo contábil (1, 2, 3 ou 4).

    Returns:
        Valor com sinal aplicado.

    Raises:
        ValueError: Se o grupo contábil não for 1, 2, 3 ou 4.

    Examples:
        >>> apply_sign(1000.0, "D", 1)
        1000.0
        >>> apply_sign(1000.0, "C", 1)
        -1000.0
        >>> apply_sign(500.0, "C", 2)
        -500.0
    """
    if not indicator:
        return 0.0

    indicator = indicator.upper().strip()

    if account_group not in (1, 2, 3, 4):
        raise ValueError(
            f"Grupo contábil inválido: {account_group}. Esperado: 1, 2, 3 ou 4."
        )

    # Definir mapa de sinais: (grupo, indicador) → sinal
    # Grupo 1 (ATIVO):   D=+, C=-
    # Grupo 2 (PASSIVO): D=+, C=-
    # Grupo 3 (RECEITA): D=+, C=-
    # Grupo 4 (DESPESA): D=+, C=-
    if indicator == "D":
        return abs(value)
    elif indicator == "C":
        return -abs(value)
    else:
        return 0.0
