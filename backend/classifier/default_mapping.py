"""
Mapeamento padrão de contas contábeis para classificações DRE / BP.

Contém três dicionários:

- ``DEFAULT_MAPPING``:  código de nível 4 (sub-grupo) → classificação.
  Usado quando não há mapeamento específico por conta exata.

- ``SPECIFIC_ACCOUNT_MAPPING``:  código completo da conta → classificação.
  Refinamentos que sobrescrevem o mapeamento genérico de nível 4.

- ``CLASSIFICATION_TO_DF``:  classificação → demonstração financeira
  ("DRE" ou "BP").
"""

from __future__ import annotations

# ============================================================================
# Mapeamento: código nível 4 → classificação
# ============================================================================

DEFAULT_MAPPING: dict[str, str] = {
    # === BP - ATIVO ===
    "1.01.01.02": "(+) Caixa e Equivalentes de Caixa",    # BANCOS
    "1.01.01.03": "(+) Caixa e Equivalentes de Caixa",    # APLICACOES FINANCEIRAS
    "1.01.03.01": "(+) Clientes",                          # CLIENTES
    "1.01.03.02": "(+) Despesas Pagas Antecipadamente",    # ADIANTAMENTOS FORNECEDORES
    "1.01.03.04": "(+) Outros Créditos",                   # EMPRESTIMO RECEBIMENTO CLIENTE
    "1.01.03.05": "(+) Outros Créditos",                   # ADIANTAMENTOS COLABORADORES
    "1.01.03.06": "(+) Outros Créditos",                   # IMPOSTOS A RECUPERAR
    "1.01.03.08": "(+) Outros Créditos",                   # CREDITOS A RECUPERAR
    "1.01.03.10": "(+) Outros Créditos",                   # ANTECIPACAO DE LUCRO
    "1.02.02.07": "(+) Realizavel a Longo Prazo",          # INVESTIMENTO HINOVA SOLUCOES
    "1.02.02.18": "(+) Realizavel a Longo Prazo",          # HINOVA CONECTA
    "1.02.03.01": "(+) Bens em operação",                  # ATIVO IMOBILIZADO
    "1.02.03.03": "(-) Depreciação",                       # DEPRECIACAO ACUMULADA
    "1.02.04.01": "(+) Softwares, Projetos",               # INTANGIVEL
    "1.02.04.02": "(-) Depreciação Intangível",            # AMORTIZACAO ACUMULADA

    # === BP - PASSIVO ===
    "2.01.01.01": "(+) Fornecedores",                      # FORNECEDORES
    "2.01.01.02": "(+) Outras Obrigações",                 # ADIANTAMENTOS CLIENTES
    "2.01.01.03": "(+) Emprestimos e Financiamentos Curto Prazo",  # EMPRESTIMOS CP
    "2.01.01.05": "(+) Obrigações Tributárias",            # IMPOSTOS A RECOLHER
    "2.01.01.06": "(+) Obrigações Tributárias",            # IMPOSTOS RETIDOS
    "2.01.01.07": "(+) Obrigações Trabalhistas e Previdenciárias",  # ENCARGOS SOCIAIS
    "2.01.01.08": "(+) Obrigações Trabalhistas e Previdenciárias",  # OBRIG TRABALHISTAS
    "2.01.01.09": "(+) Obrigações Trabalhistas e Previdenciárias",  # PROVISOES TRAB
    "2.01.01.12": "(+) Dividendos a Distribuir",           # ANTECIPACAO LUCRO
    "2.01.01.99": "(+) Outras Obrigações",                 # PROVISOES CIRCULANTE
    "2.02.01.04": "(+) Emprestimos e Financiamentos Longo Prazo",  # EMPRESTIMOS LP
    "2.03.01.01": "(+) Capital Social",                    # CAPITAL SUBSCRITO
    "2.03.04.01": "(+) Lucros e Prejuízos Acumulados",    # OUTRAS CONTAS (PL)

    # === DRE - RECEITA ===
    "3.01.01.01": "(+) Receita de Serviços",               # RECEITA BRUTA
    "3.01.01.02": "(-) Deduções da Receita",               # DEDUCOES (genérico - será refinado)
    "3.01.02.01": "(+) Outras Receitas",                   # OUTRAS RECEITAS OPERACIONAIS
    "3.02.01.01": "(+) Receitas não Operacionais",         # RECEITAS NAO OPERACIONAIS

    # === DRE - DESPESA ===
    "4.01.01.01": "(-) Equipe",                            # DESPESAS COM PESSOAL
    "4.01.01.02": "(-) Equipe",                            # ENCARGOS SOBRE FOLHA
    "4.01.01.03": "(-) Equipe",                            # BENEFICIOS SOCIAIS
    "4.01.01.04": "(-) Despesas Gerais e Administrativas", # DESPESAS ADMINISTRATIVAS
    "4.01.01.05": "(-) Demais G&A",                        # DESPESAS GERAIS
    "4.01.01.06": "(-) Despesas Comerciais",               # DESPESAS COMERCIALIZACAO
    "4.01.01.07": "(-) Tributárias",                       # DESPESAS TRIBUTARIAS
    "4.01.01.08": "(-) D&A",                               # DEPRECIACAO E AMORTIZACAO
    "4.01.01.09": "(+) Resultado Financeiro",              # DESPESAS PATRIMONIAIS
    "4.01.02.01": "(-) Despesas não Operacionais",         # OUTRAS DESPESAS OPERAC
    "4.02.01.01": "(-) Despesas não Operacionais",         # DESPESAS NAO OPERACIONAIS

    # === DRE - CUSTOS ===
    "4.03.01.03": "(-) CSP",                               # CUSTOS SERVICOS PRESTADOS
    "4.03.01.04": "(-) Software",                          # CUSTOS SMS
    "4.03.01.09": "(-) Servidor/Cloud",                    # CUSTOS PROCESSAMENTO DADOS

    # === DRE - IMPOSTOS ===
    "4.98.03": "(-) CSLL",                                 # CSLL
    "4.98.04": "(-) IRPJ",                                 # IRPJ
}


