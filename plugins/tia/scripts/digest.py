"""Digest rolante (.tia/cache/digest.md): estado da Base de Conhecimento + últimas demandas aceitas. Reescrito, nunca anexado.

    tia.sh digest 
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb as kbmod  # noqa: E402
from _common import REPO_ROOT, P, require_workspace, atomic_write_text, fit_tokens, load_config, read_json  # noqa: E402

DONE = ("accepted", "publish_approved", "published")


def render(root: Path) -> str:
    cfg = load_config(root)
    dc = cfg.get("digest") or {}
    st = kbmod.stats(root)
    led = read_json(P(root, "ledger")) or {}
    done = []
    for did, d in (led.get("demandas") or {}).items():
        if d.get("state") in DONE:
            at = next((h["em"] for h in reversed(d.get("historico") or []) if h.get("para") == "accepted"), "")
            done.append((at, did, d))
    done.sort(reverse=True)
    lines = ["# Digest do harness de produto", "",
             f"Base de Conhecimento: {st['regras']} regras, {st['fontes']} fontes, {st['lacunas']} lacunas registradas.", ""]
    if st["por_dominio"]:
        lines.append("Regras por domínio: " + "; ".join(
            f"{k} {sum(v.values())} ({', '.join(f'{n} {s}' for s, n in sorted(v.items()))})"
            for k, v in sorted(st["por_dominio"].items())))
        lines.append("")
    lines.append(f"## Últimas demandas aceitas (máx. {dc.get('ultimas_entregas', 5)})")
    lines.append("")
    if not done:
        lines.append("Nenhuma ainda.")
    for at, did, d in done[: int(dc.get("ultimas_entregas", 5))]:
        e = d.get("entrega") or {}
        lines.append(f"- **{did}** ({d['state']}, {at[:10]}): {e.get('summary') or '—'}"
                     + (f" Publicado: {', '.join(d['publicado'])}." if d.get("publicado") else ""))
    text = "\n".join(lines) + "\n"
    out, _, _ = fit_tokens(text, int(dc.get("max_tokens", 1200)), "digest",
                           float((cfg.get("pacote") or {}).get("chars_per_token") or 3.0))
    return out


def main(argv: list[str] | None = None) -> int:
    root = require_workspace()
    atomic_write_text(P(root, "cache", "digest.md"), render(root))
    print(".tia/cache/digest.md reescrito")
    return 0


if __name__ == "__main__":
    sys.exit(main())
