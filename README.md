# tia-plugin

Marketplace interno da **Tia**, assistente de produto para Product Managers, como plugin do Claude Code.

A Tia transforma pedidos em épicos e histórias com critérios de aceite que cobrem as regras de negócio, mantém
uma Base de Conhecimento com a fonte de cada regra, pede aprovação humana antes de decidir ou publicar (gates) e
acompanha nos dados se a entrega moveu as métricas. Não escreve nem executa código de aplicação.

## Instalar em 3 passos

Pré-requisitos: Claude Code, Python 3.12, Git Bash (Windows) e acesso a este repositório privado. Detalhes,
diagnóstico e erros comuns: [README do plugin](plugins/tia/README.md#instalar).

Na pasta do projeto do time (PowerShell, Git Bash ou terminal do macOS/Linux):

```bash
claude plugin marketplace add isaianeFamilhao/tia-plugin --scope project
```

```bash
claude plugin install tia@tia-marketplace --scope project
```

Depois abra o Claude Code nessa pasta e digite `/tia:configurar`. Nos dias seguintes, `/tia:abrir` ou
"Tia, bom dia".

Instale por projeto (`--scope project`), não na conta: o plugin fica ligado só na pasta do time e a configuração
vai para o git junto com o projeto.

## Onde está cada coisa

| Para | Leia |
|---|---|
| Instalar, usar, funcionalidades, gates, como funciona | [plugins/tia/README.md](plugins/tia/README.md) |
| Regras para agentes e LLMs (invariantes, caminhos, comandos) | [Para agentes e LLMs](plugins/tia/README.md#para-agentes-e-llms) |
| O que mudou em cada versão | [plugins/tia/CHANGELOG.md](plugins/tia/CHANGELOG.md) |
| Por que foi desenhado assim | [plugins/tia/docs/decisoes.md](plugins/tia/docs/decisoes.md) |

## Estrutura do repositório

```text
.claude-plugin/marketplace.json   catálogo do marketplace (tia-marketplace)
plugins/tia/                      o plugin: skills, scripts, hooks, modelos, testes
```

Versão atual: 0.2.0. Uso interno do Time de Produto, sem licença por ora.
