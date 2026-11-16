"""Portfólio do GPM: times do grupo (config do time) e agregação do Jira por time, sem pessoas.

    tia.sh portfolio validar [--json]       # confere portfolio.times do .tia/config.yaml
    tia.sh portfolio agregar --entrada <resultado-jql.json> [--entrada …] [--janela 7] [--parado 5] [--json]
                             [--gravar]     # grava tia/relatorios/<data>-portfolio.json (já sem pessoas)
    tia.sh portfolio ultimo [--resumo] [--json]   # último retrato gravado (a abertura do GPM usa o resumo)

`portfolio.times` (perfil GPM): lista de times, cada um com `nome`, `jira_projeto` (chave do projeto) e, se
quiser, `board` (id do quadro). Sem pessoas na config: o portfólio é por time, nunca por responsável.

`agregar` lê o resultado das consultas JQL (o JSON do conector: `{"issues": [...]}`, uma lista de issues ou
uma lista de resultados; `-` lê da entrada padrão) e devolve, por time: itens em andamento por etapa,
travados (sinalizados, bloqueados por item aberto, ou sem movimento há `--parado` dias) e concluídos na
janela. Antes de qualquer conta, cada issue é reduzida a uma lista fechada de campos: responsável, relator,
criador, comentários e qualquer outro campo de pessoa são descartados e nunca chegam à saída nem ao disco.
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


# ------------------------------------------------------------------ agregação (item 7)
STATUS_TRAVADO_RE = re.compile(r"(?i)bloque|imped|blocked")
FLAG_VALORES = {"impediment", "impedimento", "flagged", "sinalizado"}
MAX_RESUMO = 100


def _data(v) -> str | None:
    """AAAA-MM-DD de um carimbo do Jira (`2026-11-10T14:03:22.123-0300`), ou None."""
    m = re.match(r"^\d{4}-\d{2}-\d{2}", str(v or ""))
    return m.group(0) if m else None


def _sinalizado(fields: dict) -> bool:
    if fields.get("flagged") is True:
        return True
    for k, v in fields.items():
        if not k.startswith("customfield_"):
            continue
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            val = x.get("value") if isinstance(x, dict) else x
            if isinstance(val, str) and val.strip().lower() in FLAG_VALORES:
                return True
    return False


def _bloqueado_por(fields: dict) -> list[str]:
    """Chaves que bloqueiam esta issue e ainda não terminaram (links "is blocked by")."""
    out = []
    for ln in fields.get("issuelinks") or []:
        if not isinstance(ln, dict):
            continue
        tipo = ln.get("type") or {}
        outra = ln.get("inwardIssue")
        rotulo = str(tipo.get("inward") or "")
        if not outra or not (re.search(r"(?i)blocked by|bloquead", rotulo) or str(tipo.get("name")).lower() == "blocks"):
            continue
        cat = (((outra.get("fields") or {}).get("status") or {}).get("statusCategory") or {}).get("key")
        if cat != "done" and outra.get("key"):
            out.append(str(outra["key"]))
    return out


def issue_limpa(raw: dict) -> dict | None:
    """Só os campos que o portfólio usa (lista fechada). Nenhum campo de pessoa passa daqui."""
    if not isinstance(raw, dict) or not raw.get("key"):
        return None
    f = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
    st = f.get("status") if isinstance(f.get("status"), dict) else {}
    cat = (st.get("statusCategory") or {}).get("key") if isinstance(st.get("statusCategory"), dict) else None
    key = str(raw["key"])
    projeto = ((f.get("project") or {}).get("key") if isinstance(f.get("project"), dict) else None) or key.split("-")[0]
    resumo = str(f.get("summary") or "").strip()
    return {
        "key": key,
        "projeto": str(projeto),
        "tipo": (f.get("issuetype") or {}).get("name") if isinstance(f.get("issuetype"), dict) else None,
        "resumo": resumo if len(resumo) <= MAX_RESUMO else resumo[:MAX_RESUMO - 1] + "…",
        "etapa": st.get("name") or "(sem etapa)",
        "categoria": cat or "new",
        "atualizado": _data(f.get("updated")),
        "concluido": _data(f.get("resolutiondate") or (f.get("statuscategorychangedate") if cat == "done" else None)),
        "sinalizado": _sinalizado(f),
        "bloqueado_por": _bloqueado_por(f),
    }


def _issues_de(obj) -> list[dict]:
    if isinstance(obj, list):
        out: list[dict] = []
        for x in obj:
            out += [x] if isinstance(x, dict) and "key" in x else _issues_de(x)
        return out
    if isinstance(obj, dict):
        for k in ("issues", "results", "values"):
            if isinstance(obj.get(k), list):
                return _issues_de(obj[k])
        if "key" in obj:
            return [obj]
    return []


def carregar(entradas: list[str]) -> list[dict]:
    """Lê os resultados JQL e já devolve as issues reduzidas (sem pessoas), sem repetir chave."""
    vistas: dict[str, dict] = {}
    for e in entradas:
        texto = sys.stdin.read() if e == "-" else Path(e).read_text(encoding="utf-8")
        for raw in _issues_de(json.loads(texto)):
            limpa = issue_limpa(raw)
            if limpa:
                vistas[limpa["key"]] = limpa
    return list(vistas.values())


def agregar(issues: list[dict], times_: list[dict], janela_dias: int = 7, parado_dias: int = 5,
            hoje: str | None = None) -> dict:
    from datetime import date

    d0 = date.fromisoformat(hoje) if hoje else date.today()

    def dias(s: str | None) -> int | None:
        return (d0 - date.fromisoformat(s)).days if s else None

    por_proj = {str(t.get("jira_projeto")): t for t in times_ if t.get("jira_projeto")}
    saida = {str(t.get("jira_projeto")): {"nome": t.get("nome"), "jira_projeto": t.get("jira_projeto"),
                                          "a_fazer": 0, "em_andamento": {}, "total_em_andamento": 0,
                                          "travados": [], "concluidos_janela": 0}
             for t in times_ if t.get("jira_projeto")}
    fora: dict[str, int] = {}
    for i in issues:
        t = saida.get(i["projeto"])
        if t is None:
            fora[i["projeto"]] = fora.get(i["projeto"], 0) + 1
            continue
        if i["categoria"] == "done":
            n = dias(i["concluido"])
            if n is not None and 0 <= n <= janela_dias:
                t["concluidos_janela"] += 1
            continue
        if i["categoria"] != "indeterminate":
            t["a_fazer"] += 1
            continue
        t["em_andamento"][i["etapa"]] = t["em_andamento"].get(i["etapa"], 0) + 1
        t["total_em_andamento"] += 1
        motivos = []
        if i["sinalizado"]:
            motivos.append("sinalizado")
        if i["bloqueado_por"]:
            motivos.append("bloqueado por " + ", ".join(i["bloqueado_por"]))
        if STATUS_TRAVADO_RE.search(i["etapa"]):
            motivos.append(f"etapa \"{i['etapa']}\"")
        parado = dias(i["atualizado"])
        if parado is not None and parado >= parado_dias:
            motivos.append(f"sem movimento há {parado} dias")
        if motivos:
            t["travados"].append({"key": i["key"], "resumo": i["resumo"], "etapa": i["etapa"], "motivos": motivos})
    ordem = [str(t.get("jira_projeto")) for t in times_ if t.get("jira_projeto") in por_proj]
    return {"gerado_em": d0.isoformat(), "janela_dias": janela_dias, "parado_dias": parado_dias,
            "issues": len(issues), "times": [saida[p] for p in ordem], "fora_do_portfolio": fora}


def render(rep: dict) -> str:
    out = [f"Portfólio em {rep['gerado_em']} · janela de {rep['janela_dias']} dias · parado = "
           f"{rep['parado_dias']}+ dias sem movimento", "",
           "| Time | Em andamento | Travados | Concluídos na janela | A fazer |", "|---|---|---|---|---|"]
    for t in rep["times"]:
        out.append(f"| {t['nome']} ({t['jira_projeto']}) | {t['total_em_andamento']} | {len(t['travados'])} | "
                   f"{t['concluidos_janela']} | {t['a_fazer']} |")
    for t in rep["times"]:
        if t["em_andamento"]:
            out += ["", f"**{t['nome']}** · por etapa: " + ", ".join(f"{k} {v}" for k, v in t["em_andamento"].items())]
        for tr in t["travados"]:
            out.append(f"- {tr['key']} · {tr['resumo']} · {tr['etapa']} · {'; '.join(tr['motivos'])}")
    if rep["fora_do_portfolio"]:
        out += ["", "Fora do portfólio (projeto sem time na config): "
                + ", ".join(f"{p} {n}" for p, n in rep["fora_do_portfolio"].items())]
    return "\n".join(out)


def ultimo(root: Path) -> tuple[Path | None, dict | None]:
    """Último `tia/relatorios/<data>-portfolio.json` (pela data no nome)."""
    from _common import P, read_json

    arqs = sorted(P(root, "relatorios").glob("????-??-??-portfolio.json"))
    if not arqs:
        return None, None
    return arqs[-1], read_json(arqs[-1])


def resumo(rep: dict, hoje: str | None = None) -> str:
    """Abertura do GPM: uma linha por time com trava; o resto numa linha só."""
    from datetime import date

    d0 = date.fromisoformat(hoje) if hoje else date.today()
    idade = (d0 - date.fromisoformat(rep["gerado_em"])).days
    out = [f"Retrato do portfólio de {rep['gerado_em']}" + (" (hoje)" if idade == 0 else f" (há {idade} dia(s): "
                                                             "rode a coleta da /tia:portfolio)")]
    ok = []
    for t in rep.get("times") or []:
        if t["travados"]:
            motivos = "; ".join(f"{tr['key']} {', '.join(tr['motivos'])}" for tr in t["travados"][:3])
            mais = f" (+{len(t['travados']) - 3})" if len(t["travados"]) > 3 else ""
            out.append(f"- {t['nome']}: {len(t['travados'])} travado(s) de {t['total_em_andamento']} em andamento"
                       f" · {motivos}{mais}")
        else:
            ok.append(t["nome"])
    if ok:
        out.append(f"- Sem travas: {', '.join(ok)}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validar")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("agregar")
    s.add_argument("--entrada", action="append", required=True, help="JSON do resultado JQL (`-` = entrada padrão)")
    s.add_argument("--janela", type=int, default=7, help="dias para contar concluídos (padrão 7)")
    s.add_argument("--parado", type=int, default=5, help="dias sem movimento para contar como travado (padrão 5)")
    s.add_argument("--hoje", help=argparse.SUPPRESS)
    s.add_argument("--json", action="store_true")
    s.add_argument("--gravar", action="store_true", help="grava tia/relatorios/<data>-portfolio.json")
    s = sub.add_parser("ultimo")
    s.add_argument("--resumo", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--hoje", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    root = a.root or DATA_ROOT
    if a.cmd == "ultimo":
        arq, rep = ultimo(root)
        if not rep:
            print("Nenhum retrato do portfólio ainda: rode /tia:portfolio.")
            return 0
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(resumo(rep, a.hoje) if a.resumo else render(rep))
        return 0
    if a.cmd == "agregar":
        cfg = load_config(root)
        val = validar_times(cfg)
        if val["erros"]:
            print("[tia] times do portfólio inválidos: " + "; ".join(val["erros"]), file=sys.stderr)
            return 1
        if not times(cfg):
            print("[tia] nenhum time em portfolio.times: diga \"Tia, configurar\" ou edite .tia/config.yaml",
                  file=sys.stderr)
            return 1
        rep = agregar(carregar(a.entrada), times(cfg), a.janela, a.parado, a.hoje)
        if a.gravar:
            from _common import P, write_json

            destino = P(root, "relatorios", f"{rep['gerado_em']}-portfolio.json")
            write_json(destino, rep)
            print(f"[tia] gravado: {destino.relative_to(root).as_posix()}", file=sys.stderr)
        print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else render(rep))
        return 0
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
