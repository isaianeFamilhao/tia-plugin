"""Valida a fila de demandas (tia/demandas.yaml): schema + regras do harness. Zero tokens.

    tia.sh validate  [--demandas PATH] [--json]

Código 0 = válida (avisos não bloqueiam); 1 = erros; 2 = uso/arquivo ilegível.
O agente só COMENTA ambiguidades; quem corrige a fila é o humano.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, P, SCHEMA_DEMANDAS, load_config, load_yaml  # noqa: E402

DEFAULT_DEMANDAS = P(REPO_ROOT, "fila")
SCHEMA = SCHEMA_DEMANDAS
# Palavras que costumam trazer a solução pronta no pedido (o harness quer o problema primeiro).
SOLUTION_WORDS = ("criar um botão", "criar uma tela", "criar tela", "dashboard", "planilha", "integrar com", "api ")
VAGUE_WORDS = ("melhorar", "otimizar", "agilizar", "facilitar", "intuitiv", "rápido", "rapido")


def validate(path: Path, root: Path = REPO_ROOT) -> dict:
    import jsonschema

    rep: dict = {"ok": True, "erros": [], "avisos": [], "demandas": []}
    try:
        data = load_yaml(path)
    except FileNotFoundError:
        rep.update(ok=False, erros=[{"demanda": "-", "erro": f"arquivo não encontrado: {path}"}])
        return rep
    except Exception as e:  # yaml inválido
        rep.update(ok=False, erros=[{"demanda": "-", "erro": f"YAML inválido: {e}"}])
        return rep
    data = data or []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    for e in sorted(v.iter_errors(data), key=lambda e: list(e.path)):
        idx = e.path[0] if e.path else None
        did = data[idx].get("id", f"#{idx}") if isinstance(idx, int) and isinstance(data[idx], dict) else "-"
        rep["erros"].append({"demanda": did, "erro": f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}"})
    if not isinstance(data, list):
        rep["ok"] = False
        return rep
    cfg = load_config(root)
    sizes = (cfg.get("tamanhos") or {})
    seen: set[str] = set()
    for d in data:
        if not isinstance(d, dict):
            continue
        did = str(d.get("id", "?"))
        if did in seen:
            rep["erros"].append({"demanda": did, "erro": "id duplicado"})
        seen.add(did)
        if d.get("tipo") == "novo_epico" and d.get("epico_jira"):
            rep["avisos"].append({"demanda": did, "aviso": "tipo novo_epico com epico_jira: é refinamento? confirme no G1"})
        pedido = str(d.get("pedido", "")).lower()
        if any(w in pedido for w in SOLUTION_WORDS):
            rep["avisos"].append({"demanda": did, "aviso": "o pedido parece trazer a solução pronta; o épico parte do problema"})
        if any(w in pedido for w in VAGUE_WORDS):
            rep["avisos"].append({"demanda": did, "aviso": "pedido com termo vago (melhorar/agilizar/intuitivo...): pedir o resultado observável"})
        if not d.get("termos"):
            rep["avisos"].append({"demanda": did, "aviso": "sem `termos`: a busca na Base de Conhecimento usará o título"})
        t = d.get("tamanho")
        rep["demandas"].append({"id": did, "titulo": d.get("titulo"), "tipo": d.get("tipo"),
                                "epico_jira": d.get("epico_jira"), "tamanho": t,
                                "max_historias": (sizes.get(t) or {}).get("max_historias")})
    rep["ok"] = not rep["erros"]
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demandas", type=Path, default=DEFAULT_DEMANDAS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = validate(a.demandas)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"demandas: {len(rep['demandas'])} — {'OK' if rep['ok'] else 'ERROS'}")
        for e in rep["erros"]:
            print(f"  ERRO  {e['demanda']}: {e['erro']}")
        for w in rep["avisos"]:
            print(f"  AVISO {w['demanda']}: {w['aviso']}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
