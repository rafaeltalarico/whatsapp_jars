import pytest
from conftest import CPF_VALIDO, Conversa

from jars.fluxo import NoEncaminhar, NoMenu, NoPergunta
from jars.motor import NO_IDENTIFICACAO, Anexo, MensagemRecebida, Status

DOCUMENTO = MensagemRecebida(anexo=Anexo(tipo="document", id_midia="m1", nome_arquivo="laudo.pdf"))


# ----------------------------------------------------------------------
# Identificação
# ----------------------------------------------------------------------
def test_primeira_mensagem_recebe_boas_vindas(conversa):
    conversa.diz("Oi, boa tarde")
    assert "Seja bem-vindo(a)" in conversa.texto
    assert "*_J. Alencar e R. Sousa Advogadas Associadas_*" in conversa.texto
    assert conversa.sessao.no_atual == NO_IDENTIFICACAO


def test_nome_e_cpf_na_mesma_mensagem_levam_ao_menu(conversa):
    conversa.identificada()
    assert conversa.texto.startswith("Obrigada pelas informações! 😊")
    assert "qual assunto traz você até nós?" in conversa.texto
    assert conversa.sessao.nome == "Maria da Silva"
    assert conversa.sessao.cpf == CPF_VALIDO
    assert conversa.sessao.no_atual == "menu_principal"


def test_nome_e_cpf_em_mensagens_separadas(conversa):
    conversa.diz("Oi")
    conversa.diz("Maria da Silva")
    assert "CPF" in conversa.texto
    assert conversa.sessao.no_atual == NO_IDENTIFICACAO
    conversa.diz(CPF_VALIDO)
    assert conversa.sessao.no_atual == "menu_principal"


def test_cpf_antes_do_nome(conversa):
    conversa.diz("Oi")
    conversa.diz(CPF_VALIDO)
    assert "nome completo" in conversa.texto
    conversa.diz("Maria da Silva")
    assert conversa.sessao.no_atual == "menu_principal"


def test_cpf_invalido_pede_novamente(conversa):
    conversa.diz("Oi")
    conversa.diz("Maria da Silva 52998224724")
    assert "não parece válido" in conversa.texto
    assert conversa.sessao.cpf is None
    assert conversa.sessao.nome == "Maria da Silva"
    conversa.diz(CPF_VALIDO)
    assert conversa.sessao.no_atual == "menu_principal"


def test_mensagem_sem_dados_pede_nome_e_cpf(conversa):
    conversa.diz("Oi")
    conversa.diz("quero falar com a doutora")
    assert "nome completo" in conversa.texto
    assert "CPF" in conversa.texto


# ----------------------------------------------------------------------
# Menus e navegação
# ----------------------------------------------------------------------
def test_opcao_invalida_repete_o_menu(conversa):
    conversa.identificada()
    conversa.diz("9")
    assert "Não entendi a sua resposta" in conversa.texto
    assert "1️⃣ *PASEP*" in conversa.texto
    assert conversa.sessao.no_atual == "menu_principal"


def test_aceita_numero_em_emoji(conversa):
    conversa.identificada()
    conversa.diz("4️⃣")
    assert conversa.sessao.no_atual == "bancario"


def test_previdenciario_aceita_opcoes_de_dois_digitos(conversa):
    conversa.identificada()
    conversa.diz("5")
    conversa.diz("11")
    assert conversa.sessao.no_atual == "previdenciario_relato"
    assert conversa.sessao.respostas["previdenciario"] == "Outro assunto"


def test_zero_volta_ao_menu_anterior(conversa):
    conversa.identificada()
    conversa.diz("3")
    conversa.diz("2")
    assert conversa.sessao.no_atual == "saude_plano"
    conversa.diz("0")
    assert conversa.sessao.no_atual == "saude"
    assert "*3. DIREITO DA SAÚDE*" in conversa.texto
    conversa.diz("0")
    assert conversa.sessao.no_atual == "menu_principal"


def test_zero_no_menu_principal_permanece_nele(conversa):
    conversa.identificada()
    conversa.diz("0")
    assert conversa.sessao.no_atual == "menu_principal"


