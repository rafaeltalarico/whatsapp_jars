"""Motor de conversa: decide o que responder a cada mensagem do cliente.

O motor não sabe nada de WhatsApp nem de banco de dados. Ele recebe uma
``Sessao`` e uma ``MensagemRecebida``, atualiza a sessão e devolve as
mensagens que devem ser enviadas. Isso deixa toda a regra de negócio
testável sem rede.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from jars.fluxo import Fluxo, NoEncaminhar, NoMenu, NoPergunta
from jars.resumo import gerar_resumo
from jars.validacao import extrair_identificacao, normalizar_entrada

NO_IDENTIFICACAO = "_identificacao"
RESPOSTA_SO_ANEXO = "📎 (documento enviado)"


class Status(StrEnum):
    BOT = "bot"
    AGUARDANDO_HUMANO = "aguardando_humano"
    HUMANO = "humano"
    ENCERRADO = "encerrado"


@dataclass
class Anexo:
    tipo: str
    id_midia: str
    nome_arquivo: str | None = None
    legenda: str | None = None


@dataclass
class MensagemRecebida:
    texto: str = ""
    anexo: Anexo | None = None


@dataclass
class AnexoRecebido:
    anexo: Anexo
    no: str
    recebido_em: datetime


@dataclass
class Sessao:
    contato: str
    iniciada_em: datetime
    atualizada_em: datetime
    status: Status = Status.BOT
    no_atual: str = NO_IDENTIFICACAO
    pilha: list[str] = field(default_factory=list)
    boas_vindas_enviada: bool = False
    nome: str | None = None
    cpf: str | None = None
    respostas: dict[str, str] = field(default_factory=dict)
    anexos: list[AnexoRecebido] = field(default_factory=list)

    @property
    def caminho(self) -> list[str]:
        """Nós percorridos até o atual (desconsidera ramos abandonados com "voltar")."""
        return [*self.pilha, self.no_atual]


@dataclass
class Resultado:
    respostas: list[str]
    encaminhamento: str | None = None
    """Resumo da triagem para a equipe, quando a conversa foi encaminhada."""


Relogio = Callable[[], datetime]


def _agora_utc() -> datetime:
    return datetime.now(UTC)


class Motor:
    def __init__(self, fluxo: Fluxo, relogio: Relogio = _agora_utc) -> None:
        self.fluxo = fluxo
        self._relogio = relogio

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def nova_sessao(self, contato: str) -> Sessao:
        agora = self._relogio()
        return Sessao(contato=contato, iniciada_em=agora, atualizada_em=agora)

    def processar(self, sessao: Sessao, mensagem: MensagemRecebida) -> Resultado:
        agora = self._relogio()
        if self._expirou(sessao, agora):
            self._reiniciar(sessao, agora)
        sessao.atualizada_em = agora

        if sessao.status is Status.HUMANO:
            self._guardar_anexo(sessao, mensagem, agora)
            return Resultado([])

        if not sessao.boas_vindas_enviada:
            sessao.boas_vindas_enviada = True
            return Resultado([self.fluxo.formatar(self.fluxo.mensagens.boas_vindas)])

        comando = normalizar_entrada(mensagem.texto) if mensagem.anexo is None else ""
        comandos = self.fluxo.comandos

        if comando == comandos.finalizar:
            sessao.status = Status.ENCERRADO
            return Resultado([self.fluxo.formatar(self.fluxo.mensagens.encerramento)])

        if sessao.no_atual == NO_IDENTIFICACAO:
            return self._identificar(sessao, mensagem)

        if comando == comandos.inicio:
            sessao.status = Status.BOT
            sessao.pilha.clear()
            return self._mostrar(sessao, self.fluxo.inicio)

        if comando == comandos.voltar:
            sessao.status = Status.BOT
            anterior = sessao.pilha.pop() if sessao.pilha else self.fluxo.inicio
            return self._mostrar(sessao, anterior)

        if sessao.status is Status.AGUARDANDO_HUMANO:
            # A equipe já foi avisada: o robô apenas registra o que chegar.
            self._guardar_anexo(sessao, mensagem, agora)
            return Resultado([])

        no = self.fluxo.nos[sessao.no_atual]
        if isinstance(no, NoMenu):
            return self._responder_menu(sessao, no, mensagem, comando, agora)
        if isinstance(no, NoPergunta):
            return self._responder_pergunta(sessao, no, mensagem, agora)
        # Um nó de encaminhamento coloca a sessão em AGUARDANDO_HUMANO,
        # então não deveria receber respostas no estado BOT.
        return self._mostrar(sessao, sessao.no_atual)

    def humano_assumiu(self, sessao: Sessao) -> None:
        """Uma advogada respondeu ao cliente: o robô fica em silêncio."""
        sessao.status = Status.HUMANO
        sessao.atualizada_em = self._relogio()

    def finalizar_atendimento_humano(self, sessao: Sessao) -> None:
        """A equipe concluiu o atendimento; a próxima mensagem recomeça com o robô."""
        sessao.status = Status.ENCERRADO
        sessao.atualizada_em = self._relogio()

    # ------------------------------------------------------------------
    # Etapas
    # ------------------------------------------------------------------
    def _identificar(self, sessao: Sessao, mensagem: MensagemRecebida) -> Resultado:
        msgs = self.fluxo.mensagens
        dados = extrair_identificacao(mensagem.texto)
        sessao.nome = dados.nome or sessao.nome
        sessao.cpf = dados.cpf or sessao.cpf

        if dados.cpf_encontrado_invalido and not dados.cpf:
            respostas = [msgs.cpf_invalido]
            if not sessao.nome:
                respostas.append(msgs.pedir_nome)
            return Resultado(respostas)
        if not sessao.nome and not sessao.cpf:
            return Resultado([msgs.pedir_nome, msgs.pedir_cpf])
        if not sessao.nome:
            return Resultado([msgs.pedir_nome])
        if not sessao.cpf:
            return Resultado([msgs.pedir_cpf])

        sessao.no_atual = self.fluxo.inicio
        menu = self.fluxo.renderizar(self.fluxo.inicio)
        return Resultado([f"{msgs.identificacao_concluida}\n\n{menu}"])

    def _responder_menu(
        self,
        sessao: Sessao,
        no: NoMenu,
        mensagem: MensagemRecebida,
        escolha: str,
        agora: datetime,
    ) -> Resultado:
        if mensagem.anexo is not None:
            self._guardar_anexo(sessao, mensagem, agora)
            return Resultado([self.fluxo.mensagens.anexo_em_menu])

        opcao = no.opcoes.get(escolha)
        if opcao is None:
            invalida = self.fluxo.mensagens.opcao_invalida
            return Resultado([f"{invalida}\n\n{self.fluxo.renderizar(sessao.no_atual)}"])

        sessao.respostas[sessao.no_atual] = opcao.rotulo
        return self._avancar(sessao, opcao.destino)

    def _responder_pergunta(
        self,
        sessao: Sessao,
        no: NoPergunta,
        mensagem: MensagemRecebida,
        agora: datetime,
    ) -> Resultado:
        self._guardar_anexo(sessao, mensagem, agora)
        texto = mensagem.texto.strip()
        if mensagem.anexo is not None:
            texto = (mensagem.anexo.legenda or "").strip() or RESPOSTA_SO_ANEXO
        if not texto:
            return self._mostrar(sessao, sessao.no_atual)
        sessao.respostas[sessao.no_atual] = texto
        return self._avancar(sessao, no.proximo)

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------
    def _avancar(self, sessao: Sessao, destino: str) -> Resultado:
        sessao.pilha.append(sessao.no_atual)
        return self._mostrar(sessao, destino)

    def _mostrar(self, sessao: Sessao, no_id: str) -> Resultado:
        sessao.no_atual = no_id
        texto = self.fluxo.renderizar(no_id)
        if isinstance(self.fluxo.nos[no_id], NoEncaminhar):
            sessao.status = Status.AGUARDANDO_HUMANO
            return Resultado([texto], encaminhamento=gerar_resumo(self.fluxo, sessao))
        return Resultado([texto])

    # ------------------------------------------------------------------
    # Ciclo de vida da sessão
    # ------------------------------------------------------------------
    def _expirou(self, sessao: Sessao, agora: datetime) -> bool:
        parada = agora - sessao.atualizada_em
        config = self.fluxo.sessao
        if sessao.status is Status.ENCERRADO:
            return True
        if sessao.status is Status.BOT:
            return parada > timedelta(hours=config.expira_bot_horas)
        if sessao.status is Status.HUMANO:
            return parada > timedelta(hours=config.retorno_bot_apos_humano_horas)
        # AGUARDANDO_HUMANO nunca expira sozinho: o cliente ainda espera retorno.
        return False

    def _reiniciar(self, sessao: Sessao, agora: datetime) -> None:
        nova = self.nova_sessao(sessao.contato)
        nova.iniciada_em = agora
        vars(sessao).update(vars(nova))

    @staticmethod
    def _guardar_anexo(sessao: Sessao, mensagem: MensagemRecebida, agora: datetime) -> None:
        if mensagem.anexo is not None:
            sessao.anexos.append(AnexoRecebido(mensagem.anexo, sessao.no_atual, agora))
