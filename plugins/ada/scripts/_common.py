"""Utilitários comuns do harness de produto (Python 3.12+, PyYAML).

Herdado do harness-lean (commit e136ba0), enxugado para o harness de produto:
- `transcript_usage()`: uso por mensagem da transcrição JSONL, deduplicado por `message.id` [V F0];
- `atomic_write_text()`: escrita atômica em UTF-8/LF, com tentativas (Windows);
- `est_tokens()` / `fit_tokens()`: tokens ESTIMADOS [E] e recorte explícito (nunca em silêncio);
- `path_allowed()`: escopo de escrita por padrões glob.

Sem worktrees, branches de tarefa nem commits: a unidade de trabalho é a DEMANDA (D-NNN), executada
numa sessão só, supervisionada pelo humano.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Saída sempre em UTF-8 (o console do Windows usa cp1252/cp850 e quebrava os acentos), sem precisar
# de PYTHONIOENCODING no comando — o prefixo fazia o hook pedir confirmação à toa.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
HARNESS = REPO_ROOT / ".harness"
DEFAULT_CHARS_PER_TOKEN = 3.0  # calibrado na F3 do harness-lean (app desktop)

DEMAND_ID_RE = re.compile(r"^D-\d{3}$")
RULE_ID_RE = re.compile(r"^RN-[A-Z]{3}-\d{3}$")        # regra da kb
CANDIDATE_ID_RE = re.compile(r"^RC-\d{2,3}$")            # regra candidata, só da demanda
SOURCE_ID_RE = re.compile(r"^SRC-(EMP|IT|DEM)-\d{3}$")
JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


# ------------------------------------------------------------------ métricas da transcrição
def _context_of(usage: dict) -> int:
    return (int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
            + int(usage.get("cache_read_input_tokens") or 0))


def transcript_usage(path: str | Path | None) -> dict:
    """Soma o `message.usage` de cada resposta do assistente (deduplicado por `message.id`)."""
    out: dict = {"messages_with_usage": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                 "first_context_tokens": None, "last_context_tokens": None, "peak_context_tokens": None,
                 "models": []}
    if not path or not Path(path).exists():
        out["error"] = f"transcrição ausente: {path}"
        return out
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            msg = ev.get("message") if isinstance(ev, dict) else None
            if not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                continue
            mid = msg.get("id") or ev.get("uuid")
            if mid in seen:
                continue
            seen.add(mid)
            u = msg["usage"]
            out["messages_with_usage"] += 1
            for k in USAGE_KEYS:
                out[k] += int(u.get(k) or 0)
            out["thinking_tokens"] += int((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0)
            ctx = _context_of(u)
            if out["first_context_tokens"] is None:
                out["first_context_tokens"] = ctx
            out["last_context_tokens"] = ctx
            out["peak_context_tokens"] = max(ctx, out["peak_context_tokens"] or 0)
            model = msg.get("model")
            if model and not model.startswith("<") and model not in out["models"]:
                out["models"].append(model)
    return out


# ------------------------------------------------------------------ disco
def atomic_write_text(path: str | Path, text: str, retries: int = 5) -> None:
    """Grava em UTF-8/LF de forma atômica (temporário + fsync + os.replace, com tentativas)."""
    import os
    import tempfile
    import time

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = text.replace("\r\n", "\n")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(retries):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == retries - 1:
                    raise
                time.sleep(0.05 * (2 ** attempt))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: str | Path, obj: object) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def read_json(path: str | Path) -> object | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_yaml(path: str | Path):
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def now_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    from datetime import date

    return date.today().isoformat()


def load_config(root: Path | None = None) -> dict:
    return load_yaml((root or REPO_ROOT) / ".harness" / "config.yaml") or {}


# ------------------------------------------------------------------ tokens [E]
def est_tokens(text: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
    import math

    return math.ceil(len(text) / float(chars_per_token)) if text else 0


def fit_tokens(text: str, cap: int, label: str,
               chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> tuple[str, bool, int]:
    """Recorta `text` para `cap` tokens [E] com marcação explícita. Devolve (texto, recortado?, originais)."""
    original = est_tokens(text, chars_per_token)
    if original <= cap:
        return text, False, original
    marker = f"\n[RECORTADO pelo harness: {label} tinha ~{original} tokens [E]; teto {cap}]\n"
    budget = int((cap - est_tokens(marker, chars_per_token)) * chars_per_token)
    while budget > 0:
        head = text[:budget]
        nl = head.rfind("\n")
        if nl >= budget // 2:
            head = head[:nl]
        out = head.rstrip() + marker
        if est_tokens(out, chars_per_token) <= cap:
            return out, True, original
        budget -= max(1, int(chars_per_token))
    return marker.lstrip("\n")[: int(cap * chars_per_token)], True, original


# ------------------------------------------------------------------ caminhos e escopo
def norm_path(p: str | Path | None) -> str:
    """Caminho com `/`, sem barra final; `C:/x` e `/c/x` comparáveis (drive minúsculo)."""
    s = str(p or "").replace("\\", "/")
    s = re.sub(r"/+", "/", s).rstrip("/")
    m = re.match(r"^/([a-zA-Z])/(.*)$", s)
    if m:
        s = f"{m.group(1)}:/{m.group(2)}"
    if re.match(r"^[A-Za-z]:", s):
        s = s[0].lower() + s[1:]
    return s


def rel_to_root(root: Path, path: str) -> str | None:
    """Caminho relativo à raiz do repositório, ou None se estiver fora dela."""
    if not path:
        return None
    p = norm_path(path)
    r = norm_path(root)
    if not re.match(r"^[A-Za-z]:/|^/", p):  # relativo: já é relativo à raiz
        rel = p.lstrip("./")
    elif p.lower() == r.lower():
        return ""
    elif p.lower().startswith(r.lower() + "/"):
        rel = p[len(r) + 1:]
    else:
        return None
    if ".." in rel.split("/"):
        return None
    return rel


def glob_to_regex(pat: str) -> re.Pattern[str]:
    """`**` atravessa pastas, `*` não; sem diferenciar maiúsculas (Windows)."""
    out, i = "", 0
    pat = pat.replace("\\", "/")
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    return re.compile(f"^{out}$", re.IGNORECASE)


def path_allowed(rel: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(rel) for p in patterns)
