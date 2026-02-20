"""
Testes para o módulo de parsers de balancetes Hinova.

Inclui:
- Testes unitários para value_converter (sempre rodam)
- Testes unitários para header_extractor (regex, sempre rodam)
- Testes de integração para balancete_parser (requerem arquivo de teste)
"""

from __future__ import annotations

import os
import math

import pytest

from backend.parsers.value_converter import apply_sign, parse_brazilian_value


# ============================================================================
# Testes de value_converter
# ============================================================================


class TestParseBrazilianValue:
    """Testes para parse_brazilian_value."""

    def test_valor_debito(self) -> None:
        """Valor com sufixo D retorna indicador 'D'."""
        value, ind = parse_brazilian_value("18.623.655,70D")
        assert value == pytest.approx(18623655.70)
        assert ind == "D"

    def test_valor_credito(self) -> None:
        """Valor com sufixo C retorna indicador 'C'."""
        value, ind = parse_brazilian_value("1.234.567,89C")
        assert value == pytest.approx(1234567.89)
        assert ind == "C"

    def test_valor_zero(self) -> None:
        """Valor '0,00' retorna zero sem indicador."""
        value, ind = parse_brazilian_value("0,00")
        assert value == pytest.approx(0.0)
        assert ind == ""

    def test_none(self) -> None:
        """None retorna zero sem indicador."""
        value, ind = parse_brazilian_value(None)
        assert value == pytest.approx(0.0)
        assert ind == ""

    def test_nan(self) -> None:
        """NaN retorna zero sem indicador."""
        value, ind = parse_brazilian_value(float("nan"))
        assert value == pytest.approx(0.0)
        assert ind == ""

    def test_string_vazia(self) -> None:
        """String vazia retorna zero sem indicador."""
        value, ind = parse_brazilian_value("")
        assert value == pytest.approx(0.0)
        assert ind == ""

    def test_valor_com_espacos(self) -> None:
        """Valor com espaços ao redor é tratado corretamente."""
        value, ind = parse_brazilian_value("  1.000,50D  ")
        assert value == pytest.approx(1000.50)
        assert ind == "D"

    def test_valor_simples_sem_milhar(self) -> None:
        """Valor sem separador de milhar."""
        value, ind = parse_brazilian_value("500,00D")
        assert value == pytest.approx(500.0)
        assert ind == "D"

    def test_valor_grande(self) -> None:
        """Valor com milhões."""
        value, ind = parse_brazilian_value("123.456.789,01C")
        assert value == pytest.approx(123456789.01)
        assert ind == "C"

    def test_valor_numerico_float(self) -> None:
        """Entrada numérica float é convertida diretamente."""
        value, ind = parse_brazilian_value(1234.56)  # type: ignore[arg-type]
        assert value == pytest.approx(1234.56)
        assert ind == ""


class TestApplySign:
    """Testes para apply_sign."""

    def test_ativo_debito(self) -> None:
        """Grupo 1 (ATIVO) + D = positivo."""
        assert apply_sign(1000.0, "D", 1) == pytest.approx(1000.0)

    def test_ativo_credito(self) -> None:
        """Grupo 1 (ATIVO) + C = negativo."""
        assert apply_sign(1000.0, "C", 1) == pytest.approx(-1000.0)

    def test_passivo_credito(self) -> None:
        """Grupo 2 (PASSIVO) + C = negativo."""
        assert apply_sign(500.0, "C", 2) == pytest.approx(-500.0)

    def test_passivo_debito(self) -> None:
        """Grupo 2 (PASSIVO) + D = positivo."""
        assert apply_sign(500.0, "D", 2) == pytest.approx(500.0)

    def test_receita_credito(self) -> None:
        """Grupo 3 (RECEITA) + C = negativo."""
        assert apply_sign(2000.0, "C", 3) == pytest.approx(-2000.0)

    def test_receita_debito(self) -> None:
        """Grupo 3 (RECEITA) + D = positivo."""
        assert apply_sign(2000.0, "D", 3) == pytest.approx(2000.0)

    def test_despesa_debito(self) -> None:
        """Grupo 4 (DESPESA) + D = positivo."""
        assert apply_sign(750.0, "D", 4) == pytest.approx(750.0)

    def test_despesa_credito(self) -> None:
        """Grupo 4 (DESPESA) + C = negativo."""
        assert apply_sign(750.0, "C", 4) == pytest.approx(-750.0)

    def test_indicador_vazio(self) -> None:
        """Indicador vazio retorna zero."""
        assert apply_sign(1000.0, "", 1) == pytest.approx(0.0)

    def test_grupo_invalido(self) -> None:
        """Grupo inválido levanta ValueError."""
        with pytest.raises(ValueError, match="Grupo contábil inválido"):
            apply_sign(100.0, "D", 9)


