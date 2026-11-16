"""Máquina de estados das demandas (.tia/ledger.json). Estado só no disco, nunca na conversa.

    tia.sh ledger  sync
    tia.sh ledger  status [--json]
    tia.sh ledger  show D-001
    tia.sh ledger  g1 D-001 --approve|--skip [--note TXT]
    tia.sh ledger  iniciar D-001 --session-id ID
    tia.sh ledger  coletar D-001
    tia.sh ledger  abandonar D-001 --note TXT
    tia.sh ledger  g2 D-001 --accept|--rework|--reject --note TXT
    tia.sh ledger  k1 D-001 --regras RN-ITR-010,RN-ITR-011 --note TXT
    tia.sh ledger  g3 D-001 --approve --note "<resposta literal do humano>"
    tia.sh ledger  publicada D-001 --refs IT-70,IT-71

Ciclo (README, "Ciclo da demanda"):
  draft ─validate─► valid ─G1─► approved ─iniciar─► running ─coletar─► delivered | blocked
  running ─abandonar─► abandoned ;  blocked|abandoned ─G1─► approved (nova tentativa)
  delivered ─G2─► accepted | rework (motivo; máx. 2) | rejected ;  rework ─iniciar─► running
  accepted ─G3 (opcional)─► publish_approved ─publicada─► published
Gates só com resposta explícita do humano no turno (o script registra; quem pergunta é o agente).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (DEMAND_ID_RE, JIRA_KEY_RE, REPO_ROOT, P, RULE_ID_RE,  # noqa: E402
                     load_config, load_yaml, now_iso, read_json, write_json)

SCHEMA_VERSION = 1
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("valid",),
    "valid": ("approved", "draft"),
    "approved": ("running", "valid", "draft"),
    "running": ("delivered", "blocked", "abandoned"),
    "delivered": ("accepted", "rework", "rejected"),
    "blocked": ("approved", "valid", "draft"),
    "abandoned": ("approved", "valid", "draft"),
    "rework": ("running",),
    "accepted": ("publish_approved",),
    "rejected": (),
    "publish_approved": ("published",),
    "published": (),
}
ACTIVE = ("running",)
TERMINAL = ("accepted", "rejected", "published", "publish_approved")


class LedgerError(Exception):
    pass


def paths(root: Path) -> dict[str, Path]:
    return {"ledger": P(root, "ledger"), "demandas": P(root, "fila"), "dir": P(root, "demandas")}


def demand_hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


class Ledger:
    def __init__(self, root: Path = REPO_ROOT):
        self.root = root
        self.p = paths(root)
        data = read_json(self.p["ledger"])
        self.data: dict = data if isinstance(data, dict) else {"schema": SCHEMA_VERSION, "demandas": {}, "eventos": []}
        self.data.setdefault("demandas", {})
        self.data.setdefault("eventos", [])

    def save(self) -> None:
        self.data["atualizado"] = now_iso()
        write_json(self.p["ledger"], self.data)

    def get(self, did: str) -> dict:
        if did not in self.data["demandas"]:
            raise LedgerError(f"{did} não está no ledger (rode `ledger.py sync`)")
        return self.data["demandas"][did]

    def move(self, did: str, to: str, by: str, note: str | None = None, **extra) -> dict:
        d = self.get(did)
        frm = d["state"]
        if to not in TRANSITIONS.get(frm, ()):
            raise LedgerError(f"{did}: transição {frm} → {to} não permitida")
        d["state"] = to
        ev = {"em": now_iso(), "de": frm, "para": to, "por": by}
        if note:
            ev["nota"] = note
        ev.update(extra)
        d["historico"].append(ev)
        return d

    def active(self) -> str | None:
        for did, d in self.data["demandas"].items():
            if d["state"] in ACTIVE:
                return did
        return None

    # ---------------------------------------------------------------- comandos
    def sync(self) -> list[str]:
        import validate

        rep = validate.validate(self.p["demandas"], self.root)
        items = load_yaml(self.p["demandas"]) if self.p["demandas"].exists() else []
        by_id = {str(i.get("id")): i for i in items or [] if isinstance(i, dict)}
        bad = {e["demanda"] for e in rep["erros"]}
        changes = []
        for did, item in by_id.items():
            if not DEMAND_ID_RE.match(did):
                continue
            h = demand_hash(item)
            d = self.data["demandas"].get(did)
            if d is None:
                st = "draft" if did in bad else "valid"
                self.data["demandas"][did] = {"state": st, "hash": h, "tentativa": 0, "retrabalhos": 0,
                                              "sessao": None, "historico": [{"em": now_iso(), "de": None,
                                                                             "para": st, "por": "sync"}],
                                              "g1": None, "g2": [], "k1": [], "g3": None, "publicado": []}
                changes.append(f"{did}: nova ({st})")
                continue
            if did in bad and d["state"] in ("valid", "approved"):
                self.move(did, "draft", "sync", "fila inválida")
                changes.append(f"{did}: voltou para draft (erro na fila)")
            elif d["hash"] != h:
                d["hash"] = h
                if d["state"] == "approved":
                    self.move(did, "valid", "sync", "pedido mudou depois do G1: refazer G1")
                    changes.append(f"{did}: mudou depois do G1 → valid")
                else:
                    changes.append(f"{did}: pedido atualizado (estado {d['state']})")
            elif d["state"] == "draft" and did not in bad:
                self.move(did, "valid", "sync")
                changes.append(f"{did}: corrigida → valid")
        self.save()
        return changes

    def g1(self, did: str, approve: bool, note: str | None) -> None:
        d = self.get(did)
        if approve:
            if self.active() and self.active() != did:
                raise LedgerError(f"{self.active()} está em andamento: uma demanda por vez")
            self.move(did, "approved", "humano", note)
            d["g1"] = {"em": now_iso(), "decisao": "aprovada", "nota": note}
        else:
            if d["state"] not in ("valid", "blocked", "abandoned"):
                raise LedgerError(f"{did} em {d['state']}: nada a pular")
            d["g1"] = {"em": now_iso(), "decisao": "pulada", "nota": note}
            d["historico"].append({"em": now_iso(), "de": d["state"], "para": d["state"], "por": "humano",
                                   "nota": f"G1 pulado: {note or '-'}"})
        self.save()

    def iniciar(self, did: str, session_id: str) -> None:
        from _common import aviso_fora_do_perfil, habilidade_disponivel, perfil

        pf = perfil(self.root)
        if not habilidade_disponivel("demanda", pf):
            raise LedgerError(aviso_fora_do_perfil("demanda", pf))
        d = self.get(did)
        other = self.active()
        if other and other != did:
            raise LedgerError(f"{other} já está em andamento: uma demanda por vez")
        if d["state"] not in ("approved", "rework"):
            raise LedgerError(f"{did} em {d['state']}: iniciar exige approved (G1) ou rework (G2)")
        if not session_id or len(session_id) < 6:
            raise LedgerError("session-id inválido (use o id que o hook SessionStart informou)")
        d["tentativa"] += 1
        d["sessao"] = {"session_id": session_id, "inicio": now_iso(), "tentativa": d["tentativa"]}
        self.move(did, "running", "agente", f"tentativa {d['tentativa']}", session_id=session_id)
        self.save()

    def coletar(self, did: str) -> dict:
        import coverage

        d = self.get(did)
        if d["state"] != "running":
            raise LedgerError(f"{did} em {d['state']}: coletar exige running")
        rep = coverage.evaluate(did, self.root)
        ddir = self.p["dir"] / did
        if ddir.exists():
            coverage.atomic_write_text(ddir / "cobertura.md", coverage.render(rep))
            coverage.write_json(ddir / "cobertura.json", rep)
        if not rep["ok"]:
            raise LedgerError(f"{did}: entrega reprovada pela cobertura ({len(rep['erros'])} erro(s)); "
                              f"veja tia/demandas/{did}/cobertura.md")
        to = "blocked" if rep["status"] == "blocked" else "delivered"
        res = read_json(ddir / "result.json") or {}
        d["entrega"] = {"em": now_iso(), "status": to, "historias": res.get("historias"),
                        "regras": len(res.get("regras_relevantes") or []), "lacunas": len(res.get("lacunas") or []),
                        "avisos": len(rep["avisos"]), "summary": res.get("summary")}
        self.move(did, to, "coletar", res.get("blocked_reason"))
        self.save()
        return rep

    def abandonar(self, did: str, note: str) -> None:
        self.move(did, "abandoned", "humano", note)
        self.save()

    def g2(self, did: str, decision: str, note: str | None) -> None:
        d = self.get(did)
        if decision in ("rework", "reject") and not (note or "").strip():
            raise LedgerError("retrabalho e rejeição exigem motivo (--note)")
        if decision == "rework":
            limit = int(load_config(self.root).get("max_retrabalho", 2))
            if d["retrabalhos"] >= limit:
                raise LedgerError(f"{did} já teve {limit} retrabalhos: divida a demanda ou rejeite")
            d["retrabalhos"] += 1
        to = {"accept": "accepted", "rework": "rework", "reject": "rejected"}[decision]
        self.move(did, to, "humano", note)
        d["g2"].append({"em": now_iso(), "decisao": to, "nota": note, "tentativa": d["tentativa"]})
        self.save()

    def k1(self, did: str, regras: list[str], note: str | None) -> None:
        d = self.get(did)
        bad = [r for r in regras if not RULE_ID_RE.match(r)]
        if bad:
            raise LedgerError(f"IDs fora do padrão RN-XXX-NNN: {', '.join(bad)}")
        d["k1"].append({"em": now_iso(), "regras": regras, "nota": note})
        self.data["eventos"].append({"em": now_iso(), "tipo": "K1", "demanda": did, "regras": regras})
        self.save()

    def g3(self, did: str, note: str) -> None:
        if not (note or "").strip():
            raise LedgerError("G3 exige a resposta literal do humano em --note")
        d = self.get(did)
        self.move(did, "publish_approved", "humano", note)
        d["g3"] = {"em": now_iso(), "aprovacao": note}
        self.save()

    def publicada(self, did: str, refs: list[str]) -> None:
        bad = [r for r in refs if not (JIRA_KEY_RE.match(r) or r.startswith("http"))]
        if bad or not refs:
            raise LedgerError(f"refs inválidas: {bad or 'nenhuma'} (chaves Jira ou URLs)")
        d = self.get(did)
        d["publicado"] = refs
        self.move(did, "published", "agente", ", ".join(refs))
        self.save()

    def status(self) -> dict:
        rows = []
        for did, d in sorted(self.data["demandas"].items()):
            rows.append({"id": did, "estado": d["state"], "tentativa": d["tentativa"], "retrabalhos": d["retrabalhos"],
                         "sessao": (d.get("sessao") or {}).get("session_id"),
                         "ultima": (d["historico"][-1] if d["historico"] else None)})
        ready = [r["id"] for r in rows if r["estado"] in ("valid", "blocked", "abandoned")]
        return {"ativa": self.active(), "prontas_para_g1": ready,
                "aprovadas": [r["id"] for r in rows if r["estado"] == "approved"],
                "aguardando_g2": [r["id"] for r in rows if r["estado"] == "delivered"],
                "retrabalho": [r["id"] for r in rows if r["estado"] == "rework"],
                "demandas": rows}


# ------------------------------------------------------------------ C1: alteração no Confluence
def confluence_policy(cfg: dict, espaco: str | None = None, space_id: str | None = None) -> tuple[str | None, str]:
    """(chave do espaço, política) pela chave ou pelo id; espaço desconhecido usa `padrao`."""
    conf = cfg.get("confluence") or {}
    for key, e in (conf.get("espacos") or {}).items():
        if (espaco and key.upper() == espaco.upper()) or (space_id and str(e.get("id")) == str(space_id)):
            return key, e.get("politica", "somente_leitura")
    return None, conf.get("padrao", "somente_leitura")


def c1_authorize(root: Path, espaco: str, pagina: str, nota: str, titulo: str | None = None) -> dict:
    """Registra a autorização da humana para alterar UMA página (ou criar uma, `pagina=novo`) no espaço."""
    from datetime import datetime, timedelta

    if not (nota or "").strip():
        raise LedgerError("C1 exige a resposta literal da humana em --nota")
    cfg = load_config(root)
    key, pol = confluence_policy(cfg, espaco=espaco)
    if pol != "manter":
        raise LedgerError(f"espaço {espaco} é somente leitura: o harness nunca altera páginas nele "
                          "(aponte a dúvida em tia/kb/apontamentos.md)")
    if pagina != "novo" and not pagina.isdigit():
        raise LedgerError("--pagina deve ser o id numérico da página ou `novo`")
    horas = int((cfg.get("confluence") or {}).get("c1_validade_horas") or 24)
    L = Ledger(root)
    reg = {"em": now_iso(), "espaco": key, "pagina": pagina, "titulo": titulo, "nota": nota,
           "valido_ate": (datetime.now().astimezone() + timedelta(hours=horas)).isoformat(timespec="seconds")}
    L.data.setdefault("c1", []).append(reg)
    L.data["eventos"].append({"em": reg["em"], "tipo": "C1", "espaco": key, "pagina": pagina})
    L.save()
    return reg


def c1_valid(root: Path, pagina: str | None) -> dict | None:
    """C1 vigente para a página (ou `novo`), ou None."""
    from datetime import datetime

    led = read_json(P(root, "ledger")) or {}
    now = datetime.now().astimezone()
    for reg in reversed(led.get("c1") or []):
        try:
            if str(reg.get("pagina")) == str(pagina) and datetime.fromisoformat(reg["valido_ate"]) >= now:
                return reg
        except (KeyError, ValueError):
            continue
    return None


def render_status(st: dict) -> str:
    out = [f"Ativa: {st['ativa'] or '—'} · prontas para G1: {', '.join(st['prontas_para_g1']) or '—'} · "
           f"aguardando G2: {', '.join(st['aguardando_g2']) or '—'}", "",
           "| Demanda | Estado | Tentativa | Retrabalhos | Último evento |", "|---|---|---|---|---|"]
    for r in st["demandas"]:
        u = r["ultima"] or {}
        out.append(f"| {r['id']} | {r['estado']} | {r['tentativa']} | {r['retrabalhos']} | "
                   f"{u.get('em', '')} {u.get('por', '')} {u.get('nota', '') or ''} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync")
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("id")
    s = sub.add_parser("g1")
    s.add_argument("id")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--skip", action="store_true")
    s.add_argument("--note")
    s = sub.add_parser("c1", help="autoriza alterar UMA página do Confluence (só espaço com política manter)")
    s.add_argument("--espaco", required=True)
    s.add_argument("--pagina", required=True, help="id numérico da página, ou `novo` para criar")
    s.add_argument("--titulo")
    s.add_argument("--nota", required=True, help="resposta literal da humana")
    sub.add_parser("c1-lista")
    s = sub.add_parser("iniciar")
    s.add_argument("id")
    s.add_argument("--session-id", required=True)
    s = sub.add_parser("coletar")
    s.add_argument("id")
    s = sub.add_parser("abandonar")
    s.add_argument("id")
    s.add_argument("--note", required=True)
    s = sub.add_parser("g2")
    s.add_argument("id")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--accept", action="store_true")
    g.add_argument("--rework", action="store_true")
    g.add_argument("--reject", action="store_true")
    s.add_argument("--note")
    s = sub.add_parser("k1")
    s.add_argument("id")
    s.add_argument("--regras", required=True)
    s.add_argument("--note")
    s = sub.add_parser("g3")
    s.add_argument("id")
    s.add_argument("--approve", action="store_true", required=True)
    s.add_argument("--note", required=True)
    s = sub.add_parser("publicada")
    s.add_argument("id")
    s.add_argument("--refs", required=True)
    a = ap.parse_args(argv)
    L = Ledger(a.root)
    try:
        if a.cmd == "sync":
            ch = L.sync()
            print("\n".join(ch) if ch else "sem mudanças")
        elif a.cmd == "status":
            st = L.status()
            print(json.dumps(st, ensure_ascii=False, indent=2) if a.json else render_status(st))
        elif a.cmd == "show":
            print(json.dumps(L.get(a.id), ensure_ascii=False, indent=2))
        elif a.cmd == "g1":
            L.g1(a.id, a.approve, a.note)
            print(f"{a.id}: G1 {'aprovado' if a.approve else 'pulado'}")
        elif a.cmd == "c1":
            reg = c1_authorize(a.root, a.espaco, a.pagina, a.nota, a.titulo)
            print(f"C1: {reg['espaco']} página {reg['pagina']} autorizada até {reg['valido_ate']} "
                  "(cada escrita ainda pede confirmação)")
        elif a.cmd == "c1-lista":
            for reg in (L.data.get("c1") or [])[-20:]:
                print(f"{reg['em']}  {reg['espaco']}  {reg['pagina']}  até {reg['valido_ate']}  {reg.get('titulo') or ''}")
        elif a.cmd == "iniciar":
            L.iniciar(a.id, a.session_id)
            print(f"{a.id}: running (tentativa {L.get(a.id)['tentativa']})")
        elif a.cmd == "coletar":
            rep = L.coletar(a.id)
            print(f"{a.id}: {L.get(a.id)['state']} — {len(rep['avisos'])} aviso(s); veja cobertura.md")
        elif a.cmd == "abandonar":
            L.abandonar(a.id, a.note)
            print(f"{a.id}: abandoned")
        elif a.cmd == "g2":
            dec = "accept" if a.accept else "rework" if a.rework else "reject"
            L.g2(a.id, dec, a.note)
            print(f"{a.id}: {L.get(a.id)['state']}")
        elif a.cmd == "k1":
            L.k1(a.id, [r.strip() for r in a.regras.split(",") if r.strip()], a.note)
            print(f"{a.id}: K1 registrado")
        elif a.cmd == "g3":
            L.g3(a.id, a.note)
            print(f"{a.id}: publicação aprovada (cada escrita no Jira/Confluence ainda pede confirmação)")
        elif a.cmd == "publicada":
            L.publicada(a.id, [r.strip() for r in a.refs.split(",") if r.strip()])
            print(f"{a.id}: published")
    except LedgerError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
