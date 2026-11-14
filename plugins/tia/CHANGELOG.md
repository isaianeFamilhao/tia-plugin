# Changelog

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
