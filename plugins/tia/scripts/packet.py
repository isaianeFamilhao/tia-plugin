"""Pacote de contexto de uma demanda, gerado do disco (nunca da conversa), com tetos por bloco.

    tia.sh packet  D-001 [--json]

Grava `tia/demandas/D-001/packet.md`. Blocos, na ordem: demanda, digest, épico (se houver
`epico_jira` e ele estiver num tia/kb/**/epicos.md), regras da Base de Conhecimento que batem com os termos,
lacunas conhecidas, motivo de retrabalho. É o ponto de partida da pesquisa, não o fim dela.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb as kbmod  # noqa: E402
from _common import (REPO_ROOT, P, atomic_write_text, est_tokens, fit_tokens,  # noqa: E402
                     load_config, load_yaml, read_json)

ORDER = ("demanda", "digest", "epico", "regras", "lacunas", "retrabalho")


def find_demand(root: Path, did: str) -> dict:
    for d in load_yaml(P(root, "fila")) or []:
        if isinstance(d, dict) and d.get("id") == did:
            return d
    raise SystemExit(f"{did} não está em tia/demandas.yaml")


def block_demanda(d: dict) -> str:
    out = [f"## Demanda {d['id']} · {d['titulo']}", "",
           f"- **Tipo:** {d['tipo']} · **Tamanho:** {d['tamanho']} · **Solicitante:** {d['solicitante']}"
           + (f" · **Épico Jira:** {d['epico_jira']}" if d.get("epico_jira") else "")
           + (f" · **Prazo:** {d['prazo']}" if d.get("prazo") else ""),
           f"- **Pedido:** {str(d['pedido']).strip()}"]
    if d.get("fora_de_escopo"):
        out.append("- **Fora de escopo (do pedido):** " + "; ".join(d["fora_de_escopo"]))
    if d.get("fontes_extra"):
        out.append("- **Fontes indicadas:** " + ", ".join(d["fontes_extra"]))
    return "\n".join(out)


def block_epico(root: Path, key: str | None) -> str:
    if not key:
        return ""
    arquivos = sorted(P(root, "kb").rglob("epicos.md"))
    if not arquivos:
        return f"## Épico {key}\n\n(nenhum epicos.md na Base de Conhecimento: buscar {key} no Jira)"
    m = None
    for p in arquivos:
        m = re.search(rf"(?ms)^## {re.escape(key)}\b.*?(?=^## |\Z)", p.read_text(encoding="utf-8"))
        if m:
            break
    if not m:
        return f"## Épico {key}\n\n({key} não está na Base de Conhecimento: buscar no Jira e registrar em epicos.md)"
    return "## Épico na Base de Conhecimento\n\n" + m.group(0).strip()


def block_regras(root: Path, query: str, max_rules: int) -> tuple[str, list[str]]:
    hits = kbmod.search(root, query, max_rules)
    if not hits:
        return "## Regras da Base de Conhecimento\n\nNenhuma regra da Base de Conhecimento bate com os termos. Pesquise no Confluence/Jira.", []
    srcs = kbmod.load_sources(root)
    lines = ["## Regras da Base de Conhecimento (por relevância aos termos; confira se se aplicam)", "",
             "Na conversa, cite pelo nome; o código (Ref.) é para os artefatos.", ""]
    for h in hits:
        fontes = "; ".join(kbmod.source_label(s, srcs) for s in h["fontes"])
        lines.append(f"- **{h['titulo']}** [{h['status']}] — {h['regra']} Fontes: {fontes}. "
                     f"Ref.: {h['id']} ({', '.join(h['fontes'])})")
    return "\n".join(lines), [h["id"] for h in hits]


def block_lacunas(root: Path, query: str) -> str:
    terms = [kbmod._fold(t) for t in re.split(r"\W+", query) if len(t) >= 4]
    hits = [l for l in kbmod.lacunas(root) if any(t in kbmod._fold(l["texto"]) for t in terms)]
    if not hits:
        return ""
    return "## Lacunas conhecidas na Base de Conhecimento\n\n" + "\n".join(f"- [{l['arquivo']}] {l['texto']}" for l in hits[:15])


def block_retrabalho(root: Path, did: str) -> str:
    led = read_json(P(root, "ledger")) or {}
    d = (led.get("demandas") or {}).get(did) or {}
    reworks = [g for g in d.get("g2") or [] if g.get("decisao") == "rework"]
    if not reworks:
        return ""
    return "## Motivo do retrabalho (G2)\n\n" + "\n".join(f"- tentativa {g.get('tentativa')}: {g.get('nota')}" for g in reworks)


def build(root: Path, did: str) -> tuple[str, dict]:
    cfg = load_config(root)
    pc = cfg.get("pacote") or {}
    caps = pc.get("caps") or {}
    cpt = float(pc.get("chars_per_token") or 3.0)
    d = find_demand(root, did)
    query = " ".join(d.get("termos") or []) or d["titulo"]
    digest_p = P(root, "cache", "digest.md")
    regras_txt, regra_ids = block_regras(root, query, int(pc.get("max_regras") or 25))
    raw = {
        "demanda": block_demanda(d),
        "digest": digest_p.read_text(encoding="utf-8") if digest_p.exists() else "",
        "epico": block_epico(root, d.get("epico_jira")),
        "regras": regras_txt,
        "lacunas": block_lacunas(root, query),
        "retrabalho": block_retrabalho(root, did),
    }
    meta: dict = {"demanda": did, "blocos": {}, "regras_kb": regra_ids, "recortados": []}
    parts = [f"# Pacote da demanda {did}", "",
             "Gerado por `packet.py` a partir do disco. Tokens estimados [E]. Ponto de partida da pesquisa: "
             "confirme cada regra na fonte antes de usá-la.", ""]
    total = 0
    for k in ORDER:
        if not raw[k]:
            continue
        txt, cut, orig = fit_tokens(raw[k], int(caps.get(k) or 2000), k, cpt)
        meta["blocos"][k] = {"tokens": est_tokens(txt, cpt), "originais": orig}
        if cut:
            meta["recortados"].append(k)
        total += est_tokens(txt, cpt)
        parts += [txt, ""]
    meta["total_tokens"] = total
    meta["teto"] = int(caps.get("total") or 0)
    meta["dentro_do_teto"] = not meta["teto"] or total <= meta["teto"]
    return "\n".join(parts), meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demanda")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    a = ap.parse_args(argv)
    text, meta = build(a.root, a.demanda)
    out = P(a.root, "demandas", a.demanda, "packet.md")
    atomic_write_text(out, text)
    meta["arquivo"] = out.relative_to(a.root).as_posix()
    if a.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print(f"{meta['arquivo']}: ~{meta['total_tokens']} tokens [E] (teto {meta['teto']}); "
              f"regras da Base de Conhecimento: {len(meta['regras_kb'])}; recortados: {', '.join(meta['recortados']) or '—'}")
    return 0 if meta["dentro_do_teto"] else 1


if __name__ == "__main__":
    sys.exit(main())