def test_zero_zero_retorna_ao_inicio(conversa):
    conversa.identificada()
    conversa.diz("4")
    conversa.diz("5")
    conversa.diz("1")
    assert conversa.sessao.no_atual == "bancario_golpe_banco"
    conversa.diz("00")
    assert conversa.sessao.no_atual == "menu_principal"
    assert conversa.sessao.pilha == []


def test_cerquilha_finaliza_com_alerta_de_golpe(conversa):
    conversa.identificada()
    conversa.diz("2")
    conversa.diz("#")
    assert conversa.sessao.status is Status.ENCERRADO
    assert "golpe do falso advogado" in conversa.texto
    assert conversa.texto.count("*_J. Alencar e R. Sousa Advogadas Associadas_*") == 2


def test_cerquilha_funciona_durante_identificacao(conversa):
    conversa.diz("Oi")
    conversa.diz("#")
    assert conversa.sessao.status is Status.ENCERRADO


def test_nova_mensagem_apos_finalizar_recomeca(conversa):
    conversa.identificada()
    conversa.diz("#")
    conversa.diz("Oi de novo")
    assert "Seja bem-vindo(a)" in conversa.texto
    assert conversa.sessao.status is Status.BOT
    assert conversa.sessao.nome is None


def test_documento_enviado_em_um_menu_e_guardado(conversa):
    conversa.identificada()
    conversa.diz("3")
    conversa.diz("1")
    conversa.envia(DOCUMENTO)
    assert "Documento recebido" in conversa.texto
    assert conversa.sessao.no_atual == "saude_sus"
    assert len(conversa.sessao.anexos) == 1


# ----------------------------------------------------------------------
# Encaminhamento para a equipe
# ----------------------------------------------------------------------
def test_fluxo_pasep_completo_gera_resumo(conversa):
    conversa.identificada()
    conversa.diz("1")
    conversa.diz("2015")
    conversa.diz("1")
    resultado = conversa.envia(DOCUMENTO)
    assert conversa.sessao.status is Status.AGUARDANDO_HUMANO
    assert "um de nossos advogados dará continuidade" in conversa.texto
    resumo = resultado.encaminhamento
    assert resumo is not None
    assert "Maria da Silva" in resumo
    assert "529.982.247-25" in resumo
    assert "*Assunto:* PASEP" in resumo
    assert "*Ano da aposentadoria:* 2015" in resumo
    assert "*Documentos recebidos:* 1" in resumo


def test_resumo_ignora_ramos_abandonados(conversa):
    conversa.identificada()
    conversa.diz("3")
    conversa.diz("0")
    conversa.diz("2")
    resultado = conversa.diz("Comprei um produto com defeito")
    assert "*Assunto:* DIREITO CIVIL" in resultado.encaminhamento
    assert "SAÚDE" not in resultado.encaminhamento


def test_andamento_processual_encaminha_direto(conversa):
    conversa.identificada()
    resultado = conversa.diz("7")
    assert "um de nossos advogados entrará em contato" in conversa.texto
    assert conversa.sessao.status is Status.AGUARDANDO_HUMANO
    assert "[CONSULTA DE ANDAMENTO PROCESSUAL]" in resultado.encaminhamento


def test_aguardando_humano_o_robo_fica_em_silencio(conversa):
    conversa.identificada()
    conversa.diz("2")
    conversa.diz("Tenho um problema com o meu vizinho")
    assert conversa.diz("Alguém aí?").respostas == []
    assert conversa.envia(DOCUMENTO).respostas == []
    assert len(conversa.sessao.anexos) == 1


def test_aguardando_humano_cliente_pode_voltar_ao_inicio(conversa):
    conversa.identificada()
    conversa.diz("7")
    conversa.diz("00")
    assert conversa.sessao.status is Status.BOT
    assert conversa.sessao.no_atual == "menu_principal"


# ----------------------------------------------------------------------
# Atendimento humano
# ----------------------------------------------------------------------
def test_advogada_assume_e_robo_nao_responde_nem_a_comandos(conversa, motor):
    conversa.identificada()
    motor.humano_assumiu(conversa.sessao)
    for texto in ["Bom dia, doutora", "1", "0", "00", "#"]:
        assert conversa.diz(texto).respostas == []
    assert conversa.sessao.status is Status.HUMANO


