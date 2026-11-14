#!/usr/bin/env bash
# Wrapper dos hooks da Tia (plugin). Chamado pelo hooks/hooks.json:
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/hook.sh" <session_start|prompt|pretool|posttool|stop> [python]
#
# Ordem das decisões (antes de qualquer Python):
# 1. Sem `.tia/config.yaml` em $CLAUDE_PROJECT_DIR (ou no cwd): não é workspace da Tia → sai em silêncio
#    (exit 0, sem saída), mesmo sem venv. Exceção: prompt que começa com "Tia," → injeta o convite para
#    configurar (ou a skill tia:configurar, se o pedido for esse).
# 2. Dentro do workspace, sem o venv do plugin: SessionStart cria o venv (bootstrap.sh); PreToolUse nega só
#    as ferramentas de escrita, a escrita no Jira/Confluence e o shell que não seja leitura simples ou
#    tia.sh doctor/configurar/bootstrap. O resto (leitura, ferramentas do app, agentes) passa.
# 3. Com venv: chama hooks.py com tempo máximo. Python falhou → nega (PreToolUse) ou avisa (SessionStart).
# TIA_DEV=1 no ambiente de quem abriu o Claude Code (manutenção do plugin) desliga o fail-closed.
# Só usa bash, grep, sed, head, tr, cygpath (se houver) e timeout (se houver).

event="${1:-}"
py="${2:-}"
limit="${TIA_HOOK_TIMEOUT:-25}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
root="${TIA_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
input="$(cat)"
dev=""
if [ "${TIA_DEV:-}" = "1" ]; then dev=1; fi

json_str() {  # texto → conteúdo de string JSON (barras invertidas e aspas escapadas, sem quebras)
  printf '%s' "$1" | tr '\r\n\t' '   ' | sed 's/\\/\\\\/g; s/"/\\"/g'
}
ctx() {  # $1 = evento, $2 = texto
  printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}' "$1" "$(json_str "$2")"
}
deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$(json_str "[tia] $1")"
}
prompt_text() {  # campo "prompt" do JSON (o início basta para reconhecer o chamado)
  printf '%s' "$input" | tr '\r\n' '  ' | grep -o '"prompt"[[:space:]]*:[[:space:]]*"[^"]*' | head -n 1 \
    | sed 's/^"prompt"[[:space:]]*:[[:space:]]*"//'
}
como_rodar() {  # $1 = subcomando do tia.sh → comando pronto no Git Bash e, no Windows, no PowerShell
  sh="$here/tia.sh"
  if command -v cygpath >/dev/null 2>&1; then
    # bin\bash.exe do Git (não usr\bin): é o que monta o PATH com sed, grep e cksum quando chamado do PowerShell.
    wbash=""
    gitroot="$(cygpath -m / 2>/dev/null)"
    for cand in "${gitroot%/}/bin/bash.exe" "C:/Program Files/Git/bin/bash.exe"; do
      if [ -f "$cand" ]; then wbash="$(cygpath -w "$cand" 2>/dev/null)"; break; fi
    done
    [ -n "$wbash" ] || wbash='C:\Program Files\Git\bin\bash.exe'
    printf 'no Git Bash: bash "%s" %s; no PowerShell: & "%s" "%s" %s' "$sh" "$1" "$wbash" "$(cygpath -w "$sh")" "$1"
  else
    printf 'bash "%s" %s' "$sh" "$1"
  fi
}

# ---------------------------------------------------------------- 1. marcador
if [ ! -f "$root/.tia/config.yaml" ]; then
  if [ "$event" = "prompt" ]; then
    p="$(prompt_text)"
    if printf '%s' "$p" | grep -qiE '^[[:space:]]*Tia,[[:space:]]*(configura|configurar|instala|instalar|inicializa|inicializar|prepara|preparar)([^[:alnum:]]|$)'; then
      ctx UserPromptSubmit "[tia] Pedido de configuração: invoque a skill tia:configurar (cria .tia/config.yaml e a pasta tia/ neste projeto, com aprovação da PM)."
    elif printf '%s' "$p" | grep -qiE '^[[:space:]]*Tia,'; then
      ctx UserPromptSubmit "[tia] Esta pasta ainda não é um workspace da Tia (falta .tia/config.yaml). Responda em uma linha, sem saudação nem exclamação, oferecendo configurar (a PM diz: Tia, configurar). Não execute o pedido antes disso."
    fi
  fi
  exit 0
fi

# ---------------------------------------------------------------- 2. venv do plugin
data="${CLAUDE_PLUGIN_DATA:-}"
if [ -n "$data" ]; then  # o lançador (tia.sh), rodado pelo Bash do agente, não recebe a variável: deixa o caminho
  mkdir -p "$root/.tia/cache" 2>/dev/null && printf '%s\n' "$data" >"$root/.tia/cache/plugin-data" 2>/dev/null
