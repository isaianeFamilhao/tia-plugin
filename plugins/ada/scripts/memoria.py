"""Memória do PM (kb/memoria-pm.md): o que a Ada aprendeu sobre como a PM gosta de trabalhar.

    python .harness/bin/memoria.py listar [--todas]      # ativas por padrão
    python .harness/bin/memoria.py validar
    python .harness/bin/memoria.py proximo               # próximo ID livre (PM-NNN)

Cada aprendizado só entra com o "sim" da PM na conversa (gate Memória). Nada é apagado: o que ela
mandar esquecer vira `revogada`, com motivo, e deixa de ser aplicado.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT  # noqa: E402

HEAD_RE = re.compile(r"^###\s+(PM-\d{3})\s*[·\-—:]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(Aprendi|Evidência|Aplicar em|Status|Desde|Revogada em|Motivo):\*\*\s*(.*)$")
REQUIRED = ("Aprendi", "Evidência", "Aplicar em", "Status", "Desde")
STATUS = ("ativa", "revogada")
ONDE = ("geral", "conversa", "épicos", "histórias", "relatórios", "dados", "confluence", "jira", "fluxo")


def path(root: Path = REPO_ROOT) -> Path:
    return root / "kb" / "memoria-pm.md"


def parse(root: Path = REPO_ROOT) -> list[dict]:
    p = path(root)
    if not p.exists():
        return []
    out, cur, fenced = [], None, False
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced, cur = not fenced, None
            continue
        if fenced:
            continue
        m = HEAD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "titulo": m.group(2), "linha": n, "campos": {}}
            out.append(cur)
        elif line.startswith("#"):
            cur = None
        elif cur and (f := FIELD_RE.match(line.strip())):
            cur["campos"][f.group(1)] = f.group(2).strip()
    return out


def validate(root: Path = REPO_ROOT) -> list[dict]:
    errs, seen = [], set()
    for e in parse(root):
        where = f"kb/memoria-pm.md:{e['linha']}"
        c = e["campos"]
        if e["id"] in seen:
            errs.append({"id": e["id"], "onde": where, "erro": "ID duplicado"})
        seen.add(e["id"])
        for k in REQUIRED:
            if not c.get(k):
                errs.append({"id": e["id"], "onde": where, "erro": f"campo obrigatório ausente: {k}"})
        st = c.get("Status", "").lower()
        if st and st not in STATUS:
            errs.append({"id": e["id"], "onde": where, "erro": f"Status deve ser {' | '.join(STATUS)}"})
        if st == "revogada" and not (c.get("Revogada em") and c.get("Motivo")):
            errs.append({"id": e["id"], "onde": where, "erro": "revogada exige **Revogada em:** e **Motivo:**"})
        onde = [x.strip().lower() for x in c.get("Aplicar em", "").split(",") if x.strip()]
        bad = [x for x in onde if x not in ONDE]
        if bad:
            errs.append({"id": e["id"], "onde": where, "erro": f"Aplicar em fora da lista ({', '.join(ONDE)}): {', '.join(bad)}"})
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", c.get("Desde", "")):
            errs.append({"id": e["id"], "onde": where, "erro": "Desde deve ser AAAA-MM-DD"})
    return errs


def proximo(root: Path = REPO_ROOT) -> str:
    nums = [int(e["id"][3:]) for e in parse(root)]
    return f"PM-{(max(nums) if nums else 0) + 1:03d}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("listar")
    s.add_argument("--todas", action="store_true")
    sub.add_parser("validar")
    sub.add_parser("proximo")
    a = ap.parse_args(argv)
    if a.cmd == "listar":
        rows = [e for e in parse() if a.todas or e["campos"].get("Status", "").lower() == "ativa"]
        for e in rows:
            c = e["campos"]
            print(f"- {e['titulo']} [{c.get('Aplicar em')}] — {c.get('Aprendi')}"
                  + ("" if c.get("Status", "").lower() == "ativa" else f" (revogada: {c.get('Motivo')})")
                  + f"  ·  {e['id']}")
        if not rows:
            print("Memória vazia.")
        return 0
    if a.cmd == "validar":
        errs = validate()
        print("Memória do PM: OK" if not errs else "Memória do PM: ERROS")
        for e in errs:
            print(f"  ERRO {e['id']} ({e['onde']}): {e['erro']}")
        return 1 if errs else 0
    print(proximo())
    return 0


if __name__ == "__main__":
    sys.exit(main())
