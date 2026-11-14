# Ada · plugin do Claude Code

A **Ada** é uma assistente de produto para Product Managers. Ela transforma pedidos em **épicos e histórias
prontos para o time**, com critérios de aceite que cobrem as regras de negócio, cita de onde vem cada regra,
aponta o que ainda falta decidir e acompanha **nos dados** se o que foi entregue moveu as métricas. Consulta o
Confluence, o Jira e as fontes de dados conectadas, mantém uma Base de Conhecimento versionada e aprende como a
PM gosta de trabalhar. Nada é publicado ou alterado sem aprovação humana (gates).

**Motor no plugin, conteúdo no projeto.** O plugin traz skills, scripts, hooks, avaliadores e modelos. Cada
projeto (workspace) guarda o conteúdo do time em `ada/` e o estado da máquina em `.ada/`. A Ada só age onde
existe `.ada/config.yaml`; em qualquer outra pasta os hooks saem em silêncio.

## Pré-requisitos

- **Claude Code** (app desktop ou CLI). O Cowork carrega skills e hooks, mas a casa da Ada é o Claude Code.
- **Python 3.12** (python.org; marque "Add python.exe to PATH").
- **Git for Windows** (os hooks rodam em Git Bash).
- Acesso ao índice de pacotes do Python (pypi.org) na primeira sessão. Rede com proxy: veja "Problemas".
- Recomendado: conector Atlassian (Confluence e Jira) na conta do Claude.

## Instalar

```bash
claude plugin marketplace add <caminho ou URL do repositório ada-plugin>
```

```bash
claude plugin install ada@ada-marketplace
```

Para testar sem instalar: `claude --plugin-dir <ada-plugin>/plugins/ada`.

## Primeira sessão num projeto

1. Abra o Claude Code na pasta do projeto e diga **"Ada, configurar"** (ou `/ada:configurar`).
2. A Ada propõe site, projeto do Jira e espaços do Confluence a partir do conector Atlassian. Só **um** espaço é
   `manter` (o do time, alterado só com C1); os demais são somente leitura. Com o seu sim, ela cria:
   `.ada/config.yaml` (marcador e config do time), `ada/` (fila, Base de Conhecimento, padrões, Memória),
   o `CLAUDE.md` do time (ou `ada/CLAUDE.md` + `@ada/CLAUDE.md`, se o projeto já tiver um) e o bloco no `.gitignore`.
3. Ela cria o ambiente Python do plugin (`${CLAUDE_PLUGIN_DATA}/venv`), o que leva alguns minutos na primeira vez,
   e roda o diagnóstico.
4. Preencha o `CLAUDE.md` do time e o padrão de épico (`ada/kb/padroes/epico.md`), alimente a Base
   (`/ada:base`) e escreva a primeira demanda em `ada/demandas.yaml`.
5. Commite `ada/`, `.ada/config.yaml`, `.ada/ledger.json`, `.ada/monitoramento/` e o `CLAUDE.md`.
   Ficam fora do git: `.ada/logs/`, `.ada/cache/`, `ada/memoria/pessoal/`.

Depois disso, todo dia: **"Ada, bom dia"**.

## Comandos

| Comando | O que faz |
|---|---|
| `/ada:abrir` · "Ada, bom dia" | Abertura: alertas de métricas, gates pendentes, fila, apontamentos; encaminha pedidos "Ada, …" |
| `/ada:demanda D-NNN` | Executa uma demanda aprovada: pesquisa, épico, histórias, cobertura, revisão cética, entrega |
| `/ada:metricas` | Métricas de outcome com checagem de dados e tracking spec |
| `/ada:okr` | OKRs pragmáticos, calibrados pelo momento do time |
| `/ada:report diario\|semanal` | Pulso do dia ou visão de OKR cruzando entrega e dados |
| `/ada:base` | Confere a Base de Conhecimento contra Confluence/Jira (K1) |
| `/ada:confluence` | Consulta, aponta dúvidas e mantém o espaço do time (C1) |
| `/ada:configurar [atualizar]` | Prepara o projeto ou compara os modelos copiados com os do plugin |
| `/ada:ajuda` | Lista completa: skills, atalhos, gates, scripts |

