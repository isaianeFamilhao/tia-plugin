#!/usr/bin/env bash
# Cria (ou recria) o venv da Ada em <dados do plugin>/venv a partir de requirements-runtime.txt.
#
#   bash bootstrap.sh <CLAUDE_PLUGIN_DATA> [--force]
#
# Pré-requisito: Python 3.12+ na máquina (py -3.12, python3.12, python3 ou python). Precisa de acesso ao
# índice de pacotes (pip). Idempotente: se o venv existe e o hash dos requisitos bate, não faz nada.
# A última linha da saída é a mensagem para a PM.
data="${1:-}"
force="${2:-}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
req="$here/../requirements-runtime.txt"
[ -n "$data" ] || { echo "pasta de dados do plugin não informada"; exit 1; }
[ -f "$req" ] || { echo "requirements-runtime.txt ausente no plugin"; exit 1; }
mkdir -p "$data" || { echo "não consegui criar $data"; exit 1; }
hash="$(cksum <"$req" | cut -d' ' -f1)"
venv="$data/venv"
vpy() { for c in "$1/Scripts/python.exe" "$1/bin/python"; do [ -f "$c" ] && { printf '%s' "$c"; return 0; }; done; return 1; }

if [ -z "$force" ] && vpy "$venv" >/dev/null && [ "$(cat "$venv/.ada-req-hash" 2>/dev/null)" = "$hash" ]; then
  echo "ambiente Python da Ada já pronto"; exit 0
fi

# Um bootstrap por vez (duas sessões abrindo juntas).
lock="$data/.bootstrap.lock"
if ! mkdir "$lock" 2>/dev/null; then
  echo "outro bootstrap em andamento; abra a sessão de novo em alguns minutos"; exit 1
fi
trap 'rm -rf "$lock"' EXIT

base=""
for cand in "py -3.12" "py -3" "python3.12" "python3" "python"; do
  if $cand -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)" >/dev/null 2>&1; then base="$cand"; break; fi
done
[ -n "$base" ] || { echo "Python 3.12 não encontrado. Instale o Python 3.12 (python.org, marque Add to PATH) e abra a sessão de novo"; exit 1; }

tmp="$data/venv.novo"
rm -rf "$tmp"
$base -m venv "$tmp" >/dev/null 2>&1 || { echo "falha ao criar o venv com $base"; rm -rf "$tmp"; exit 1; }
tpy="$(vpy "$tmp")" || { echo "venv criado sem python"; rm -rf "$tmp"; exit 1; }
if ! "$tpy" -m pip install --disable-pip-version-check --no-input -q -r "$req" >"$data/bootstrap.log" 2>&1; then
  echo "falha no pip install (sem internet ou proxy?). Detalhes em $data/bootstrap.log"; rm -rf "$tmp"; exit 1
fi
printf '%s' "$hash" >"$tmp/.ada-req-hash"
rm -rf "$venv.velho"; [ -d "$venv" ] && mv "$venv" "$venv.velho"
mv "$tmp" "$venv" || { echo "não consegui ativar o venv novo"; exit 1; }
rm -rf "$venv.velho"
echo "ambiente Python da Ada criado em $venv"
