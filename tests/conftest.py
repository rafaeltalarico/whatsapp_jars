from datetime import UTC, datetime, timedelta

import pytest

from jars.fluxo import carregar_fluxo
from jars.motor import MensagemRecebida, Motor, Resultado, Sessao

CPF_VALIDO = "52998224725"


class Relogio:
    def __init__(self) -> None:
        self.agora = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, horas: float) -> None:
        self.agora += timedelta(hours=horas)


@pytest.fixture(scope="session")
def fluxo():
    return carregar_fluxo()


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def motor(fluxo, relogio):
    return Motor(fluxo, relogio)


class Conversa:
    """Atalho para escrever cenários de teste como diálogos."""

    def __init__(self, motor: Motor) -> None:
        self.motor = motor
        self.sessao: Sessao = motor.nova_sessao("5588999990000")
        self.ultimo: Resultado | None = None

    def diz(self, texto: str) -> Resultado:
        self.ultimo = self.motor.processar(self.sessao, MensagemRecebida(texto=texto))
        return self.ultimo

    def envia(self, mensagem: MensagemRecebida) -> Resultado:
        self.ultimo = self.motor.processar(self.sessao, mensagem)
        return self.ultimo

    @property
    def texto(self) -> str:
        assert self.ultimo is not None
        return "\n".join(self.ultimo.respostas)

    def identificada(self) -> "Conversa":
        self.diz("Olá")
        self.diz(f"Maria da Silva {CPF_VALIDO}")
        return self


@pytest.fixture
def conversa(motor):
    return Conversa(motor)