"Ada, <frase>" no **início** da mensagem chama a skill certa ("Ada, roda o semanal" → `/ada:report semanal`).
"nada, …" e "cada, …" não disparam. Atalhos pessoais vão no seu `pessoal.md`.

**Gates** (só com a sua resposta explícita): G1 aprovar a demanda · G2 aceitar a entrega · K1 mudança na Base ·
G3 publicar no Jira · C1 alterar página do espaço do time · M1 ativar monitoramento · Memória guardar um aprendizado.

## Personalização e Memória

- **`pessoal.md`** — você escreve, sem gate: estilo, formatos, atalhos. Em `~/.ada/pessoal.md` (todos os
  projetos) e `ada/memoria/pessoal/pessoal.md` (só este projeto). Ganha do time em estilo, **nunca em política**.
- **Memória** — o que a Ada aprende com você, um arquivo por aprendizado, só com o seu sim ("Guardo para você ou
  para o time?"): `ada/memoria/time/` (versionada), `ada/memoria/pessoal/`, `~/.ada/memoria/`. Revogar não apaga.
- **Precedência:** princípios da Ada > políticas do time > pessoal do workspace > pessoal global.

## Configuração em três camadas

1. **Inegociável (só no plugin):** princípios, gates, hooks, contrato da Base, formato do ledger, escopo de escrita,
   escrita no Jira/Confluence/dados, espaços fora do `manter` somente leitura.
2. **Padrão com ajuste:** tamanhos, retrabalho, palavras vagas, regex de fontes de dados, validade do C1. Ajuste
   repetindo só a chave em `.ada/config.yaml` (deep merge; lista substitui lista).
3. **Do time:** site, cloud_id, projeto Jira, espaços e políticas, padrões de épico e história, `CLAUDE.md`,
   modelo e esforço. Copiado no configurar; depois só a humana edita.

## Proteções

Escrita do agente só em `ada/**` (md, yaml, yml, json), exceto `ada/demandas.yaml` e o contrato da Base. Negados:
escrever em `.ada/**` (só scripts), `CLAUDE.md`, settings, cache e dados do plugin, e qualquer comando que desligue a
fiscalização (`claude plugin disable|uninstall`, `enabledPlugins`, `disableAllHooks`, `HARNESS_DEV`). Jira só
leitura até o G3; fontes de dados só leitura. Fail-closed: dentro do workspace, hook com erro nega a ação.

## Atualizar

```bash
claude plugin marketplace update ada-marketplace
```

```bash
claude plugin update ada@ada-marketplace
```

Na sessão seguinte o ambiente Python é recriado sozinho se os requisitos mudaram. Diga **"Ada, atualiza a
configuração"** para comparar os modelos copiados (`modelo_versao`) com os do plugin e decidir arquivo a arquivo.

## Desinstalar

```bash
claude plugin uninstall ada@ada-marketplace
```

Por padrão o Claude Code apaga também `${CLAUDE_PLUGIN_DATA}` (o ambiente Python); `--keep-data` preserva.
O conteúdo do projeto (`ada/`, `.ada/`) e o `~/.ada/` continuam seus. Sem o plugin, a pasta vira uma pasta comum.

## Problemas

Rode o diagnóstico: `/ada:abrir` já roda; manualmente, `bash "<plugin>/scripts/ada.sh" doctor`.

| Sintoma | O que fazer |
|---|---|
| "ambiente Python da Ada ainda não existe" | `bash "<plugin>/scripts/ada.sh" bootstrap` ou abra uma sessão nova |
| Bloqueio de rede/proxy no bootstrap | Peça ao suporte para liberar pypi.org e files.pythonhosted.org ou configurar `HTTPS_PROXY` |
| "Git Bash não encontrado" | Instale o Git for Windows e abra o Claude Code de novo |
| Modelos desatualizados | "Ada, atualiza a configuração" |

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

Para mexer no plugin com a fiscalização desligada, quem abre o Claude Code define `ADA_DEV=1` no próprio terminal
(o agente nunca define). Decisões de desenho: `docs/decisoes.md`. Histórico: `CHANGELOG.md`.
