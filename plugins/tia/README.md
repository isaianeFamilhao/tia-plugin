# Tia · plugin do Claude Code

Referência completa do plugin `tia@tia-marketplace` (versão 0.3.0). Vale para quem instala, para quem usa e para
agentes (LLMs) que trabalham num projeto com a Tia.

## O que é e para quem

A **Tia** é um **harness de produto** para a gestão de um squad. Dá à Product Manager uma estrutura de trabalho
dentro do Claude Code: uma fila de demandas com estado, uma Base de Conhecimento com fonte, decisões que só
avançam com aprovação humana, métricas acompanhadas nos dados e uma memória de como o time e a PM trabalham. O
modelo faz o trabalho pesado; o harness garante método, fonte, rastro e aprovação.

O resultado é um squad que decide com base no que está escrito e no que os dados mostram, não no que alguém
lembra. Épicos e histórias são uma das entregas, não o todo.

| Frente da gestão | O que a Tia mantém | Onde |
|---|---|---|
| Fila e ritmo | Demandas com ciclo de vida (aprovar, executar, aceitar, publicar) e abertura do dia com o que espera decisão. | `tia/demandas.yaml`, `.tia/ledger.json`, `/tia:abrir` |
| Conhecimento do time | Regras de negócio com fonte, conflitos, lacunas e apontamentos sobre a documentação. | `tia/kb/`, `/tia:base`, `/tia:confluence` |
| Refinamento | Épicos e histórias com critérios que cobrem as regras, matriz de cobertura e revisão independente. | `tia/demandas/D-NNN/`, `/tia:demanda` |
| Outcome | Métricas de outcome com checagem de dados, OKRs e monitoramento com alertas. | `/tia:metricas`, `/tia:okr`, `.tia/monitoramento/` |
| Acompanhamento | Relatório diário (pulso) e semanal (OKR × entrega), com recomendação de ajuste de rota. | `tia/relatorios/`, `/tia:report` |
| Documentação | Manutenção do espaço do time no Confluence, só com aprovação por página. | `/tia:confluence` |
| Memória | O que a PM e o time ensinaram, por escopo, revogável. | `tia/memoria/`, `~/.tia/` |

Ela consulta o Confluence, o Jira e as fontes de dados conectadas na sua conta do Claude. Não escreve nem executa
código de aplicação.

### Por que harness

Um prompt pede; um harness garante. A Tia não depende de o modelo lembrar das regras. Ela tem:

| Peça | O que garante |
|---|---|
| Skills com roteiro (`/tia:*`) | O mesmo método a cada vez: abertura do dia, demanda, Base, métricas, OKR, relatório. |
| Hooks | Escrita só em `tia/`, Jira e Confluence só com gate, dados só leitura. O que foge disso é negado, e hook com erro nega (fail-closed). |
| Avaliadores determinísticos | `coverage` reprova a entrega se uma regra relevante ficou sem critério; `kb validar` reprova regra da Base sem fonte; o Stop não deixa a sessão terminar com entrega reprovada. |
| Estado em disco (`.tia/ledger.json`, `.tia/monitoramento/`) | Demandas e monitores ficam no disco, não na conversa. Uma sessão nova retoma de onde parou e, versionado no git, o time vê o mesmo estado. |
| Gates humanos | G1, G2, K1, G3, C1, M1 e Memória só avançam com resposta explícita da PM. |

Origem: a Tia nasceu como harness de produto num workspace (`harness-cowork`) e virou plugin na 0.1.0
([CHANGELOG](CHANGELOG.md)).

## Sumário

