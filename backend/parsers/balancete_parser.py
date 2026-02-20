"""
Parser principal de balancetes de verificação exportados do sistema Hinova.

Lê arquivos .xls/.xlsx e retorna um dicionário de cabeçalho junto com
um DataFrame pandas contendo todas as contas contábeis com tipos,
níveis, grupos e saldos com sinais aplicados.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from backend.parsers.header_extractor import extract_header
from backend.parsers.value_converter import apply_sign, parse_brazilian_value


# Mapa do primeiro dígito da conta para grupo contábil
_GROUP_MAP: dict[str, tuple[str, int]] = {
    "1": ("ATIVO", 1),
    "2": ("PASSIVO", 2),
    "3": ("RECEITA", 3),
    "4": ("DESPESA", 4),
    "5": ("DESPESA", 4),  # Grupo 5 também é despesa/custos em alguns planos
}


def _read_data_rows(filepath: str) -> list[list[Any]]:
    """Lê todas as linhas de dados do balancete (a partir da linha 3).

    Lê até encontrar uma linha com "Total Geral" na coluna 0.

    Args:
        filepath: Caminho para o arquivo .xls ou .xlsx.

    Returns:
        Lista de listas com os valores de cada linha (7 colunas).

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o formato não for .xls nem .xlsx.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".xls":
        return _read_xls_data(filepath)
    elif ext == ".xlsx":
        return _read_xlsx_data(filepath)
    else:
        raise ValueError(
            f"Formato de arquivo não suportado: '{ext}'. Use .xls ou .xlsx."
        )


def _read_xls_data(filepath: str) -> list[list[Any]]:
    """Lê dados de um arquivo .xls (Excel 97-2003) via xlrd."""
    import xlrd

    workbook = xlrd.open_workbook(filepath)
    sheet = workbook.sheet_by_index(0)
    rows: list[list[Any]] = []

    # Dados começam na linha 3 (0-indexed), cabeçalho são linhas 0-2
    for row_idx in range(3, sheet.nrows):
        row: list[Any] = []
        for col_idx in range(min(7, sheet.ncols)):
            row.append(sheet.cell_value(row_idx, col_idx))

        # Parar ao encontrar "Total Geral"
        cell0 = str(row[0]).strip() if row and row[0] else ""
        if "total geral" in cell0.lower():
            break

        rows.append(row)

    return rows


def _read_xlsx_data(filepath: str) -> list[list[Any]]:
    """Lê dados de um arquivo .xlsx via openpyxl."""
    import openpyxl

    workbook = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    sheet = workbook.active
    rows: list[list[Any]] = []

    for row_idx, row in enumerate(
        sheet.iter_rows(max_col=7, values_only=True)
    ):
        # Pular cabeçalho (linhas 0-2)
        if row_idx < 3:
            continue

        row_list = list(row)

        # Parar ao encontrar "Total Geral"
        cell0 = str(row_list[0]).strip() if row_list and row_list[0] else ""
        if "total geral" in cell0.lower():
            break

        rows.append(row_list)

    workbook.close()
    return rows


def _determine_account_level(codigo: str) -> int:
    """Determina o nível da conta pela quantidade de partes separadas por ponto.

    Args:
        codigo: Código da conta contábil, ex: "1.01.01.02.00004"

    Returns:
        Número de partes: "1" → 1, "1.01" → 2, "1.01.01.02.00004" → 5

    Examples:
        >>> _determine_account_level("1")
        1
        >>> _determine_account_level("4.03.01.03")
        4
    """
    if not codigo:
        return 0
    return len(codigo.split("."))


def _get_account_group(codigo: str) -> tuple[str, int]:
    """Retorna o grupo contábil baseado no primeiro caractere da conta.

    Args:
        codigo: Código da conta contábil.

    Returns:
        Tupla (nome_grupo, numero_grupo).

    Raises:
        ValueError: Se o primeiro caractere não for mapeável.
    """
    if not codigo:
        raise ValueError("Código de conta vazio.")

    first_char = codigo[0]
    if first_char in _GROUP_MAP:
        return _GROUP_MAP[first_char]

    raise ValueError(
        f"Grupo contábil desconhecido para conta '{codigo}'. "
        f"Primeiro caractere '{first_char}' não está no mapa: {list(_GROUP_MAP.keys())}"
    )


