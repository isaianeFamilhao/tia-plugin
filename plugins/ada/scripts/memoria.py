"""Memória da Ada: o que ela aprendeu sobre como a PM e o time gostam de trabalhar. Um arquivo por aprendizado.

    ada.sh memoria listar [--todas] [--escopo time|pessoal|global]
    ada.sh memoria validar
    ada.sh memoria gravar --escopo time|pessoal|global --nome <slug> --descricao "<uma linha>" \\
                          --aprendi "<comportamento>" --evidencia "<o que a PM disse, com data>" \\
                          [--aplicar-em geral,conversa] --nota "<resposta literal da PM>"
    ada.sh memoria revogar --nome <slug> [--escopo …] --motivo "<por quê>" --nota "<resposta literal da PM>"
    ada.sh memoria migrar [--de <memoria-pm.md antigo>] --escopo pessoal|time --nota "<resposta literal da PM>"
    ada.sh memoria contexto              # o que o SessionStart injeta (índice + pessoal.md)

Escopos (pastas): time = ada/memoria/time/ (versionada) · pessoal = ada/memoria/pessoal/ (fora do git) ·
global = ~/.ada/memoria/ (segue a pessoa entre projetos). `pessoal.md` (escrito pela PM, sem gate) fica em
ada/memoria/pessoal/ e em ~/.ada/.

Gate *Memória*: só grava com o "sim" da PM no turno, e a pergunta é "Guardo para você ou para o time?".
Nada é apagado: revogar = `status: revogada`, com data e motivo.
Precedência: princípios > políticas do time > pessoal do workspace > pessoal global. Pessoal ganha do time
em estilo, nunca em política.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELOS, REPO_ROOT, P, atomic_write_text, frontmatter, today  # noqa: E402

ESCOPOS = ("time", "pessoal", "global")
STATUS = ("ativa", "revogada")
ONDE = ("geral", "conversa", "épicos", "histórias", "relatórios", "dados", "confluence", "jira", "fluxo")
NOME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
MAX_DESCRICAO = 200
PESSOAL_MD = "pessoal.md"


def home_ada() -> Path:
    """~/.ada (ADA_HOME só para testes)."""
    return Path(os.environ["ADA_HOME"]) if os.environ.get("ADA_HOME") else Path.home() / ".ada"


def pasta(escopo: str, root: Path | None = None) -> Path:
    if escopo == "time":
        return P(root, "memoria_time")
    if escopo == "pessoal":
        return P(root, "memoria_pessoal")
    if escopo == "global":
        return home_ada() / "memoria"
    raise ValueError(f"escopo desconhecido: {escopo} (use {', '.join(ESCOPOS)})")


def rotulo(escopo: str, root: Path | None, p: Path) -> str:
    if escopo == "global":
        return f"~/.ada/memoria/{p.name}"
    try:
        return p.resolve().relative_to(Path(root or REPO_ROOT).resolve()).as_posix()
    except ValueError:
        return str(p)


def _lista(v) -> list[str]:
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def parse(root: Path | None = None, escopos: tuple[str, ...] = ESCOPOS) -> list[dict]:
    """Aprendizados dos escopos pedidos, na ordem de precedência (time, pessoal, global)."""
    out = []
    for esc in escopos:
        d = pasta(esc, root)
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            if p.name.lower() == PESSOAL_MD:
                continue
            meta, corpo = frontmatter(p)
            out.append({"escopo": esc, "arquivo": p, "onde": rotulo(esc, root, p), "meta": meta, "corpo": corpo.strip(),
                        "nome": str(meta.get("nome") or ""), "descricao": str(meta.get("descricao") or ""),
                        "status": str(meta.get("status") or "").lower()})
    return out


def ativas(root: Path | None = None) -> list[dict]:
    return [e for e in parse(root) if e["status"] == "ativa"]


def validate(root: Path | None = None) -> list[dict]:
    errs = []
    seen: dict[tuple[str, str], str] = {}
    for e in parse(root):
        m, where, nome = e["meta"], e["onde"], e["nome"] or e["arquivo"].stem
        def err(msg: str) -> None:
            errs.append({"id": f"MEM:{nome}", "onde": where, "erro": msg})
        if not m:
            err("sem frontmatter (--- nome, descricao, status ---)")
            continue
        if not NOME_RE.match(e["nome"]):
            err("`nome` deve ser slug (minúsculas, números e hífen)")
        elif e["nome"] != e["arquivo"].stem:
            err(f"`nome` ({e['nome']}) diferente do arquivo ({e['arquivo'].stem}.md)")
        key = (e["escopo"], e["nome"])
        if key in seen:
            err(f"nome duplicado no escopo {e['escopo']}")
        seen[key] = where
        if not e["descricao"]:
            err("`descricao` obrigatória (uma linha)")
        elif len(e["descricao"]) > MAX_DESCRICAO or "\n" in e["descricao"]:
            err(f"`descricao` deve ter uma linha de até {MAX_DESCRICAO} caracteres")
        if e["status"] not in STATUS:
            err(f"`status` deve ser {' | '.join(STATUS)}")
        if e["status"] == "revogada" and not (m.get("revogada_em") and m.get("motivo")):
            err("revogada exige `revogada_em` e `motivo`")
        bad = [x for x in _lista(m.get("aplicar_em")) if x.lower() not in ONDE]
        if bad:
            err(f"`aplicar_em` fora da lista ({', '.join(ONDE)}): {', '.join(bad)}")
        if m.get("desde") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(m.get("desde"))):
            err("`desde` deve ser AAAA-MM-DD")
    return errs


# ------------------------------------------------------------------ pessoal.md e contexto da sessão
def pessoal_paths(root: Path | None = None) -> list[tuple[str, Path]]:
    """(rótulo, caminho) dos pessoal.md, do mais forte para o mais fraco."""
    return [("workspace", P(root, "memoria_pessoal", PESSOAL_MD)), ("global", home_ada() / PESSOAL_MD)]


def pessoal_texto(p: Path) -> str:
    if not p.exists():
        return ""
    _, corpo = frontmatter(p)
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S).strip()
    return corpo


def contexto_sessao(root: Path | None = None) -> str:
    """Índice da Memória (só nome e descrição) + pessoal.md, em ordem de precedência."""
    secoes = []
    nomes = {"time": "do time", "pessoal": "pessoal (este workspace)", "global": "pessoal (global)"}
    ativos = ativas(root)
    if ativos:
        linhas = ["[ada] Memória (aprendizados ativos; precedência: time > pessoal do workspace > pessoal global; "
                  "o pessoal ganha em estilo, nunca em política). Detalhe: `ada.sh memoria listar`."]
        for esc in ESCOPOS:
            grupo = [e for e in ativos if e["escopo"] == esc]
            if grupo:
                linhas.append(f"Memória {nomes[esc]}:")
                linhas += [f"- {e['nome']}: {e['descricao']}" for e in grupo]
        secoes.append("\n".join(linhas))
    for rot, p in pessoal_paths(root):
        txt = pessoal_texto(p)
        if txt:
            secoes.append(f"[ada] pessoal.md ({rot}; estilo e atalhos da PM, nunca política):\n{txt}")
    return "\n\n".join(secoes)


# ------------------------------------------------------------------ escrita (gate Memória)
def _yaml_str(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def render(meta: dict, corpo: str) -> str:
    ordem = ("nome", "descricao", "status", "aplicar_em", "desde", "evidencia", "revogada_em", "motivo", "id", "gate")
    linhas = ["---"]
    for k in ordem + tuple(k for k in meta if k not in ordem):
        if k not in meta or meta[k] in (None, "", []):
            continue
        v = meta[k]
        if isinstance(v, list):
            linhas.append(f"{k}: [{', '.join(v)}]")
        else:
            linhas.append(f"{k}: {_yaml_str(v)}")
    linhas.append("---")
    return "\n".join(linhas) + "\n" + corpo.strip() + "\n"


def exigir_nota(nota: str | None) -> None:
    if not (nota or "").strip():
        raise SystemExit("gate Memória: informe --nota com a resposta literal da PM (o sim e para quem guardar)")


def gravar(root: Path | None, escopo: str, nome: str, descricao: str, aprendi: str, evidencia: str,
           aplicar_em: list[str], nota: str, extra: dict | None = None) -> Path:
    exigir_nota(nota)
    if not NOME_RE.match(nome):
        raise SystemExit(f"nome inválido: {nome} (slug: minúsculas, números e hífen)")
    p = pasta(escopo, root) / f"{nome}.md"
    if p.exists():
        raise SystemExit(f"{rotulo(escopo, root, p)} já existe: revogue e grave com outro nome, ou edite com a PM")
    meta = {"nome": nome, "descricao": descricao.strip(), "status": "ativa", "aplicar_em": aplicar_em or ["geral"],
            "desde": today(), "evidencia": evidencia, "gate": nota.strip(), **(extra or {})}
    corpo = f"**Aprendi:** {aprendi.strip()}\n"
    errs = _valida_meta(meta)
    if errs:
        raise SystemExit("; ".join(errs))
    atomic_write_text(p, render(meta, corpo))
    return p


def _valida_meta(meta: dict) -> list[str]:
    errs = []
    if not meta.get("descricao") or len(meta["descricao"]) > MAX_DESCRICAO:
        errs.append(f"descricao obrigatória, até {MAX_DESCRICAO} caracteres")
    bad = [x for x in meta.get("aplicar_em") or [] if x.lower() not in ONDE]
    if bad:
        errs.append(f"aplicar_em fora da lista ({', '.join(ONDE)}): {', '.join(bad)}")
    return errs


def revogar(root: Path | None, nome: str, motivo: str, nota: str, escopo: str | None = None) -> Path:
    exigir_nota(nota)
    if not motivo.strip():
        raise SystemExit("revogar exige --motivo")
    alvo = [e for e in parse(root, (escopo,) if escopo else ESCOPOS) if e["nome"] == nome]
    if not alvo:
        raise SystemExit(f"aprendizado {nome} não encontrado")
    if len(alvo) > 1:
        raise SystemExit(f"{nome} existe em mais de um escopo ({', '.join(e['escopo'] for e in alvo)}): use --escopo")
    e = alvo[0]
    meta = dict(e["meta"], status="revogada", revogada_em=today(), motivo=motivo.strip())
    atomic_write_text(e["arquivo"], render(meta, e["corpo"]))
    return e["arquivo"]


# ------------------------------------------------------------------ migração do formato antigo (kb/memoria-pm.md)
HEAD_RE = re.compile(r"^###\s+(PM-\d{3})\s*[·\-—:]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(Aprendi|Evidência|Aplicar em|Status|Desde|Revogada em|Motivo):\*\*\s*(.*)$")


def slug(texto: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "aprendizado"


def parse_antigo(path: Path) -> list[dict]:
    out, cur, fenced = [], None, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced, cur = not fenced, None
            continue
        if fenced:
            continue
        m = HEAD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "titulo": m.group(2), "campos": {}}
            out.append(cur)
        elif line.startswith("#"):
            cur = None
        elif cur and (f := FIELD_RE.match(line.strip())):
            cur["campos"][f.group(1)] = f.group(2).strip()
    return out


def migrar(root: Path | None, origem: Path, escopo: str, nota: str) -> list[Path]:
    """Um arquivo por PM-NNN no escopo pedido. Não apaga a origem. Idempotente (pula o que já existe)."""
    exigir_nota(nota)
    if not origem.exists():
        raise SystemExit(f"{origem} não existe")
    feitos = []
    for b in parse_antigo(origem):
        c = b["campos"]
        nome = slug(b["titulo"])
        p = pasta(escopo, root) / f"{nome}.md"
        if p.exists():
            continue
        meta = {"nome": nome, "descricao": (c.get("Aprendi") or b["titulo"])[:MAX_DESCRICAO],
                "status": (c.get("Status") or "ativa").lower(), "aplicar_em": _lista(c.get("Aplicar em")) or ["geral"],
                "desde": c.get("Desde"), "evidencia": c.get("Evidência"), "revogada_em": c.get("Revogada em"),
                "motivo": c.get("Motivo"), "id": b["id"], "gate": f"migrado de {origem.name}: {nota.strip()}"}
        atomic_write_text(p, render(meta, f"**Aprendi:** {c.get('Aprendi') or b['titulo']}\n"))
        feitos.append(p)
    return feitos


def modelo_pessoal() -> str:
    return (MODELOS / "pessoal.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("listar")
    s.add_argument("--todas", action="store_true")
    s.add_argument("--escopo", choices=ESCOPOS)
    sub.add_parser("validar")
    sub.add_parser("contexto")
    g = sub.add_parser("gravar")
    g.add_argument("--escopo", choices=ESCOPOS, required=True)
    g.add_argument("--nome", required=True)
    g.add_argument("--descricao", required=True)
    g.add_argument("--aprendi", required=True)
    g.add_argument("--evidencia", required=True)
    g.add_argument("--aplicar-em", default="geral")
    g.add_argument("--nota", required=True)
    r = sub.add_parser("revogar")
    r.add_argument("--nome", required=True)
    r.add_argument("--escopo", choices=ESCOPOS)
    r.add_argument("--motivo", required=True)
    r.add_argument("--nota", required=True)
    m = sub.add_parser("migrar")
    m.add_argument("--de", type=Path, default=None)
    m.add_argument("--escopo", choices=("time", "pessoal"), default="pessoal")
    m.add_argument("--nota", required=True)
    a = ap.parse_args(argv)
    root = a.root or REPO_ROOT

    if a.cmd == "listar":
        rows = [e for e in parse(root, (a.escopo,) if a.escopo else ESCOPOS) if a.todas or e["status"] == "ativa"]
        for e in rows:
            print(f"- [{e['escopo']}] {e['nome']}: {e['descricao']}"
                  + ("" if e["status"] == "ativa" else f" (revogada: {e['meta'].get('motivo')})"))
        if not rows:
            print("Memória vazia.")
        return 0
    if a.cmd == "validar":
        errs = validate(root)
        print(f"Memória: {len(ativas(root))} aprendizado(s) ativo(s) — " + ("OK" if not errs else "ERROS"))
        for e in errs:
            print(f"  ERRO {e['id']} ({e['onde']}): {e['erro']}")
        return 1 if errs else 0
    if a.cmd == "contexto":
        print(contexto_sessao(root) or "(Memória e pessoal.md vazios)")
        return 0
    if a.cmd == "gravar":
        p = gravar(root, a.escopo, a.nome, a.descricao, a.aprendi, a.evidencia, _lista(a.aplicar_em), a.nota)
        print(f"gravado: {rotulo(a.escopo, root, p)}")
        return 0
    if a.cmd == "revogar":
        p = revogar(root, a.nome, a.motivo, a.nota, a.escopo)
        print(f"revogado: {p.name}")
        return 0
    if a.cmd == "migrar":
        origem = a.de or (Path(root) / "kb" / "memoria-pm.md")
        feitos = migrar(root, origem, a.escopo, a.nota)
        print(f"{len(feitos)} aprendizado(s) migrado(s) para {pasta(a.escopo, root)}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