- [Instalar](#instalar)
- [Primeiro uso num projeto](#primeiro-uso-num-projeto)
- [Diagnóstico (doctor)](#diagnóstico-doctor)
- [Erros comuns](#erros-comuns)
- [Funcionalidades](#funcionalidades)
- [Como funciona](#como-funciona)
- [Para agentes e LLMs](#para-agentes-e-llms)
- [Atualizar, desinstalar e versões](#atualizar-desinstalar-e-versões)

## Instalar

### Pré-requisitos

| Item | Por quê | Como conferir |
|---|---|---|
| Claude Code (app desktop ou CLI) | É a casa da Tia. O Cowork carrega skills e hooks, mas o uso previsto é no Claude Code. | `claude --version` |
| Python 3.12 ou mais novo | Os scripts e os hooks rodam em Python, num ambiente próprio do plugin. | Windows: `py -3.12 --version` · macOS/Linux: `python3.12 --version` |
| Git Bash (Windows) | Os hooks rodam em `bash`. No Windows, vem com o Git for Windows. | `Test-Path "C:\Program Files\Git\bin\bash.exe"` no PowerShell |
| Acesso ao repositório privado `isaianeFamilhao/tia-plugin` | O marketplace é clonado desse repositório. | `git ls-remote https://github.com/isaianeFamilhao/tia-plugin` responde sem erro |
| Acesso a pypi.org e files.pythonhosted.org | A primeira sessão instala PyYAML e jsonschema no ambiente do plugin. | Veja [Erros comuns](#erros-comuns) se a rede tiver proxy |
| Recomendado: conector Atlassian na conta do Claude | Sem ele a Tia não lê Confluence nem Jira, e o configurar pede os dados à mão. | Ferramentas `mcp__…Atlassian…` aparecem na sessão |

No Windows, ao instalar o Python (python.org), marque **"Add python.exe to PATH"**.

Como o Claude Code autentica no GitHub para clonar o repositório privado (credencial do git, `gh auth login` ou
token): `[a confirmar]`. O teste prático é o `git ls-remote` acima funcionar no mesmo terminal.

### Adicionar o marketplace e instalar

**Instale por projeto, não na conta.** Com `--scope project`, o plugin fica ligado só na pasta do time (em
`.claude/settings.json`, versionado) e não age nos seus outros projetos. Fora de um projeto configurado os hooks
já saem em silêncio, mas o escopo de projeto deixa isso explícito e permite que o time inteiro herde a
configuração pelo git.

Abra o terminal **na pasta do projeto do time** e rode os dois comandos. São os mesmos no PowerShell, no Git Bash
e no terminal do macOS/Linux.

```bash
claude plugin marketplace add isaianeFamilhao/tia-plugin --scope project
```

```bash
claude plugin install tia@tia-marketplace --scope project
```

Depois, abra (ou reabra) o Claude Code nessa pasta. Na primeira sessão o plugin cria o seu ambiente Python; isso
leva alguns minutos e só acontece de novo quando os requisitos mudam.

Variações:

- **Clone local do repositório:** `claude plugin marketplace add <caminho do clone> --scope project`. Útil para
  testar uma branch. Não versione um caminho local no `.claude/settings.json` do time.
- **Testar sem instalar:** `claude --plugin-dir <caminho do clone>/plugins/tia`.
- **Instalar na conta (`--scope user`, o padrão do CLI):** funciona, mas o plugin fica carregado em todo projeto.
  Use só se você for a única pessoa e quiser a Tia em várias pastas.

## Primeiro uso num projeto

1. No Claude Code, na pasta do projeto, digite `/tia:configurar` (ou "Tia, configurar"). A Tia pergunta o perfil
   da pasta: PM (os passos abaixo) ou GPM (veja [Perfis PM e GPM](#perfis-pm-e-gpm)).
2. A Tia lê o conector Atlassian e propõe numa tabela: site, `cloud_id`, projeto do Jira e espaços do Confluence.
   **Só um** espaço pode ser `manter` (o do time, alterado só com o gate C1). Os outros ficam somente leitura.
3. Com o seu sim, ela cria só o que falta, sem sobrescrever nada:
   - `.tia/config.yaml` (marcador e configuração do time);
   - `tia/` (fila, exemplo de demanda, Base de Conhecimento com o contrato, padrões de épico e de história,
     apontamentos, prefixos, Memória do time e pessoal com `pessoal.md`);
   - o `CLAUDE.md` do time (ou `tia/CLAUDE.md` e a linha `@tia/CLAUDE.md`, se o projeto já tiver um);
   - o bloco da Tia no `.gitignore`.
4. Ela roda o bootstrap do ambiente Python e o diagnóstico (`doctor`).
5. Preencha o `CLAUDE.md` do time e o padrão de épico (`tia/kb/padroes/epico.md`). Alimente a Base com
   `/tia:base`. Escreva a primeira demanda em `tia/demandas.yaml` a partir de `tia/demandas.exemplo.yaml`.
6. Commite `tia/`, `.tia/config.yaml`, `.tia/ledger.json`, `.tia/monitoramento/`, o `CLAUDE.md` e o
   `.claude/settings.json`. Ficam fora do git: `.tia/logs/`, `.tia/cache/` e `tia/memoria/pessoal/`.

A partir daí, todo dia: `/tia:abrir` ou "Tia, bom dia".

## Diagnóstico (doctor)

O `/tia:abrir` já roda o diagnóstico. Para rodar à mão, use o lançador do plugin. O plugin instalado fica em
`~/.claude/plugins/cache/tia-marketplace/tia/<versão>/`.

Git Bash, macOS ou Linux:

```bash
bash ~/.claude/plugins/cache/tia-marketplace/tia/0.3.0/scripts/tia.sh doctor
```

PowerShell (chame o `bash` do Git; o `bash` do PATH pode ser o do WSL):

```powershell
& "C:\Program Files\Git\bin\bash.exe" "$HOME\.claude\plugins\cache\tia-marketplace\tia\0.3.0\scripts\tia.sh" doctor
```

As mensagens de erro da Tia já trazem esses dois comandos prontos, com o caminho certo do plugin.

Cada linha sai como `OK`, `AVISO` (siga, mas saiba) ou `FALHA` (pare e corrija). O doctor confere: versão do
Python, Git Bash, se a pasta é workspace, ambiente Python do plugin, resposta dos hooks, modo manutenção ligado,
estrutura do workspace, modelos desatualizados, config tentando mudar regras inegociáveis, Base de Conhecimento,
fila, monitoramento, Memória e demanda em andamento. `--json` devolve o mesmo em JSON.

## Erros comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "o ambiente Python da Tia ainda não existe" | Primeira sessão não terminou o bootstrap. Escrita e shell que não seja leitura ficam negados até lá. | Abra uma sessão nova no projeto ou rode `tia.sh bootstrap` (comando pronto na mensagem). |
| "pasta de dados do plugin desconhecida" | O lançador ainda não sabe onde fica o ambiente. | Abra uma sessão no projeto: o hook grava o caminho em `.tia/cache/plugin-data`. |
| "falha no pip install (sem internet ou proxy?)" | Rede bloqueia o índice de pacotes. | Peça ao suporte para liberar pypi.org e files.pythonhosted.org ou configurar `HTTPS_PROXY`. Detalhes em `bootstrap.log`, na pasta de dados do plugin. |
| "Python 3.12 não encontrado" | Python ausente ou fora do PATH. | Instale o 3.12 (python.org, marque "Add to PATH") e abra o Claude Code de novo. |
| "Git Bash não encontrado" | Git for Windows ausente. | Instale o Git for Windows e reabra o Claude Code. |
| "outro bootstrap em andamento" | Duas sessões abriram juntas. | Espere alguns minutos e abra a sessão de novo. |
| "Tia, …" responde com convite para configurar | A pasta não tem `.tia/config.yaml`. | `/tia:configurar` na pasta certa. |
| `bash` no PowerShell abre o WSL | O `bash` do PATH não é o do Git. | Use `& "C:\Program Files\Git\bin\bash.exe" ...` |
| `AVISO` de modelos desatualizados | O plugin foi atualizado e os modelos copiados são de uma versão anterior. | "Tia, atualiza a configuração" (`/tia:configurar atualizar`). |
| Ação negada com prefixo `[tia]` | Um hook barrou a ação por regra. | Leia o motivo. Negação é regra, não erro a contornar. |

## Funcionalidades

### Skills

| Comando | Perfil | Quando usar | O que entrega |
|---|---|---|---|
| `/tia:abrir` · "Tia, bom dia" | PM e GPM | Início do dia, retomar, ver a fila ou pendências. | Briefing curto. PM: alertas de métricas, gates que esperam você, fila, apontamentos e fontes de dados conectadas. GPM: alertas, times com travas e OKRs do grupo em risco. Conduz os gates e encaminha pedidos "Tia, …". |
| `/tia:demanda D-NNN` | PM | Depois de aprovar uma demanda (G1) e começar a execução. | Pesquisa com fonte, épico no padrão do time, histórias com critérios Dado/Quando/Então, matriz de cobertura, revisão independente e `result.json` para o G2. |
| `/tia:portfolio [janela] [time]` | GPM | Ver como estão os times do grupo. | Por time, no Jira e sem pessoas: em andamento por etapa, travados e entregas da janela, com causa provável e próximo passo, em `tia/relatorios/<data>-portfolio.md`. |
| `/tia:base [escopo]` | PM e GPM | A Base de Conhecimento está desatualizada ou precisa crescer. | Diferenças entre a Base e o Confluence/Jira (regra nova, mudou, revogada, conflito, lacuna) e o lote para o K1. |
| `/tia:confluence [consultar\|documentar\|revisar\|apontamentos]` | PM e GPM | Consultar páginas, apontar dúvidas ou documentar no espaço do time. | Resposta com título, espaço e link; apontamentos em `tia/kb/apontamentos.md`; rascunho e diff para o C1. |
| `/tia:metricas` | PM e GPM | Definir como medir uma feature, épico, OKR ou iniciativa. | Árvore output → outcome, 1 métrica principal com hipótese, 1–2 guardrails, status dos dados (mensurável hoje, sem acesso, ponto cego), fórmula, janela e tracking spec. |
| `/tia:okr` | PM e GPM | Fechar, revisar ou desdobrar OKRs. No GPM, os OKRs do grupo. | Objetivos qualitativos, 2–4 KRs "de X para Y", guardrail, checagem de dados e iniciativas separadas. |
| `/tia:report diario\|semanal` | PM e GPM | Pulso do dia ou visão semanal. | Relatório em `tia/relatorios/` cruzando entrega e dados, com até 3 recomendações. No GPM, o semanal é o de portfólio (tabela por time, OKRs do grupo). |
| `/tia:report diretoria` | GPM | Levar a situação do grupo à diretoria. | Formato executivo curto (situação, riscos, decisões pedidas) em `tia/relatorios/<data>-diretoria.md`. Não envia nem publica sem pedido. |
| `/tia:configurar [atualizar]` | PM e GPM | Preparar o projeto ou comparar modelos depois de atualizar o plugin. | Estrutura do workspace criada, ou o diff dos modelos com decisão arquivo a arquivo. |
| `/tia:ajuda` | PM e GPM | Ver todos os comandos. | Lista de skills, atalhos, gates e scripts do perfil da pasta, e o próximo passo útil. |

**Chamado "Tia, …".** No início da mensagem, "Tia, <frase>" chama a skill certa. Exemplos: "Tia, roda o semanal"
→ `/tia:report semanal`; "Tia, atualiza a configuração" → `/tia:configurar atualizar`. Só vale no começo da
frase: "garantia, …" e "notícia, …" não disparam, nem o antigo "Ada, …". Atalhos pessoais vão no seu
`pessoal.md`.

### Gates

Gate é uma decisão que só a humana toma, com resposta explícita no turno. A Tia pergunta; o script registra.

| Gate | Nome | Quando aparece |
|---|---|---|
| G1 | Aprovar a demanda | Demanda válida na fila (`/tia:abrir`). |
| G2 | Aceitar a entrega | A demanda foi entregue com a cobertura aprovada. Opções: aceitar, retrabalho (com motivo, até 2 vezes), rejeitar. |
| K1 | Mudar a Base de Conhecimento | Regra nova, alterada ou revogada (`/tia:base` ou regras candidatas de uma demanda). |
| G3 | Publicar no Jira | Só se a PM pedir, depois do G2. Cada escrita ainda pede confirmação. |
| C1 | Alterar o Confluence | Só no espaço `manter`, uma página por vez, com validade de 24 h (ajustável). |
| M1 | Ativar monitoramento | Depois do G2, de um épico em produção ou de um OKR novo. |
| Memória | Guardar um aprendizado | "Aprendi: … Guardo para você ou para o time?" |

Ciclo da demanda: `draft → valid → (G1) approved → running → delivered | blocked → (G2) accepted | rework |
rejected → (G3, opcional) publish_approved → published`.

### Perfis PM e GPM

A Tia tem dois perfis com o mesmo motor, os mesmos princípios e as mesmas regras. Muda o que cada um faz.

| Perfil | Para quem | O centro do trabalho |
|---|---|---|
| **PM** | Product Manager de um time | Fila de demandas, épicos e histórias, Base de Conhecimento, métricas e OKRs do time. |
| **GPM** | Quem lidera um grupo de times | Portfólio dos times, OKRs do grupo e relatórios (semanal de portfólio e diretoria). |

**O perfil é da pasta.** Fica em `perfil: pm|gpm` no `.tia/config.yaml`; sem a chave, vale `pm` (pastas da 0.2.0
seguem iguais). O `/tia:configurar` pergunta o perfil ao criar a pasta. Quem tem os dois papéis usa duas pastas.
Perfil com valor inválido é `FALHA` no `doctor`.

**Habilidades por perfil.** `/tia:demanda` e a fila (`tia/demandas.yaml` e os gates G1, G2 e G3) só existem no
PM; `/tia:portfolio` e `/tia:report diretoria` só no GPM; o resto vale nos dois. A `/tia:ajuda` e os atalhos
"Tia, …" mostram só as do perfil da pasta. Pedido de habilidade do outro perfil recebe uma linha dizendo de qual
perfil ela é (ex.: "escreve um épico" numa pasta GPM: isso fica na pasta da PM do time).

**Configurar no GPM.** A Tia propõe pelo conector Atlassian (ou pergunta) os **times do portfólio**
(`portfolio.times: [{nome, jira_projeto, board?}]`), os projetos do Jira e os espaços do Confluence; nada vem
fixado (D-PM-32). Zero ou um espaço `manter`. Não há fila: a pasta não tem `tia/demandas.yaml` nem
`tia/demandas/`. O `CLAUDE.md` vem de um modelo próprio do GPM. O `doctor` acusa time sem projeto e projeto
repetido.

**Portfólio (`/tia:portfolio`).** Consultas JQL só leitura por time; o script agrega por time os itens em
andamento por etapa, os travados (sinalizados, bloqueados ou sem movimento há 5 dias) e os concluídos na janela
(7 dias por padrão). Responsável e qualquer campo de pessoa saem antes de gravar: o portfólio é por time, nunca
por pessoa. Relatório em `tia/relatorios/<data>-portfolio.md`, com a fonte e a data da consulta. Nesta versão a
fonte é só o Jira; o app de WIP entra como fonte de dados quando existir (D-PM-30).

**Abertura do dia no GPM.** No lugar da fila: alertas de métricas, times com travas (time, o que trava, próximo
passo) e OKRs do grupo em risco, nessa ordem. Depois, o que espera decisão (K1, M1, Memória).

**OKRs do grupo.** No GPM, `/tia:okr` cria e revisa OKRs com `nivel: grupo` e `id` por objetivo (`OBJ-NN`). Na
pasta de um time, o `alinhamento` do OKR pode citar esse id; `okr validar --grupo <arquivo do grupo>` reprova id
que não existe (texto livre segue valendo, com aviso). A consolidação dos OKRs dos times ainda não existe.

**Relatórios do GPM.** `/tia:report semanal` é o semanal de portfólio: tabela por time (WIP, travas, entregas,
situação), OKRs do grupo e até 3 recomendações com evidência e trade-off. `/tia:report diretoria` é o executivo
curto: situação, riscos e decisões pedidas. Nenhum dos dois é enviado ou publicado sem pedido; publicar é um
documento ou uma página no espaço `manter`, com C1.

**Sem integração entre Tias.** A Tia do GPM não lê a pasta de nenhuma PM; vê o portfólio pelo Jira, pelo
Confluence e pelas fontes de dados (D-PM-29). Demanda que ainda não está no Jira não aparece para o GPM.

## Como funciona

### Motor no plugin, conteúdo no workspace

| Onde | O que fica | Quem edita |
|---|---|---|
| Plugin (`plugins/tia/`) | Skills, scripts, hooks, avaliadores, modelos e princípios. | Só a manutenção do plugin. |
| `.tia/` no projeto | Máquina: `config.yaml` (marcador), `ledger.json` (estado das demandas), `monitoramento/`, `logs/`, `cache/`. | Só scripts. `config.yaml` também a humana. |
| `tia/` no projeto | Conteúdo que gente lê e revisa: `demandas.yaml` (fila), `demandas/D-NNN/`, `kb/` (Base de Conhecimento), `memoria/`, `propostas/`, `relatorios/`. | A Tia, dentro das regras abaixo. `demandas.yaml` só a humana. |
| `~/.tia/` | Memória e `pessoal.md` globais da pessoa. | A Tia, com o gate Memória; `pessoal.md` a pessoa. |

A Tia só age onde existe `.tia/config.yaml`. Em qualquer outra pasta os hooks saem em silêncio, sem nem chamar o
Python.

### Configuração em camadas

1. **Inegociável** (só no plugin, o workspace não sobrepõe): escopo de escrita, regras de escrita no Jira, no
   Confluence e nos dados, espaço padrão somente leitura, exigência de cobertura e formato do critério.
2. **Padrão com ajuste:** tamanhos (P até 3 histórias, M até 6, G até 10), limite de retrabalho, palavras vagas,
   detecção de fontes de dados, validade do C1. Para ajustar, repita só a chave em `.tia/config.yaml`
   (deep merge; lista substitui lista).
3. **Do time:** site, `cloud_id`, projeto do Jira, espaços e a política de cada um, padrões de épico e história,
   `CLAUDE.md`, modelos permitidos e esforço. Copiado no configurar; depois só a humana edita.

Precedência no comportamento: princípios da Tia > políticas do time (`CLAUDE.md`, `.tia/config.yaml`) > pessoal
do workspace > pessoal global. O pessoal ganha do time em estilo, nunca em política.

### Memória em três escopos

| Escopo | Pasta | Versionada | Vale para |
|---|---|---|---|
| `time` | `tia/memoria/time/` | sim | todo o time neste projeto |
| `pessoal` | `tia/memoria/pessoal/` | não | você, neste projeto |
| `global` | `~/.tia/memoria/` | não | você, em todos os projetos |

Um arquivo por aprendizado, gravado só com o seu sim. Revogar marca `status: revogada`, não apaga. O
`pessoal.md` (estilo, formatos, atalhos) você escreve sem gate, em `tia/memoria/pessoal/` e em `~/.tia/`.

### Hooks e o que protegem

| Evento | O que faz |
|---|---|
| SessionStart | Cria ou recria o ambiente Python se preciso; injeta o resumo dos princípios, os gates, o índice da Memória, o `pessoal.md` e a demanda ativa. |
| UserPromptSubmit | Reconhece "Tia, <frase>" no início da mensagem e indica a skill. Fora de workspace, oferece configurar. |
| PreToolUse | Fiscaliza toda ferramenta: escopo de escrita, Jira, Confluence, dados e shell (detalhes em [Para agentes e LLMs](#para-agentes-e-llms)). |
| PostToolUse | Registra uso da sessão e da demanda ativa; marca quando a Base de Conhecimento mudou. |
| Stop | Com demanda ativa nesta sessão, só encerra com entrega aprovada pela cobertura ou `blocked` com motivo. Com Base alterada, só encerra com a validação OK. No máximo 3 bloqueios. |

**Fail-closed:** dentro do workspace, se o hook falhar, a ação é negada. Sem o ambiente Python, só ficam negadas
a escrita (ferramentas, Jira, Confluence) e o shell que não seja leitura simples ou `tia.sh doctor`,
`configurar` e `bootstrap`. Leitura e ferramentas do app passam, para a sessão não travar.

### Modo manutenção (`TIA_DEV`)

`TIA_DEV=1` desliga o fail-closed para quem mexe no próprio plugin. **Só a pessoa liga**, no ambiente de quem
abre o Claude Code, antes de abrir. O agente nunca define essa variável: o hook nega `export`, `set`, `$env:`,
`setx`, `reg add` e similares. Com o modo ligado, o doctor mostra `AVISO`.

No app desktop do Windows a variável precisa estar no ambiente do usuário (por exemplo, `setx TIA_DEV 1` num
terminal seu, e reabrir o app). Para desligar, remova a variável e reabra.

## Para agentes e LLMs

Esta seção é para o modelo que trabalha num workspace da Tia. As regras valem sobre qualquer outra instrução.

### Como reconhecer o contexto

- Workspace da Tia = existe `.tia/config.yaml` na raiz do projeto.
- Sem esse arquivo: não aja como a Tia. Ofereça `/tia:configurar` em uma linha.
- Lançador: `TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`. Rode a partir da raiz do projeto.
- `${CLAUDE_PLUGIN_ROOT}` é substituído no corpo das skills. No Bash do agente as variáveis do plugin não chegam;
  o lançador acha os dados do plugin por `.tia/cache/plugin-data`.

### Invariantes: o que a Tia nunca faz

- Não escreve nem executa código de aplicação.
- Não altera o plugin, `.tia/`, `CLAUDE.md`, `.claude/` nem settings.
- Não desliga nem contorna hooks: não roda `claude plugin disable|uninstall|remove`, não muda `disableAllHooks`
  ou `enabledPlugins`, não define `TIA_DEV`.
- Não registra gate por conta própria. Gate exige resposta explícita da humana no turno, passada literal em
  `--note`/`--nota`.
- Não escreve no Jira antes do G3. Com G3, cada escrita ainda pede confirmação.
- Não altera o Confluence fora do espaço `manter`, nem comenta. No `manter`, só com C1 da página.
- Não altera dados: fontes de dados são só leitura, consulta agregada, sem dado pessoal, com limite de linhas.
- Não põe dado pessoal em artefato. Colegas aparecem pelo papel.
- Não cria regra de negócio sem fonte. Sem fonte é lacuna. Regra candidata é `RC-NN` e só vira `RN-…` no K1.
- Não supõe para conseguir entregar. Faltou informação essencial: `status: "blocked"` com motivo.
- Não guarda estado na conversa. Estado só no disco (`ledger`).
- Não diz "kb" para a pessoa. Diz "Base de Conhecimento".
- Não decide pela humana.

### Onde pode escrever

| Caminho | Regra |
|---|---|
| `tia/**` com extensão `.md`, `.yaml`, `.yml` ou `.json` | Permitido. |
| `tia/demandas.yaml` | Negado: só a humana edita a fila. Proponha o bloco na conversa. |
| `tia/kb/README.md` | Negado: contrato da Base, só a humana. |
| `tia/kb/**` | Pede confirmação (K1). |
| `tia/memoria/**` | Pede confirmação (gate Memória). Grave pelo `memoria gravar`. |
| `tia/demandas/<outra>/` | Negado enquanto há outra demanda ativa. |
| `.tia/**` | Negado direto. Só pelos scripts do lançador. |
| Qualquer outro caminho | Negado. |

No shell: é negado gravar em `.tia/`, `CLAUDE.md`, settings e arquivos de hooks. Ler ou citar esses nomes passa.
Mensagens de commit (`-m`, `-F`, heredoc) e texto entre aspas não contam como comando.

### Como descobrir o estado

- Perfil: `perfil` em `.tia/config.yaml` (sem a chave, `pm`); o início da sessão também informa. No GPM não há
  fila: o estado é o último retrato do portfólio (`TIA portfolio ultimo --json`) e os OKRs (`TIA okr listar`).
- Fila e gates (PM): `TIA ledger status --json`. Campos úteis: `ativa` (demanda em andamento), `prontas_para_g1`,
  `aprovadas`, `aguardando_g2`, `retrabalho` e `demandas` (uma linha por demanda, com `estado`).
- Uma demanda: `TIA ledger show D-NNN`.
- Saúde do ambiente: `TIA doctor --json`. `FALHA` = pare e explique a correção.
- Antes de ler o estado, sincronize a fila: `TIA ledger sync`.

### Comandos determinísticos

Todos via `TIA <script> ...`. Os que registram gate exigem a resposta literal da humana.

| Comando | Quando chamar |
|---|---|
| `doctor [--json]` | Abertura e sempre que algo falhar. |
| `bootstrap` | Ambiente Python ausente. |
| `configurar status [--json]` | Antes de configurar: o que falta. |
| `configurar criar --time … --site … --cloud-id … --jira … --espaco "CHAVE\|id\|Nome\|politica" --nota …` | Depois do sim no configurar (PM). |
| `configurar criar --perfil gpm --time … --site … --cloud-id … --portfolio "Nome\|CHAVE[\|board]" … [--espaco …] --nota …` | Depois do sim no configurar (GPM). |
| `configurar atualizar [--aplicar ARQUIVO --nota …]` | Comparar e trocar modelos copiados, arquivo a arquivo. |
| `validate [--json]` | Validar `tia/demandas.yaml`. |
| `ledger sync` · `ledger status [--json]` · `ledger show ID` | Ler o estado. |
| `ledger g1 ID --approve\|--skip --note …` | G1. |
| `ledger iniciar ID --session-id …` | Começar a demanda aprovada (uma por vez). |
| `ledger coletar ID` | Fechar a execução; recusa se a cobertura reprovar. |
| `ledger abandonar ID --note …` | Parar uma demanda em andamento. |
| `ledger g2 ID --accept\|--rework\|--reject --note …` | G2. Retrabalho e rejeição exigem motivo. |
| `ledger k1 ID --regras RN-…,RN-… --note …` | K1 das regras de uma demanda. |
| `ledger g3 ID --approve --note …` · `ledger publicada ID --refs CHAVE-1,CHAVE-2` | G3 e registro do que foi publicado no Jira. |
| `ledger c1 --espaco CHAVE --pagina ID\|novo --titulo … --nota …` · `ledger c1-lista` | C1 de uma página do Confluence. |
| `packet ID [--json]` | Pacote de contexto da demanda (Base, épico, lacunas). |
| `coverage ID [--json]` | Avaliar a cobertura antes da entrega. Repita até OK. |
| `kb buscar "termos"` · `kb regra RN-…` | Consultar a Base antes da web. |
| `kb validar` · `kb stats` · `kb lacunas` · `kb apontamentos [--abertos]` | Validar e inspecionar a Base. `validar` depois de qualquer mudança nela. |
| `metricas plano ARQUIVO` | Avaliar um plano de métricas. |
| `metricas ativar --arquivo … --nota …` | M1. |
| `metricas ativos [--json]` · `metricas avaliar --monitor M-NNN --valor N [--fonte … --consulta …]` | Leituras devidas dos monitores. |
| `metricas alertas [--dias N]` · `metricas resumo [--dias N]` · `metricas encerrar --monitor … --nota …` · `metricas validar` | Alertas, resumo, encerrar e validar monitores. |
| `okr validar [ARQUIVO] [--grupo ARQUIVO]` · `okr listar [--ativos] [--nivel grupo\|time]` | Avaliar e listar OKRs; `--grupo` confere o alinhamento com os ids do grupo. |
| `portfolio validar` · `portfolio agregar --entrada JSON [--janela N --parado N --gravar]` · `portfolio ultimo [--resumo\|--tabela\|--executivo]` | Só GPM: times do portfólio, agregação do resultado JQL por time (sem pessoas) e o último retrato para a abertura, o semanal e a diretoria. |
| `memoria listar` · `memoria gravar --escopo time\|pessoal\|global --nome … --descricao … --aprendi … --evidencia … --nota …` · `memoria revogar --nome … --motivo … --nota …` | Memória. Gravar e revogar só com o sim. |
| `report [--json]` · `digest` | Resumo da entrega; digest rolante depois do aceite. |
| `ajuda [--json]` | Lista de comandos. |

## Atualizar, desinstalar e versões

### Atualizar

```bash
claude plugin marketplace update tia-marketplace
```

```bash
claude plugin update tia@tia-marketplace
```

Reinicie o Claude Code. Na sessão seguinte o ambiente Python é recriado sozinho se os requisitos mudaram. Depois
diga "Tia, atualiza a configuração" para comparar os modelos copiados (`modelo_versao`) com os do plugin e
decidir arquivo a arquivo. `.tia/config.yaml` e `CLAUDE.md` nunca são trocados por script.

### Desinstalar

Rode no seu terminal (o hook nega esse comando vindo do agente):

```bash
claude plugin uninstall tia@tia-marketplace --scope project
```

Por padrão o Claude Code apaga também a pasta de dados do plugin (`~/.claude/plugins/data/tia-tia-marketplace/`,
onde fica o ambiente Python). `--keep-data` preserva. O conteúdo do projeto (`tia/`, `.tia/`) e o `~/.tia/`
continuam seus. Sem o plugin, a pasta vira uma pasta comum.

### Versões

- Histórico: [CHANGELOG.md](CHANGELOG.md).
- Decisões de desenho: [docs/decisoes.md](docs/decisoes.md).
- Roteiro do piloto do perfil GPM: [docs/piloto-gpm.md](docs/piloto-gpm.md).
- Migração de um workspace da Ada (até 0.1.1): veja a entrada 0.2.0 do [CHANGELOG](CHANGELOG.md).

## Desenvolvimento

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

```bash
.venv/Scripts/python.exe -m pytest -q
```

```bash
claude plugin validate --strict .
```

No macOS/Linux, troque `.venv/Scripts/python.exe` por `.venv/bin/python`. Para mexer no plugin com a fiscalização
desligada, use o [modo manutenção](#modo-manutenção-tia_dev).

## Uso

Uso interno do Time de Produto. Sem licença por ora.
