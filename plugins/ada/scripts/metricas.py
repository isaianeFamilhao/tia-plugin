"""Monitoramento de métricas: monitores ativados pela PM (gate M1), leituras e avaliador determinístico.

    ada.sh metricas  validar
    ada.sh metricas  ativar --arquivo <plano.yaml> --nota "<resposta literal da PM>"
    ada.sh metricas  ativos [--json]            # monitores ativos e quais estão devidos
    ada.sh metricas  avaliar --monitor M-001 --valor 12.5 [--data AAAA-MM-DD] [--fonte X] [--consulta "..."]
    ada.sh metricas  alertas [--dias 7] [--json]
    ada.sh metricas  resumo [--dias 7] [--json]  # base dos relatórios diário e semanal
    ada.sh metricas  encerrar --monitor M-001 --nota "<motivo>"

Quem busca o número é a Ada, na fonte que estiver conectada (MCP ou CLI), sempre só leitura. Quem decide
se é alerta é este script, pela regra do monitor — não a impressão do modelo.
Arquivos: `.ada/monitoramento/monitores.yaml` e `leituras.jsonl` (só por este script);
`ada/kb/metricas.yaml` e `ada/kb/okrs.yaml` (opcionais, aprendidos com o uso).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, P, atomic_write_text, load_yaml, now_iso, today  # noqa: E402

DIRECOES = ("menor_melhor", "maior_melhor")
CADENCIAS = {"diaria": 1, "semanal": 7}
CAMPOS = ("nome", "origem", "fonte", "consulta", "unidade", "direcao", "cadencia", "janela_dias")


class MetricasError(Exception):
    pass


def root_dir(root: Path) -> Path:
    return P(root, "monitoramento")


def load_monitors(root: Path) -> list[dict]:
    p = root_dir(root) / "monitores.yaml"
    return (load_yaml(p) or []) if p.exists() else []


def save_monitors(root: Path, mons: list[dict]) -> None:
    import yaml

    atomic_write_text(root_dir(root) / "monitores.yaml",
                      "# Gerado por metricas.py (gate M1). Não edite à mão.\n"
                      + yaml.safe_dump(mons, allow_unicode=True, sort_keys=False))


def readings(root: Path) -> list[dict]:
    p = root_dir(root) / "leituras.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# ------------------------------------------------------------------ validação
def _check_rule(m: dict, key: str) -> list[str]:
    r = m.get(key)
    if r is None:
        return []
    if not isinstance(r, dict) or not (("limite" in r) ^ ("variacao_pct" in r)):
        return [f"`{key}` deve ter exatamente um de: limite, variacao_pct"]
    v = r.get("limite", r.get("variacao_pct"))
    if not isinstance(v, (int, float)):
        return [f"`{key}` precisa de número"]
    if "variacao_pct" in r and v <= 0:
        return [f"`{key}.variacao_pct` deve ser > 0"]
    return []


def validate_monitor(m: dict) -> list[str]:
    errs = [f"campo ausente: {k}" for k in CAMPOS if m.get(k) in (None, "")]
    if m.get("direcao") and m["direcao"] not in DIRECOES:
        errs.append(f"direcao deve ser {' | '.join(DIRECOES)}")
    if m.get("cadencia") and m["cadencia"] not in CADENCIAS:
        errs.append(f"cadencia deve ser {' | '.join(CADENCIAS)}")
    if m.get("janela_dias") is not None and (not isinstance(m["janela_dias"], int) or not 1 <= m["janela_dias"] <= 120):
        errs.append("janela_dias deve ser inteiro de 1 a 120")
    errs += _check_rule(m, "alerta") + _check_rule(m, "critico")
    if not (m.get("alerta") or m.get("critico")):
        errs.append("defina ao menos `alerta` ou `critico` (limite ou variacao_pct)")
    for k in ("alerta", "critico"):
        if "variacao_pct" in (m.get(k) or {}) and m.get("baseline") is None:
            pass  # sem baseline, a variação é contra a leitura anterior
    q = str(m.get("consulta") or "").upper()
    if any(w in q.split() for w in ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT")):
        errs.append("consulta precisa ser só leitura (sem INSERT/UPDATE/DELETE/CREATE/DROP…)")
    return errs


def validate(root: Path = REPO_ROOT) -> list[str]:
    errs = []
    ids = set()
    for m in load_monitors(root):
        mid = m.get("id", "?")
        if mid in ids:
            errs.append(f"{mid}: ID duplicado")
        ids.add(mid)
        errs += [f"{mid}: {e}" for e in validate_monitor(m)]
    okrs = P(root, "kb", "okrs.yaml")
    if okrs.exists():
        import okr

        try:
            errs += [f"ada/kb/okrs.yaml: {e}" for e in okr.validar(okr.load(okrs))["erros"]]
        except Exception as e:  # noqa: BLE001
            errs.append(f"ada/kb/okrs.yaml: ilegível ({str(e).splitlines()[0]})")
    for f, key in (("metricas.yaml", "id"),):
        p = P(root, "kb", f)
        if p.exists():
            try:
                data = load_yaml(p)
            except Exception as e:  # noqa: BLE001
                errs.append(f"ada/kb/{f}: YAML inválido ({str(e).splitlines()[0]})")
                continue
            if data and not isinstance(data, list):
                errs.append(f"ada/kb/{f}: deve ser uma lista")
            for i, item in enumerate(data or []):
                if not isinstance(item, dict) or not item.get(key):
                    errs.append(f"ada/kb/{f}[{i}]: campo `{key}` obrigatório")
    return errs


# ------------------------------------------------------------------ M1: ativar
def ativar(root: Path, arquivo: Path, nota: str) -> list[dict]:
    if not (nota or "").strip():
        raise MetricasError("ativar exige a resposta literal da PM em --nota (gate M1)")
    plano = load_yaml(arquivo) or []
    plano = plano.get("monitores", []) if isinstance(plano, dict) else plano
    if not plano:
        raise MetricasError(f"{arquivo}: nenhum monitor no plano")
    errs = [f"{m.get('nome', '?')}: {e}" for m in plano for e in validate_monitor(m)]
    if errs:
        raise MetricasError("plano inválido — " + "; ".join(errs))
    mons = load_monitors(root)
    n = max([int(str(m["id"])[2:]) for m in mons if str(m.get("id", "")).startswith("M-")] or [0])
    novos = []
    for m in plano:
        n += 1
        ini = date.today()
        m = dict(m, id=f"M-{n:03d}", status="ativo", inicio=ini.isoformat(),
                 fim=(ini + timedelta(days=int(m["janela_dias"]))).isoformat(),
                 aprovado={"em": now_iso(), "nota": nota, "plano": str(arquivo).replace("\\", "/")})
        novos.append(m)
    save_monitors(root, mons + novos)
    return novos


def encerrar(root: Path, mid: str, nota: str) -> None:
    mons = load_monitors(root)
    for m in mons:
        if m.get("id") == mid:
            m["status"] = "encerrado"
            m["encerrado"] = {"em": now_iso(), "nota": nota}
            save_monitors(root, mons)
            return
    raise MetricasError(f"{mid} não existe")


# ------------------------------------------------------------------ avaliador
def _ref(m: dict, prev: list[dict]) -> float | None:
    if m.get("baseline") is not None:
        return float(m["baseline"])
    return float(prev[-1]["valor"]) if prev else None


def classify(m: dict, valor: float, prev: list[dict]) -> tuple[str, str]:
    """(status, detalhe). status: ok | alerta | critico | sem_referencia."""
    worse_up = m["direcao"] == "menor_melhor"
    ref = _ref(m, prev)
    for nivel in ("critico", "alerta"):
        r = m.get(nivel) or {}
        if "limite" in r:
            lim = float(r["limite"])
            if (valor >= lim) if worse_up else (valor <= lim):
                return nivel, f"{valor}{m['unidade']} {'≥' if worse_up else '≤'} limite de {nivel} {lim}{m['unidade']}"
        elif "variacao_pct" in r:
            if ref in (None, 0):
                continue
            delta = (valor - ref) / abs(ref) * 100
            ruim = delta > 0 if worse_up else delta < 0
            if ruim and abs(delta) >= float(r["variacao_pct"]):
                base = "baseline" if m.get("baseline") is not None else "leitura anterior"
                return nivel, f"variação de {delta:+.1f}% contra a {base} ({ref}{m['unidade']}); limite de {nivel}: {r['variacao_pct']}%"
    needs_ref = any("variacao_pct" in (m.get(k) or {}) for k in ("alerta", "critico"))
    only_var = needs_ref and not any("limite" in (m.get(k) or {}) for k in ("alerta", "critico"))
    if only_var and ref in (None, 0):
        return "sem_referencia", "primeira leitura sem baseline: vira referência para a próxima"
    return "ok", "dentro dos limites"


def avaliar(root: Path, mid: str, valor: float, data_ref: str | None = None, fonte: str | None = None,
            consulta: str | None = None) -> dict:
    m = next((x for x in load_monitors(root) if x.get("id") == mid), None)
    if not m:
        raise MetricasError(f"{mid} não existe")
    if m.get("status") != "ativo":
        raise MetricasError(f"{mid} está {m.get('status')}")
    prev = [r for r in readings(root) if r.get("monitor") == mid]
    status, detalhe = classify(m, valor, prev)
    rec = {"em": now_iso(), "monitor": mid, "nome": m["nome"], "valor": valor, "unidade": m["unidade"],
           "data_ref": data_ref or today(), "fonte": fonte or m["fonte"], "consulta": (consulta or "")[:300] or None,
           "status": status, "detalhe": detalhe}
    p = root_dir(root) / "leituras.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def ativos(root: Path) -> list[dict]:
    hoje = date.today()
    out = []
    lidas = readings(root)
    for m in load_monitors(root):
        if m.get("status") != "ativo":
            continue
        ult = max((r for r in lidas if r.get("monitor") == m["id"]), key=lambda r: r["em"], default=None)
        dias = (hoje - datetime.fromisoformat(ult["em"]).date()).days if ult else None
        devido = ult is None or dias >= CADENCIAS[m["cadencia"]]
        venceu = date.fromisoformat(m["fim"]) < hoje
        out.append({"id": m["id"], "nome": m["nome"], "origem": m["origem"], "fonte": m["fonte"],
                    "consulta": m["consulta"], "cadencia": m["cadencia"], "fim": m["fim"],
                    "devido": devido and not venceu, "janela_encerrada": venceu,
                    "ultima": ult and {k: ult[k] for k in ("valor", "status", "data_ref")}})
    return out


def alertas(root: Path, dias: int = 7) -> list[dict]:
    corte = datetime.now().astimezone() - timedelta(days=dias)
    last: dict[str, dict] = {}
    for r in readings(root):
        if datetime.fromisoformat(r["em"]) >= corte:
            last[r["monitor"]] = r
    return [r for r in last.values() if r["status"] in ("alerta", "critico")]


def resumo(root: Path, dias: int = 7) -> list[dict]:
    corte = datetime.now().astimezone() - timedelta(days=dias)
    lidas = [r for r in readings(root) if datetime.fromisoformat(r["em"]) >= corte]
    out = []
    for m in load_monitors(root):
        rs = [r for r in lidas if r["monitor"] == m["id"]]
        out.append({"id": m["id"], "nome": m["nome"], "origem": m["origem"], "status_monitor": m.get("status"),
                    "unidade": m["unidade"], "baseline": m.get("baseline"), "leituras": len(rs),
                    "primeira": rs[0]["valor"] if rs else None, "ultima": rs[-1]["valor"] if rs else None,
                    "pior_status": max((r["status"] for r in rs), key=["sem_referencia", "ok", "alerta", "critico"].index,
                                       default=None)})
    return out


# ------------------------------------------------------------------ plano de métricas (/ada-metricas)
CAMADAS = ("product_outcome", "business_outcome")
PAPEIS = ("principal", "guardrail", "apoio")
STATUS_DADOS = {"mensuravel_hoje": "mensurável hoje", "sem_acesso": "sem acesso", "ponto_cego": "ponto cego"}
PLANO_CAMPOS = ("nome", "camada", "papel", "formula", "janela", "direcao", "status_dados")
RAZAO_RE = __import__("re").compile(r"(?i)/|÷|\btaxa\b|\bm[eé]dia\b|\bmediana\b|\bp\d{2}\b|\bpor (usu[aá]rio|sess[aã]o|conta|pedido|cliente)\b|%|\bpropor[cç][aã]o\b|\bcoorte\b|\bratio\b")
VAIDADE_RE = __import__("re").compile(r"(?i)\b(total de|n[uú]mero de|quantidade de|qtd|page ?views?|downloads?|cadastrad[oa]s|cliques|impress[oõ]es|seguidores|visitas|acessos)\b")
EVENTO_RE = __import__("re").compile(r"^[a-z][a-z0-9_]{2,60}$")


def validar_plano(plano: dict) -> dict:
    """Reprova plano sem contexto, sem árvore completa, sem 1 principal e 1–2 guardrails, com número
    absoluto isolado, ou com ponto cego sem tracking spec. Avisa vaidade e baseline ausente."""
    errs, avisos = [], []
    for k, msg in (("problema", "problema do usuário"), ("objetivo_negocio", "objetivo de negócio"),
                   ("output", "output (a entrega, que não é sucesso)")):
        if not str(plano.get(k) or "").strip():
            errs.append(f"falta o {msg}: sem contexto não há métrica")
    ms = plano.get("metricas") or []
    if not isinstance(ms, list) or not ms:
        return {"ok": False, "erros": errs + ["nenhuma métrica"], "avisos": avisos, "monitoraveis": []}
    principais = [m for m in ms if m.get("papel") == "principal"]
    guardrails = [m for m in ms if m.get("papel") == "guardrail"]
    if len(principais) != 1:
        errs.append(f"precisa de exatamente 1 métrica principal (tem {len(principais)})")
    if not 1 <= len(guardrails) <= 2:
        errs.append(f"precisa de 1 a 2 guardrails (tem {len(guardrails)})")
    camadas = {m.get("camada") for m in ms}
    for c in CAMADAS:
        if c not in camadas:
            errs.append(f"árvore incompleta: nenhuma métrica de {c.replace('_', ' ')}")
    for m in ms:
        n = m.get("nome", "?")
        for k in PLANO_CAMPOS:
            if not str(m.get(k) or "").strip():
                errs.append(f"{n}: campo ausente: {k}")
        if m.get("camada") and m["camada"] not in CAMADAS:
            errs.append(f"{n}: camada deve ser {' | '.join(CAMADAS)} (output não é métrica de sucesso)")
        if m.get("papel") and m["papel"] not in PAPEIS:
            errs.append(f"{n}: papel deve ser {' | '.join(PAPEIS)}")
        if m.get("direcao") and m["direcao"] not in DIRECOES:
            errs.append(f"{n}: direcao deve ser {' | '.join(DIRECOES)}")
        st = m.get("status_dados")
        if st and st not in STATUS_DADOS:
            errs.append(f"{n}: status_dados deve ser {' | '.join(STATUS_DADOS)}")
        texto = f"{n} {m.get('formula', '')}"
        if m.get("formula") and not RAZAO_RE.search(str(m["formula"])):
            errs.append(f"{n}: número absoluto isolado — use taxa, proporção, média por usuário ou coorte")
        if VAIDADE_RE.search(texto):
            avisos.append(f"{n}: cheira a métrica de vaidade ou de volume — confirme o \"e daí?\"")
        if m.get("papel") == "principal" and not str(m.get("hipotese") or "").strip():
            errs.append(f"{n}: a principal precisa de hipótese causal (como move o negócio)")
        if st == "mensuravel_hoje" and m.get("baseline") is None:
            avisos.append(f"{n}: mensurável hoje sem baseline — puxe na fonte ({m.get('fonte') or 'fonte?'})")
        if st == "sem_acesso" and not str(m.get("acesso") or "").strip():
            avisos.append(f"{n}: sem acesso — diga o que falta (conector, permissão ou export)")
        if st == "ponto_cego":
            tr = m.get("tracking") or []
            if not tr:
                errs.append(f"{n}: ponto cego sem tracking spec (evento, gatilho, propriedades)")
            for ev in tr if isinstance(tr, list) else []:
                if not EVENTO_RE.match(str(ev.get("evento") or "")):
                    errs.append(f"{n}: evento de tracking precisa de nome em snake_case")
                if not str(ev.get("gatilho") or "").strip() or not ev.get("propriedades"):
                    errs.append(f"{n}: evento {ev.get('evento')} sem gatilho ou propriedades")
    if principais and principais[0].get("status_dados") == "ponto_cego":
        avisos.append("a métrica principal é ponto cego: o lançamento depende da instrumentação")
    monit = [m["nome"] for m in ms if m.get("status_dados") == "mensuravel_hoje"]
    return {"ok": not errs, "erros": errs, "avisos": avisos, "monitoraveis": monit}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validar")
    s = sub.add_parser("ativar")
    s.add_argument("--arquivo", type=Path, required=True)
    s.add_argument("--nota", required=True)
    s = sub.add_parser("ativos")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("avaliar")
    s.add_argument("--monitor", required=True)
    s.add_argument("--valor", type=float, required=True)
    s.add_argument("--data")
    s.add_argument("--fonte")
    s.add_argument("--consulta")
    for name in ("alertas", "resumo"):
        s = sub.add_parser(name)
        s.add_argument("--dias", type=int, default=7)
        s.add_argument("--json", action="store_true")
    s = sub.add_parser("encerrar")
    s.add_argument("--monitor", required=True)
    s.add_argument("--nota", required=True)
    s = sub.add_parser("plano", help="avalia um plano de métricas de outcome (/ada-metricas)")
    s.add_argument("arquivo", type=Path)
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "plano":
            rep = validar_plano(load_yaml(a.arquivo) or {})
            if a.json:
                print(json.dumps(rep, ensure_ascii=False, indent=2))
            else:
                print("Plano de métricas: " + ("OK" if rep["ok"] else "REPROVADO"))
                for e in rep["erros"]:
                    print(f"  ERRO  {e}")
                for w in rep["avisos"]:
                    print(f"  AVISO {w}")
                if rep["monitoraveis"]:
                    print("  Podem virar monitoramento agora: " + "; ".join(rep["monitoraveis"]))
            return 0 if rep["ok"] else 1
        if a.cmd == "validar":
            errs = validate(a.root)
            print("Monitoramento: OK" if not errs else "Monitoramento: ERROS\n" + "\n".join(f"  ERRO {e}" for e in errs))
            return 1 if errs else 0
        if a.cmd == "ativar":
            for m in ativar(a.root, a.arquivo, a.nota):
                print(f"{m['id']} · {m['nome']} — ativo até {m['fim']} ({m['cadencia']}, fonte: {m['fonte']})")
            return 0
        if a.cmd == "ativos":
            rows = ativos(a.root)
            if a.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                for r in rows:
                    flag = "DEVIDO" if r["devido"] else ("janela encerrada: propor encerrar" if r["janela_encerrada"] else "em dia")
                    print(f"- {r['nome']} ({r['origem']}, {r['fonte']}) — {flag}; última: {r['ultima'] or '—'}  ·  {r['id']}")
                if not rows:
                    print("Nenhum monitor ativo.")
            return 0
        if a.cmd == "avaliar":
            r = avaliar(a.root, a.monitor, a.valor, a.data, a.fonte, a.consulta)
            print(f"{r['nome']}: {r['valor']}{r['unidade']} — {r['status'].upper()} ({r['detalhe']})")
            return 0
        if a.cmd in ("alertas", "resumo"):
            rows = alertas(a.root, a.dias) if a.cmd == "alertas" else resumo(a.root, a.dias)
            if a.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            elif a.cmd == "alertas":
                for r in rows:
                    print(f"- {r['status'].upper()}: {r['nome']} — {r['detalhe']} ({r['data_ref']}, {r['fonte']})")
                if not rows:
                    print(f"Sem alertas nos últimos {a.dias} dias.")
            else:
                for r in rows:
                    print(f"- {r['nome']} ({r['origem']}): {r['primeira']} → {r['ultima']} {r['unidade']}, "
                          f"{r['leituras']} leitura(s), pior: {r['pior_status'] or '—'}")
                if not rows:
                    print("Nenhum monitor.")
            return 0
        if a.cmd == "encerrar":
            encerrar(a.root, a.monitor, a.nota)
            print(f"{a.monitor}: encerrado")
            return 0
    except MetricasError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
