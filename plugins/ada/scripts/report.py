"""Relatório das demandas: estado, entregas, cobertura e consumo (métricas da transcrição).

    ada.sh report  [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, P, read_json  # noqa: E402


def build(root: Path = REPO_ROOT) -> list[dict]:
    led = read_json(P(root, "ledger")) or {}
    rows = []
    for did, d in sorted((led.get("demandas") or {}).items()):
        ddir = P(root, "demandas", did)
        cov = read_json(ddir / "cobertura.json") or {}
        met = read_json(ddir / "metrics.json") or {}
        matriz = cov.get("matriz") or []
        rows.append({
            "demanda": did, "estado": d.get("state"), "tentativas": d.get("tentativa"),
            "retrabalhos": d.get("retrabalhos"), "historias": len(cov.get("historias") or []),
            "regras": len(matriz),
            "cobertas": sum(1 for m in matriz if m.get("situacao") == "coberta"),
            "fora_escopo": sum(1 for m in matriz if m.get("situacao") == "fora do escopo"),
            "a_confirmar": sum(1 for m in matriz if m.get("status") in ("a confirmar", "conflito")),
            "avisos": len(cov.get("avisos") or []),
            "saida_tokens": met.get("output_tokens"), "pico_contexto": met.get("peak_context_tokens"),
            "alerta_saida": met.get("alerta_saida"),
        })
    return rows


def render(rows: list[dict]) -> str:
    out = ["| Demanda | Estado | Tent. | Retrab. | Histórias | Regras (cobertas/fora/a confirmar) | Avisos | Saída [tokens] | Pico contexto |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['demanda']} | {r['estado']} | {r['tentativas']} | {r['retrabalhos']} | {r['historias']} | "
                   f"{r['regras']} ({r['cobertas']}/{r['fora_escopo']}/{r['a_confirmar']}) | {r['avisos']} | "
                   f"{r['saida_tokens'] or '—'}{' ALERTA' if r['alerta_saida'] else ''} | {r['pico_contexto'] or '—'} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = build()
    print(json.dumps(rows, ensure_ascii=False, indent=2) if a.json else render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