# ============================================================================
# Testes de header_extractor (unitários com regex)
# ============================================================================


class TestHeaderRegex:
    """Testes das regex usadas na extração de cabeçalho."""

    def test_periodo_regex(self) -> None:
        """Regex de período parseia corretamente."""
        import re

        texto = "Período: 01/01/2025 à 31/12/2025"
        match = re.search(
            r"Per[ií]odo:\s*(\d{2}/\d{2}/\d{4})\s*[àa]\s*(\d{2}/\d{2}/\d{4})",
            texto,
            re.IGNORECASE,
        )
        assert match is not None
        assert match.group(1) == "01/01/2025"
        assert match.group(2) == "31/12/2025"

    def test_cnpj_regex(self) -> None:
        """Regex de CNPJ parseia corretamente."""
        import re

        texto = "CNPJ: 23.313.200/0001-08"
        match = re.search(r"CNPJ:\s*([\d./-]+)", texto, re.IGNORECASE)
        assert match is not None
        assert match.group(1) == "23.313.200/0001-08"

    def test_emissao_regex(self) -> None:
        """Regex de emissão parseia corretamente."""
        import re

        texto = "Emissão: 04/02/2026 17:23:21"
        match = re.search(
            r"Emiss[ãa]o:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})",
            texto,
            re.IGNORECASE,
        )
        assert match is not None
        assert match.group(1) == "04/02/2026"
        assert match.group(2) == "17:23:21"


# ============================================================================
# Testes do nível e grupo de contas
# ============================================================================


class TestAccountHelpers:
    """Testes para helpers internos do parser."""

    def test_nivel_conta_simples(self) -> None:
        """Conta '1' tem nível 1."""
        from backend.parsers.balancete_parser import _determine_account_level

        assert _determine_account_level("1") == 1

    def test_nivel_conta_dois(self) -> None:
        """Conta '1.01' tem nível 2."""
        from backend.parsers.balancete_parser import _determine_account_level

        assert _determine_account_level("1.01") == 2

    def test_nivel_conta_tres(self) -> None:
        """Conta '1.01.01' tem nível 3."""
        from backend.parsers.balancete_parser import _determine_account_level

        assert _determine_account_level("1.01.01") == 3

    def test_nivel_conta_quatro(self) -> None:
        """Conta '4.03.01.03' tem nível 4."""
        from backend.parsers.balancete_parser import _determine_account_level

        assert _determine_account_level("4.03.01.03") == 4

    def test_nivel_conta_cinco(self) -> None:
        """Conta '1.01.01.02.00004' tem nível 5."""
        from backend.parsers.balancete_parser import _determine_account_level

        assert _determine_account_level("1.01.01.02.00004") == 5

    def test_grupo_ativo(self) -> None:
        """Conta começando com '1' é ATIVO."""
        from backend.parsers.balancete_parser import _get_account_group

        grupo, num = _get_account_group("1.01.01")
        assert grupo == "ATIVO"
        assert num == 1

    def test_grupo_passivo(self) -> None:
        """Conta começando com '2' é PASSIVO."""
        from backend.parsers.balancete_parser import _get_account_group

        grupo, num = _get_account_group("2.01")
        assert grupo == "PASSIVO"
        assert num == 2

    def test_grupo_receita(self) -> None:
        """Conta começando com '3' é RECEITA."""
        from backend.parsers.balancete_parser import _get_account_group

        grupo, num = _get_account_group("3.01.01")
        assert grupo == "RECEITA"
        assert num == 3

    def test_grupo_despesa(self) -> None:
        """Conta começando com '4' é DESPESA."""
        from backend.parsers.balancete_parser import _get_account_group

        grupo, num = _get_account_group("4.03")
        assert grupo == "DESPESA"
        assert num == 4

    def test_grupo_desconhecido(self) -> None:
        """Conta com primeiro dígito não mapeado levanta ValueError."""
        from backend.parsers.balancete_parser import _get_account_group

        with pytest.raises(ValueError, match="Grupo contábil desconhecido"):
            _get_account_group("9.01")


