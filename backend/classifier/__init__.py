"""
Pacote classificador de contas contábeis (DEPARA).

Mapeia cada conta de último nível do balancete para uma classificação
usada na DRE ou Balanço Patrimonial.

Exporta:
- DEFAULT_MAPPING: mapeamento padrão por prefixo nível 4
- SPECIFIC_ACCOUNT_MAPPING: refinamentos por conta exata
- CLASSIFICATION_TO_DF: classificação → grupo DF (DRE/BP)
- DEPARAManager: classe principal de gestão do DEPARA
- classify_new_accounts: classificação via IA (Gemini)
"""

from backend.classifier.ai_classifier import classify_new_accounts
from backend.classifier.default_mapping import (
    CLASSIFICATION_TO_DF,
    DEFAULT_MAPPING,
    SPECIFIC_ACCOUNT_MAPPING,
)
from backend.classifier.depara_manager import DEPARAManager

__all__ = [
    "DEFAULT_MAPPING",
    "SPECIFIC_ACCOUNT_MAPPING",
    "CLASSIFICATION_TO_DF",
    "DEPARAManager",
    "classify_new_accounts",
]
