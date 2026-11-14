#!/usr/bin/env bash
# Wrapper dos hooks da Ada (plugin). Chamado pelo hooks/hooks.json:
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/hook.sh" <session_start|prompt|pretool|posttool|stop> [python]
#
# Ordem das decisões (antes de qualquer Python):
# 1. Sem `.ada/config.yaml` em $CLAUDE_PROJECT_DIR (ou no cwd): não é workspace da Ada → sai em silêncio
#    (exit 0, sem saída), mesmo sem venv. Exceção: prompt que começa com "Ada," → injeta o convite para
#    configurar (ou a skill ada:configurar, se o pedido for esse).
# 2. Dentro do workspace, sem o venv do plugin: SessionStart cria o venv (bootstrap.sh); PreToolUse nega
#    escrita e shell (exceto o doctor) até o venv existir. Fail-closed só dentro do workspace.
# 3. Com venv: chama hooks.py com tempo máximo. Python falhou → nega (PreToolUse) ou avisa (SessionStart).
# HARNESS_DEV=1 / ADA_DEV=1 no ambiente de quem abriu o Claude Code (manutenção do plugin) desliga o fail-closed.
# Só usa bash, grep, sed, head, tr e (se houver) timeout.

event="${1:-}"
py="${2:-}"
limit="${HARNESS_HOOK_TIMEOUT:-25}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
root="${ADA_ROOT:-${HARNESS_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}}"
input="$(cat)"
dev=""
if [ "${HARNESS_DEV:-}" = "1" ] || [ "${ADA_DEV:-}" = "1" ]; then dev=1; fi

ctx() {  # $1 = evento, $2 = texto (sem aspas duplas nem barras invertidas)
  printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}' "$1" "$2"
}
deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "[ada] $1"
}
prompt_text() {  # campo "prompt" do JSON (o início basta para reconhecer o chamado)
  printf '%s' "$input" | tr '\r\n' '  ' | grep -o '"prompt"[[:space:]]*:[[:space:]]*"[^"]*' | head -n 1 \
    | sed 's/^"prompt"[[:space:]]*:[[:space:]]*"//'
}

# ---------------------------------------------------------------- 1. marcador
if [ ! -f "$root/.ada/config.yaml" ]; then
  if [ "$event" = "prompt" ]; then
    p="$(prompt_text)"
    if printf '%s' "$p" | grep -qiE '^[[:space:]]*Ada,[[:space:]]*(configura|configurar|instala|instalar|inicializa|inicializar|prepara|preparar)([^[:alnum:]]|$)'; then
      ctx UserPromptSubmit "[ada] Pedido de configuração: invoque a skill ada:configurar (cria .ada/config.yaml e a pasta ada/ neste projeto, com aprovação da PM)."
    elif printf '%s' "$p" | grep -qiE '^[[:space:]]*Ada,'; then
      ctx UserPromptSubmit "[ada] Esta pasta ainda não é um workspace da Ada (falta .ada/config.yaml). Responda em uma linha oferecendo configurar (a PM diz: Ada, configurar). Não execute o pedido antes disso."
    fi
  fi
  exit 0
fi

# ---------------------------------------------------------------- 2. venv do plugin
data="${CLAUDE_PLUGIN_DATA:-}"
if [ -n "$data" ]; then  # o lançador (ada.sh), rodado pelo Bash do agente, não recebe a variável: deixa o caminho
  mkdir -p "$root/.ada/cache" 2>/dev/null && printf '%s\n' "$data" >"$root/.ada/cache/plugin-data" 2>/dev/null
elif [ -f "$root/.ada/cache/plugin-data" ]; then
  data="$(head -n 1 "$root/.ada/cache/plugin-data" | tr -d '\r\n')"