# ============================================================================
# Refinamentos por conta exata (sobrescreve DEFAULT_MAPPING)
# ============================================================================

SPECIFIC_ACCOUNT_MAPPING: dict[str, str] = {
    "3.01.01.02.00004": "(-) PIS",
    "3.01.01.02.00005": "(-) COFINS",
    "3.01.01.02.00006": "(-) ISS",
    "3.01.01.02.00012": "(-) Descontos e Devoluções",
}


# ============================================================================
# Classificação → Demonstração Financeira (DRE ou BP)
# ============================================================================

CLASSIFICATION_TO_DF: dict[str, str] = {
    # DRE
    "(+) Receita de Serviços": "DRE",
    "(+) Outras Receitas": "DRE",
    "(-) Deduções da Receita": "DRE",
    "(-) ISS": "DRE",
    "(-) PIS": "DRE",
    "(-) COFINS": "DRE",
    "(-) Descontos e Devoluções": "DRE",
    "(-) CSP": "DRE",
    "(-) Equipe": "DRE",
    "(-) Servidor/Cloud": "DRE",
    "(-) Software": "DRE",
    "(-) Ocupação": "DRE",
    "(-) D&A": "DRE",
    "(-) Despesas Comerciais": "DRE",
    "(-) Equipe de Originação": "DRE",
    "(-) Despesas de Marketing": "DRE",
    "(-) Despesas Gerais e Administrativas": "DRE",
    "(-) Tributárias": "DRE",
    "(-) Demais G&A": "DRE",
    "(+) Receitas Financeiras": "DRE",
    "(-) Despesas Financeiras": "DRE",
    "(+) Resultado Financeiro": "DRE",
    "(+) Receitas não Operacionais": "DRE",
    "(-) Despesas não Operacionais": "DRE",
    "(-) IRPJ": "DRE",
    "(-) CSLL": "DRE",
    # BP
    "(+) Caixa e Equivalentes de Caixa": "BP",
    "(+) Clientes": "BP",
    "(+) Despesas Pagas Antecipadamente": "BP",
    "(+) Outros Créditos": "BP",
    "(+) Realizavel a Longo Prazo": "BP",
    "(+) Bens em operação": "BP",
    "(-) Depreciação": "BP",
    "(+) Softwares, Projetos": "BP",
    "(-) Depreciação Intangível": "BP",
    "(+) Emprestimos e Financiamentos Curto Prazo": "BP",
    "(+) Dividendos a Distribuir": "BP",
    "(+) Fornecedores": "BP",
    "(+) Obrigações Trabalhistas e Previdenciárias": "BP",
    "(+) Obrigações Tributárias": "BP",
    "(+) Outras Obrigações": "BP",
    "(+) Emprestimos e Financiamentos Longo Prazo": "BP",
    "(+) Capital Social": "BP",
    "(+) Reserva de Lucros": "BP",
    "(+) Lucros e Prejuízos Acumulados": "BP",
}
