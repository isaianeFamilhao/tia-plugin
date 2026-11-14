#!/usr/bin/env bash
# Wrapper fail-closed dos hooks do harness de produto (herdado do harness-lean, R-H1).
#
#   bash .harness/bin/hook.sh <session_start|pretool|posttool|stop> [python]
#
# O app roda o comando do hook em Git Bash, na raiz do projeto [V F0 do harness-lean]. Hook que sai
# com código diferente de 0/2 NÃO bloqueia nada. Por isso:
# - o Python é o do .venv do projeto (ou o 2º argumento), com tempo máximo;
# - se o Python não existir, falhar ou estourar o tempo, ESTE script decide sozinho: nega a ação
#   (PreToolUse) ou avisa (SessionStart). O Stop não prende a sessão por defeito do próprio hook.
# - HARNESS_DEV=1 (manutenção do harness) desliga o fail-closed.
# Só usa bash, head, tr e (se houver) timeout.

event="${1:-}"
py="${2:-}"
limit="${HARNESS_HOOK_TIMEOUT:-25}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
input="$(cat)"

if [ -z "$py" ] && [ -n "$here" ]; then
  root="$(cd "$here/../.." 2>/dev/null && pwd)"
  for cand in "$root/.venv/Scripts/python.exe" "$root/.venv/bin/python"; do
    if [ -f "$cand" ]; then py="$cand"; break; fi
  done
fi

errf="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/harness-hook.$$")"
rc=127
out=""
if [ -n "$py" ] && [ -n "$here" ] && [ -f "$here/hooks.py" ]; then
  if command -v timeout >/dev/null 2>&1; then
    out="$(printf '%s' "$input" | PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 timeout "$limit" "$py" "$here/hooks.py" "$event" 2>"$errf")"
    rc=$?
  else
    out="$(printf '%s' "$input" | PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 "$py" "$here/hooks.py" "$event" 2>"$errf")"
    rc=$?
  fi
else
  echo "python ou hooks.py não encontrado (python='$py')" >"$errf"
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

# ---------------------------------------------------------------- Python falhou
err="rc=$rc $(head -c 240 "$errf" 2>/dev/null | tr '\r\n\t' '   ' | tr -d '"\\')"
rm -f "$errf"
[ "${HARNESS_DEV:-}" = "1" ] && exit 0

reason="[harness] hook sem Python ($err): ação negada (fail-closed). Rode .harness/bin/doctor.py."
case "$event" in
  pretool)
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$reason"
    ;;
  session_start)
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}' \
      "[harness] ALERTA: hooks sem Python ($err). Ferramentas de escrita serão negadas. Rode doctor.py."
    ;;
  *) ;;
esac
exit 0
