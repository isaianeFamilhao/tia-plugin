#!/usr/bin/env bash
# Lançador dos scripts da Tia. As skills chamam:
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh" <script> [args]      ex.: tia.sh kb buscar "limite"
#
# Acha o venv do plugin (CLAUDE_PLUGIN_DATA, ou o caminho que o hook deixou em .tia/cache/plugin-data) e roda
# scripts/<script>.py. `doctor` e `configurar` rodam com o Python do sistema se o venv ainda não existe.
# `tia.sh bootstrap` cria o venv (o hook deixa o caminho dos dados em .tia/cache/plugin-data).
# `--data <pasta>` antes do script informa a pasta de dados do plugin explicitamente.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
data="${CLAUDE_PLUGIN_DATA:-${TIA_PLUGIN_DATA:-}}"
if [ "${1:-}" = "--data" ]; then
  case "${2:-}" in ""|*'${'*) ;; *) data="$2" ;; esac   # variável não substituída na skill: ignora
  shift 2
fi
script="${1:-}"
shift 2>/dev/null
case "$script" in
  ""|-h|--help) echo "uso: tia.sh [--data <pasta>] <script> [args]  (scripts: bootstrap $(cd "$here" && ls *.py | grep -v '^_' | sed 's/\.py$//' | tr '\n' ' '))"; exit 0 ;;
esac
if [ "$script" != "bootstrap" ] && { ! printf '%s' "$script" | grep -qE '^[a-z_]+$' || [ ! -f "$here/$script.py" ]; }; then
  echo "[tia] script desconhecido: $script" >&2; exit 2
fi

if [ -z "$data" ]; then
  d="${CLAUDE_PROJECT_DIR:-$PWD}"
  while [ -n "$d" ]; do
    if [ -f "$d/.tia/cache/plugin-data" ]; then data="$(head -n 1 "$d/.tia/cache/plugin-data" | tr -d '\r\n')"; break; fi
    [ "$d" = "/" ] || [ "$d" = "$(dirname "$d")" ] && break
    d="$(dirname "$d")"
  done
fi
if [ "$script" = "bootstrap" ]; then
  [ -n "$data" ] || { echo "[tia] pasta de dados do plugin desconhecida: abra uma sessão neste projeto (o hook informa o caminho) e tente de novo." >&2; exit 3; }
  exec bash "$here/bootstrap.sh" "$data" "$@"
fi
py=""
if [ -n "$data" ]; then
  for c in "$data/venv/Scripts/python.exe" "$data/venv/bin/python"; do [ -f "$c" ] && { py="$c"; break; }; done
fi
if [ -z "$py" ]; then
  case "$script" in
    doctor|configurar)
      for cand in "py -3.12" "py -3" "python3.12" "python3" "python"; do
        if $cand -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)" >/dev/null 2>&1; then py="$cand"; break; fi
      done
      [ -n "$py" ] || { echo "[tia] Python 3.12 não encontrado. Instale o Python 3.12 (python.org) e tente de novo." >&2; exit 3; }
      ;;
    *) echo "[tia] o ambiente Python da Tia ainda não existe. Abra uma sessão nova neste projeto (o início da sessão cria o ambiente) ou rode: bash \"$here/tia.sh\" doctor" >&2; exit 3 ;;
  esac
fi
export TIA_PLUGIN_DATA="$data"
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
case "$py" in
  "py -"*|python*) exec $py "$here/$script.py" "$@" ;;   # Python do sistema (comando com argumento)
  *) exec "$py" "$here/$script.py" "$@" ;;             # venv (caminho pode ter espaço)
esac
