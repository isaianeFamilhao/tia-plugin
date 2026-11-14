# Changelog

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
