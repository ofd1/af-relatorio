"""
Módulo de extração do cabeçalho de balancetes Hinova.

Lê as 3 primeiras linhas de um arquivo .xls/.xlsx e extrai:
empresa, CNPJ, período, data de emissão, mês de referência e tipo.
"""

from __future__ import annotations

import os
import re
from datetime import datetime


def _read_header_rows(filepath: str) -> list[list]:
    """Lê as 3 primeiras linhas do arquivo Excel.

    Args:
        filepath: Caminho para o arquivo .xls ou .xlsx.

    Returns:
        Lista com 3 listas, cada uma contendo os valores das colunas (até 7 cols).

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o formato não for .xls nem .xlsx.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(filepath)
        sheet = workbook.sheet_by_index(0)
        rows = []
        for row_idx in range(min(3, sheet.nrows)):
            row = []
            for col_idx in range(min(7, sheet.ncols)):
                row.append(sheet.cell_value(row_idx, col_idx))
            rows.append(row)
        return rows

    elif ext == ".xlsx":
        import openpyxl

        workbook = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet = workbook.active
        rows = []
        for row_idx, row in enumerate(sheet.iter_rows(max_row=3, max_col=7, values_only=True)):
            rows.append(list(row))
        workbook.close()
        return rows

    else:
        raise ValueError(
            f"Formato de arquivo não suportado: '{ext}'. Use .xls ou .xlsx."
        )


def extract_header(filepath: str) -> dict:
    """Extrai metadados do cabeçalho de um balancete Hinova.

    Espera a seguinte estrutura nas 3 primeiras linhas do arquivo:
        - Linha 0: Nome da empresa (col 0) + "Período: DD/MM/AAAA à DD/MM/AAAA" (col 5)
        - Linha 1: "CNPJ: XX.XXX.XXX/XXXX-XX" (col 0) + "Emissão: DD/MM/AAAA HH:MM:SS" (col 5)
        - Linha 2: Headers das colunas (ignorada)

    Args:
        filepath: Caminho para o arquivo .xls ou .xlsx.

    Returns:
        Dicionário com:
            - empresa (str): Nome da empresa
            - cnpj (str): CNPJ formatado
            - periodo_inicio (str): Data ISO "YYYY-MM-DD"
            - periodo_fim (str): Data ISO "YYYY-MM-DD"
            - emissao (str): Datetime ISO "YYYY-MM-DDTHH:MM:SS"
            - mes_referencia (str): "YYYY-MM" extraído do periodo_fim
            - tipo (str): "anual" se Jan 1 → Dec 31, senão "mensal"

    Raises:
        ValueError: Se não conseguir parsear os campos obrigatórios.
    """
    rows = _read_header_rows(filepath)

    if len(rows) < 2:
        raise ValueError(
            f"Arquivo tem apenas {len(rows)} linhas. Esperado pelo menos 2 linhas de cabeçalho."
        )

    # --- Linha 0 ---
    row0 = rows[0]

    # Empresa (coluna 0)
    empresa = str(row0[0]).strip() if len(row0) > 0 and row0[0] else ""
    if not empresa:
        raise ValueError("Campo 'empresa' não encontrado na linha 0, coluna 0.")

    # Período (coluna 5)
    periodo_str = str(row0[5]).strip() if len(row0) > 5 and row0[5] else ""
    periodo_match = re.search(
        r"Per[ií]odo:\s*(\d{2}/\d{2}/\d{4})\s*[àa]\s*(\d{2}/\d{2}/\d{4})",
        periodo_str,
        re.IGNORECASE,
    )
    if not periodo_match:
        raise ValueError(
            f"Não foi possível extrair o período da linha 0, coluna 5: '{periodo_str}'"
        )

    periodo_inicio = datetime.strptime(periodo_match.group(1), "%d/%m/%Y")
    periodo_fim = datetime.strptime(periodo_match.group(2), "%d/%m/%Y")

    # --- Linha 1 ---
    row1 = rows[1]

    # CNPJ (coluna 0)
    cnpj_str = str(row1[0]).strip() if len(row1) > 0 and row1[0] else ""
    cnpj_match = re.search(
        r"CNPJ:\s*([\d./-]+)",
        cnpj_str,
        re.IGNORECASE,
    )
    if not cnpj_match:
        raise ValueError(
            f"Não foi possível extrair o CNPJ da linha 1, coluna 0: '{cnpj_str}'"
        )
    cnpj = cnpj_match.group(1).strip()

    # Emissão (coluna 5)
    emissao_str = str(row1[5]).strip() if len(row1) > 5 and row1[5] else ""
    emissao_match = re.search(
        r"Emiss[ãa]o:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})",
        emissao_str,
        re.IGNORECASE,
    )
    if not emissao_match:
        raise ValueError(
            f"Não foi possível extrair a emissão da linha 1, coluna 5: '{emissao_str}'"
        )
    emissao = datetime.strptime(
        f"{emissao_match.group(1)} {emissao_match.group(2)}", "%d/%m/%Y %H:%M:%S"
    )

    # --- Derivados ---
    mes_referencia = periodo_fim.strftime("%Y-%m")

    # Tipo: anual se de 01/01 até 31/12 do mesmo ano (ou ano seguinte)
    is_anual = (
        periodo_inicio.month == 1
        and periodo_inicio.day == 1
        and periodo_fim.month == 12
        and periodo_fim.day == 31
    )
    tipo = "anual" if is_anual else "mensal"

    return {
        "empresa": empresa,
        "cnpj": cnpj,
        "periodo_inicio": periodo_inicio.strftime("%Y-%m-%d"),
        "periodo_fim": periodo_fim.strftime("%Y-%m-%d"),
        "emissao": emissao.strftime("%Y-%m-%dT%H:%M:%S"),
        "mes_referencia": mes_referencia,
        "tipo": tipo,
    }
