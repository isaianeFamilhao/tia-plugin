"""OKRs: esquema e avaliador pragmático (skill /ada-okr). Zero tokens.

    python .harness/bin/okr.py validar [ARQUIVO]      # padrão: kb/okrs.yaml (rascunhos podem estar em .harness/propostas/)
    python .harness/bin/okr.py listar [--ativos]

Reprova o que quebra o OKR (KR que é entrega, KR de outcome sem meta, estrutura inválida). Avisa o que
merece conversa, sem dogma: foco (≤3 objetivos, 2–4 KRs), tensão saudável, baseline, momento do time,
alinhamento e dados disponíveis.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, load_yaml  # noqa: E402

MOMENTOS = ("crescimento", "retencao", "descoberta", "eficiencia", "fundacao")
MODOS = ("comprometido", "aspiracional")
STATUS = ("rascunho", "ativo", "encerrado")
TIPOS_KR = ("outcome", "learning", "milestone", "baseline", "guardrail")
STATUS_DADOS = ("mensuravel_hoje", "sem_acesso", "ponto_cego", "manual")
ENTREGA_RE = re.compile(r"(?i)^\s*(entregar|lan[cç]ar|implementar|criar|desenvolver|construir|publicar|migrar|"
                        r"fazer|concluir|finalizar|executar|realizar)\b")
# Sinal de resultado mensurável (não basta ter um número: "app v2" e "5 features" não são resultado).
METRICA_RE = re.compile(r"(?i)\bde\s+[<>≤≥]?\s*\d[\d.,]*\s*\S*\s+para\b|%|[<>≤≥]\s*\d|\b(abaixo|acima) de\s+\d"
                        r"|\btaxa\b|\bm[eé]dia\b|\bmediana\b|\bp\d{2}\b|\bNPS\b|\bCSAT\b|\bpor usu")
RECEITA_RE = re.compile(r"(?i)receita|faturamento|\bGMV\b|\bMRR\b|\bARR\b|\bLTV\b|\bticket m[eé]dio\b")
JARGAO_RE = re.compile(r"(?i)\b(sinergia|alavancar|world[- ]class|excel[eê]ncia|disruptiv|best[- ]in[- ]class|360)")


def load(path: Path) -> list[dict]:
    data = load_yaml(path) if path.exists() else []
    if isinstance(data, dict):
        data = [data]
    return data or []


def validar(ciclos: list[dict]) -> dict:
    errs, avisos = [], []
    for c in ciclos:
        tag = f"{c.get('ciclo', '?')} · {c.get('time', '?')}"
        for k in ("ciclo", "time", "horizonte", "momento", "modo", "status", "objetivos"):
            if not c.get(k):
                errs.append(f"{tag}: campo ausente: {k}")
        if c.get("momento") and c["momento"] not in MOMENTOS:
            errs.append(f"{tag}: momento deve ser {' | '.join(MOMENTOS)}")
        if c.get("modo") and c["modo"] not in MODOS:
            errs.append(f"{tag}: modo deve ser {' | '.join(MODOS)}")
        if c.get("status") and c["status"] not in STATUS:
            errs.append(f"{tag}: status deve ser {' | '.join(STATUS)}")
        if not str(c.get("alinhamento") or "").strip():
            avisos.append(f"{tag}: sem alinhamento com objetivo superior — confirme se é intencional")
        objs = c.get("objetivos") or []
        if len(objs) > 3:
            avisos.append(f"{tag}: {len(objs)} objetivos — acima de 3 o foco se dilui; vale priorizar")
        tipos_ciclo = []
        for o in objs:
            ot = f"{tag} · {o.get('titulo', '?')[:50]}"
            if not str(o.get("titulo") or "").strip():
                errs.append(f"{ot}: objetivo sem título")
            elif re.search(r"\d", o["titulo"]):
                avisos.append(f"{ot}: objetivo com número — o número mora no KR; o objetivo diz a mudança de estado")
            if o.get("titulo") and JARGAO_RE.search(o["titulo"]):
                avisos.append(f"{ot}: jargão no objetivo — troque por uma mudança concreta")
            krs = o.get("krs") or []
            if not 2 <= len(krs) <= 4:
                avisos.append(f"{ot}: {len(krs)} KR(s) — o usual é 2 a 4")
            for kr in krs:
                kt = f"{ot} · {str(kr.get('texto', '?'))[:60]}"
                texto, tipo = str(kr.get("texto") or ""), kr.get("tipo")
                tipos_ciclo.append(tipo)
                if not texto.strip():
                    errs.append(f"{kt}: KR sem texto")
                    continue
                if tipo not in TIPOS_KR:
                    errs.append(f"{kt}: tipo deve ser {' | '.join(TIPOS_KR)}")
                if ENTREGA_RE.search(texto) and tipo != "milestone" and not METRICA_RE.search(texto):
                    errs.append(f"{kt}: KR é entrega, não resultado — mova para iniciativas e reescreva como mudança mensurável")
                if tipo in ("outcome", "guardrail"):
                    if kr.get("meta") is None:
                        errs.append(f"{kt}: KR de {tipo} sem meta")
                    if kr.get("baseline") is None:
                        avisos.append(f"{kt}: sem baseline — use um KR de baseline (medir nas 2 primeiras semanas) "
                                      "antes de travar a meta")
                if tipo == "milestone" and not METRICA_RE.search(texto):
                    avisos.append(f"{kt}: marco sem valor mensurável (ex.: latência p95 de 800 ms para < 200 ms)")
                if c.get("momento") == "descoberta" and RECEITA_RE.search(texto):
                    avisos.append(f"{kt}: KR de receita em momento de descoberta — considere um KR de aprendizado")
                sd = kr.get("status_dados")
                if sd and sd not in STATUS_DADOS:
                    errs.append(f"{kt}: status_dados deve ser {' | '.join(STATUS_DADOS)}")
                if sd in ("ponto_cego", "manual"):
                    avisos.append(f"{kt}: check-in depende de {'instrumentação' if sd == 'ponto_cego' else 'medição manual'}")
                if not sd and tipo in ("outcome", "guardrail"):
                    avisos.append(f"{kt}: sem status dos dados — rode a checagem (/ada-metricas)")
            if not o.get("iniciativas"):
                avisos.append(f"{ot}: sem iniciativas mapeadas — elas são o meio, separadas dos KRs")
        if tipos_ciclo and "guardrail" not in tipos_ciclo:
            avisos.append(f"{tag}: nenhum guardrail — falta tensão saudável (qualidade, margem, suporte)")
    return {"ok": not errs, "erros": errs, "avisos": avisos}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validar")
    s.add_argument("arquivo", nargs="?", type=Path, default=REPO_ROOT / "kb" / "okrs.yaml")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("listar")
    s.add_argument("--ativos", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "validar":
        rep = validar(load(a.arquivo))
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print("OKRs: " + ("OK" if rep["ok"] else "REPROVADO"))
            for e in rep["erros"]:
                print(f"  ERRO  {e}")
            for w in rep["avisos"]:
                print(f"  AVISO {w}")
        return 0 if rep["ok"] else 1
    ciclos = [c for c in load(REPO_ROOT / "kb" / "okrs.yaml") if not a.ativos or c.get("status") == "ativo"]
    for c in ciclos:
        print(f"{c.get('ciclo')} · {c.get('time')} ({c.get('status')}, {c.get('modo')})")
        for o in c.get("objetivos") or []:
            print(f"  {o.get('titulo')}")
            for kr in o.get("krs") or []:
                print(f"    - {kr.get('texto')}  [{kr.get('tipo')}; dados: {kr.get('status_dados') or '?'}]")
    if not ciclos:
        print("Nenhum OKR registrado" + (" ativo." if a.ativos else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
