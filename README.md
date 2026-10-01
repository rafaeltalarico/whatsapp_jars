# whatsapp_jars

Chatbot no WhatsApp para o escritório de advocacia **J. Alencar e R. Sousa Advogadas Associadas** (JARS).

O robô faz o atendimento inicial (identificação e triagem por assunto) e passa a conversa para uma advogada. Ela pode entrar na conversa a qualquer momento, pelo celular ou pelo painel de atendimento, e o robô fica em silêncio.

## Arquitetura

```
Cliente ── WhatsApp ──► WhatsApp Cloud API (modo Coexistence) ◄── Advogada (app no celular)
                               │ webhook        ▲ envio
                               ▼                │
                      Backend JARS (Python) ────┘
                      • motor de conversa + fluxo em YAML
                      • estados: BOT / AGUARDANDO_HUMANO / HUMANO / ENCERRADO
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
           PostgreSQL                 Chatwoot (painel) ◄── Advogada (computador)
```

### Etapas

1. **Motor de fluxo, testes e simulador no terminal** ✅ (esta versão)
2. Integração com a WhatsApp Cloud API: webhook, envio de mensagens, mídia e handoff pelo celular
3. Persistência em PostgreSQL, painel Chatwoot e deploy com Docker

## Estrutura

```
config/fluxo.yaml      todos os textos, menus e caminhos do atendimento
src/jars/
  fluxo.py             carrega e valida o fluxo; monta as mensagens
  motor.py             máquina de estados da conversa (regras de negócio)
  validacao.py         CPF, nome e normalização do que o cliente digita
  resumo.py            resumo da triagem enviado à equipe
  atendimento.py       junta o motor ao armazenamento das sessões
  simulador.py         simulador do atendimento no terminal
tests/                 testes automatizados
```

## Como rodar

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                            # testes
ruff check . && ruff format --check .   # lint e formatação
python -m jars.simulador          # conversa simulada no terminal
```

No simulador, digite as mensagens como se fosse o cliente. Comandos extras: `/anexo laudo.pdf` (envia um documento), `/assumir` (a advogada entra na conversa), `/finalizar`, `/horas 25` (avança o relógio), `/estado` e `/sair`.

## Regras do atendimento

| Situação | Comportamento |
|---|---|
| Primeira mensagem | Boas-vindas com aviso da LGPD e pedido de nome completo e CPF |
| Nome e CPF | Podem vir juntos ou separados. O CPF tem o dígito verificador validado |
| `0` | Volta ao menu anterior |
| `00` | Retorna ao menu principal |
| `#` | Finaliza com a mensagem de despedida e o alerta sobre o golpe do falso advogado |
| Fim da triagem | O cliente recebe a confirmação e a equipe recebe um resumo (nome, CPF, respostas, nº de documentos). Estado `AGUARDANDO_HUMANO` |
| `AGUARDANDO_HUMANO` | O robô fica em silêncio e só guarda os documentos que chegarem. `0`, `00` e `#` continuam funcionando |
| Advogada responde | Estado `HUMANO`: o robô não responde nada, nem a comandos |
| Inatividade | Conversa com o robô parada há mais de 24 h recomeça do início. Conversa com a advogada parada há mais de 12 h volta para o robô (configurável em `fluxo.yaml`) |

## Como alterar o fluxo

Edite `config/fluxo.yaml`. Os menus são numerados automaticamente a partir das opções, e o rodapé de navegação é incluído em cada tela. Rode `pytest` depois de editar: ao carregar o arquivo, o sistema recusa destinos inexistentes, telas inalcançáveis, caminhos sem saída e opções que colidam com `0`, `00` ou `#`. Os testes também percorrem **todos os caminhos** do fluxo.

Formatação do WhatsApp: `*negrito*`, `_itálico_`, `*_negrito e itálico_*`. O marcador `{escritorio}` vira o nome do escritório em negrito e itálico.
