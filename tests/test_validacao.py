import pytest

from jars.validacao import (
    cpf_valido,
    extrair_identificacao,
    formatar_cpf,
    nome_valido,
    normalizar_entrada,
)


@pytest.mark.parametrize("cpf", ["52998224725", "529.982.247-25", "11144477735"])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize(
    "cpf", ["52998224724", "11111111111", "00000000000", "1234567890", "123456789012", ""]
)
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


def test_formatar_cpf():
    assert formatar_cpf("52998224725") == "529.982.247-25"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("1", "1"),
        (" 2 ", "2"),
        ("3.", "3"),
        ("4)", "4"),
        ("1️⃣", "1"),
        ("🔟", "10"),
        ("1️⃣1️⃣", "11"),
        ("#", "#"),
        ("00", "00"),
        ("0", "0"),
    ],
)
def test_normalizar_entrada(entrada, esperado):
    assert normalizar_entrada(entrada) == esperado


@pytest.mark.parametrize(
    "nome", ["Maria da Silva", "José Antônio", "Ana D'Ávila", "Ana Maria-Souza", "Pedro e Paulo"]
)
def test_nome_valido(nome):
    assert nome_valido(nome)


@pytest.mark.parametrize(
    "nome",
    [
        "Maria",
        "",
        "Oi",
        "Maria 123",
        "12 34",
        "quero falar com a doutora",
        "Boa tarde",
        "oi tudo bem",
    ],
)
def test_nome_invalido(nome):
    assert not nome_valido(nome)


@pytest.mark.parametrize(
    "mensagem",
    [
        "Maria da Silva 52998224725",
        "Maria da Silva\n529.982.247-25",
        "Nome completo: Maria da Silva\nCPF: 52998224725",
        "52998224725 - Maria da Silva",
    ],
)
def test_extrai_nome_e_cpf_juntos(mensagem):
    dados = extrair_identificacao(mensagem)
    assert dados.nome == "Maria da Silva"
    assert dados.cpf == "52998224725"
    assert not dados.cpf_encontrado_invalido


def test_extrai_so_o_nome():
    dados = extrair_identificacao("Maria da Silva")
    assert (dados.nome, dados.cpf) == ("Maria da Silva", None)


def test_extrai_so_o_cpf():
    dados = extrair_identificacao("CPF: 52998224725")
    assert (dados.nome, dados.cpf) == (None, "52998224725")


@pytest.mark.parametrize("mensagem", ["Maria da Silva 52998224724", "Maria da Silva 123456789"])
def test_sinaliza_cpf_invalido(mensagem):
    dados = extrair_identificacao(mensagem)
    assert dados.cpf is None
    assert dados.cpf_encontrado_invalido
    assert dados.nome == "Maria da Silva"
