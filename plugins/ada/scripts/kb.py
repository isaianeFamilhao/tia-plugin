"""Base de conhecimento: leitura, busca e validação determinística (formato em ada/kb/README.md).

    ada.sh kb  buscar "reprocessamento limite mensal" [--max 15] [--json]
    ada.sh kb  regra RN-ITR-001
    ada.sh kb  validar [--json]
    ada.sh kb  stats

Também é a biblioteca usada por packet.py, coverage.py, doctor.py e pelo hook Stop.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (CANDIDATE_ID_RE, REPO_ROOT, P, RULE_ID_RE, SOURCE_ID_RE,  # noqa: E402
                     load_yaml)

RULE_HEAD_RE = re.compile(r"^###\s+((?:RN-[A-Z]{3}-\d{3})|(?:RC-\d{2,3}))\s*[·\-—:]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(Regra|Status|Fontes|Atualizado|Notas):\*\*\s*(.*)$")
STATUSES = ("confirmada", "a confirmar", "conflito", "revogada")
REQUIRED = ("Regra", "Status", "Fontes", "Atualizado")


@dataclass
class Rule:
    id: str
    titulo: str
    arquivo: str
    linha: int
    regra: str = ""
    status: str = ""
    fontes: list[str] = field(default_factory=list)
    atualizado: str = ""
    notas: str = ""
    campos: list[str] = field(default_factory=list)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def parse_rules(path: Path, root: Path = REPO_ROOT) -> list[Rule]:
    """Lê blocos `### RN-XXX-NNN · título` (ou `RC-NN`) com os campos em lista."""
    rules: list[Rule] = []
    cur: Rule | None = None
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = RULE_HEAD_RE.match(line)
        if m:
            cur = Rule(id=m.group(1), titulo=m.group(2), arquivo=rel, linha=n)
            rules.append(cur)
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None:
            continue
        f = FIELD_RE.match(line.strip())
        if not f:
            continue
        key, val = f.group(1), f.group(2).strip()
        cur.campos.append(key)
        if key == "Regra":
            cur.regra = val
        elif key == "Status":
            cur.status = val.lower().strip()
        elif key == "Fontes":
            cur.fontes = [s for s in re.split(r"[,\s;]+", val) if s]
        elif key == "Atualizado":
            cur.atualizado = val
        elif key == "Notas":
            cur.notas = val
    return rules


def rule_files(root: Path = REPO_ROOT) -> list[Path]:
    kb = P(root, "kb")
    return sorted(p for p in kb.rglob("*.md") if "regras" in p.parts)


def load_rules(root: Path = REPO_ROOT) -> list[Rule]:
    out: list[Rule] = []
    for p in rule_files(root):
        out.extend(parse_rules(p, root))
    return out


def load_sources(root: Path = REPO_ROOT, extra: list[Path] | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    files = sorted(P(root, "kb", "fontes").glob("*.yaml")) + list(extra or [])
    for p in files:
        if not p.exists():
            continue
        try:
            data = load_yaml(p) or []
        except Exception as e:  # YAML inválido vira erro de validação, não traceback
            out[f"YAML-INVALIDO:{p.name}"] = {"_arquivo": p.name, "_erro": str(e).splitlines()[0][:200]}
            continue
        for s in data if isinstance(data, list) else []:
            if isinstance(s, dict) and s.get("id"):
                s = dict(s)
                s["_arquivo"] = p.name
                out.setdefault(str(s["id"]), s)
    return out


def lacunas(root: Path = REPO_ROOT) -> list[dict]:
    """Itens de `## Lacunas` dos arquivos da Base de Conhecimento."""
    out = []
    for p in sorted(P(root, "kb").rglob("*.md")):
        inside = False
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                inside = line.strip().lower().startswith("## lacunas")
                continue
            if inside and line.strip().startswith("- "):
                out.append({"arquivo": p.relative_to(root).as_posix(), "texto": line.strip()[2:]})
    return out


# ------------------------------------------------------------------ validação
def validate_rules(rules: list[Rule], sources: dict[str, dict], candidates: bool = False) -> list[dict]:
    """Erros de formato. `candidates=True` aceita/exige IDs RC-NN (regras.md de uma demanda)."""
    errs: list[dict] = []
    seen: dict[str, Rule] = {}
    for r in rules:
        where = f"{r.arquivo}:{r.linha}"
        ok_id = CANDIDATE_ID_RE.match(r.id) if candidates else RULE_ID_RE.match(r.id)
        if not ok_id:
            errs.append({"id": r.id, "onde": where, "erro": "ID fora do padrão"
                         + (" RC-NN" if candidates else " RN-XXX-NNN")})
        if r.id in seen:
            errs.append({"id": r.id, "onde": where, "erro": f"ID duplicado (também em {seen[r.id].arquivo}:{seen[r.id].linha})"})
        seen.setdefault(r.id, r)
        for k in REQUIRED:
            if k not in r.campos:
                errs.append({"id": r.id, "onde": where, "erro": f"campo obrigatório ausente: {k}"})
        if r.status and r.status not in STATUSES:
            errs.append({"id": r.id, "onde": where, "erro": f"status inválido: {r.status!r} (use {', '.join(STATUSES)})"})
        if "Regra" in r.campos and len(r.regra) < 15:
            errs.append({"id": r.id, "onde": where, "erro": "enunciado da regra vazio ou curto demais"})
        if "Fontes" in r.campos and not r.fontes:
            errs.append({"id": r.id, "onde": where, "erro": "regra sem fonte"})
        for s in r.fontes:
            if not SOURCE_ID_RE.match(s):
                errs.append({"id": r.id, "onde": where, "erro": f"fonte fora do padrão SRC-XXX-NNN: {s}"})
            elif s not in sources:
                errs.append({"id": r.id, "onde": where, "erro": f"fonte não registrada: {s}"})
        if "Atualizado" in r.campos and not re.match(r"^\d{4}-\d{2}-\d{2}$", r.atualizado):
            errs.append({"id": r.id, "onde": where, "erro": "Atualizado deve ser AAAA-MM-DD"})
    return errs


def validate_sources(sources: dict[str, dict]) -> list[dict]:
    errs = []
    for sid, s in sources.items():
        where = s.get("_arquivo", "?")
        if s.get("_erro"):
            errs.append({"id": where, "onde": where, "erro": f"YAML inválido: {s['_erro']}"})
            continue
        if not SOURCE_ID_RE.match(sid):
            errs.append({"id": sid, "onde": where, "erro": "ID de fonte fora do padrão"})
        for k in ("titulo", "tipo", "ref", "lido_em"):
            if not s.get(k):
                errs.append({"id": sid, "onde": where, "erro": f"campo ausente: {k}"})
        if s.get("tipo") not in ("confluence", "jira", "local", "conversa"):
            errs.append({"id": sid, "onde": where, "erro": f"tipo inválido: {s.get('tipo')}"})
        if s.get("apelido") and len(str(s["apelido"])) > 60:
            errs.append({"id": sid, "onde": where, "erro": "apelido com mais de 60 caracteres"})
    return errs


def validate_padroes(root: Path = REPO_ROOT) -> list[dict]:
    """`cobertura.secoes_epico` do config do time (se houver) bate com o padrão de épico do workspace."""
    from _common import config_workspace, frontmatter

    p = P(root, "kb", "padroes", "epico.md")
    meta, corpo = frontmatter(p)
    errs: list[dict] = []
    where = "ada/kb/padroes/epico.md"
    secoes = meta.get("secoes_epico")
    if p.exists() and not secoes:
        errs.append({"id": "PADRAO-EPICO", "onde": where, "erro": "frontmatter sem `secoes_epico`"})
    cfg_sec = ((config_workspace(root).get("cobertura") or {}).get("secoes_epico"))
    if secoes and cfg_sec and list(cfg_sec) != list(secoes):
        errs.append({"id": "PADRAO-EPICO", "onde": ".ada/config.yaml",
                     "erro": "cobertura.secoes_epico diferente do padrão de épico do workspace: "
                             f"{list(cfg_sec)} × {list(secoes)}"})
    return errs


def validate_kb(root: Path = REPO_ROOT) -> dict:
    rules = load_rules(root)
    sources = load_sources(root)
    import memoria

    errs = (validate_sources(sources) + validate_rules(rules, sources) + validate_apontamentos(root)
            + memoria.validate(root) + validate_padroes(root))
    return {"ok": not errs, "erros": errs, "regras": len(rules), "fontes": len(sources)}


# ------------------------------------------------------------------ apontamentos (ada/kb/apontamentos.md)
AP_HEAD_RE = re.compile(r"^###\s+(AP-\d{3})\s*[·\-—:]\s*(.+?)\s*$")
AP_FIELD_RE = re.compile(r"^-\s+\*\*(Tipo|Espaço|Página|O quê|Sugestão|Status|Aberto em|Resolução):\*\*\s*(.*)$")
AP_REQUIRED = ("Tipo", "Espaço", "Página", "O quê", "Status", "Aberto em")
AP_TIPOS = ("documentar", "duvida")
AP_STATUS = ("aberto", "resolvido", "descartado")


def parse_apontamentos(root: Path = REPO_ROOT) -> list[dict]:
    p = P(root, "kb", "apontamentos.md")
    if not p.exists():
        return []
    out: list[dict] = []
    cur: dict | None = None
    fenced = False
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            cur = None
            continue
        if fenced:
            continue
        m = AP_HEAD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "titulo": m.group(2), "linha": n, "campos": {}}
            out.append(cur)
            continue
        if line.startswith("#"):
            cur = None
            continue
        f = AP_FIELD_RE.match(line.strip()) if cur else None
        if f:
            cur["campos"][f.group(1)] = f.group(2).strip()
    return out


def validate_apontamentos(root: Path, cfg: dict | None = None) -> list[dict]:
    """Formato, e coerência com a política: `documentar` só em espaço `manter` (INT)."""
    from _common import load_config

    cfg = cfg if cfg is not None else load_config(root)
    espacos = (cfg.get("confluence") or {}).get("espacos") or {}
    errs, seen = [], set()
    for a in parse_apontamentos(root):
        where = f"ada/kb/apontamentos.md:{a['linha']}"
        c = a["campos"]
        if a["id"] in seen:
            errs.append({"id": a["id"], "onde": where, "erro": "ID duplicado"})
        seen.add(a["id"])
        for k in AP_REQUIRED:
            if not c.get(k):
                errs.append({"id": a["id"], "onde": where, "erro": f"campo obrigatório ausente: {k}"})
        tipo, esp, st = c.get("Tipo", "").lower(), c.get("Espaço", "").upper(), c.get("Status", "").lower()
        if tipo and tipo not in AP_TIPOS:
            errs.append({"id": a["id"], "onde": where, "erro": f"Tipo deve ser {' | '.join(AP_TIPOS)}"})
        if st and st not in AP_STATUS:
            errs.append({"id": a["id"], "onde": where, "erro": f"Status deve ser {' | '.join(AP_STATUS)}"})
        pol = (espacos.get(esp) or {}).get("politica", (cfg.get("confluence") or {}).get("padrao", "somente_leitura"))
        if tipo == "documentar" and pol != "manter":
            errs.append({"id": a["id"], "onde": where,
                         "erro": f"`documentar` só vale para espaço que o harness mantém (INT); em {esp} use `duvida`"})
        if st in ("resolvido", "descartado") and not c.get("Resolução"):
            errs.append({"id": a["id"], "onde": where, "erro": "apontamento fechado sem **Resolução:**"})
    return errs


# ------------------------------------------------------------------ busca
def search(root: Path, query: str, limit: int = 15) -> list[dict]:
    """Busca por termos (sem acento, sem maiúsculas). Pontua título ×3, regra ×2, notas ×1."""
    terms = [t for t in re.split(r"\W+", _fold(query)) if len(t) >= 3]
    if not terms:
        return []
    hits = []
    for r in load_rules(root):
        title, body, notes = _fold(r.titulo), _fold(r.regra), _fold(r.notas)
        score = 0
        for t in terms:
            score += 3 * title.count(t) + 2 * body.count(t) + notes.count(t)
        if score and r.status != "revogada":
            hits.append((score, r))
    hits.sort(key=lambda x: (-x[0], x[1].id))
    return [dict(asdict(r), score=s) for s, r in hits[:limit]]


def stats(root: Path = REPO_ROOT) -> dict:
    rules = load_rules(root)
    by_prefix: dict[str, dict[str, int]] = {}
    for r in rules:
        pre = r.id[:6]
        by_prefix.setdefault(pre, {}).setdefault(r.status or "?", 0)
        by_prefix[pre][r.status or "?"] += 1
    return {"regras": len(rules), "fontes": len(load_sources(root)), "lacunas": len(lacunas(root)),
            "por_dominio": by_prefix}


def source_label(sid: str, sources: dict[str, dict]) -> str:
    """Nome humano da fonte: apelido, senão título; o código fica de fora (vai em "Ref.")."""
    s = sources.get(sid) or {}
    return s.get("apelido") or s.get("titulo") or sid


def render_rule(r: dict, sources: dict[str, dict] | None = None) -> str:
    """Nome primeiro, código no fim: é o formato que o agente usa na conversa."""
    srcs = sources or {}
    out = [f"{r['titulo']} — {r['status']}",
           f"  {r['regra']}",
           f"  Fontes: {'; '.join(source_label(s, srcs) for s in r['fontes'])}"]
    if r.get("notas"):
        out.append(f"  Notas: {r['notas']}")
    out.append(f"  Ref.: {r['id']} · {', '.join(r['fontes'])} · {r['arquivo']}:{r['linha']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buscar")
    b.add_argument("termos")
    b.add_argument("--max", type=int, default=15)
    b.add_argument("--json", action="store_true")
    g = sub.add_parser("regra")
    g.add_argument("id")
    v = sub.add_parser("validar")
    v.add_argument("--json", action="store_true")
    sub.add_parser("stats")
    sub.add_parser("lacunas")
    ap_ = sub.add_parser("apontamentos")
    ap_.add_argument("--abertos", action="store_true")
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    a = ap.parse_args(argv)
    root = a.root

    if a.cmd == "buscar":
        hits = search(root, a.termos, a.max)
        if a.json:
            print(json.dumps(hits, ensure_ascii=False, indent=2))
        else:
            srcs = load_sources(root)
            print("\n\n".join(render_rule(h, srcs) for h in hits) if hits else "Nenhuma regra encontrada na Base de Conhecimento.")
        return 0
    if a.cmd == "regra":
        for r in load_rules(root):
            if r.id == a.id:
                srcs = load_sources(root)
                print(render_rule(asdict(r), srcs))
                for s in r.fontes:
                    src = srcs.get(s, {})
                    print(f"  · {source_label(s, srcs)}: {src.get('ref', '?')} (lido em {src.get('lido_em', '?')})")
                return 0
        print(f"Regra {a.id} não existe na Base de Conhecimento.", file=sys.stderr)
        return 1
    if a.cmd == "validar":
        rep = validate_kb(root)
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"Base de Conhecimento: {rep['regras']} regras, {rep['fontes']} fontes — {'OK' if rep['ok'] else 'ERROS'}")
            for e in rep["erros"]:
                print(f"  ERRO {e['id']} ({e['onde']}): {e['erro']}")
        return 0 if rep["ok"] else 1
    if a.cmd == "stats":
        print(json.dumps(stats(root), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "apontamentos":
        rows = [x for x in parse_apontamentos(root)
                if not a.abertos or x["campos"].get("Status", "").lower() == "aberto"]
        for x in rows:
            c = x["campos"]
            print(f"{x['id']} [{c.get('Tipo')}/{c.get('Espaço')}/{c.get('Status')}] {x['titulo']} — {c.get('Página')}")
        if not rows:
            print("Nenhum apontamento" + (" aberto." if a.abertos else "."))
        return 0
    if a.cmd == "lacunas":
        for l in lacunas(root):
            print(f"- [{l['arquivo']}] {l['texto']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
