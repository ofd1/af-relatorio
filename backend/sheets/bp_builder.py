"""
Montagem do Balanço Patrimonial (BP) no Google Sheets.

Diferente da DRE, o BP usa o **saldo final acumulado** do período
(SUMIFS direto, sem subtrair o mês anterior).
Contas patrimoniais (grupos 1 e 2) já representam saldos acumulados.
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
SHEET_NAME = "Balanço Patrimonial"
BASE_SHEET = "Base Balancete"
DRE_SHEET = "DRE"

_MONTH_ABBR: dict[str, str] = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

# Linha do Lucro Líquido na DRE (row 42)
_DRE_LUCRO_LIQUIDO_ROW = 42


# ---------------------------------------------------------------------------
# Estrutura do BP
# ---------------------------------------------------------------------------

@dataclass
class _BPLine:
    """Descrição de uma linha do Balanço Patrimonial."""
    label: str
    line_type: str  # somases | subtotal | formula | blank | label | dre_ref
    classification: str = ""
    children_rows: list[int] = field(default_factory=list)
    formula_tpl: str = ""
    bold: bool = False


# Cada entrada mapeia para uma linha do sheet (índice 0 → row 2).
_BP_STRUCTURE: list[_BPLine] = [
    # ── ATIVO ────────────────────────────────────────────────────────────
    _BPLine("ATIVO", "label", bold=True),                                                        # row 2
    _BPLine("Ativo Circulante", "subtotal", children_rows=[4, 5, 6, 7], bold=True),              # row 3
    _BPLine("  (+) Caixa e Equivalentes de Caixa", "somases",
            classification="Caixa e Equivalentes de Caixa"),                                     # row 4
    _BPLine("  (+) Clientes", "somases", classification="Clientes"),                              # row 5
    _BPLine("  (+) Despesas Pagas Antecipadamente", "somases",
            classification="Despesas Pagas Antecipadamente"),                                    # row 6
    _BPLine("  (+) Outros Créditos", "somases", classification="Outros Créditos"),                # row 7
    _BPLine("Ativo Não Circulante", "subtotal", children_rows=[9, 10, 13], bold=True),           # row 8
    _BPLine("  (+) Realizável a Longo Prazo", "somases",
            classification="Realizável a Longo Prazo"),                                          # row 9
    _BPLine("  (+) Imobilizado", "subtotal", children_rows=[11, 12], bold=True),                 # row 10
    _BPLine("    (+) Bens em Operação", "somases", classification="Bens em Operação"),           # row 11
    _BPLine("    (-) Depreciação Acumulada", "somases",
            classification="Depreciação Acumulada"),                                             # row 12
    _BPLine("  (+) Intangível", "subtotal", children_rows=[14, 15], bold=True),                  # row 13
    _BPLine("    (+) Softwares, Projetos", "somases",
            classification="Softwares, Projetos"),                                               # row 14
    _BPLine("    (-) Amortização Acumulada", "somases",
            classification="Amortização Acumulada"),                                             # row 15
    _BPLine("Total Ativo", "formula",
            formula_tpl="={c}3+{c}8", bold=True),                                               # row 16
    _BPLine("", "blank"),                                                                        # row 17
    # ── PASSIVO + PL ─────────────────────────────────────────────────────
    _BPLine("PASSIVO + PL", "label", bold=True),                                                 # row 18
    _BPLine("Passivo Circulante", "subtotal",
            children_rows=[20, 21, 22, 23, 24, 25], bold=True),                                 # row 19
    _BPLine("  (+) Empréstimos e Financiamentos CP", "somases",
            classification="Empréstimos e Financiamentos CP"),                                   # row 20
    _BPLine("  (+) Dividendos a Distribuir", "somases",
            classification="Dividendos a Distribuir"),                                           # row 21
    _BPLine("  (+) Fornecedores", "somases", classification="Fornecedores"),                     # row 22
    _BPLine("  (+) Obrigações Trabalhistas e Previd.", "somases",
            classification="Obrigações Trabalhistas e Previd."),                                 # row 23
    _BPLine("  (+) Obrigações Tributárias", "somases",
            classification="Obrigações Tributárias"),                                            # row 24
    _BPLine("  (+) Outras Obrigações", "somases",
            classification="Outras Obrigações"),                                                 # row 25
    _BPLine("Passivo Não Circulante", "subtotal", children_rows=[27], bold=True),                # row 26
    _BPLine("  (+) Empréstimos e Financiamentos LP", "somases",
            classification="Empréstimos e Financiamentos LP"),                                   # row 27
    _BPLine("Patrimônio Líquido", "subtotal",
            children_rows=[29, 30, 31, 32], bold=True),                                         # row 28
    _BPLine("  (+) Capital Social", "somases", classification="Capital Social"),                  # row 29
    _BPLine("  (+) Reserva de Lucros", "somases", classification="Reserva de Lucros"),           # row 30
    _BPLine("  (+) Lucros/Prejuízos Acumulados", "somases",
            classification="Lucros/Prejuízos Acumulados"),                                       # row 31
    _BPLine("  (+) Resultado do Exercício", "dre_ref"),                                          # row 32
    _BPLine("Total Passivo + PL", "formula",
            formula_tpl="={c}19+{c}26+{c}28", bold=True),                                       # row 33
    _BPLine("", "blank"),                                                                        # row 34
    # ── Validação ────────────────────────────────────────────────────────
    _BPLine("Validação", "label", bold=True),                                                    # row 35
    _BPLine("Diferença (Ativo + Passivo+PL)", "formula",
            formula_tpl="={c}16+{c}33"),                                                         # row 36
    _BPLine("Check", "formula",
            formula_tpl='=IF(ABS({c}36)<0.02,\"✓\",\"✗ Diff: \"&TEXT({c}36,\"#,##0.00\"))'),     # row 37
]

_LAST_DATA_ROW = len(_BP_STRUCTURE) + 1  # row 1 = header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_letter(n: int) -> str:
    """Converte número de coluna 1-based para letra (1→A, 2→B, …)."""
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
    """SUMIFS direto (saldo acumulado, sem subtração de mês anterior)."""
    b = f"'{BASE_SHEET}'"
    return (
        f"SUMIFS({b}!I:I,"
        f"{b}!J:J,\"{classification}\","
        f"{b}!F:F,\"{period}\","
        f"{b}!D:D,\"Último Nível\")"
    )


def _somases_formula(classification: str, period: str) -> str:
    """Fórmula SUMIFS para saldo acumulado (BP)."""
    return f"={_sumifs(classification, period)}"


def _subtotal_formula(col: str, children_rows: list[int]) -> str:
    """Soma dos filhos."""
    return "=" + "+".join(f"{col}{r}" for r in children_rows)


def _dre_lucro_acumulado_formula(first_month_col: str, current_col: str) -> str:
    """
    Fórmula para Resultado do Exercício no PL.
    Soma os lucros líquidos mensais da DRE do primeiro mês até o mês atual.
    """
    r = _DRE_LUCRO_LIQUIDO_ROW
    if first_month_col == current_col:
        return f"='{DRE_SHEET}'!{current_col}{r}"
    return f"=SUM('{DRE_SHEET}'!{first_month_col}{r}:{current_col}{r})"


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class BPBuilder:
    """Monta e gerencia a aba Balanço Patrimonial no Google Sheets."""

    def __init__(self, sheets_client: SheetsClient) -> None:
        self._client = sheets_client

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def build_bp(self, periods: list[str]) -> None:
        """
        Monta (ou remonta) a aba Balanço Patrimonial.

        Args:
            periods: Lista de períodos ordenados, ex ``["2025-01", …, "2025-12"]``.
        """
        if not periods:
            raise ValueError("Lista de períodos não pode ser vazia.")

        n = len(periods)
        total_col_idx = n + 2
        last_month_col_idx = n + 1
        total_col = _col_letter(total_col_idx)
        first_month_col = _col_letter(2)  # B
        last_month_col = _col_letter(last_month_col_idx)

        # 1) Garantir que a aba existe e limpar
        self._client.ensure_sheet_exists(SHEET_NAME)
        self._client.clear_sheet(SHEET_NAME, preserve_headers=False)

        # 2) Headers (row 1)
        headers = [""] + [_period_to_header(p) for p in periods] + ["Último Período"]
        self._client.update_range(SHEET_NAME, "A1", [headers])

        # 3) Labels (coluna A)
        labels = [[line.label] for line in _BP_STRUCTURE]
        self._client.update_range(
            SHEET_NAME, f"A2:A{_LAST_DATA_ROW}", labels
        )

        # 4) Fórmulas
        formulas: list[dict[str, Any]] = []

        for idx, line in enumerate(_BP_STRUCTURE):
            row = idx + 2

            if line.line_type in ("blank", "label"):
                continue

            # ── Colunas de meses ──
            for pi, period in enumerate(periods):
                col_idx = pi + 2
                col = _col_letter(col_idx)

                if line.line_type == "somases":
                    f = _somases_formula(line.classification, period)
                elif line.line_type == "subtotal":
                    f = _subtotal_formula(col, line.children_rows)
                elif line.line_type == "formula":
                    f = line.formula_tpl.replace("{c}", col)
                elif line.line_type == "dre_ref":
                    f = _dre_lucro_acumulado_formula(first_month_col, col)
                else:
                    continue  # pragma: no cover

                formulas.append({"row": row, "col": col_idx, "formula": f})

            # ── Coluna "Último Período" ──
            # No BP, o último período mostra o saldo final do último mês
            # (não a soma dos meses como na DRE)
            last_col = _col_letter(last_month_col_idx)
            if line.line_type == "dre_ref":
                f = _dre_lucro_acumulado_formula(first_month_col, last_col)
            elif line.line_type == "somases":
                f = _somases_formula(line.classification, periods[-1])
            elif line.line_type == "subtotal":
                f = _subtotal_formula(total_col, line.children_rows)
            elif line.line_type == "formula":
                f = line.formula_tpl.replace("{c}", total_col)
            else:
                continue  # pragma: no cover

            formulas.append({"row": row, "col": total_col_idx, "formula": f})

        self._client.batch_write_formulas(SHEET_NAME, formulas)
        logger.info(
            "Balanço Patrimonial montado: %d fórmulas para %d períodos.",
            len(formulas), n,
        )

        # 5) Formatação
        self._apply_formatting(total_col_idx)

    def get_bp_data(self) -> pd.DataFrame:
        """Retorna os dados calculados do BP (valores resolvidos)."""
        return self._client.read_sheet(SHEET_NAME)

    # ------------------------------------------------------------------
    # Formatação
    # ------------------------------------------------------------------

    def _apply_formatting(self, last_col_idx: int) -> None:
        last_col = _col_letter(last_col_idx)

        # Header row 1: negrito
        self._client.format_range(
            SHEET_NAME, f"A1:{last_col}1",
            {"textFormat": {"bold": True}},
        )

        # Linhas em negrito
        for idx, line in enumerate(_BP_STRUCTURE):
            row = idx + 2
            if line.bold:
                self._client.format_range(
                    SHEET_NAME, f"A{row}:{last_col}{row}",
                    {"textFormat": {"bold": True}},
                )

        # Formato numérico
        value_range = f"B2:{last_col}{_LAST_DATA_ROW}"
        self._client.format_range(
            SHEET_NAME, value_range,
            {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}},
        )

        logger.info("Formatação do Balanço Patrimonial aplicada.")

    # ------------------------------------------------------------------
    # Introspecção
    # ------------------------------------------------------------------

    @staticmethod
    def get_structure() -> list[dict]:
        """Retorna a estrutura do BP como lista de dicts."""
        return [
            {
                "row": i + 2,
                "label": line.label,
                "type": line.line_type,
                "classification": line.classification,
            }
            for i, line in enumerate(_BP_STRUCTURE)
        ]

    @staticmethod
    def get_classifications() -> list[str]:
        """Retorna todas as classificações SOMASES usadas no BP."""
        return [
            line.classification
            for line in _BP_STRUCTURE
            if line.line_type == "somases" and line.classification
        ]
