# Changelog

## 0.3.0 · 2026-11-16

A Tia passa a ter dois perfis, **PM** e **GPM**, com o mesmo motor e os mesmos princípios (D-PM-28 a D-PM-32).
Compatível com a 0.2.0: pasta sem a chave `perfil` continua PM e nada muda para ela.

**Perfis (Fase 1)**

- Chave `perfil: pm|gpm` em `.tia/config.yaml` (do time; sem a chave, `pm`). Valor inválido é `FALHA` no `doctor`.
- Princípios neutros: copiloto pessoal de quem lidera produto (PM ou GPM); "a humana" nas regras gerais. Gates e
  regras fixas iguais; o resumo injetado segue abaixo de 9.000 caracteres.
- Habilidades por perfil (tabela `HABILIDADES` no plugin): `demanda` só no PM, `portfolio` só no GPM, as demais
  nos dois. `/tia:ajuda` e os atalhos "Tia, …" só mostram e encaminham as do perfil; habilidade do outro perfil
  responde em uma linha.
- Fila só no PM: `ledger iniciar` e `/tia:demanda` recusam numa pasta GPM; o `doctor` não cobra fila no GPM.
- `/tia:configurar` pergunta o perfil. No GPM: vários projetos do Jira, zero ou um espaço `manter`, sem fila
  (sem `tia/demandas.yaml` nem `tia/demandas/`) e `CLAUDE.md` próprio (modelo `CLAUDE.gpm.md`).

**Portfólio do GPM, só com o Jira (Fase 2)**

- `portfolio.times: [{nome, jira_projeto, board?}]` na config do GPM, proposto no configurar
  (`--portfolio "Nome|CHAVE|board"`). `portfolio validar` e o `doctor` acusam time sem projeto e projeto repetido.
- `portfolio agregar`: resultado das consultas JQL → por time, em andamento por etapa, travados (sinalizados,
  bloqueados ou sem movimento há `--parado` dias, padrão 5) e concluídos na janela (`--janela`, padrão 7). Lista
  fechada de campos; responsável e qualquer campo de pessoa são descartados antes de gravar.
- `/tia:portfolio [janela] [time]` (só GPM): JQL só leitura por time → agregação → situação por time com causa
  provável e próximo passo, em `tia/relatorios/<data>-portfolio.md` (o retrato agregado fica em `.json` ao lado).
- Abertura do GPM: alertas, times com travas e OKRs do grupo em risco, nessa ordem, no lugar da fila e das
  aprovações de demanda.

**OKRs do grupo (Fase 3)**

- OKR com `nivel: grupo|time` (ausente = time) e `id` por objetivo (`OBJ-NN`). O `alinhamento` de um OKR de time
  cita o id do grupo; id inexistente reprova, texto livre segue valendo com aviso.
- `/tia:okr` no perfil GPM cria e revisa os OKRs do grupo com o mesmo método.

**Relatórios do GPM (Fase 4)**

- `/tia:report semanal` no GPM é o semanal de portfólio: tabela por time (WIP, travas, entregas, situação), OKRs
  do grupo e até 3 recomendações com evidência e trade-off.
- `/tia:report diretoria` (só GPM): formato executivo curto (situação, riscos, decisões pedidas) em
  `tia/relatorios/<data>-diretoria.md`. Nada é enviado nem publicado sem pedido; publicar é documento ou o
  espaço `manter` com C1.

**Desvios em relação ao plano**

- Comandos que o plano não previa: `portfolio ultimo --resumo` (abertura), `--tabela` (semanal) e `--executivo`
  (diretoria), que leem o último retrato gravado; `okr validar --grupo ARQUIVO`, para conferir na pasta de um
  time os ids do grupo; `okr listar --nivel grupo|time`.
- A abertura do GPM lê só os OKRs de nível grupo; OKR de time não entra no briefing.
- No GPM, `configurar criar` aceita `--jira` opcional (padrão: os projetos dos times do portfólio).
- `/tia:report diretoria` numa pasta PM responde em uma linha; o diário e o semanal do PM não mudaram.
- A consolidação dos OKRs dos times no GPM ficou de fora (depende de decisão pendente, abaixo).

**Adiado: Fase 5 (app de WIP).** O painel de WIP ainda não existe e não se sabe se terá MCP ou API. Nesta versão
o portfólio usa só o Jira. Quando o app existir, entra como fonte de dados (D-PM-30): só leitura, agregado, sem
dado pessoal.

**Pendentes (sem decisão)**

- De onde vêm os OKRs dos times para o GPM consolidar (app, Confluence ou o GPM informa a cada ciclo).
- Como a Tia acessa o app de WIP (MCP ou API) quando ele existir.
- WIP de produto de cada PM não aparece para o GPM: depende do app, e demanda que não foi publicada no Jira não
  aparece no portfólio (limite conhecido).

## 0.2.0 · 2026-11-14

A assistente passa a se chamar **Tia** (D-PM-27). Quebra compatibilidade: as entradas abaixo desta versão
descrevem a Ada com os nomes da época.