# ============================================================================
# Testes de integração (requerem arquivo de teste)
# ============================================================================


# Caminho para o arquivo de teste — ajustar conforme necessário
_TEST_FILE_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "balancete_teste.xls"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "balancete_teste.xlsx"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "balancete_teste.xls"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "balancete_teste.xlsx"),
]

def _find_test_file() -> str | None:
    """Localiza o primeiro arquivo de teste existente."""
    for path in _TEST_FILE_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            return abs_path
    return None


_test_file = _find_test_file()
_skip_integration = _test_file is None


@pytest.mark.skipif(_skip_integration, reason="Arquivo de teste de balancete não encontrado")
class TestBalanceteIntegration:
    """Testes de integração que dependem de um arquivo real de balancete."""

    def test_total_geral_not_in_dataframe(self) -> None:
        """'Total Geral' não deve estar no DataFrame."""
        from backend.parsers.balancete_parser import parse_balancete

        assert _test_file is not None
        _, df = parse_balancete(_test_file)
        assert not df["codigo_conta"].str.contains("Total Geral", case=False, na=False).any(), (
            "'Total Geral' encontrado no DataFrame — deveria ter sido excluído."
        )

    def test_conta_1_is_macro(self) -> None:
        """A conta '1' deve ter tipo 'Macro'."""
        from backend.parsers.balancete_parser import parse_balancete

        assert _test_file is not None
        _, df = parse_balancete(_test_file)
        conta_1 = df[df["codigo_conta"] == "1"]
        assert not conta_1.empty, "Conta '1' não encontrada no DataFrame."
        assert conta_1.iloc[0]["tipo"] == "Macro", (
            f"Conta '1' deveria ser 'Macro', mas é '{conta_1.iloc[0]['tipo']}'."
        )

    def test_conta_ultimo_nivel(self) -> None:
        """A conta '1.01.01.02.00004' deve ter tipo 'Último Nível'."""
        from backend.parsers.balancete_parser import parse_balancete

        assert _test_file is not None
        _, df = parse_balancete(_test_file)
        conta = df[df["codigo_conta"] == "1.01.01.02.00004"]
        assert not conta.empty, "Conta '1.01.01.02.00004' não encontrada no DataFrame."
        assert conta.iloc[0]["tipo"] == "Último Nível", (
            f"Conta '1.01.01.02.00004' deveria ser 'Último Nível', "
            f"mas é '{conta.iloc[0]['tipo']}'."
        )

    def test_saldo_ativo_soma(self) -> None:
        """O saldo da conta '1' deve ≈ saldo de '1.01' + '1.02'."""
        from backend.parsers.balancete_parser import parse_balancete

        assert _test_file is not None
        _, df = parse_balancete(_test_file)

        saldo_1 = df[df["codigo_conta"] == "1"]["saldo_atual"].values
        saldo_101 = df[df["codigo_conta"] == "1.01"]["saldo_atual"].values
        saldo_102 = df[df["codigo_conta"] == "1.02"]["saldo_atual"].values

        assert len(saldo_1) > 0, "Conta '1' não encontrada."
        assert len(saldo_101) > 0, "Conta '1.01' não encontrada."
        assert len(saldo_102) > 0, "Conta '1.02' não encontrada."

        soma = saldo_101[0] + saldo_102[0]
        assert saldo_1[0] == pytest.approx(soma, rel=1e-2), (
            f"Saldo da conta '1' ({saldo_1[0]}) não bate com "
            f"'1.01' ({saldo_101[0]}) + '1.02' ({saldo_102[0]}) = {soma}"
        )

    def test_header_extraction(self) -> None:
        """O header deve conter todos os campos obrigatórios."""
        from backend.parsers.balancete_parser import parse_balancete

        assert _test_file is not None
        header, _ = parse_balancete(_test_file)

        required_keys = [
            "empresa", "cnpj", "periodo_inicio", "periodo_fim",
            "emissao", "mes_referencia", "tipo",
        ]
        for key in required_keys:
            assert key in header, f"Campo '{key}' ausente no header."
            assert header[key], f"Campo '{key}' está vazio no header."


# ============================================================================
# Função test_parser() para uso direto
# ============================================================================


