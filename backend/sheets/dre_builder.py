"""
Montagem da DRE (Demonstração do Resultado do Exercício) no Google Sheets.

Gera fórmulas SUMIFS nativas que referenciam a aba "Base Balancete",
calculando a variação mensal (saldo acumulado atual − anterior) e
invertendo o sinal para a convenção da DRE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backend.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SHEET_NAME = "DRE"
BASE_SHEET = "Base Balancete"

_MONTH_ABBR: dict[str, str] = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}


# ---------------------------------------------------------------------------
# Estrutura da DRE
# ---------------------------------------------------------------------------

@dataclass
class _DRELine:
    """Descrição de uma linha da DRE."""
    label: str
    line_type: str  # somases | subtotal | formula | blank | label | margin
    classification: str = ""
    children_rows: list[int] = field(default_factory=list)
    formula_tpl: str = ""
    bold: bool = False
    pct_format: bool = False


# Cada entrada mapeia para uma linha do sheet (índice 0 → row 2, pois row 1 = headers).
_DRE_STRUCTURE: list[_DRELine] = [
    # ── Receita ──────────────────────────────────────────────────────────
    _DRELine("Receita Bruta", "subtotal", children_rows=[3, 4], bold=True),                        # row 2
    _DRELine("  (+) Receita de Serviços", "somases", classification="Receita de Serviços"),         # row 3
    _DRELine("  (+) Outras Receitas", "somases", classification="Outras Receitas"),                 # row 4
    _DRELine("(-) Deduções da Receita", "subtotal", children_rows=[6, 7, 8, 9], bold=True),        # row 5
    _DRELine("  (-) ISS", "somases", classification="ISS"),                                        # row 6
    _DRELine("  (-) PIS", "somases", classification="PIS"),                                        # row 7
    _DRELine("  (-) COFINS", "somases", classification="COFINS"),                                  # row 8
    _DRELine("  (-) Descontos e Devoluções", "somases", classification="Descontos e Devoluções"),   # row 9
    _DRELine("= Receita Líquida", "formula", formula_tpl="={c}2+{c}5", bold=True),                 # row 10
    _DRELine("", "blank"),                                                                         # row 11
    # ── CSP ──────────────────────────────────────────────────────────────
    _DRELine("(-) CSP", "subtotal", children_rows=[13, 14, 15], bold=True),                        # row 12
    _DRELine("  (-) Equipe", "somases", classification="CSP - Equipe"),                             # row 13
    _DRELine("  (-) Servidor/Cloud", "somases", classification="Servidor/Cloud"),                   # row 14
    _DRELine("  (-) Software", "somases", classification="Software"),                               # row 15
    _DRELine("= Lucro Bruto", "formula", formula_tpl="={c}10+{c}12", bold=True),                   # row 16
    _DRELine("", "blank"),                                                                         # row 17
    # ── OpEx ─────────────────────────────────────────────────────────────
    _DRELine("(-) Ocupação", "somases", classification="Ocupação"),                                 # row 18
    _DRELine("(-) D&A", "somases", classification="D&A"),                                           # row 19
    _DRELine("(-) Despesas Comerciais", "subtotal", children_rows=[21, 22], bold=True),             # row 20
    _DRELine("  (-) Equipe de Originação", "somases", classification="Equipe de Originação"),       # row 21
    _DRELine("  (-) Viagens e Estadias", "somases", classification="Viagens e Estadias"),           # row 22
    _DRELine("(-) Despesas de Marketing", "somases", classification="Despesas de Marketing"),       # row 23
    _DRELine("(-) Despesas Gerais e Administrativas", "subtotal",
             children_rows=[25, 26, 27, 28], bold=True),                                           # row 24
    _DRELine("  (-) Equipe Administrativa e RH", "somases",
             classification="Equipe Administrativa e RH"),                                         # row 25
    _DRELine("  (-) Serviços de Terceiros", "somases", classification="Serviços de Terceiros"),     # row 26
    _DRELine("  (-) Tributárias", "somases", classification="Tributárias"),                          # row 27
    _DRELine("  (-) Demais G&A", "somases", classification="Demais G&A"),                           # row 28
    # EBITDA = Lucro Bruto + OpEx (sem D&A)
    _DRELine("= EBITDA", "formula",
             formula_tpl="={c}16+{c}18+{c}20+{c}23+{c}24", bold=True),                            # row 29
    _DRELine("", "blank"),                                                                         # row 30
    # ── Abaixo do EBITDA ─────────────────────────────────────────────────
    _DRELine("(+) D&A", "formula", formula_tpl="=-{c}19"),                                         # row 31
    _DRELine("(+) Resultado Financeiro", "subtotal", children_rows=[33, 34], bold=True),            # row 32
    _DRELine("  (+) Receitas Financeiras", "somases", classification="Receitas Financeiras"),       # row 33
    _DRELine("  (-) Despesas Financeiras", "somases", classification="Despesas Financeiras"),       # row 34
    _DRELine("(+) Resultado não Operacional", "subtotal", children_rows=[36, 37], bold=True),      # row 35
    _DRELine("  (+) Receitas não Operacionais", "somases",
             classification="Receitas não Operacionais"),                                          # row 36
    _DRELine("  (-) Despesas não Operacionais", "somases",
             classification="Despesas não Operacionais"),                                          # row 37
    # Lucro antes IR = EBITDA - D&A + Financeiro + Não-op
    _DRELine("= Lucro Antes IR/CSLL", "formula",
             formula_tpl="={c}29+{c}19+{c}32+{c}35", bold=True),                                  # row 38
    _DRELine("(-) IRPJ e CSLL", "subtotal", children_rows=[40, 41], bold=True),                    # row 39
    _DRELine("  (-) IRPJ", "somases", classification="IRPJ"),                                      # row 40
    _DRELine("  (-) CSLL", "somases", classification="CSLL"),                                      # row 41
    _DRELine("= Lucro Líquido", "formula", formula_tpl="={c}38+{c}39", bold=True),                 # row 42
    _DRELine("", "blank"),                                                                         # row 43
    # ── Análise Vertical ─────────────────────────────────────────────────
    _DRELine("--- Análise Vertical ---", "label", bold=True),                                      # row 44
    _DRELine("Margem Bruta", "margin", formula_tpl="=IFERROR({c}16/{c}10,0)", pct_format=True),    # row 45
    _DRELine("Margem EBITDA", "margin", formula_tpl="=IFERROR({c}29/{c}10,0)", pct_format=True),   # row 46
    _DRELine("Margem Líquida", "margin", formula_tpl="=IFERROR({c}42/{c}10,0)", pct_format=True),  # row 47
]

# Último row da estrutura
_LAST_DATA_ROW = len(_DRE_STRUCTURE) + 1  # +1 porque row 1 = header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_letter(n: int) -> str:
    """Converte número de coluna 1-based para letra (1→A, 2→B, …, 27→AA)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _period_to_header(period: str) -> str:
    """Converte '2025-01' para 'Jan/25'."""
    parts = period.split("-")
    return f"{_MONTH_ABBR.get(parts[1], parts[1])}/{parts[0][2:]}"


