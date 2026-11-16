"""Portfólio do GPM: times do grupo (config do time) e, mais adiante, a agregação do Jira por time.

    tia.sh portfolio validar [--json]       # confere portfolio.times do .tia/config.yaml

`portfolio.times` (perfil GPM): lista de times, cada um com `nome`, `jira_projeto` (chave do projeto) e, se
quiser, `board` (id do quadro). Sem pessoas na config: o portfólio é por time, nunca por responsável.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_ROOT, load_config  # noqa: E402

CHAVE_RE = re.compile(r"^[A-Z][A-Z0-9]+$")
CAMPOS_TIME = {"nome", "jira_projeto", "board"}


def times(cfg: dict) -> list[dict]:
    t = ((cfg or {}).get("portfolio") or {}).get("times") or []
    return [x for x in t if isinstance(x, dict)] if isinstance(t, list) else []


def validar_times(cfg: dict) -> dict:
    """{erros, avisos, times}. Erro: time sem nome ou sem projeto, projeto inválido ou repetido."""
    erros: list[str] = []
    avisos: list[str] = []
    bruto = ((cfg or {}).get("portfolio") or {}).get("times")
    if bruto is not None and not isinstance(bruto, list):
        return {"erros": ["portfolio.times precisa ser uma lista de times"], "avisos": [], "times": 0}
    vistos: dict[str, str] = {}
    nomes: set[str] = set()
    for i, t in enumerate(bruto or [], 1):
        onde = f"time {i}"
        if not isinstance(t, dict):
            erros.append(f"{onde}: precisa ter nome e jira_projeto")
            continue
        nome = str(t.get("nome") or "").strip()
        onde = f"time {i} ({nome})" if nome else onde
        proj = str(t.get("jira_projeto") or "").strip()
        if not nome:
            erros.append(f"{onde}: sem nome")
        if not proj:
            erros.append(f"{onde}: sem jira_projeto")
        elif not CHAVE_RE.match(proj):
            erros.append(f"{onde}: jira_projeto \"{proj}\" não é chave de projeto do Jira (ex.: CAD)")
        elif proj in vistos:
            erros.append(f"{onde}: projeto {proj} repetido (já é do time {vistos[proj]})")
        else:
            vistos[proj] = nome or onde
        if nome and nome.lower() in nomes:
            avisos.append(f"{onde}: nome repetido")
        nomes.add(nome.lower())
        extras = sorted(set(t) - CAMPOS_TIME)
        if extras:
            avisos.append(f"{onde}: campos ignorados ({', '.join(extras)}); pessoas não entram na config")
    lista = ((cfg or {}).get("atlassian") or {}).get("jira_projetos")
    if isinstance(lista, list) and lista:
        fora = [p for p in vistos if p not in [str(x) for x in lista]]
        if fora:
            avisos.append(f"projetos dos times fora de atlassian.jira_projetos: {', '.join(fora)}")
    return {"erros": erros, "avisos": avisos, "times": len(bruto or [])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validar")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = a.root or DATA_ROOT
    if a.cmd == "validar":
        rep = validar_times(load_config(root))
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"Portfólio: {rep['times']} time(s), {len(rep['erros'])} erro(s), {len(rep['avisos'])} aviso(s)")
            for e in rep["erros"]:
                print(f"  ERRO  {e}")
            for w in rep["avisos"]:
                print(f"  AVISO {w}")
        return 1 if rep["erros"] else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
