"""Item 10: o que os scripts importam de fora da biblioteca padrão está em requirements-runtime.txt; pytest não."""
from __future__ import annotations

import ast
import re
import sys

from conftest import BIN, REPO

PACOTE = {"yaml": "pyyaml", "jsonschema": "jsonschema"}


def importados() -> set[str]:
    out = set()
    locais = {p.stem for p in BIN.glob("*.py")}
    for p in BIN.glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                out |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                out.add(node.module.split(".")[0])
    return {m for m in out if m not in sys.stdlib_module_names and m not in locais}


def reqs(nome: str) -> set[str]:
    linhas = (REPO / nome).read_text(encoding="utf-8").splitlines()
    return {re.split(r"[=<>;\s]", l.strip())[0].lower() for l in linhas if l.strip() and not l.startswith(("#", "-r"))}


def test_runtime_cobre_os_imports():
    faltam = {PACOTE.get(m, m) for m in importados()} - reqs("requirements-runtime.txt")
    assert not faltam, faltam


def test_runtime_sem_ferramenta_de_teste():
    assert "pytest" not in reqs("requirements-runtime.txt")
    assert "pytest" in reqs("requirements-dev.txt")
    assert "-r requirements-runtime.txt" in (REPO / "requirements-dev.txt").read_text(encoding="utf-8")
