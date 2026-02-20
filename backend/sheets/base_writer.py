"""
Escritor da aba "Base Balancete" no Google Sheets.

Responsável por manter a tabela principal com todas as linhas do balancete
(macro e último nível), todos os meses, em formato longo.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from backend.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SHEET_NAME = "Base Balancete"

HEADERS = [
    "codigo_conta",
    "titulo_conta",
    "nivel",
    "tipo",
    "grupo",
    "periodo",
    "saldo_original",
    "indicador_dc",
    "saldo_sinalizado",
    "classificacao_depara",
]

# Índice 1-based da coluna classificacao_depara (coluna J)
_COL_CLASSIFICACAO = HEADERS.index("classificacao_depara") + 1
# Índice 1-based da coluna periodo (coluna F)
_COL_PERIODO = HEADERS.index("periodo") + 1


class BaseWriter:
    """Escreve e gerencia dados na aba 'Base Balancete'."""

    def __init__(self, sheets_client: SheetsClient) -> None:
        self._client = sheets_client
        self._client.ensure_sheet_exists(SHEET_NAME, headers=HEADERS)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_rows(df: pd.DataFrame) -> list[list[Any]]:
        """Converte DataFrame para lista de listas na ordem dos HEADERS."""
        rows: list[list[Any]] = []
        for _, r in df.iterrows():
            rows.append(
                [
                    str(r.get("codigo_conta", "")),
                    str(r.get("titulo_conta", "")),
                    int(r["nivel"]) if pd.notna(r.get("nivel")) else "",
                    str(r.get("tipo", "")),
                    str(r.get("grupo", "")),
                    str(r.get("periodo", "")),
                    float(r["saldo_original"])
                    if pd.notna(r.get("saldo_original"))
                    else "",
                    str(r.get("indicador_dc", "")),
                    float(r["saldo_sinalizado"])
                    if pd.notna(r.get("saldo_sinalizado"))
                    else "",
                    str(r.get("classificacao_depara", "")),
                ]
            )
        return rows

    @staticmethod
    def _prepare_df(header: dict, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara o DataFrame do parser para o formato da aba.

        Mapeia colunas do parser (`saldo_atual` → `saldo_sinalizado`, etc.)
        e adiciona `classificacao_depara` vazia para Macros.
        """
        out = pd.DataFrame()
        out["codigo_conta"] = df["codigo_conta"]
        out["titulo_conta"] = df["titulo_conta"]
        out["nivel"] = df["nivel"]
        out["tipo"] = df["tipo"]
        out["grupo"] = df["grupo"]
        out["periodo"] = df.get("periodo", header.get("mes_referencia", ""))
        out["saldo_original"] = df["saldo_atual"].abs()
        out["indicador_dc"] = df["indicador_dc"]
        out["saldo_sinalizado"] = df["saldo_atual"]

        # classificacao_depara: preservar se existir, senão vazio
        if "classificacao_depara" in df.columns:
            out["classificacao_depara"] = df["classificacao_depara"].fillna("")
        else:
            out["classificacao_depara"] = ""

        # Ordenação: periodo ASC, codigo_conta ASC
        out = out.sort_values(
            ["periodo", "codigo_conta"], ascending=True
        ).reset_index(drop=True)

        return out

    def _read_existing(self) -> pd.DataFrame:
        """Lê os dados existentes da aba, retornando um DataFrame."""
        df = self._client.read_sheet(SHEET_NAME)
        if df.empty:
            return pd.DataFrame(columns=HEADERS)
        return df

    def _rewrite_all(self, df: pd.DataFrame) -> None:
        """Limpa a aba (preservando headers) e reescreve todo o DataFrame."""
        self._client.clear_sheet(SHEET_NAME, preserve_headers=True)
        if df.empty:
            return
        # Ordenação global
        df = df.sort_values(
            ["periodo", "codigo_conta"], ascending=True
        ).reset_index(drop=True)
        rows = self._df_to_rows(df)
        self._client.append_rows(SHEET_NAME, rows)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def write_month(self, header: dict, df: pd.DataFrame) -> dict:
        """
        Escreve dados de um mês na Base Balancete.

        Se o período já existe, SUBSTITUI (permite re-processamento).
        Caso contrário, ADICIONA ao final.

        Args:
            header: Dicionário do parser contendo ao menos ``mes_referencia``.
            df: DataFrame de saída do parser com todas as colunas.

        Returns:
            Dict ``{"rows_written": N, "replaced": bool, "periodo": "YYYY-MM"}``.
        """
        periodo = header["mes_referencia"]
        new_data = self._prepare_df(header, df)
        existing = self._read_existing()
        replaced = False

        if not existing.empty and "periodo" in existing.columns:
            mask = existing["periodo"].astype(str) == periodo
            if mask.any():
                # Remover dados do período antigo e concatenar os novos
                existing = existing[~mask]
                replaced = True

        frames = [f for f in (existing, new_data) if not f.empty]
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=HEADERS)
        self._rewrite_all(combined)

        rows_written = len(new_data)
        logger.info(
            "Base Balancete — período %s: %d linhas escritas (%s).",
            periodo,
            rows_written,
            "substituídas" if replaced else "adicionadas",
        )
        return {
            "rows_written": rows_written,
            "replaced": replaced,
            "periodo": periodo,
        }

    def get_existing_periods(self) -> list[str]:
        """Retorna lista de períodos existentes na base, ordenados."""
        df = self._read_existing()
        if df.empty or "periodo" not in df.columns:
            return []
        periodos = sorted(df["periodo"].astype(str).unique().tolist())
        return periodos

    def get_data_for_period(self, periodo: str) -> pd.DataFrame:
        """Retorna dados de um período específico."""
        df = self._read_existing()
        if df.empty or "periodo" not in df.columns:
            return pd.DataFrame(columns=HEADERS)
        return df[df["periodo"].astype(str) == periodo].reset_index(drop=True)

    def get_all_data(self) -> pd.DataFrame:
        """Retorna toda a base."""
        return self._read_existing()

    def update_classifications(
        self, codigo_conta: str, nova_classificacao: str
    ) -> int:
        """
        Atualiza ``classificacao_depara`` para todas as linhas com o
        ``codigo_conta`` dado.

        Returns:
            Número de linhas atualizadas.
        """
        df = self._read_existing()
        if df.empty:
            return 0

        mask = df["codigo_conta"].astype(str) == str(codigo_conta)
        count = int(mask.sum())

        if count == 0:
            logger.warning(
                "Conta '%s' não encontrada na Base Balancete.", codigo_conta
            )
            return 0

        df.loc[mask, "classificacao_depara"] = nova_classificacao
        self._rewrite_all(df)

        logger.info(
            "Classificação de '%s' atualizada para '%s' (%d linhas).",
            codigo_conta,
            nova_classificacao,
            count,
        )
        return count