def _sumifs(classification: str, period: str) -> str:
    """Gera o trecho SUMIFS (sem sinal)."""
    b = f"'{BASE_SHEET}'"
    return (
        f"SUMIFS({b}!I:I,"
        f"{b}!J:J,\"{classification}\","
        f"{b}!F:F,\"{period}\","
        f"{b}!D:D,\"Último Nível\")"
    )


def _somases_formula(classification: str, period: str, prev_period: str | None) -> str:
    """Fórmula SOMASES completa para uma célula da DRE."""
    if prev_period is None:
        return f"=-{_sumifs(classification, period)}"
    return f"=-({_sumifs(classification, period)}-{_sumifs(classification, prev_period)})"


def _subtotal_formula(col: str, children_rows: list[int]) -> str:
    """Fórmula de soma dos filhos."""
    return "=" + "+".join(f"{col}{r}" for r in children_rows)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class DREBuilder:
    """Monta e gerencia a aba DRE no Google Sheets."""

    def __init__(self, sheets_client: SheetsClient) -> None:
        self._client = sheets_client

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def build_dre(self, periods: list[str]) -> None:
        """
        Monta (ou remonta) a aba DRE para os períodos informados.

        Args:
            periods: Lista de períodos ordenados, ex ``["2025-01", …, "2025-12"]``.
        """
        if not periods:
            raise ValueError("Lista de períodos não pode ser vazia.")

        n = len(periods)
        total_col_idx = n + 2           # coluna "Total Ano"
        last_month_col_idx = n + 1      # última coluna de mês
        total_col = _col_letter(total_col_idx)
        first_month_col = _col_letter(2)  # B
        last_month_col = _col_letter(last_month_col_idx)

        # 1) Garantir que a aba existe e limpar
        self._client.ensure_sheet_exists(SHEET_NAME)
        self._client.clear_sheet(SHEET_NAME, preserve_headers=False)

        # 2) Headers (row 1)
        headers = [""] + [_period_to_header(p) for p in periods] + ["Total Ano"]
        self._client.update_range(SHEET_NAME, "A1", [headers])

        # 3) Labels (coluna A, rows 2‑N)
        labels = [[line.label] for line in _DRE_STRUCTURE]
        self._client.update_range(
            SHEET_NAME, f"A2:A{_LAST_DATA_ROW}", labels
        )

        # 4) Fórmulas — coletar tudo para um único batch
        formulas: list[dict[str, Any]] = []

        for idx, line in enumerate(_DRE_STRUCTURE):
            row = idx + 2  # sheet row

            if line.line_type in ("blank", "label"):
                continue

            # ── Colunas de meses ──
            for pi, period in enumerate(periods):
                col_idx = pi + 2
                col = _col_letter(col_idx)
                prev = periods[pi - 1] if pi > 0 else None

                if line.line_type == "somases":
                    f = _somases_formula(line.classification, period, prev)
                elif line.line_type == "subtotal":
                    f = _subtotal_formula(col, line.children_rows)
                elif line.line_type in ("formula", "margin"):
                    f = line.formula_tpl.replace("{c}", col)
                else:
                    continue  # pragma: no cover

                formulas.append({"row": row, "col": col_idx, "formula": f})

            # ── Coluna Total Ano ──
            if line.line_type in ("margin", ):
                f = line.formula_tpl.replace("{c}", total_col)
            else:
                f = f"=SUM({first_month_col}{row}:{last_month_col}{row})"

            formulas.append({"row": row, "col": total_col_idx, "formula": f})

        self._client.batch_write_formulas(SHEET_NAME, formulas)
        logger.info(
            "DRE montada: %d fórmulas escritas para %d períodos.",
            len(formulas), n,
        )

        # 5) Formatação
        self._apply_formatting(total_col_idx)

    def get_dre_data(self) -> pd.DataFrame:
        """Retorna os dados calculados da DRE (valores resolvidos)."""
        return self._client.read_sheet(SHEET_NAME)

    # ------------------------------------------------------------------
    # Formatação
    # ------------------------------------------------------------------

    def _apply_formatting(self, last_col_idx: int) -> None:
        """Aplica negrito, formato numérico e formato percentual."""
        last_col = _col_letter(last_col_idx)

        # Header row 1: negrito
        self._client.format_range(
            SHEET_NAME, f"A1:{last_col}1",
            {"textFormat": {"bold": True}},
        )

        # Linhas em negrito
        for idx, line in enumerate(_DRE_STRUCTURE):
            row = idx + 2
            if line.bold:
                self._client.format_range(
                    SHEET_NAME, f"A{row}:{last_col}{row}",
                    {"textFormat": {"bold": True}},
                )

        # Formato numérico para colunas de valores (B em diante)
        value_range = f"B2:{last_col}{_LAST_DATA_ROW}"
        self._client.format_range(
            SHEET_NAME, value_range,
            {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}},
        )

        # Formato percentual para margens
        for idx, line in enumerate(_DRE_STRUCTURE):
            row = idx + 2
            if line.pct_format:
                self._client.format_range(
                    SHEET_NAME, f"B{row}:{last_col}{row}",
                    {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}},
                )

        logger.info("Formatação da DRE aplicada.")

    # ------------------------------------------------------------------
    # Gerenciamento de classificações
    # ------------------------------------------------------------------

    @staticmethod
    def get_structure() -> list[dict]:
        """Retorna a estrutura da DRE como lista de dicts (para introspecção)."""
        return [
            {
                "row": i + 2,
                "label": line.label,
                "type": line.line_type,
                "classification": line.classification,
            }
            for i, line in enumerate(_DRE_STRUCTURE)
        ]

    @staticmethod
    def get_classifications() -> list[str]:
        """Retorna todas as classificações SOMASES usadas na DRE."""
        return [
            line.classification
            for line in _DRE_STRUCTURE
            if line.line_type == "somases" and line.classification
        ]