- Plugin `tia@tia-marketplace`, skills `/tia:*`, lançador `scripts/tia.sh`, repositório `tia-plugin`.
- Workspace: marcador `.tia/config.yaml`, conteúdo em `tia/`, máquina em `.tia/`; Memória global em `~/.tia/`.
- Variáveis `TIA_DEV`, `TIA_ROOT`, `TIA_HOME`, `TIA_PLUGIN_DATA` e `TIA_HOOK_TIMEOUT`. `HARNESS_DEV`,
  `HARNESS_ROOT` e `HARNESS_HOOK_TIMEOUT` saem, e `ADA_*` não vale mais.
- Chamado "Tia, …" só no início da mensagem; "Ada, …" não dispara mais nada, nem "garantia, …" ou "notícia, …".
- Mensagens dos hooks com o prefixo `[tia]`.
- Migração de um workspace da Ada: `git mv ada tia`, `git mv .ada .tia`, trocar caminhos e nome no `CLAUDE.md`,
  no `.gitignore` e no conteúdo, e instalar o plugin novo (o ambiente Python é recriado no bootstrap).

## 0.1.1 · 2026-11-14

Correções do hook encontradas no primeiro uso real (D-PM-26).

- **Commit do workspace deixou de ser negado.** A mensagem de commit/tag (`-m`, `-F`, heredoc) e o texto entre
  aspas não contam mais como comando: `git commit -m "kb/ -> ada/kb/; ada/demandas.yaml"` volta a pedir
  confirmação. Aspas que são código de outro interpretador (`bash -c "…"`, `python -c "…"`) continuam conferidas.
- **Ler não é desligar.** Citar ou ler `hook.sh`, `hooks.json`, settings, `enabledPlugins`, `ADA_DEV` ou o ledger
  passa. Negado só o que desliga: `claude plugin disable|uninstall|remove`, `claude config set` de
  `disableAllHooks`/`enabledPlugins`, definir `ADA_DEV`/`HARNESS_DEV` (`export`, `set`, `$env:`, `VAR=`, `setx`,
  `reg add`, `SetEnvironmentVariable`) e gravar em hooks, settings ou no ledger.
- **Sem o ambiente Python, a sessão não trava.** Ficam negados só as ferramentas de escrita, a escrita no
  Jira/Confluence e o shell que não seja leitura simples ou `ada.sh doctor|configurar|bootstrap`. Leitura,
  ferramentas do app e agentes passam.
- **PowerShell.** As mensagens do hook trazem o comando pronto para o Git Bash e para o PowerShell
  (`& "C:\Program Files\Git\bin\bash.exe" "<ada.sh>" <comando>`); o README também. Mensagens com caminhos do
  Windows saem como JSON válido.
- Testes: regressões dos casos reais e prova de que continua negado gravar em `.ada/` pelo shell,
  `claude plugin disable` e `export ADA_DEV=1`. A suíte ignora `ADA_DEV` ligado na máquina.

## 0.1.0 · 2026-11-13

Primeira versão como plugin do Claude Code, a partir do harness `harness-cowork`.

- **Motor no plugin, conteúdo no workspace.** Marcador `.ada/config.yaml`; conteúdo em `ada/`, máquina em `.ada/`.
  Fora de workspace, os hooks saem em silêncio (sem Python).
- **Raízes separadas** (`CODE_ROOT` do plugin, `DATA_ROOT` do workspace) em todos os scripts.
- **Config em três camadas:** inegociável (plugin), padrão com sobreposição (deep merge) e do time.
  `secoes_epico` no frontmatter do padrão de épico do workspace; `kb.py validar` confere com o config.
- **Hooks do plugin** (`hooks/hooks.json`): SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop.
  Venv em `${CLAUDE_PLUGIN_DATA}/venv` criado pelo bootstrap; lançador `scripts/ada.sh`.
- **Proteções novas:** escrita só em `ada/**`; `.ada/`, `CLAUDE.md`, settings e dados do plugin negados; negado
  desligar a fiscalização; fail-closed só dentro do workspace.
- **Princípios** injetados no início da sessão (teto de 9.000 caracteres); texto completo em `/ada:abrir`.
- **Memória** com um arquivo por aprendizado em três escopos (time, pessoal, global), revogação e migração do
  `kb/memoria-pm.md` antigo; `pessoal.md` sem gate.
- **Skills pelo verbo:** `abrir`, `demanda`, `base`, `confluence`, `metricas`, `okr`, `report`, `configurar`,
  `ajuda` (sai `pm-init`). Aliases "Ada, <frase>" no início da mensagem.
- **`/ada:configurar`** cria só o que falta e mostra diff dos modelos (`modelo_versao`) em `atualizar`.
- **`doctor`** para primeira instalação: Python 3.12, Git Bash, ambiente do plugin, proxy, modelos.
- **Dependências** separadas: `requirements-runtime.txt` (PyYAML, jsonschema) × `requirements-dev.txt` (pytest).
- Fontes passam a `SRC-<2 a 4 letras>-NNN`; `epicos.md` pode estar em qualquer área da Base.
