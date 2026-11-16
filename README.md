# tia-plugin

Marketplace interno da **Tia**, um **harness de produto** para a gestão de um squad, como plugin do Claude Code.

Harness de produto é a estrutura que envolve o modelo e faz a gestão de produto seguir regras, não só boa
vontade: skills com roteiro, hooks que barram o que está fora do escopo, avaliadores determinísticos que
reprovam entrega incompleta, estado em disco e gates que só a humana aprova.

Com isso a PM conduz o squad numa estrutura só:
- **fila de demandas** com ciclo de vida e abertura do dia com o que espera decisão;
- **Base de Conhecimento** com a fonte de cada regra de negócio, conflitos e lacunas;
- **refinamento**: épicos e histórias com critérios que cobrem as regras;
- **outcome**: métricas, OKRs e monitoramento nos dados, com relatório diário e semanal;
- **documentação** do espaço do time no Confluence, com aprovação por página;
- **memória** de como a PM e o time trabalham.

Não escreve nem executa código de aplicação.

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
