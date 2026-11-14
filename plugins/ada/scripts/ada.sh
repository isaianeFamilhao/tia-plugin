#!/usr/bin/env bash
# Lançador dos scripts da Ada. As skills chamam:
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/ada.sh" <script> [args]      ex.: ada.sh kb buscar "limite"
#
# Acha o venv do plugin (CLAUDE_PLUGIN_DATA, ou o caminho que o hook deixou em .ada/cache/plugin-data) e roda
# scripts/<script>.py. `doctor` e `configurar` rodam com o Python do sistema se o venv ainda não existe.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
script="${1:-}"
shift 2>/dev/null
case "$script" in
  ""|-h|--help) echo "uso: ada.sh <script> [args]  (scripts: $(cd "$here" && ls *.py | grep -v '^_' | sed 's/\.py$//' | tr '\n' ' '))"; exit 0 ;;
esac
if ! printf '%s' "$script" | grep -qE '^[a-z_]+$' || [ ! -f "$here/$script.py" ] || [ "${script#_}" != "$script" ]; then
  echo "[ada] script desconhecido: $script" >&2; exit 2
fi

data="${CLAUDE_PLUGIN_DATA:-}"
if [ -z "$data" ]; then
  d="${CLAUDE_PROJECT_DIR:-$PWD}"
  while [ -n "$d" ]; do
    if [ -f "$d/.ada/cache/plugin-data" ]; then data="$(head -n 1 "$d/.ada/cache/plugin-data" | tr -d '\r\n')"; break; fi
    [ "$d" = "/" ] || [ "$d" = "$(dirname "$d")" ] && break
    d="$(dirname "$d")"
  done
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
      [ -n "$py" ] || { echo "[ada] Python 3.12 não encontrado. Instale o Python 3.12 (python.org) e tente de novo." >&2; exit 3; }
      ;;
    *) echo "[ada] o ambiente Python da Ada ainda não existe. Abra uma sessão nova neste projeto (o início da sessão cria o ambiente) ou rode: bash \"$here/ada.sh\" doctor" >&2; exit 3 ;;
  esac
fi
export ADA_PLUGIN_DATA="$data"
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
case "$py" in
  "py -"*|python*) exec $py "$here/$script.py" "$@" ;;   # Python do sistema (comando com argumento)
  *) exec "$py" "$here/$script.py" "$@" ;;             # venv (caminho pode ter espaço)
esac
