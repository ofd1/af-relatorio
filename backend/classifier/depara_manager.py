"""
Gerenciador do DEPARA de contas contábeis.

Coordena a leitura/escrita do mapeamento no Google Sheets, aplica
classificações automáticas usando os dicionários de ``default_mapping``
e marca contas não-mapeadas para revisão por IA.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import pandas as pd

from backend.classifier.default_mapping import (
    CLASSIFICATION_TO_DF,
    DEFAULT_MAPPING,
    SPECIFIC_ACCOUNT_MAPPING,
)

logger = logging.getLogger(__name__)


class SheetsError(Exception):
    """Erro ao interagir com o Google Sheets."""


class DEPARAManager:
    """Gerencia o DEPARA (de-para) de contas contábeis.

    O DEPARA mapeia cada conta analítica (último nível) do balancete para
    uma classificação usada na DRE ou Balanço Patrimonial.

    Args:
        sheets_client: Client autenticado do Google Sheets com métodos
            ``read_sheet(range) -> list[list]`` e
            ``append_rows(range, values)`` e
            ``update_cell(range, value)``.
    """

    # Colunas esperadas no DEPARA do Sheets
    _DEPARA_COLUMNS = [
        "codigo_conta",
        "titulo_original",
        "classificacao",
        "grupo_df",
        "status",
    ]

    def __init__(self, sheets_client: Any) -> None:
        self._sheets = sheets_client
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def get_full_depara(self) -> pd.DataFrame:
        """Lê o DEPARA atual da planilha do Google Sheets.

        Returns:
            DataFrame com colunas: codigo_conta, titulo_original,
            classificacao, grupo_df, status.

        Raises:
            SheetsError: Se a leitura da planilha falhar.
        """
        try:
            raw = self._sheets.read_sheet("DEPARA!A:E")
        except Exception as exc:
            logger.error("Falha ao ler DEPARA do Sheets: %s", exc)
            raise SheetsError(f"Falha ao ler DEPARA: {exc}") from exc

        if not raw or len(raw) < 2:
            logger.warning("DEPARA vazio ou sem dados no Sheets.")
            return pd.DataFrame(columns=self._DEPARA_COLUMNS)

        header = raw[0]
        data = raw[1:]
        df = pd.DataFrame(data, columns=header)

        # Garante que colunas esperadas existem
        for col in self._DEPARA_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        logger.info("DEPARA carregado: %d contas.", len(df))
        return df[self._DEPARA_COLUMNS]

    # ------------------------------------------------------------------
    # Classificação
    # ------------------------------------------------------------------

    def classify_accounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classifica contas de último nível do balancete.

        Prioridade de busca:
            1. DEPARA existente no Sheets (por ``codigo_conta``)
            2. ``SPECIFIC_ACCOUNT_MAPPING`` (código exato da conta)
            3. ``DEFAULT_MAPPING`` (prefixo nível 4 da conta)
            4. Marca como ``"Pendente IA"`` para revisão futura

        Args:
            df: DataFrame do balancete parseado.  Deve conter ao menos as
                colunas ``codigo_conta``, ``titulo_conta`` e ``tipo``.

        Returns:
            Cópia do DataFrame com coluna ``classificacao_depara`` e
            ``grupo_df`` adicionadas.

        Raises:
            ValueError: Se colunas obrigatórias estiverem ausentes.
        """
        required = {"codigo_conta", "titulo_conta", "tipo"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}"
            )

        result = df.copy()
        result["classificacao_depara"] = ""
        result["grupo_df"] = ""

        # Filtra apenas contas de último nível
        mask_ultimo = result["tipo"] == "Último Nível"

        # Carrega DEPARA existente para lookup
        try:
            depara_df = self.get_full_depara()
            depara_map: dict[str, tuple[str, str]] = {}
            for _, row in depara_df.iterrows():
                codigo = str(row.get("codigo_conta", "")).strip()
                if codigo:
                    depara_map[codigo] = (
                        str(row.get("classificacao", "")),
                        str(row.get("grupo_df", "")),
                    )
        except SheetsError:
            logger.warning(
                "Não foi possível carregar DEPARA do Sheets; "
                "usando apenas mapeamentos padrão."
            )
            depara_map = {}

        new_accounts: list[dict[str, str]] = []

        for idx in result.index[mask_ultimo]:
            codigo = str(result.at[idx, "codigo_conta"]).strip()
            titulo = str(result.at[idx, "titulo_conta"]).strip()

            classificacao = ""
            grupo_df = ""

            # 1) DEPARA existente
            if codigo in depara_map:
                classificacao, grupo_df = depara_map[codigo]
                if classificacao:
                    result.at[idx, "classificacao_depara"] = classificacao
                    result.at[idx, "grupo_df"] = grupo_df
                    continue

            # 2) Mapeamento específico por conta exata
            if codigo in SPECIFIC_ACCOUNT_MAPPING:
                classificacao = SPECIFIC_ACCOUNT_MAPPING[codigo]
                grupo_df = CLASSIFICATION_TO_DF.get(classificacao, "")
                result.at[idx, "classificacao_depara"] = classificacao
                result.at[idx, "grupo_df"] = grupo_df
                new_accounts.append(
                    {
                        "codigo_conta": codigo,
                        "titulo_original": titulo,
                        "classificacao": classificacao,
                        "grupo_df": grupo_df,
                        "status": "Auto",
                    }
                )
                continue

            # 3) Mapeamento padrão por prefixo nível 4
            prefix = self._get_level4_prefix(codigo)
            if prefix and prefix in DEFAULT_MAPPING:
                classificacao = DEFAULT_MAPPING[prefix]
                grupo_df = CLASSIFICATION_TO_DF.get(classificacao, "")
                result.at[idx, "classificacao_depara"] = classificacao
                result.at[idx, "grupo_df"] = grupo_df
                new_accounts.append(
                    {
                        "codigo_conta": codigo,
                        "titulo_original": titulo,
                        "classificacao": classificacao,
                        "grupo_df": grupo_df,
                        "status": "Auto",
                    }
                )
                continue

            # 4) Não encontrado → Pendente IA
            result.at[idx, "classificacao_depara"] = "Pendente IA"
            result.at[idx, "grupo_df"] = ""
            new_accounts.append(
                {
                    "codigo_conta": codigo,
                    "titulo_original": titulo,
                    "classificacao": "Pendente IA",
                    "grupo_df": "",
                    "status": "Pendente",
                }
            )
            logger.info(
                "Conta sem mapeamento: %s (%s) → Pendente IA", codigo, titulo
            )

        # Persiste novas contas automaticamente
        if new_accounts:
            try:
                self.add_new_accounts(new_accounts)
            except SheetsError:
                logger.error(
                    "Falha ao persistir %d novas contas no Sheets.",
                    len(new_accounts),
                )

        classified = int(
            (result.loc[mask_ultimo, "classificacao_depara"] != "Pendente IA")
            .sum()
        )
        pending = int(
            (result.loc[mask_ultimo, "classificacao_depara"] == "Pendente IA")
            .sum()
        )
        logger.info(
            "Classificação concluída: %d classificadas, %d pendentes.",
            classified,
            pending,
        )

        return result

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def add_new_accounts(self, new_accounts: list[dict[str, str]]) -> None:
        """Adiciona novas contas ao DEPARA no Google Sheets.

        Args:
            new_accounts: Lista de dicts com chaves: ``codigo_conta``,
                ``titulo_original``, ``classificacao``, ``grupo_df``,
                ``status``.

        Raises:
            SheetsError: Se a escrita na planilha falhar.
        """
        if not new_accounts:
            return

        rows = [
            [
                acc["codigo_conta"],
                acc["titulo_original"],
                acc["classificacao"],
                acc["grupo_df"],
                acc["status"],
            ]
            for acc in new_accounts
        ]

        with self._lock:
            try:
                self._sheets.append_rows("DEPARA!A:E", rows)
                logger.info(
                    "%d novas contas adicionadas ao DEPARA.", len(rows)
                )
            except Exception as exc:
                logger.error("Falha ao escrever no Sheets: %s", exc)
                raise SheetsError(
                    f"Falha ao adicionar contas: {exc}"
                ) from exc

    def update_classification(
        self, codigo_conta: str, nova_classificacao: str
    ) -> dict[str, Any]:
        """Atualiza a classificação de uma conta no DEPARA.

        Args:
            codigo_conta: Código da conta a atualizar.
            nova_classificacao: Nova classificação (ex: ``"(-) PIS"``).

        Returns:
            Dict com:
                - ``propagated`` (bool): se a atualização foi persistida.
                - ``new_df_line_needed`` (bool): True se a classificação
                  não existe em ``CLASSIFICATION_TO_DF``.
                - ``classification`` (str): a classificação aplicada.
                - ``grupo_df`` (str): grupo DF correspondente.

        Raises:
            SheetsError: Se a leitura ou escrita na planilha falhar.
        """
        new_df_line_needed = nova_classificacao not in CLASSIFICATION_TO_DF
        grupo_df = CLASSIFICATION_TO_DF.get(nova_classificacao, "")

        with self._lock:
            try:
                depara_df = self.get_full_depara()
            except SheetsError:
                raise

            mask = depara_df["codigo_conta"] == codigo_conta

            if not mask.any():
                logger.warning(
                    "Conta %s não encontrada no DEPARA para atualização.",
                    codigo_conta,
                )
                return {
                    "propagated": False,
                    "new_df_line_needed": new_df_line_needed,
                    "classification": nova_classificacao,
                    "grupo_df": grupo_df,
                }

            # Encontra a linha no Sheets (offset +2: header + 1-indexed)
            row_idx = int(depara_df.index[mask][0]) + 2

            try:
                self._sheets.update_cell(
                    f"DEPARA!C{row_idx}", nova_classificacao
                )
                self._sheets.update_cell(f"DEPARA!D{row_idx}", grupo_df)
                self._sheets.update_cell(f"DEPARA!E{row_idx}", "Revisado")
            except Exception as exc:
                logger.error(
                    "Falha ao atualizar conta %s no Sheets: %s",
                    codigo_conta,
                    exc,
                )
                raise SheetsError(
                    f"Falha ao atualizar classificação: {exc}"
                ) from exc

        logger.info(
            "Conta %s reclassificada para '%s' (grupo_df='%s').",
            codigo_conta,
            nova_classificacao,
            grupo_df,
        )

        return {
            "propagated": True,
            "new_df_line_needed": new_df_line_needed,
            "classification": nova_classificacao,
            "grupo_df": grupo_df,
        }

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_pending_reviews(self) -> list[dict[str, str]]:
        """Retorna contas com status ``'Pendente'`` no DEPARA.

        Returns:
            Lista de dicts com chaves: ``codigo_conta``,
            ``titulo_original``, ``classificacao``, ``grupo_df``,
            ``status``.

        Raises:
            SheetsError: Se a leitura da planilha falhar.
        """
        depara_df = self.get_full_depara()
        pending = depara_df[depara_df["status"] == "Pendente"]
        records: list[dict[str, str]] = pending.to_dict(orient="records")
        logger.info("%d contas pendentes de revisão.", len(records))
        return records

    def get_all_classifications(self) -> list[str]:
        """Retorna lista de todas as classificações únicas existentes.

        Combina as classificações do ``CLASSIFICATION_TO_DF`` com as
        classificações já presentes no DEPARA do Sheets.

        Returns:
            Lista ordenada de strings de classificação.
        """
        classifications = set(CLASSIFICATION_TO_DF.keys())

        try:
            depara_df = self.get_full_depara()
            sheets_classif = (
                depara_df["classificacao"].dropna().unique().tolist()
            )
            classifications.update(
                c for c in sheets_classif if c and c != "Pendente IA"
            )
        except SheetsError:
            logger.warning(
                "Falha ao ler classificações do Sheets; "
                "retornando apenas as padrão."
            )

        return sorted(classifications)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_level4_prefix(codigo: str) -> str:
        """Extrai o prefixo de nível 4 do código da conta.

        Para contas com 5 partes (ex: ``"1.01.01.02.00004"``), retorna
        as 4 primeiras (``"1.01.01.02"``).  Para contas com exatamente
        4 partes, retorna o próprio código.  Para códigos com 3 partes
        ou menos (ex: impostos ``"4.98.03"``), retorna o código como
        está para permitir lookup direto no ``DEFAULT_MAPPING``.

        Args:
            codigo: Código completo da conta contábil.

        Returns:
            Prefixo de nível 4 ou string vazia se o código for inválido.
        """
        if not codigo:
            return ""
        parts = codigo.split(".")
        if len(parts) >= 4:
            return ".".join(parts[:4])
        # Contas com menos partes (ex: 4.98.03) → tenta lookup direto
        return codigo
