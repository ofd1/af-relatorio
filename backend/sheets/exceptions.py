"""Exceções customizadas para o módulo Google Sheets."""


class SheetsError(Exception):
    """Exceção base para erros do SheetsClient."""


class SheetNotFoundError(SheetsError):
    """Aba não encontrada na planilha."""

    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name
        super().__init__(f"Aba '{sheet_name}' não encontrada na planilha.")


class AuthenticationError(SheetsError):
    """Falha na autenticação com a Google API."""

    def __init__(self, detail: str = ""):
        msg = "Falha na autenticação com a Google API."
        if detail:
            msg += f" Detalhe: {detail}"
        super().__init__(msg)


class QuotaExceededError(SheetsError):
    """Quota da Google API excedida (HTTP 429)."""

    def __init__(self):
        super().__init__(
            "Quota da Google Sheets API excedida. Tente novamente em alguns instantes."
        )
