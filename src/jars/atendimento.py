"""Camada de aplicação: junta o motor ao armazenamento das sessões.

É o ponto de entrada que o webhook do WhatsApp e o painel de atendimento
vão usar nas próximas etapas.
"""

from __future__ import annotations

from typing import Protocol

from jars.motor import MensagemRecebida, Motor, Resultado, Sessao


class RepositorioSessoes(Protocol):
    def obter(self, contato: str) -> Sessao | None: ...

    def salvar(self, sessao: Sessao) -> None: ...


class RepositorioEmMemoria:
    """Guarda as sessões em memória (simulador e testes)."""

    def __init__(self) -> None:
        self._sessoes: dict[str, Sessao] = {}

    def obter(self, contato: str) -> Sessao | None:
        return self._sessoes.get(contato)

    def salvar(self, sessao: Sessao) -> None:
        self._sessoes[sessao.contato] = sessao


class Atendimento:
    def __init__(self, motor: Motor, repositorio: RepositorioSessoes) -> None:
        self.motor = motor
        self.repositorio = repositorio

    def sessao(self, contato: str) -> Sessao:
        return self.repositorio.obter(contato) or self.motor.nova_sessao(contato)

    def receber(self, contato: str, mensagem: MensagemRecebida) -> Resultado:
        sessao = self.sessao(contato)
        resultado = self.motor.processar(sessao, mensagem)
        self.repositorio.salvar(sessao)
        return resultado

    def humano_respondeu(self, contato: str) -> None:
        sessao = self.sessao(contato)
        self.motor.humano_assumiu(sessao)
        self.repositorio.salvar(sessao)

    def finalizar_atendimento_humano(self, contato: str) -> None:
        sessao = self.sessao(contato)
        self.motor.finalizar_atendimento_humano(sessao)
        self.repositorio.salvar(sessao)
