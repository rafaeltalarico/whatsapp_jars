"""Simulador do atendimento no terminal.

Permite testar o fluxo completo, como se fosse o cliente no WhatsApp, sem
nenhuma conta na Meta. Uso:

    python -m jars.simulador [caminho/do/fluxo.yaml]
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from jars.atendimento import Atendimento, RepositorioEmMemoria
from jars.fluxo import CAMINHO_PADRAO, carregar_fluxo
from jars.motor import Anexo, MensagemRecebida, Motor, Resultado

CONTATO = "5588999990000"

AJUDA = """\
Digite as mensagens como se fosse o cliente. Comandos do simulador:
  /anexo [nome]   envia um documento (ex.: /anexo laudo.pdf)
  /assumir        simula a advogada respondendo (o robô fica em silêncio)
  /finalizar      simula a advogada concluindo o atendimento
  /horas N        avança o relógio em N horas (testa a expiração)
  /estado         mostra o estado da sessão
  /sair           encerra o simulador
"""


class RelogioSimulado:
    def __init__(self) -> None:
        self.agora = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, horas: float) -> None:
        self.agora += timedelta(hours=horas)


def _mostrar(resultado: Resultado) -> None:
    if not resultado.respostas:
        print("   (robô em silêncio)")
    for texto in resultado.respostas:
        print("\n🤖 ROBÔ ─────────────────────────────")
        print(texto)
    if resultado.encaminhamento:
        print("\n🔔 AVISO PARA A EQUIPE ──────────────")
        print(resultado.encaminhamento)
    print()


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    caminho = argv[0] if argv else CAMINHO_PADRAO
    relogio = RelogioSimulado()
    atendimento = Atendimento(Motor(carregar_fluxo(caminho), relogio), RepositorioEmMemoria())
    print(AJUDA)

    while True:
        try:
            entrada = input("👤 VOCÊ > ")
        except (EOFError, KeyboardInterrupt):
            print()
            return

        comando, _, argumento = entrada.strip().partition(" ")
        if comando == "/sair":
            return
        if comando == "/assumir":
            atendimento.humano_respondeu(CONTATO)
            print("   (advogada assumiu a conversa)\n")
        elif comando == "/finalizar":
            atendimento.finalizar_atendimento_humano(CONTATO)
            print("   (atendimento humano finalizado)\n")
        elif comando == "/horas":
            relogio.avancar(float(argumento or 1))
            print(f"   (relógio avançado em {argumento or 1} h)\n")
        elif comando == "/estado":
            sessao = atendimento.sessao(CONTATO)
            print(f"   status={sessao.status} nó={sessao.no_atual} pilha={sessao.pilha}\n")
        elif comando == "/anexo":
            nome = argumento or "documento.pdf"
            anexo = Anexo(tipo="document", id_midia=f"sim-{nome}", nome_arquivo=nome)
            _mostrar(atendimento.receber(CONTATO, MensagemRecebida(anexo=anexo)))
        else:
            _mostrar(atendimento.receber(CONTATO, MensagemRecebida(texto=entrada)))


if __name__ == "__main__":
    main()