fi
find_py() {
  for cand in "$data/venv/Scripts/python.exe" "$data/venv/bin/python"; do
    if [ -f "$cand" ]; then printf '%s' "$cand"; return 0; fi
  done
  return 1
}
if [ -z "$py" ] && [ -n "$data" ]; then
  py="$(find_py)"
  # Plugin atualizado com requisitos novos: recria o venv no início da sessão.
  if [ -n "$py" ] && [ "$event" = "session_start" ] && [ -f "$here/../requirements-runtime.txt" ]; then
    want="$(cksum <"$here/../requirements-runtime.txt" | cut -d' ' -f1)"
    if [ "$want" != "$(cat "$data/venv/.ada-req-hash" 2>/dev/null)" ]; then
      bash "$here/bootstrap.sh" "$data" >/dev/null 2>&1
      py="$(find_py)"
    fi
  fi
fi

if [ -z "$py" ]; then
  if [ "$event" = "session_start" ] && [ -n "$data" ] && [ -f "$here/bootstrap.sh" ]; then
    msg="$(bash "$here/bootstrap.sh" "$data" 2>&1 | tail -n 1 | tr -d '"\\' | tr '\r\n\t' '   ')"
    py="$(find_py)"
    if [ -z "$py" ]; then
      ctx SessionStart "[ada] ALERTA: o ambiente Python da Ada não foi criado ($msg). Até resolver, escrita e shell ficam negados neste projeto. Diagnóstico: bash $here/ada.sh doctor"
      exit 0
    fi
  else
    [ -n "$dev" ] && exit 0
    case "$event" in
      pretool)
        tool="$(printf '%s' "$input" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')"
        case "$tool" in
          Read|Glob|Grep|LS|WebFetch|WebSearch|TodoWrite|Skill|ToolSearch|AskUserQuestion) exit 0 ;;
          Bash|PowerShell)
            if printf '%s' "$input" | grep -qE 'ada\.sh(\\?["'"'"'])?[[:space:]]+(--data[[:space:]]+[^[:space:]]+[[:space:]]+)?(doctor|configurar|bootstrap)'; then exit 0; fi ;;
        esac
        deny "o ambiente Python da Ada ainda não existe: escrita e comandos ficam negados até o bootstrap. Crie agora com: bash $here/ada.sh bootstrap (ou abra uma sessão nova). Diagnóstico: bash $here/ada.sh doctor"
        ;;
      session_start)
        ctx SessionStart "[ada] ALERTA: pasta de dados do plugin desconhecida; ambiente Python não verificado. Diagnóstico: bash $here/ada.sh doctor"
        ;;
    esac
    exit 0
  fi
fi

# ---------------------------------------------------------------- 3. Python
errf="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/ada-hook.$$")"
rc=127
out=""
if [ -f "$here/hooks.py" ]; then
  if command -v timeout >/dev/null 2>&1; then
    out="$(printf '%s' "$input" | ADA_ROOT="$root" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 timeout "$limit" "$py" "$here/hooks.py" "$event" 2>"$errf")"
    rc=$?
  else
    out="$(printf '%s' "$input" | ADA_ROOT="$root" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 "$py" "$here/hooks.py" "$event" 2>"$errf")"
    rc=$?
  fi
else
  echo "hooks.py não encontrado" >"$errf"
fi

if [ "$rc" -eq 0 ] && [ -z "$out" ]; then
  rc=125
  echo "o interpretador não produziu saída" >"$errf"
fi
if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then
  printf '%s' "$out"
  [ "$rc" -eq 2 ] && cat "$errf" >&2
  rm -f "$errf"
  exit "$rc"
fi

# ---------------------------------------------------------------- Python falhou (dentro do workspace)
err="rc=$rc $(head -c 240 "$errf" 2>/dev/null | tr '\r\n\t' '   ' | tr -d '"\\')"
rm -f "$errf"
[ -n "$dev" ] && exit 0
case "$event" in
  pretool)
    deny "hook sem Python ($err): ação negada (fail-closed). Diagnóstico: bash $here/ada.sh doctor"
    ;;
  session_start)
    ctx SessionStart "[ada] ALERTA: hooks sem Python ($err). Ferramentas de escrita serão negadas. Diagnóstico: bash $here/ada.sh doctor"
    ;;
  *) ;;
esac
exit 0
