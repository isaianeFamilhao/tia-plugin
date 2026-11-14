"""Avaliador determinístico da entrega de uma demanda (o "evaluator" do harness). Zero tokens.

    python .harness/bin/coverage.py D-001 [--json] [--no-write]

Lê os artefatos de `.harness/demandas/D-001/` e confere o contrato (README, seção "Artefatos"):
result.json, épico no padrão de épico da squad, histórias com critérios Dado/Quando/Então,
regras existentes (Base de Conhecimento ou candidatas com fonte) e COBERTURA: toda regra relevante tem pelo menos
um critério que a cita, ou está fora do escopo com motivo. Grava `cobertura.md` e `cobertura.json`.

Código 0 = sem erros (avisos não bloqueiam); 1 = erros; 2 = uso.
Não julga qualidade de texto: isso é do revisor independente e do humano no G2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb as kbmod  # noqa: E402
from _common import (CANDIDATE_ID_RE, DEMAND_ID_RE, REPO_ROOT, RULE_ID_RE,  # noqa: E402
                     SOURCE_ID_RE, atomic_write_text, load_config, read_json, write_json)

RESULT_KEYS = ("demanda_id", "status", "historias", "regras_relevantes", "fora_do_escopo", "lacunas",
               "fontes", "summary", "open_questions", "blocked_reason")
SUMMARY_MAX_WORDS = 120
STORY_HEAD_RE = re.compile(r"^##\s+(H-\d{2})\s*[·\-—:]\s*(.+?)\s*$")
CA_RE = re.compile(r"^-\s+\*\*(CA-\d{2})\*\*\s*(?:\[([^\]]*)\])?\s*:?\s*(.*)$")
COBRE_RE = re.compile(r"^\*\*Cobre:\*\*\s*(.*)$")
USER_STORY_RE = re.compile(r"(?is)\*\*Hist[óo]ria:\*\*\s*como\b.+?\bquero\b.+?\bpara\b")
RULE_REF_RE = re.compile(r"RN-[A-Z]{3}-\d{3}|RC-\d{2,3}")


def demand_dir(root: Path, did: str) -> Path:
    return root / ".harness" / "demandas" / did


# ------------------------------------------------------------------ result.json
def validate_result(data: object, did: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["result.json ausente ou não é um objeto JSON"]
    missing = [k for k in RESULT_KEYS if k not in data]
    if missing:
        errs.append(f"result.json sem as chaves: {', '.join(missing)}")
    extra = [k for k in data if k not in RESULT_KEYS]
    if extra:
        errs.append(f"result.json com chaves fora do contrato: {', '.join(extra)}")
    if data.get("demanda_id") != did:
        errs.append(f"demanda_id deve ser {did}")
    st = data.get("status")
    if st not in ("delivered", "blocked"):
        errs.append("status deve ser delivered ou blocked")
    if st == "blocked" and not str(data.get("blocked_reason") or "").strip():
        errs.append("status blocked exige blocked_reason")
    if st == "delivered" and data.get("blocked_reason"):
        errs.append("status delivered com blocked_reason preenchido")
    for k in ("historias", "regras_relevantes", "lacunas", "fontes", "open_questions", "fora_do_escopo"):
        if k in data and not isinstance(data[k], list):
            errs.append(f"{k} deve ser lista")
    for f in data.get("fora_do_escopo") or []:
        if not (isinstance(f, dict) and f.get("regra") and str(f.get("motivo") or "").strip()):
            errs.append("cada item de fora_do_escopo precisa de {regra, motivo}")
    words = len(str(data.get("summary") or "").split())
    if not words:
        errs.append("summary vazio")
    elif words > SUMMARY_MAX_WORDS:
        errs.append(f"summary com {words} palavras (máx. {SUMMARY_MAX_WORDS})")
    return errs


# ------------------------------------------------------------------ épico
def check_epic(path: Path, sections: list[str]) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if not path.exists():
        return ["epico.md ausente"], warns
    lines = path.read_text(encoding="utf-8").splitlines()
    h1 = [l for l in lines if l.startswith("# ")]
    if not h1:
        errs.append("épico sem título H1")
    elif not re.match(r"^#\s+Épico\s+[\dX]+\.[\dY]+\s*:", h1[0], re.IGNORECASE):
        errs.append("título do épico fora do padrão `# Épico X.Y: <quem> <verbo> <o quê>…`")
    found = [l[3:].strip() for l in lines if l.startswith("## ")]
    pos = -1
    for s in sections:
        idx = next((i for i, f in enumerate(found) if f.lower() == s.lower()), None)
        if idx is None:
            errs.append(f"épico sem a seção obrigatória `## {s}`")
        elif idx < pos:
            errs.append(f"seção `## {s}` fora da ordem do padrão")
        else:
            pos = idx
    extras = [f for f in found if f.lower() not in {s.lower() for s in sections}]
    if extras:
        errs.append(f"épico com seções fora do padrão: {', '.join(extras)}")
    text = "\n".join(lines)
    if "| Situação |" not in text and "| Situação|" not in text:
        warns.append("tabela Situação/Hoje/Depois não encontrada em `O que muda no dia a dia`")
    if re.search(r"(?i)\bcomo\b.{0,40}\bquero\b", text):
        errs.append("épico contém história de usuário (o padrão de épico da squad não permite)")
    return errs, warns


# ------------------------------------------------------------------ histórias
def parse_stories(path: Path) -> list[dict]:
    stories: list[dict] = []
    cur: dict | None = None
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = STORY_HEAD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "titulo": m.group(2), "linha": n, "cobre": [], "criterios": [], "texto": ""}
            stories.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("## "):
            cur = None
            continue
        cur["texto"] += line + "\n"
        c = COBRE_RE.match(line.strip())
        if c:
            cur["cobre"] = RULE_REF_RE.findall(c.group(1))
            continue
        ca = CA_RE.match(line.strip())
        if ca:
            refs = RULE_REF_RE.findall(ca.group(2) or "")
            cur["criterios"].append({"id": ca.group(1), "regras": refs, "texto": ca.group(3).strip(), "linha": n})
    return stories


def check_stories(stories: list[dict], cfg: dict, size: str | None, universe: set[str]) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    cob = cfg.get("cobertura") or {}
    fmt = re.compile(cob.get("formato_criterio") or r"(?is)\bdado\b.+\bquando\b.+\bent[aã]o\b")
    vague = [w.lower() for w in cob.get("palavras_vagas") or []]
    lim = (cfg.get("tamanhos") or {}).get(size or "", {})
    if not stories:
        return ["historias.md sem nenhuma história `## H-01 · título`"], warns
    if lim.get("max_historias") and len(stories) > lim["max_historias"]:
        errs.append(f"{len(stories)} histórias para tamanho {size} (máx. {lim['max_historias']}): dividir a demanda")
    seen: set[str] = set()
    for s in stories:
        sid = s["id"]
        if sid in seen:
            errs.append(f"{sid} duplicada")
        seen.add(sid)
        if not USER_STORY_RE.search(s["texto"]):
            errs.append(f"{sid} sem a linha **História:** Como …, quero …, para …")
        if not s["cobre"]:
            errs.append(f"{sid} sem a linha **Cobre:** com as regras")
        if not s["criterios"]:
            errs.append(f"{sid} sem critérios de aceite (`- **CA-01** [RN-…]: Dado…, quando…, então…`)")
        if lim.get("max_criterios_por_historia") and len(s["criterios"]) > lim["max_criterios_por_historia"]:
            warns.append(f"{sid} com {len(s['criterios'])} critérios: talvez sejam duas histórias")
        ca_seen: set[str] = set()
        cited: set[str] = set()
        for c in s["criterios"]:
            tag = f"{sid}/{c['id']}"
            if c["id"] in ca_seen:
                errs.append(f"{tag} duplicado")
            ca_seen.add(c["id"])
            if not fmt.search(c["texto"]):
                errs.append(f"{tag} fora do formato Dado/Quando/Então")
            low = c["texto"].lower()
            hits = [w for w in vague if w in low]
            if hits:
                warns.append(f"{tag} com termo vago ({', '.join(hits)}): troque por algo observável")
            if not c["regras"]:
                warns.append(f"{tag} não cita regra: é comportamento sem regra de negócio?")
            for r in c["regras"]:
                cited.add(r)
                if r not in universe:
                    errs.append(f"{tag} cita {r}, que não existe na Base de Conhecimento nem em regras.md")
        for r in s["cobre"]:
            if r not in universe:
                errs.append(f"{sid} declara cobrir {r}, que não existe na Base de Conhecimento nem em regras.md")
        missing = cited - set(s["cobre"])
        if missing:
            warns.append(f"{sid}: critérios citam {', '.join(sorted(missing))}, ausentes em **Cobre:**")
        loose = set(s["cobre"]) - cited
        if loose:
            errs.append(f"{sid} declara cobrir {', '.join(sorted(loose))} sem nenhum critério que cite")
    return errs, warns


# ------------------------------------------------------------------ avaliação
def evaluate(did: str, root: Path = REPO_ROOT) -> dict:
    cfg = load_config(root)
    d = demand_dir(root, did)
    rep: dict = {"demanda": did, "ok": False, "status": None, "erros": [], "avisos": [], "matriz": [], "historias": []}
    if not DEMAND_ID_RE.match(did):
        rep["erros"].append("id de demanda inválido")
        return rep
    result = read_json(d / "result.json")
    rerrs = validate_result(result, did)
    rep["erros"] += rerrs
    if not isinstance(result, dict):
        return rep
    rep["status"] = result.get("status")
    if result.get("status") == "blocked":
        rep["ok"] = not rerrs
        rep["avisos"].append(f"demanda bloqueada: {result.get('blocked_reason')}")
        return rep

    # universo de regras e fontes
    kb_rules = {r.id: r for r in kbmod.load_rules(root)}
    demand_sources = d / "fontes.yaml"
    sources = kbmod.load_sources(root, extra=[demand_sources])
    cands: dict[str, kbmod.Rule] = {}
    if (d / "regras.md").exists():
        parsed = kbmod.parse_rules(d / "regras.md", root)
        for e in kbmod.validate_rules(parsed, sources, candidates=True):
            rep["erros"].append(f"regras.md {e['id']}: {e['erro']}")
        cands = {r.id: r for r in parsed}
    for e in kbmod.validate_sources({k: v for k, v in sources.items() if k.startswith("SRC-DEM-")}):
        rep["erros"].append(f"fontes.yaml {e['id']}: {e['erro']}")
    universe = set(kb_rules) | set(cands)

    # pesquisa e fontes
    pesq = d / "pesquisa.md"
    if not pesq.exists():
        rep["erros"].append("pesquisa.md ausente (fontes consultadas e achados)")
    fontes = [str(s) for s in result.get("fontes") or []]
    if not fontes:
        rep["erros"].append("result.json sem fontes citadas")
    for s in fontes:
        if not SOURCE_ID_RE.match(s):
            rep["erros"].append(f"fonte fora do padrão: {s}")
        elif s not in sources:
            rep["erros"].append(f"fonte {s} não registrada (kb/fontes ou fontes.yaml da demanda)")
    if pesq.exists():
        ptxt = pesq.read_text(encoding="utf-8")
        unseen = [s for s in fontes if s not in ptxt]
        if unseen:
            rep["avisos"].append(f"fontes citadas no result.json e ausentes em pesquisa.md: {', '.join(unseen)}")

    # épico
    e_errs, e_warns = check_epic(d / "epico.md", (cfg.get("cobertura") or {}).get("secoes_epico") or [])
    rep["erros"] += e_errs
    rep["avisos"] += e_warns

    # histórias
    size = None
    try:
        from _common import load_yaml
        for item in load_yaml(root / ".harness" / "demandas.yaml") or []:
            if isinstance(item, dict) and item.get("id") == did:
                size = item.get("tamanho")
    except (OSError, ValueError):
        pass
    hpath = d / "historias.md"
    stories = parse_stories(hpath) if hpath.exists() else []
    if not hpath.exists():
        rep["erros"].append("historias.md ausente")
    else:
        s_errs, s_warns = check_stories(stories, cfg, size, universe)
        rep["erros"] += s_errs
        rep["avisos"] += s_warns
    ids = [s["id"] for s in stories]
    if sorted(result.get("historias") or []) != sorted(ids):
        rep["erros"].append(f"result.json lista histórias {result.get('historias')} e historias.md tem {ids}")
    rep["historias"] = [{"id": s["id"], "titulo": s["titulo"], "cobre": s["cobre"],
                         "criterios": len(s["criterios"])} for s in stories]

    # cobertura
    relevant = [str(r) for r in result.get("regras_relevantes") or []]
    if not relevant:
        rep["erros"].append("regras_relevantes vazio: nenhuma regra de negócio identificada")
    out_of_scope = {str(f.get("regra")): str(f.get("motivo")) for f in result.get("fora_do_escopo") or []
                    if isinstance(f, dict)}
    cited_by: dict[str, list[str]] = {}
    for s in stories:
        for c in s["criterios"]:
            for r in c["regras"]:
                cited_by.setdefault(r, []).append(f"{s['id']}/{c['id']}")
    for r in out_of_scope:
        if r not in universe:
            rep["erros"].append(f"fora_do_escopo cita {r}, que não existe")
        if r not in relevant:
            rep["avisos"].append(f"{r} está em fora_do_escopo mas não em regras_relevantes")
    weak = []
    for r in relevant:
        if not (RULE_ID_RE.match(r) or CANDIDATE_ID_RE.match(r)):
            rep["erros"].append(f"regra relevante com ID inválido: {r}")
            continue
        rule = kb_rules.get(r) or cands.get(r)
        if rule is None:
            rep["erros"].append(f"regra relevante {r} não existe na Base de Conhecimento nem em regras.md")
            continue
        where = cited_by.get(r, [])
        if where:
            sit = "coberta"
        elif r in out_of_scope:
            sit = "fora do escopo"
        else:
            sit = "SEM COBERTURA"
            if (cfg.get("cobertura") or {}).get("exigir_regra_coberta", True):
                rep["erros"].append(f"regra {r} sem critério de aceite e sem justificativa em fora_do_escopo")
        if rule.status == "revogada":
            rep["erros"].append(f"regra {r} está revogada: use a regra indicada nas notas ({rule.notas[:120]})")
        if rule.status in ("a confirmar", "conflito"):
            weak.append(r)
        rep["matriz"].append({"regra": r, "titulo": rule.titulo, "status": rule.status,
                              "origem": "kb" if r in kb_rules else "candidata",
                              "criterios": where, "situacao": sit, "motivo": out_of_scope.get(r)})
    extra_cited = sorted(set(cited_by) - set(relevant))
    if extra_cited:
        rep["avisos"].append(f"critérios citam regras fora de regras_relevantes: {', '.join(extra_cited)}")
    unused = sorted(set(cands) - set(relevant))
    if unused:
        rep["avisos"].append(f"regras candidatas não usadas: {', '.join(unused)}")
    if weak:
        rep["avisos"].append(f"regras a confirmar/em conflito usadas: {', '.join(weak)} — confirmar antes de publicar")
        if not (result.get("lacunas") or result.get("open_questions")):
            rep["erros"].append("há regras a confirmar/em conflito e nenhuma lacuna ou pergunta em aberto registrada")
    rep["ok"] = not rep["erros"]
    return rep


def render(rep: dict) -> str:
    out = [f"# Cobertura · {rep['demanda']}", "",
           f"Resultado: **{'OK' if rep['ok'] else 'REPROVADO'}** · status da entrega: {rep['status']} · "
           f"gerado por `coverage.py` (determinístico).", ""]
    if rep["matriz"]:
        out += ["## Matriz regra × critério", "", "| Regra | Status | Origem | Critérios | Situação |",
                "|---|---|---|---|---|"]
        for m in rep["matriz"]:
            crit = ", ".join(m["criterios"]) or (f"— ({m['motivo']})" if m["motivo"] else "—")
            out.append(f"| {m['titulo']} <sub>{m['regra']}</sub> | {m['status']} | {m['origem']} | {crit} | {m['situacao']} |")
        out.append("")
    if rep["historias"]:
        names = {m["regra"]: m["titulo"] for m in rep["matriz"]}
        out += ["## Histórias", "", "| História | Cobre | Critérios |", "|---|---|---|"]
        for h in rep["historias"]:
            cobre = "; ".join(names.get(r, r) for r in h["cobre"])
            out.append(f"| {h['titulo']} <sub>{h['id']}</sub> | {cobre} | {h['criterios']} |")
        out.append("")
    if rep["erros"]:
        out += ["## Erros (bloqueiam a entrega)", ""] + [f"- {e}" for e in rep["erros"]] + [""]
    if rep["avisos"]:
        out += ["## Avisos", ""] + [f"- {w}" for w in rep["avisos"]] + [""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demanda")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    a = ap.parse_args(argv)
    rep = evaluate(a.demanda, a.root)
    if not a.no_write and demand_dir(a.root, a.demanda).exists():
        atomic_write_text(demand_dir(a.root, a.demanda) / "cobertura.md", render(rep))
        write_json(demand_dir(a.root, a.demanda) / "cobertura.json", rep)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render(rep))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
