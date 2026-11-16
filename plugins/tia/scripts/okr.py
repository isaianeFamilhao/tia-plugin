"""OKRs: esquema e avaliador pragmático (skill /tia-okr). Zero tokens.

    tia.sh okr validar [ARQUIVO] [--grupo ARQUIVO]   # padrão: tia/kb/okrs.yaml (rascunhos em tia/propostas/)
    tia.sh okr listar [--ativos] [--nivel grupo|time]

Reprova o que quebra o OKR (KR que é entrega, KR de outcome sem meta, estrutura inválida). Avisa o que
merece conversa, sem dogma: foco (≤3 objetivos, 2–4 KRs), tensão saudável, baseline, momento do time,
alinhamento e dados disponíveis.

Nível: cada ciclo pode ter `nivel: grupo | time` (ausente = time, como nos arquivos antigos) e cada objetivo um
`id` no formato `OBJ-NN`. O `alinhamento` de um ciclo pode citar o `id` de um objetivo do grupo (ex.:
`alinhamento: OBJ-02`); texto livre segue valendo, com aviso no nível time. Os objetivos do grupo conhecidos são
os do próprio arquivo, os de `tia/kb/okrs.yaml` e os de `--grupo` (o arquivo de OKRs da pasta do GPM). Referência
a um id que não existe entre eles reprova; sem nenhum objetivo do grupo conhecido, a referência fica só com aviso.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, P, load_yaml  # noqa: E402

MOMENTOS = ("crescimento", "retencao", "descoberta", "eficiencia", "fundacao")
MODOS = ("comprometido", "aspiracional")
STATUS = ("rascunho", "ativo", "encerrado")
TIPOS_KR = ("outcome", "learning", "milestone", "baseline", "guardrail")
STATUS_DADOS = ("mensuravel_hoje", "sem_acesso", "ponto_cego", "manual")
NIVEIS = ("grupo", "time")
NIVEL_PADRAO = "time"
ID_RE = re.compile(r"^OBJ-\d{2,}$")
REF_RE = re.compile(r"\bOBJ-\d{2,}\b")
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


def nivel(c: dict) -> str:
    """Nível do ciclo; ausente = time (arquivos de antes do nível continuam valendo)."""
    v = c.get("nivel")
    return NIVEL_PADRAO if v is None else str(v).strip().lower()


def objetivos_do_grupo(ciclos: list[dict]) -> dict[str, list[dict]]:
    """id → ciclos de nível grupo que têm um objetivo com esse id."""
    ids: dict[str, list[dict]] = {}
    for c in ciclos:
        if nivel(c) != "grupo":
            continue
        for o in c.get("objetivos") or []:
            oid = str(o.get("id") or "").strip()
            if oid:
                ids.setdefault(oid, []).append(c)
    return ids


def _alinhamento(c: dict, tag: str, grupo: dict[str, list[dict]], errs: list, avisos: list) -> None:
    texto = str(c.get("alinhamento") or "").strip()
    if not texto:
        avisos.append(f"{tag}: sem alinhamento com objetivo superior — confirme se é intencional")
        return
    refs = REF_RE.findall(texto)
    if not refs:
        if nivel(c) == "time":
            avisos.append(f"{tag}: alinhamento em texto livre — se o grupo tem OKR registrado, cite o id do "
                          "objetivo (OBJ-NN) para o vínculo ser conferido")
        return
    if not grupo:
        avisos.append(f"{tag}: alinhamento com {', '.join(refs)} não conferido — nenhum OKR do grupo conhecido "
                      "(use --grupo <arquivo de OKRs do grupo>)")
        return
    for r in refs:
        if r not in grupo:
            errs.append(f"{tag}: alinhamento cita {r}, que não existe nos OKRs do grupo "
                        f"(conhecidos: {', '.join(sorted(grupo))})")


def validar(ciclos: list[dict], grupo_extra: list[dict] | None = None) -> dict:
    """`grupo_extra`: ciclos de outro arquivo (ex.: OKRs do grupo) usados só para conferir o alinhamento."""
    errs, avisos = [], []
    grupo = objetivos_do_grupo(list(ciclos) + list(grupo_extra or []))
    vistos_grupo: dict[tuple[str, str], str] = {}
    for c in ciclos:
        tag = f"{c.get('ciclo', '?')} · {c.get('time', '?')}"
        if nivel(c) not in NIVEIS:
            errs.append(f"{tag}: nivel deve ser {' | '.join(NIVEIS)}")
        ids_ciclo: set[str] = set()
        for o in c.get("objetivos") or []:
            if o.get("id") is None:
                if nivel(c) == "grupo":
                    avisos.append(f"{tag} · {str(o.get('titulo', '?'))[:50]}: objetivo do grupo sem id (OBJ-NN) — "
                                  "os times não conseguem citá-lo no alinhamento")
                continue
            oid = str(o["id"]).strip()
            if not ID_RE.match(oid):
                errs.append(f"{tag}: id de objetivo '{oid}' fora do formato OBJ-NN")
            elif oid in ids_ciclo:
                errs.append(f"{tag}: id {oid} repetido no ciclo")
            elif nivel(c) == "grupo" and (str(c.get("ciclo")), oid) in vistos_grupo:
                errs.append(f"{tag}: id {oid} já usado por outro OKR do grupo no ciclo {c.get('ciclo')} "
                            f"({vistos_grupo[(str(c.get('ciclo')), oid)]})")
            ids_ciclo.add(oid)
            if nivel(c) == "grupo":
                vistos_grupo.setdefault((str(c.get("ciclo")), oid), tag)
        for k in ("ciclo", "time", "horizonte", "momento", "modo", "status", "objetivos"):
            if not c.get(k):
                errs.append(f"{tag}: campo ausente: {k}")
        if c.get("momento") and c["momento"] not in MOMENTOS:
            errs.append(f"{tag}: momento deve ser {' | '.join(MOMENTOS)}")
        if c.get("modo") and c["modo"] not in MODOS:
            errs.append(f"{tag}: modo deve ser {' | '.join(MODOS)}")
        if c.get("status") and c["status"] not in STATUS:
            errs.append(f"{tag}: status deve ser {' | '.join(STATUS)}")
        _alinhamento(c, tag, grupo, errs, avisos)
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
                    avisos.append(f"{kt}: sem status dos dados — rode a checagem (/tia-metricas)")
            if not o.get("iniciativas"):
                avisos.append(f"{ot}: sem iniciativas mapeadas — elas são o meio, separadas dos KRs")
        if tipos_ciclo and "guardrail" not in tipos_ciclo:
            avisos.append(f"{tag}: nenhum guardrail — falta tensão saudável (qualidade, margem, suporte)")
    return {"ok": not errs, "erros": errs, "avisos": avisos}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validar")
    s.add_argument("arquivo", nargs="?", type=Path, default=P(REPO_ROOT, "kb", "okrs.yaml"))
    s.add_argument("--grupo", type=Path, help="arquivo com os OKRs do grupo, para conferir o alinhamento")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("listar")
    s.add_argument("--ativos", action="store_true")
    s.add_argument("--nivel", choices=NIVEIS, help="só os ciclos deste nível (ausente no arquivo = time)")
    a = ap.parse_args(argv)
    if a.cmd == "validar":
        kb_okrs = P(REPO_ROOT, "kb", "okrs.yaml")
        extra = load(a.grupo) if a.grupo else []
        if kb_okrs.resolve() != a.arquivo.resolve():
            extra += load(kb_okrs)
        rep = validar(load(a.arquivo), extra)
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print("OKRs: " + ("OK" if rep["ok"] else "REPROVADO"))
            for e in rep["erros"]:
                print(f"  ERRO  {e}")
            for w in rep["avisos"]:
                print(f"  AVISO {w}")
        return 0 if rep["ok"] else 1
    ciclos = [c for c in load(P(REPO_ROOT, "kb", "okrs.yaml"))
              if (not a.ativos or c.get("status") == "ativo") and (not a.nivel or nivel(c) == a.nivel)]
    for c in ciclos:
        marca = f" [{nivel(c)}]" if c.get("nivel") is not None else ""
        alin = REF_RE.findall(str(c.get("alinhamento") or ""))
        print(f"{c.get('ciclo')} · {c.get('time')}{marca} ({c.get('status')}, {c.get('modo')})"
              + (f" → {', '.join(alin)}" if alin else ""))
        for o in c.get("objetivos") or []:
            print(f"  {str(o['id']) + ' · ' if o.get('id') else ''}{o.get('titulo')}")
            for kr in o.get("krs") or []:
                print(f"    - {kr.get('texto')}  [{kr.get('tipo')}; dados: {kr.get('status_dados') or '?'}]")
    if not ciclos:
        print("Nenhum OKR" + (" do grupo" if a.nivel == "grupo" else " de time" if a.nivel == "time" else "")
              + " registrado" + (" ativo." if a.ativos else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