def parse_balancete(filepath: str) -> tuple[dict, pd.DataFrame]:
    """Parseia um balancete de verificação exportado do sistema Hinova.

    Detecta o formato do arquivo (.xls ou .xlsx), extrai o cabeçalho com
    metadados e parseia todas as linhas de dados, gerando um DataFrame
    com contas, níveis, tipos, grupos e valores com sinais aplicados.

    Args:
        filepath: Caminho para o arquivo .xls ou .xlsx.

    Returns:
        Tupla (header_dict, dataframe) onde:
            - header_dict: Dicionário com metadados do cabeçalho
            - dataframe: DataFrame pandas com colunas:
                - codigo_conta (str)
                - titulo_conta (str)
                - red (int | None)
                - nivel (int)
                - tipo (str): "Macro" ou "Último Nível"
                - grupo (str): "ATIVO", "PASSIVO", "RECEITA" ou "DESPESA"
                - grupo_num (int): 1, 2, 3 ou 4
                - saldo_anterior (float): com sinal aplicado
                - debitos (float): sempre positivo
                - creditos (float): sempre positivo
                - saldo_atual (float): com sinal aplicado
                - indicador_dc (str): "D", "C" ou ""
                - periodo (str): "YYYY-MM"

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o formato não for suportado ou dados estiverem corrompidos.
    """
    # 1) Extrair header
    header = extract_header(filepath)
    periodo = header["mes_referencia"]

    # 2) Ler dados brutos
    raw_rows = _read_data_rows(filepath)

    if not raw_rows:
        raise ValueError("Nenhuma linha de dados encontrada no balancete.")

    # 3) Parsear cada linha
    records: list[dict] = []

    for row in raw_rows:
        # Colunas: 0=Conta, 1=Red, 2=Título, 3=Saldo Ant, 4=Débitos, 5=Créditos, 6=Saldo Atual
        codigo_conta = str(row[0]).strip() if row[0] is not None else ""

        # Pular linhas vazias
        if not codigo_conta:
            continue

        titulo_conta = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""

        # Red (pode ser int, float, ou vazio)
        red_raw = row[1] if len(row) > 1 else None
        red: int | None = None
        if red_raw is not None and str(red_raw).strip():
            try:
                red = int(float(str(red_raw).strip()))
            except (ValueError, TypeError):
                red = None

        # Nível
        nivel = _determine_account_level(codigo_conta)

        # Grupo
        grupo, grupo_num = _get_account_group(codigo_conta)

        # Valores
        saldo_ant_str = str(row[3]) if len(row) > 3 and row[3] is not None else "0,00"
        debitos_str = str(row[4]) if len(row) > 4 and row[4] is not None else "0,00"
        creditos_str = str(row[5]) if len(row) > 5 and row[5] is not None else "0,00"
        saldo_atual_str = str(row[6]) if len(row) > 6 and row[6] is not None else "0,00"

        saldo_ant_val, saldo_ant_ind = parse_brazilian_value(saldo_ant_str)
        debitos_val, _ = parse_brazilian_value(debitos_str)
        creditos_val, _ = parse_brazilian_value(creditos_str)
        saldo_atual_val, saldo_atual_ind = parse_brazilian_value(saldo_atual_str)

        # Aplicar sinais
        saldo_anterior = apply_sign(saldo_ant_val, saldo_ant_ind, grupo_num)
        saldo_atual = apply_sign(saldo_atual_val, saldo_atual_ind, grupo_num)

        records.append(
            {
                "codigo_conta": codigo_conta,
                "titulo_conta": titulo_conta,
                "red": red,
                "nivel": nivel,
                "tipo": "",  # será preenchido depois
                "grupo": grupo,
                "grupo_num": grupo_num,
                "saldo_anterior": saldo_anterior,
                "debitos": abs(debitos_val),
                "creditos": abs(creditos_val),
                "saldo_atual": saldo_atual,
                "indicador_dc": saldo_atual_ind,
                "periodo": periodo,
            }
        )

    # 4) Determinar tipo (Macro vs Último Nível)
    for i, rec in enumerate(records):
        if i + 1 < len(records):
            next_nivel = records[i + 1]["nivel"]
            if next_nivel > rec["nivel"]:
                rec["tipo"] = "Macro"
            else:
                rec["tipo"] = "Último Nível"
        else:
            # Última linha é sempre Último Nível
            rec["tipo"] = "Último Nível"

    # 5) Montar DataFrame
    df = pd.DataFrame(records)

    return header, df