elif [ -f "$root/.tia/cache/plugin-data" ]; then
  data="$(head -n 1 "$root/.tia/cache/plugin-data" | tr -d '\r\n')"
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
    if [ "$want" != "$(cat "$data/venv/.tia-req-hash" 2>/dev/null)" ]; then
      bash "$here/bootstrap.sh" "$data" >/dev/null 2>&1
      py="$(find_py)"
    fi
  fi
fi

# Shell sem venv: passa só o lançador (doctor, configurar, bootstrap) e a leitura simples.
LEITURA='^(ls|dir|pwd|cd|cat|type|head|tail|wc|sort|uniq|echo|printf|grep|rg|findstr|which|where|printenv|git[[:space:]]+(status|log|diff|show|ls-files|branch|check-ignore|rev-parse)|Get-ChildItem|Get-Content|Get-Location|Set-Location|Select-String|Select-Object|Sort-Object|Measure-Object|Write-Output|Test-Path)([[:space:]]|$)'
# Mesma lista do inegociável atlassian.ferramentas_escrita_regex (modelos/config.padrao.yaml; o teste confere).
ATLASSIAN_ESCRITA='__(create|edit|update|transition|add|delete)[A-Za-z]*(Jira|Confluence|Issue|Page|Comment|Worklog|Compass|Link)'
comando() {  # campo "command" do JSON, com \n como separador e \" como aspas
  printf '%s' "$input" | tr '\r\n' '  ' | grep -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' | head -n 1 \
    | sed 's/^"command"[[:space:]]*:[[:space:]]*"//; s/"$//; s/\\n/;/g; s/\\"/"/g'
}
leitura_simples() {
  c="$(comando)"
  [ -n "$(printf '%s' "$c" | tr -d '[:space:];')" ] || return 1
  c="$(printf '%s' "$c" | sed 's#2>&1##g; s#2>[[:space:]]*/dev/null##g; s#2>[[:space:]]*\$null##g; s/&&/;/g; s/||/;/g')"
  case "$c" in *'`'*|*'$('*|*'>'*|*'&'*) return 1 ;; esac
  ! printf '%s' "$c" | tr ';|' '\n\n' | sed 's/^[[:space:]]*//' | grep -v '^$' | grep -qvE "$LEITURA"
}

if [ -z "$py" ]; then
  if [ "$event" = "session_start" ] && [ -n "$data" ] && [ -f "$here/bootstrap.sh" ]; then
    msg="$(bash "$here/bootstrap.sh" "$data" 2>&1 | tail -n 1 | tr -d '"\\' | tr '\r\n\t' '   ')"
    py="$(find_py)"
    if [ -z "$py" ]; then
      ctx SessionStart "[tia] ALERTA: o ambiente Python da Tia não foi criado ($msg). Até resolver, escrita e shell ficam negados neste projeto. Diagnóstico: $(como_rodar doctor)"
      exit 0
    fi
  else
    [ -n "$dev" ] && exit 0
    case "$event" in
      pretool)
        tool="$(printf '%s' "$input" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')"
        case "$tool" in
          Write|Edit|MultiEdit|NotebookEdit) ;;
          Bash|PowerShell)
            if printf '%s' "$input" | grep -qE 'tia\.sh(\\?["'"'"'])?[[:space:]]+(--data[[:space:]]+[^[:space:]]+[[:space:]]+)?(doctor|configurar|bootstrap)'; then exit 0; fi
            leitura_simples && exit 0 ;;
          mcp__*)
            printf '%s' "$tool" | grep -qiE "$ATLASSIAN_ESCRITA" || exit 0 ;;
          *) exit 0 ;;
        esac
        deny "o ambiente Python da Tia ainda não existe: escrita, escrita no Jira/Confluence e comandos que não sejam leitura ficam negados até o bootstrap. Crie agora (ou abra uma sessão nova): $(como_rodar bootstrap). Diagnóstico: $(como_rodar doctor)"
        ;;
      session_start)
        ctx SessionStart "[tia] ALERTA: pasta de dados do plugin desconhecida; ambiente Python não verificado. Diagnóstico: $(como_rodar doctor)"
        ;;
    esac
    exit 0
  fi
fi

# ---------------------------------------------------------------- 3. Python
errf="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/tia-hook.$$")"
rc=127
out=""
if [ -f "$here/hooks.py" ]; then
  if command -v timeout >/dev/null 2>&1; then
    out="$(printf '%s' "$input" | TIA_ROOT="$root" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 timeout "$limit" "$py" "$here/hooks.py" "$event" 2>"$errf")"
    rc=$?
  else
    out="$(printf '%s' "$input" | TIA_ROOT="$root" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 "$py" "$here/hooks.py" "$event" 2>"$errf")"
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
    deny "hook sem Python ($err): ação negada (fail-closed). Diagnóstico: $(como_rodar doctor)"
    ;;
  session_start)
    ctx SessionStart "[tia] ALERTA: hooks sem Python ($err). Ferramentas de escrita serão negadas. Diagnóstico: $(como_rodar doctor)"
    ;;
  *) ;;
esac
exit 0
