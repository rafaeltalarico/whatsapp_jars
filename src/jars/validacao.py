"""Validação e normalização do que o cliente digita."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_KEYCAP = "\u20e3"
_VARIACAO = "\ufe0f"
_ROTULOS_IDENTIFICACAO = re.compile(r"\b(nome\s+completo|nome|cpf)\s*:?", re.IGNORECASE)
_CPF_NO_TEXTO = re.compile(r"(?<!\d)(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")
_NOME_VALIDO = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)+$")
_PARTICULAS_DE_NOME = {"e", "y"}
# Palavras comuns em saudações e pedidos que não fazem parte de um nome.
_PALAVRAS_QUE_NAO_SAO_NOME = frozenset(
    "oi ola olá bom boa dia tarde noite tudo bem quero queria gostaria preciso falar com "
    "sobre ajuda favor por obrigado obrigada doutora doutor dra dr advogada advogado "
    "processo nome cpf meu minha sou".split()
)


def normalizar_entrada(texto: str) -> str:
    """Converte a resposta em uma forma comparável às opções do menu.

    Aceita variações comuns: espaços, ponto final ("1.") e números em
    emoji ("1️⃣", "🔟").
    """
    texto = texto.strip().replace("🔟", "10").replace(_VARIACAO, "").replace(_KEYCAP, "")
    return texto.rstrip(".)-").strip()


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def cpf_valido(cpf: str) -> bool:
    numeros = somente_digitos(cpf)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(numeros[i]) * (posicao + 1 - i) for i in range(posicao))
        digito = (soma * 10) % 11 % 10
        if digito != int(numeros[posicao]):
            return False
    return True


def formatar_cpf(cpf: str) -> str:
    n = somente_digitos(cpf)
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def nome_valido(nome: str) -> bool:
    """Exige nome e sobrenome, apenas com letras, e descarta frases comuns."""
    nome = nome.strip()
    if len(nome) < 5 or not _NOME_VALIDO.match(nome):
        return False
    palavras = re.split(r"[ \-]", nome.lower())
    if any(len(p) == 1 and p not in _PARTICULAS_DE_NOME for p in palavras):
        return False
    return not any(p in _PALAVRAS_QUE_NAO_SAO_NOME for p in palavras)


def normalizar_nome(nome: str) -> str:
    nome = unicodedata.normalize("NFC", " ".join(nome.split()))
    return nome.strip(" ,;.-")


@dataclass(frozen=True)
class Identificacao:
    nome: str | None
    cpf: str | None
    cpf_encontrado_invalido: bool = False


def extrair_identificacao(texto: str) -> Identificacao:
    """Separa nome e CPF de uma mensagem livre.

    O cliente pode enviar os dois juntos ("Maria Souza 52998224725"), em
    linhas separadas, com rótulos ("Nome completo: ...") ou só um deles.
    """
    cpf: str | None = None
    cpf_invalido = False
    encontrado = _CPF_NO_TEXTO.search(texto)
    if encontrado:
        candidato = somente_digitos(encontrado.group(1))
        if cpf_valido(candidato):
            cpf = candidato
        else:
            cpf_invalido = True
        texto = texto[: encontrado.start()] + " " + texto[encontrado.end() :]
    elif len(somente_digitos(texto)) >= 9:
        # Há uma sequência numérica que não tem o formato de um CPF.
        cpf_invalido = True

    resto = normalizar_nome(_ROTULOS_IDENTIFICACAO.sub(" ", texto))
    resto = re.sub(r"\d", "", resto)
    resto = normalizar_nome(resto)
    nome = resto if nome_valido(resto) else None
    return Identificacao(nome=nome, cpf=cpf, cpf_encontrado_invalido=cpf_invalido)
