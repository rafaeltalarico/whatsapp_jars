import copy

import pytest
import yaml

from jars.fluxo import CAMINHO_PADRAO, FluxoInvalido, NoMenu, numero_emoji, validar_fluxo


@pytest.fixture
def dados():
    with open(CAMINHO_PADRAO, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def test_fluxo_oficial_e_valido(fluxo):
    assert fluxo.inicio == "menu_principal"


def test_menu_principal_tem_as_oito_opcoes_na_ordem(fluxo):
    menu = fluxo.nos["menu_principal"]
    assert isinstance(menu, NoMenu)
    assert [op.rotulo for op in menu.opcoes.values()] == [
        "PASEP",
        "DIREITO CIVIL",
        "DIREITO DA SAÚDE",
        "DIREITO BANCÁRIO",
        "DIREITO PREVIDENCIÁRIO",
        "REQUERIMENTOS ADMINISTRATIVOS",
        "[CONSULTA DE ANDAMENTO PROCESSUAL]",
        "CANAL DE SUPORTE TÉCNICO E COMERCIAL",
    ]


def test_menu_principal_renderizado(fluxo):
    texto = fluxo.renderizar("menu_principal")
    assert "7️⃣ *[CONSULTA DE ANDAMENTO PROCESSUAL]*" in texto
    assert "8️⃣ *CANAL DE SUPORTE TÉCNICO E COMERCIAL*" in texto
    # No menu principal não há "voltar" nem "início".
    assert "digite *0*" not in texto
    assert "digite *#*" in texto


def test_submenus_tem_rodape_de_navegacao(fluxo):
    texto = fluxo.renderizar("bancario")
    assert "voltar ao menu anterior, digite *0*" in texto
    assert "retornar ao início, digite *00*" in texto
    assert "finalizar o atendimento, digite *#*" in texto


def test_nome_do_escritorio_em_negrito_e_italico(fluxo):
    destaque = "*_J. Alencar e R. Sousa Advogadas Associadas_*"
    assert destaque in fluxo.formatar(fluxo.mensagens.boas_vindas)
    assert fluxo.formatar(fluxo.mensagens.encerramento).count(destaque) == 2
    assert "{escritorio}" not in fluxo.formatar(fluxo.mensagens.encerramento)


def test_textos_usam_formatacao_do_whatsapp(fluxo):
    """O WhatsApp não entende **negrito** do Markdown."""
    textos = [fluxo.renderizar(no_id) for no_id in fluxo.nos]
    textos += [fluxo.formatar(t) for t in fluxo.mensagens.model_dump().values()]
    for texto in textos:
        assert "**" not in texto


@pytest.mark.parametrize(("chave", "emoji"), [("1", "1️⃣"), ("9", "9️⃣"), ("10", "🔟"), ("11", "1️⃣1️⃣")])
def test_numero_emoji(chave, emoji):
    assert numero_emoji(chave) == emoji


def test_rejeita_destino_inexistente(dados):
    dados["nos"]["menu_principal"]["opcoes"][1]["destino"] = "nao_existe"
    with pytest.raises(FluxoInvalido, match="nao_existe"):
        validar_fluxo(dados)


@pytest.mark.parametrize("chave", [0, "00"])
def test_rejeita_opcao_que_conflita_com_navegacao(dados, chave):
    opcao = copy.deepcopy(dados["nos"]["menu_principal"]["opcoes"][1])
    dados["nos"]["menu_principal"]["opcoes"][chave] = opcao
    with pytest.raises(FluxoInvalido):
        validar_fluxo(dados)


def test_rejeita_no_inalcancavel(dados):
    dados["nos"]["esquecido"] = {"tipo": "encaminhar"}
    with pytest.raises(FluxoInvalido, match="esquecido: nó inalcançável"):
        validar_fluxo(dados)


def test_rejeita_caminho_sem_saida(dados):
    dados["nos"]["civil"]["proximo"] = "civil"
    with pytest.raises(FluxoInvalido, match="civil: nenhum caminho"):
        validar_fluxo(dados)


def test_rejeita_campo_desconhecido(dados):
    dados["nos"]["civil"]["proxmo"] = "encaminhado"
    with pytest.raises(FluxoInvalido):
        validar_fluxo(dados)
