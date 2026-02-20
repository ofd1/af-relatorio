"""
Montagem da DFC (Demonstração de Fluxo de Caixa) pelo método indireto.

A DFC é 100 % derivada da DRE e do BP por fórmulas.
Todas as variações são calculadas como ``-(BP_atual - BP_anterior)``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backend.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes — referências cruzadas
# ---------------------------------------------------------------------------
SHEET_NAME = "DFC"
BP_SHEET = "Balanço Patrimonial"
DRE_SHEET = "DRE"

# Rows na DRE
_DRE_LUCRO_LIQUIDO_ROW = 42   # = Lucro Líquido
_DRE_DA_ROW = 19              # (-) D&A (negativo na DRE)

# Rows no BP (devem coincidir com bp_builder._BP_STRUCTURE)
_BP_CAIXA = 4
_BP_CLIENTES = 5
_BP_DESP_ANTECIP = 6
_BP_OUTROS_CRED = 7
_BP_REALIZ_LP = 9
_BP_BENS_OPER = 11
_BP_SOFT_PROJ = 14
_BP_EMP_CP = 20
_BP_DIVIDENDOS = 21
_BP_FORNECEDORES = 22
_BP_OBRIG_TRAB = 23
_BP_OBRIG_TRIB = 24
_BP_OUTRAS_OBRIG = 25
_BP_EMP_LP = 27
_BP_CAPITAL = 29
_BP_LUCROS_ACUM = 31

_MONTH_ABBR: dict[str, str] = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}


# ---------------------------------------------------------------------------
# Estrutura da DFC
# ---------------------------------------------------------------------------

@dataclass
class _DFCLine:
    """Descrição de uma linha da DFC."""
    label: str
    line_type: str
    # somases/subtotal/formula/blank/label/dre_ref/dre_ref_neg/bp_var/bp_var_multi/bp_ref_cur/bp_ref_prev
    bp_rows: list[int] = field(default_factory=list)
    dre_row: int = 0
    children_rows: list[int] = field(default_factory=list)
    formula_tpl: str = ""
    bold: bool = False


_DFC_STRUCTURE: list[_DFCLine] = [
    # ── ATIVIDADES OPERACIONAIS ──────────────────────────────────────────
    _DFCLine("ATIVIDADES OPERACIONAIS", "label", bold=True),                            # row 2
    _DFCLine("Lucro Líquido", "dre_ref", dre_row=_DRE_LUCRO_LIQUIDO_ROW),              # row 3
    _DFCLine("(+) Depreciação e Amortização", "dre_ref_neg", dre_row=_DRE_DA_ROW),     # row 4
    _DFCLine("(+/-) Δ Clientes", "bp_var", bp_rows=[_BP_CLIENTES]),                     # row 5
    _DFCLine("(+/-) Δ Desp. Pagas Antecipadamente", "bp_var", bp_rows=[_BP_DESP_ANTECIP]),  # row 6
    _DFCLine("(+/-) Δ Outros Créditos", "bp_var", bp_rows=[_BP_OUTROS_CRED]),           # row 7
    _DFCLine("(+/-) Δ Fornecedores", "bp_var", bp_rows=[_BP_FORNECEDORES]),             # row 8
    _DFCLine("(+/-) Δ Obrig. Trabalhistas", "bp_var", bp_rows=[_BP_OBRIG_TRAB]),        # row 9
    _DFCLine("(+/-) Δ Obrig. Tributárias", "bp_var", bp_rows=[_BP_OBRIG_TRIB]),         # row 10
    _DFCLine("(+/-) Δ Outras Obrigações", "bp_var", bp_rows=[_BP_OUTRAS_OBRIG]),        # row 11
    _DFCLine("Subtotal Operacional", "subtotal",
             children_rows=[3, 4, 5, 6, 7, 8, 9, 10, 11], bold=True),                  # row 12
    _DFCLine("", "blank"),                                                               # row 13
    # ── ATIVIDADES DE INVESTIMENTO ───────────────────────────────────────
    _DFCLine("ATIVIDADES DE INVESTIMENTO", "label", bold=True),                          # row 14
    _DFCLine("(+/-) Δ Imobilizado", "bp_var", bp_rows=[_BP_BENS_OPER]),                 # row 15
    _DFCLine("(+/-) Δ Intangível", "bp_var", bp_rows=[_BP_SOFT_PROJ]),                  # row 16
    _DFCLine("(+/-) Δ Realizável LP", "bp_var", bp_rows=[_BP_REALIZ_LP]),               # row 17
    _DFCLine("Subtotal Investimento", "subtotal",
             children_rows=[15, 16, 17], bold=True),                                    # row 18
    _DFCLine("", "blank"),                                                               # row 19
    # ── ATIVIDADES DE FINANCIAMENTO ──────────────────────────────────────
    _DFCLine("ATIVIDADES DE FINANCIAMENTO", "label", bold=True),                         # row 20
    _DFCLine("(+/-) Δ Empréstimos (CP + LP)", "bp_var_multi",
             bp_rows=[_BP_EMP_CP, _BP_EMP_LP]),                                         # row 21
    _DFCLine("(-) Distribuição de Lucros", "bp_var", bp_rows=[_BP_DIVIDENDOS]),          # row 22
    _DFCLine("(+/-) Δ Capital Social", "bp_var", bp_rows=[_BP_CAPITAL]),                 # row 23
    _DFCLine("(+/-) Δ Lucros Acumulados", "bp_var", bp_rows=[_BP_LUCROS_ACUM]),         # row 24
    _DFCLine("Subtotal Financiamento", "subtotal",
             children_rows=[21, 22, 23, 24], bold=True),                                # row 25
    _DFCLine("", "blank"),                                                               # row 26
    # ── RESUMO ───────────────────────────────────────────────────────────
    _DFCLine("Variação de Caixa", "formula",
             formula_tpl="={c}12+{c}18+{c}25", bold=True),                              # row 27
    _DFCLine("Saldo Inicial de Caixa", "bp_ref_prev", bp_rows=[_BP_CAIXA]),             # row 28
    _DFCLine("Saldo Final de Caixa", "bp_ref_cur", bp_rows=[_BP_CAIXA]),                # row 29
    _DFCLine("", "blank"),                                                               # row 30
    _DFCLine("Validação", "label", bold=True),                                           # row 31
    _DFCLine("Check", "check"),                                                           # row 32
]

_LAST_DATA_ROW = len(_DFC_STRUCTURE) + 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _period_to_header(period: str) -> str:
    parts = period.split("-")
    return f"{_MONTH_ABBR.get(parts[1], parts[1])}/{parts[0][2:]}"


def _bp_ref(col: str, bp_row: int) -> str:
    """Referência a uma célula do BP."""
    return f"'{BP_SHEET}'!{col}{bp_row}"


def _dre_ref(col: str, dre_row: int) -> str:
    """Referência a uma célula da DRE."""
    return f"'{DRE_SHEET}'!{col}{dre_row}"


# ── Fórmulas de variação ──

def _bp_var_formula(col: str, prev_col: str | None, bp_rows: list[int]) -> str:
    """
    Variação de um ou mais itens do BP: ``-(BP_atual - BP_anterior)``.

    Para o primeiro mês (prev_col=None): ``=-BP_atual``.
    """
    parts_cur = [_bp_ref(col, r) for r in bp_rows]
    cur_expr = "+".join(parts_cur) if len(parts_cur) > 1 else parts_cur[0]

    if prev_col is None:
        return f"=-({cur_expr})"

    parts_prev = [_bp_ref(prev_col, r) for r in bp_rows]
    prev_expr = "+".join(parts_prev) if len(parts_prev) > 1 else parts_prev[0]

    return f"=-({cur_expr}-({prev_expr}))"


def _check_formula(col: str) -> str:
    """Fórmula de validação: Variação == Final - Inicial."""
    return (
        f'=IF(ABS({col}27-({col}29-{col}28))<0.02,'
        f'"✓","✗ Diff: "&TEXT({col}27-({col}29-{col}28),"#,##0.00"))'
    )


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class DFCBuilder:
    """Monta e gerencia a aba DFC (método indireto) no Google Sheets."""

    def __init__(self, sheets_client: SheetsClient) -> None:
        self._client = sheets_client

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def build_dfc(self, periods: list[str]) -> None:
        """
        Monta (ou remonta) a aba DFC para os períodos informados.

        Args:
            periods: Lista de períodos ordenados.
        """
        if not periods:
            raise ValueError("Lista de períodos não pode ser vazia.")

        n = len(periods)
        total_col_idx = n + 2
        first_month_col = _col_letter(2)
        last_month_col = _col_letter(n + 1)
        total_col = _col_letter(total_col_idx)

        # 1) Aba
        self._client.ensure_sheet_exists(SHEET_NAME)
        self._client.clear_sheet(SHEET_NAME, preserve_headers=False)

        # 2) Headers
        headers = [""] + [_period_to_header(p) for p in periods] + ["Total Ano"]
        self._client.update_range(SHEET_NAME, "A1", [headers])

        # 3) Labels
        labels = [[line.label] for line in _DFC_STRUCTURE]
        self._client.update_range(
            SHEET_NAME, f"A2:A{_LAST_DATA_ROW}", labels
        )

        # 4) Fórmulas
        formulas: list[dict[str, Any]] = []

        for idx, line in enumerate(_DFC_STRUCTURE):
            row = idx + 2

            if line.line_type in ("blank", "label"):
                continue

            # ── Colunas de meses ──
            for pi, _period in enumerate(periods):
                col_idx = pi + 2
                col = _col_letter(col_idx)
                prev_col = _col_letter(col_idx - 1) if pi > 0 else None

                f = self._formula_for_line(line, col, prev_col, first_month_col)
                if f is not None:
                    formulas.append({"row": row, "col": col_idx, "formula": f})

            # ── Coluna Total Ano ──
            f_total = self._total_formula(line, row, first_month_col, last_month_col, total_col)
            if f_total is not None:
                formulas.append({"row": row, "col": total_col_idx, "formula": f_total})

        self._client.batch_write_formulas(SHEET_NAME, formulas)
        logger.info(
            "DFC montada: %d fórmulas para %d períodos.", len(formulas), n,
        )

        # 5) Formatação
        self._apply_formatting(total_col_idx)

    def get_dfc_data(self) -> pd.DataFrame:
        """Retorna os dados calculados da DFC."""
        return self._client.read_sheet(SHEET_NAME)

    # ------------------------------------------------------------------
    # Geração de fórmulas
    # ------------------------------------------------------------------

    @staticmethod
    def _formula_for_line(
        line: _DFCLine, col: str, prev_col: str | None, first_month_col: str,
    ) -> str | None:
        lt = line.line_type

        if lt == "dre_ref":
            return f"={_dre_ref(col, line.dre_row)}"

        if lt == "dre_ref_neg":
            return f"=-{_dre_ref(col, line.dre_row)}"

        if lt in ("bp_var", "bp_var_multi"):
            return _bp_var_formula(col, prev_col, line.bp_rows)

        if lt == "subtotal":
            return _subtotal_formula(col, line.children_rows)

        if lt == "formula":
            return line.formula_tpl.replace("{c}", col)

        if lt == "bp_ref_cur":
            return f"={_bp_ref(col, line.bp_rows[0])}"

        if lt == "bp_ref_prev":
            if prev_col is None:
                return "=0"
            return f"={_bp_ref(prev_col, line.bp_rows[0])}"

        if lt == "check":
            return _check_formula(col)

        return None  # pragma: no cover

    @staticmethod
    def _total_formula(
        line: _DFCLine, row: int,
        first_month_col: str, last_month_col: str, total_col: str,
    ) -> str | None:
        lt = line.line_type

        if lt in ("bp_ref_cur", "bp_ref_prev"):
            # Saldo Inicial Total = saldo inicial do primeiro mês (=0)
            # Saldo Final Total = saldo final do último mês
            if lt == "bp_ref_prev":
                return "=0"
            return f"={_bp_ref(last_month_col, line.bp_rows[0])}"

        if lt == "check":
            return _check_formula(total_col)

        # Para tudo o mais: soma dos meses
        return f"=SUM({first_month_col}{row}:{last_month_col}{row})"

    # ------------------------------------------------------------------
    # Formatação
    # ------------------------------------------------------------------

    def _apply_formatting(self, last_col_idx: int) -> None:
        last_col = _col_letter(last_col_idx)

        self._client.format_range(
            SHEET_NAME, f"A1:{last_col}1",
            {"textFormat": {"bold": True}},
        )

        for idx, line in enumerate(_DFC_STRUCTURE):
            row = idx + 2
            if line.bold:
                self._client.format_range(
                    SHEET_NAME, f"A{row}:{last_col}{row}",
                    {"textFormat": {"bold": True}},
                )

        value_range = f"B2:{last_col}{_LAST_DATA_ROW}"
        self._client.format_range(
            SHEET_NAME, value_range,
            {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}},
        )

        logger.info("Formatação da DFC aplicada.")

    # ------------------------------------------------------------------
    # Introspecção
    # ------------------------------------------------------------------

    @staticmethod
    def get_structure() -> list[dict]:
        return [
            {
                "row": i + 2,
                "label": line.label,
                "type": line.line_type,
                "bp_rows": line.bp_rows,
                "dre_row": line.dre_row,
            }
            for i, line in enumerate(_DFC_STRUCTURE)
        ]


def _subtotal_formula(col: str, children_rows: list[int]) -> str:
    return "=" + "+".join(f"{col}{r}" for r in children_rows)
