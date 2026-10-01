"""Modelo do fluxo de atendimento: carga, validação e renderização dos textos.

O fluxo é descrito em YAML (ver ``config/fluxo.yaml``). Este módulo garante,
ao carregar, que o arquivo é consistente: todos os destinos existem, nenhum
nó fica inalcançável, nenhum caminho termina sem encaminhar para a equipe e
nenhuma opção de menu colide com os comandos de navegação.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "fluxo.yaml"
MARCADOR_ESCRITORIO = "{escritorio}"

_EMOJI_DIGITOS = {
    "0": "0️⃣",
    "1": "1️⃣",
    "2": "2️⃣",
    "3": "3️⃣",
    "4": "4️⃣",
    "5": "5️⃣",
    "6": "6️⃣",
    "7": "7️⃣",
    "8": "8️⃣",
    "9": "9️⃣",
}


class FluxoInvalido(ValueError):
    """O arquivo de fluxo tem um erro de estrutura."""


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Opcao(_Modelo):
    rotulo: str
    destino: str
    descricao: str | None = None


class NoMenu(_Modelo):
    tipo: Literal["menu"]
    campo: str
    texto: str
    opcoes: dict[str, Opcao]
    instrucao: str = "Digite o número correspondente."
    observacao: str | None = None
    navegacao: Literal["completa", "finalizar"] = "completa"

    @field_validator("opcoes", mode="before")
    @classmethod
    def _chaves_como_texto(cls, valor: Any) -> Any:
        # No YAML as chaves "1:", "2:"... chegam como inteiros.
        if isinstance(valor, dict):
            return {str(chave): opcao for chave, opcao in valor.items()}
        return valor

    @field_validator("opcoes")
    @classmethod
    def _chaves_numericas(cls, valor: dict[str, Opcao]) -> dict[str, Opcao]:
        if not valor:
            raise ValueError("o menu precisa de ao menos uma opção")
        for chave in valor:
            if not chave.isdigit() or chave.startswith("0"):
                raise ValueError(f"a opção {chave!r} deve ser um número inteiro positivo")
        return valor


class NoPergunta(_Modelo):
    tipo: Literal["pergunta"]
    campo: str
    texto: str
    proximo: str
    navegacao: Literal["completa", "finalizar"] = "completa"


class NoEncaminhar(_Modelo):
    tipo: Literal["encaminhar"]
    texto: str | None = None


No = Annotated[NoMenu | NoPergunta | NoEncaminhar, Field(discriminator="tipo")]


class Comandos(_Modelo):
    voltar: str
    inicio: str
    finalizar: str


class ConfigSessao(_Modelo):
    expira_bot_horas: float = Field(gt=0)
    retorno_bot_apos_humano_horas: float = Field(gt=0)


class Mensagens(_Modelo):
    boas_vindas: str
    pedir_nome: str
    pedir_cpf: str
    cpf_invalido: str
    identificacao_concluida: str
    opcao_invalida: str
    anexo_em_menu: str
    encaminhado: str
    encerramento: str
    rodape_completo: str
    rodape_finalizar: str


class Fluxo(_Modelo):
    escritorio: str
    inicio: str
    comandos: Comandos
    sessao: ConfigSessao
    mensagens: Mensagens
    nos: dict[str, No]

    @model_validator(mode="after")
    def _validar_grafo(self) -> Fluxo:
        erros: list[str] = []
        if self.inicio not in self.nos:
            erros.append(f"o nó inicial {self.inicio!r} não existe")
        if not isinstance(self.nos.get(self.inicio), NoMenu):
            erros.append(f"o nó inicial {self.inicio!r} deve ser um menu")

        reservados = {self.comandos.voltar, self.comandos.inicio, self.comandos.finalizar}
        for no_id, no in self.nos.items():
            for destino in _destinos(no):
                if destino not in self.nos:
                    erros.append(f"{no_id}: destino {destino!r} não existe")
            if isinstance(no, NoMenu):
                for chave in no.opcoes.keys() & reservados:
                    erros.append(f"{no_id}: a opção {chave!r} conflita com um comando de navegação")
        if erros:
            raise ValueError("; ".join(erros))

        alcancaveis = _alcancaveis(self.nos, self.inicio)
        for no_id in self.nos.keys() - alcancaveis:
            erros.append(f"{no_id}: nó inalcançável a partir de {self.inicio!r}")

        terminam = _que_chegam_a_encaminhamento(self.nos)
        for no_id in self.nos.keys() - terminam:
            erros.append(f"{no_id}: nenhum caminho a partir deste nó chega a um encaminhamento")
        if erros:
            raise ValueError("; ".join(sorted(erros)))
        return self

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------
    @property
    def escritorio_destacado(self) -> str:
        return f"*_{self.escritorio}_*"

    def formatar(self, texto: str) -> str:
        return texto.replace(MARCADOR_ESCRITORIO, self.escritorio_destacado).strip()

    def renderizar(self, no_id: str) -> str:
        """Monta a mensagem exibida ao cliente quando ele chega ao nó."""
        no = self.nos[no_id]
        if isinstance(no, NoEncaminhar):
            return self.formatar(no.texto or self.mensagens.encaminhado)

        partes = [no.texto]
        if isinstance(no, NoMenu):
            partes.append("\n".join(_linha_opcao(chave, op) for chave, op in no.opcoes.items()))
            partes.append(no.instrucao)
            if no.observacao:
                partes.append(no.observacao)
        rodape = (
            self.mensagens.rodape_completo
            if no.navegacao == "completa"
            else self.mensagens.rodape_finalizar
        )
        partes.append(rodape)
        return self.formatar("\n\n".join(p.strip() for p in partes))


def carregar_fluxo(caminho: str | Path = CAMINHO_PADRAO) -> Fluxo:
    with open(caminho, encoding="utf-8") as arquivo:
        return validar_fluxo(yaml.safe_load(arquivo))


def validar_fluxo(dados: Any) -> Fluxo:
    try:
        return Fluxo.model_validate(dados)
    except ValidationError as erro:
        raise FluxoInvalido(str(erro)) from erro


def numero_emoji(chave: str) -> str:
    if chave == "10":
        return "🔟"
    return "".join(_EMOJI_DIGITOS[d] for d in chave)


def _linha_opcao(chave: str, opcao: Opcao) -> str:
    if opcao.descricao:
        return f"{numero_emoji(chave)} *{opcao.rotulo}:* {opcao.descricao}"
    return f"{numero_emoji(chave)} *{opcao.rotulo}*"


def _destinos(no: NoMenu | NoPergunta | NoEncaminhar) -> list[str]:
    if isinstance(no, NoMenu):
        return [op.destino for op in no.opcoes.values()]
    if isinstance(no, NoPergunta):
        return [no.proximo]
    return []


def _alcancaveis(nos: dict[str, Any], inicio: str) -> set[str]:
    vistos: set[str] = set()
    pendentes = [inicio]
    while pendentes:
        atual = pendentes.pop()
        if atual in vistos or atual not in nos:
            continue
        vistos.add(atual)
        pendentes.extend(_destinos(nos[atual]))
    return vistos


def _que_chegam_a_encaminhamento(nos: dict[str, Any]) -> set[str]:
    chegam = {no_id for no_id, no in nos.items() if isinstance(no, NoEncaminhar)}
    mudou = True
    while mudou:
        mudou = False
        for no_id, no in nos.items():
            if no_id not in chegam and any(d in chegam for d in _destinos(no)):
                chegam.add(no_id)
                mudou = True
    return chegam