def test_advogada_assume_no_meio_da_triagem(conversa, motor):
    conversa.identificada()
    conversa.diz("4")
    motor.humano_assumiu(conversa.sessao)
    assert conversa.diz("1").respostas == []
    assert conversa.sessao.no_atual == "bancario"


def test_finalizar_atendimento_humano_devolve_ao_robo(conversa, motor):
    conversa.identificada()
    motor.humano_assumiu(conversa.sessao)
    motor.finalizar_atendimento_humano(conversa.sessao)
    conversa.diz("Oi, voltei")
    assert "Seja bem-vindo(a)" in conversa.texto


# ----------------------------------------------------------------------
# Expiração
# ----------------------------------------------------------------------
def test_conversa_parada_com_o_robo_expira(conversa, relogio, fluxo):
    conversa.identificada()
    conversa.diz("4")
    relogio.avancar(fluxo.sessao.expira_bot_horas + 1)
    conversa.diz("1")
    assert "Seja bem-vindo(a)" in conversa.texto


def test_conversa_com_o_robo_dentro_do_prazo_continua(conversa, relogio, fluxo):
    conversa.identificada()
    relogio.avancar(fluxo.sessao.expira_bot_horas - 1)
    conversa.diz("4")
    assert conversa.sessao.no_atual == "bancario"


def test_conversa_com_humano_volta_ao_robo_apos_inatividade(conversa, motor, relogio, fluxo):
    conversa.identificada()
    motor.humano_assumiu(conversa.sessao)
    relogio.avancar(fluxo.sessao.retorno_bot_apos_humano_horas - 1)
    assert conversa.diz("Obrigada!").respostas == []
    relogio.avancar(fluxo.sessao.retorno_bot_apos_humano_horas + 1)
    conversa.diz("Oi, tenho outra dúvida")
    assert "Seja bem-vindo(a)" in conversa.texto


def test_aguardando_humano_nao_expira(conversa, relogio):
    conversa.identificada()
    conversa.diz("7")
    relogio.avancar(24 * 7)
    assert conversa.diz("Ainda aguardando").respostas == []
    assert conversa.sessao.status is Status.AGUARDANDO_HUMANO


# ----------------------------------------------------------------------
# Cobertura de todos os caminhos do fluxo
# ----------------------------------------------------------------------
def _todos_os_caminhos(fluxo, no_id="menu_principal", caminho=()):
    """Gera todas as sequências de respostas do menu principal até um encaminhamento."""
    no = fluxo.nos[no_id]
    if isinstance(no, NoEncaminhar):
        yield caminho
    elif isinstance(no, NoMenu):
        for chave, opcao in no.opcoes.items():
            yield from _todos_os_caminhos(fluxo, opcao.destino, (*caminho, chave))
    elif isinstance(no, NoPergunta):
        yield from _todos_os_caminhos(fluxo, no.proximo, (*caminho, "Resposta de teste"))


def test_todos_os_caminhos_terminam_encaminhados_a_equipe(fluxo, motor):
    caminhos = list(_todos_os_caminhos(fluxo))
    assert len(caminhos) > 30
    for caminho in caminhos:
        conversa = Conversa(motor).identificada()
        resultado = None
        for resposta in caminho:
            assert conversa.sessao.status is Status.BOT, caminho
            resultado = conversa.diz(resposta)
            assert resultado.respostas, caminho
        assert conversa.sessao.status is Status.AGUARDANDO_HUMANO, caminho
        assert resultado is not None and resultado.encaminhamento, caminho


@pytest.mark.parametrize("no_id", ["saude", "bancario", "previdenciario", "suporte"])
def test_voltar_de_qualquer_submenu_leva_ao_menu_principal(fluxo, motor, no_id):
    chave = next(k for k, op in fluxo.nos["menu_principal"].opcoes.items() if op.destino == no_id)
    conversa = Conversa(motor).identificada()
    conversa.diz(chave)
    assert conversa.sessao.no_atual == no_id
    conversa.diz("0")
    assert conversa.sessao.no_atual == "menu_principal"
