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
import os
import re
import sys
from pathlib import Path

# ------------------------------------------------------------------ raízes
# Motor no plugin, conteúdo no workspace.
#   CODE_ROOT: a pasta do plugin (scripts/, skills/, modelos/, schema/). Só leitura.
#   DATA_ROOT: o workspace da PM, marcado por `.tia/config.yaml`.
# Resolução do workspace: TIA_ROOT (testes) > CLAUDE_PROJECT_DIR > cwd (sobe as pastas).
CODE_ROOT = Path(__file__).resolve().parents[1]
MARCADOR = Path(".tia") / "config.yaml"


def is_workspace(root) -> bool:
    return bool(root) and (Path(root) / MARCADOR).is_file()


def find_data_root(cwd=None) -> Path | None:
    """Workspace da Tia, ou None. TIA_ROOT valem mesmo sem marcador (o chamador confere)."""
    for env in ("TIA_ROOT",):
        if os.environ.get(env):
            return Path(os.environ[env])
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        p = Path(os.environ["CLAUDE_PROJECT_DIR"])
        return p if is_workspace(p) else None
    here = Path(cwd or Path.cwd()).resolve()
    for p in (here, *here.parents):
        if is_workspace(p):
            return p
    return None


DATA_ROOT = find_data_root() or Path.cwd()
REPO_ROOT = DATA_ROOT  # nome antigo, mantido nos scripts herdados


def require_workspace(root: Path | None = None) -> Path:
    """Para os `main()`: sem marcador, explica e sai (código 2)."""
    root = Path(root or DATA_ROOT)
    if not is_workspace(root):
        print(f"[tia] {root} não é um workspace da Tia (falta {MARCADOR.as_posix()}). "
              "Diga \"Tia, configurar\" para criar.", file=sys.stderr)
        raise SystemExit(2)
    return root


# Layout do workspace: `tia/` é conteúdo (gente lê e revisa); `.tia/` é máquina (só scripts).
REL = {
    "kb": "tia/kb",
    "fila": "tia/demandas.yaml",
    "fila_exemplo": "tia/demandas.exemplo.yaml",
    "demandas": "tia/demandas",
    "relatorios": "tia/relatorios",
    "propostas": "tia/propostas",
    "memoria_time": "tia/memoria/time",
    "memoria_pessoal": "tia/memoria/pessoal",
    "config": ".tia/config.yaml",
    "ledger": ".tia/ledger.json",
    "monitoramento": ".tia/monitoramento",
    "logs": ".tia/logs",
    "cache": ".tia/cache",
}


def P(root, key: str, *parts: str) -> Path:
    """Caminho de `key` (ver REL) no workspace `root`."""
    return Path(root or DATA_ROOT).joinpath(*REL[key].split("/"), *parts)


SCHEMA_DEMANDAS = CODE_ROOT / "schema" / "demandas.schema.json"
MODELOS = CODE_ROOT / "modelos"

# Saída sempre em UTF-8 (o console do Windows usa cp1252/cp850 e quebrava os acentos), sem precisar
# de PYTHONIOENCODING no comando — o prefixo fazia o hook pedir confirmação à toa.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
DEFAULT_CHARS_PER_TOKEN = 3.0  # calibrado na F3 do harness-lean (app desktop)

DEMAND_ID_RE = re.compile(r"^D-\d{3}$")
RULE_ID_RE = re.compile(r"^RN-[A-Z]{3}-\d{3}$")        # regra da kb
CANDIDATE_ID_RE = re.compile(r"^RC-\d{2,3}$")            # regra candidata, só da demanda
SOURCE_ID_RE = re.compile(r"^SRC-[A-Z]{2,4}-\d{3}$")       # EMP, sigla do time, DEM
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


# Chaves que o workspace NÃO sobrepõe (categoria 1). Caminho com ponto = chave aninhada.
INEGOCIAVEIS = (
    "escopo_escrita",
    "atlassian.ferramentas_escrita_regex",
    "atlassian.confluence_escrita_regex",
    "confluence.padrao",
    "dados.escrita_regex",
    "cobertura.exigir_regra_coberta",
    "cobertura.formato_criterio",
)


def deep_merge(base: dict, over: dict) -> dict:
    """Sobreposição: dicionário mescla recursivamente; lista e escalar substituem."""
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return KeyError
        cur = cur[part]
    return cur


def _set(d: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    if value is KeyError:
        d.pop(parts[-1], None)
    else:
        d[parts[-1]] = value


def config_padrao() -> dict:
    return load_yaml(MODELOS / "config.padrao.yaml") or {}


def config_workspace(root: Path | None = None) -> dict:
    p = P(root, "config")
    return (load_yaml(p) or {}) if p.exists() else {}


def load_config(root: Path | None = None) -> dict:
    """Padrão do plugin + config do time (deep merge), com as chaves inegociáveis repostas do padrão."""
    import copy

    base = config_padrao()
    cfg = deep_merge(base, config_workspace(root))
    for k in INEGOCIAVEIS:
        _set(cfg, k, copy.deepcopy(_get(base, k)))
    return cfg


def config_sobreposicoes_ignoradas(root: Path | None = None) -> list[str]:
    """Chaves inegociáveis que o workspace tentou sobrepor (o doctor avisa)."""
    ws = config_workspace(root)
    return [k for k in INEGOCIAVEIS if _get(ws, k) is not KeyError]


# ------------------------------------------------------------------ padrões do workspace
def frontmatter(path: Path) -> tuple[dict, str]:
    """(metadados YAML, corpo) de um .md com frontmatter `---`; sem frontmatter: ({}, texto)."""
    import yaml

    text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), m.group(2)


def secoes_epico(root: Path | None = None, cfg: dict | None = None) -> list[str]:
    """Seções obrigatórias do épico: padrão do workspace (frontmatter) > config > padrão do plugin."""
    meta, _ = frontmatter(P(root, "kb", "padroes", "epico.md"))
    if meta.get("secoes_epico"):
        return list(meta["secoes_epico"])
    cfg = cfg if cfg is not None else load_config(root)
    if (cfg.get("cobertura") or {}).get("secoes_epico"):
        return list(cfg["cobertura"]["secoes_epico"])
    meta, _ = frontmatter(MODELOS / "padroes" / "epico.md")
    return list(meta.get("secoes_epico") or [])


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