def test_parser() -> None:
    """Executa todos os testes em sequência para validação rápida.

    Pode ser chamada diretamente:
        python -c "from backend.parsers.tests.test_parser import test_parser; test_parser()"

    Ou via pytest:
        python -m pytest backend/parsers/tests/test_parser.py -v
    """
    print("=" * 60)
    print("TESTES DO PARSER DE BALANCETE HINOVA")
    print("=" * 60)

    # 1) Testes de value_converter
    print("\n--- Testes value_converter ---")

    val, ind = parse_brazilian_value("18.623.655,70D")
    assert val == pytest.approx(18623655.70), f"Esperado 18623655.70, obteve {val}"
    assert ind == "D", f"Esperado 'D', obteve '{ind}'"
    print(f"  ✓ parse_brazilian_value('18.623.655,70D') → ({val}, '{ind}')")

    val, ind = parse_brazilian_value("0,00")
    assert val == pytest.approx(0.0)
    assert ind == ""
    print(f"  ✓ parse_brazilian_value('0,00') → ({val}, '{ind}')")

    val, ind = parse_brazilian_value(None)
    assert val == pytest.approx(0.0)
    assert ind == ""
    print(f"  ✓ parse_brazilian_value(None) → ({val}, '{ind}')")

    assert apply_sign(1000.0, "D", 1) == pytest.approx(1000.0)
    print("  ✓ apply_sign(1000, 'D', 1) → 1000.0")

    assert apply_sign(1000.0, "C", 1) == pytest.approx(-1000.0)
    print("  ✓ apply_sign(1000, 'C', 1) → -1000.0")

    assert apply_sign(500.0, "C", 2) == pytest.approx(-500.0)
    print("  ✓ apply_sign(500, 'C', 2) → -500.0")

    # 2) Testes de integração (se arquivo disponível)
    test_file = _find_test_file()
    if test_file is None:
        print("\n--- Testes de integração ---")
        print("  ⚠ Nenhum arquivo de teste encontrado. Caminhos verificados:")
        for p in _TEST_FILE_PATHS:
            print(f"    - {os.path.abspath(p)}")
        print("  ⚠ Testes de integração ignorados.\n")
    else:
        from backend.parsers.balancete_parser import parse_balancete

        print(f"\n--- Testes de integração ({os.path.basename(test_file)}) ---")
        header, df = parse_balancete(test_file)

        # Total Geral não está no DF
        assert not df["codigo_conta"].str.contains("Total Geral", case=False, na=False).any()
        print("  ✓ 'Total Geral' não está no DataFrame")

        # Conta "1" é Macro
        conta_1 = df[df["codigo_conta"] == "1"]
        assert not conta_1.empty
        assert conta_1.iloc[0]["tipo"] == "Macro"
        print("  ✓ Conta '1' tem tipo 'Macro'")

        # Conta de último nível
        conta_un = df[df["codigo_conta"] == "1.01.01.02.00004"]
        if not conta_un.empty:
            assert conta_un.iloc[0]["tipo"] == "Último Nível"
            print("  ✓ Conta '1.01.01.02.00004' tem tipo 'Último Nível'")
        else:
            print("  ⚠ Conta '1.01.01.02.00004' não encontrada (ignorando)")

        # Saldo ATIVO
        saldo_1 = df[df["codigo_conta"] == "1"]["saldo_atual"].values
        saldo_101 = df[df["codigo_conta"] == "1.01"]["saldo_atual"].values
        saldo_102 = df[df["codigo_conta"] == "1.02"]["saldo_atual"].values
        if len(saldo_1) > 0 and len(saldo_101) > 0 and len(saldo_102) > 0:
            soma = saldo_101[0] + saldo_102[0]
            assert saldo_1[0] == pytest.approx(soma, rel=1e-2)
            print(f"  ✓ Saldo conta '1' ({saldo_1[0]:,.2f}) ≈ 1.01 + 1.02 ({soma:,.2f})")

        print(f"\n  Header: {header}")
        print(f"  DataFrame: {len(df)} linhas, {len(df.columns)} colunas")
        print(f"  Contas: {df['codigo_conta'].nunique()} únicas")

    print("\n" + "=" * 60)
    print("TODOS OS TESTES PASSARAM ✓")
    print("=" * 60)


if __name__ == "__main__":
    test_parser()
