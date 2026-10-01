"""Resumo da triagem enviado à equipe quando a conversa é encaminhada."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jars.fluxo import Fluxo, NoMenu, NoPergunta
from jars.validacao import formatar_cpf

if TYPE_CHECKING:
    from jars.motor import Sessao


def gerar_resumo(fluxo: Fluxo, sessao: Sessao) -> str:
    linhas = [
        "📋 *Nova triagem — aguardando atendimento*",
        "",
        f"👤 *Nome:* {sessao.nome or '(não informado)'}",
        f"🔢 *CPF:* {formatar_cpf(sessao.cpf) if sessao.cpf else '(não informado)'}",
        f"📱 *WhatsApp:* {sessao.contato}",
        "",
    ]
    # Só os nós já respondidos: a pilha descarta ramos abandonados com "voltar".
    for no_id in sessao.pilha:
        no = fluxo.nos.get(no_id)
        resposta = sessao.respostas.get(no_id)
        if isinstance(no, NoMenu | NoPergunta) and resposta:
            linhas.append(f"• *{no.campo}:* {resposta}")
    linhas.append("")
    linhas.append(f"📎 *Documentos recebidos:* {len(sessao.anexos)}")
    return "\n".join(linhas)
