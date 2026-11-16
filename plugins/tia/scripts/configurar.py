"""Prepara um projeto para a Tia (cria o marcador .tia/config.yaml e a pasta tia/) ou atualiza os modelos copiados.
Só biblioteca padrão: roda com o Python do sistema antes de o ambiente do plugin existir.

    tia.sh configurar status [--json]
    tia.sh configurar criar --time "<nome>" --site <url> --cloud-id <id> --jira <CHAVE> \\
        --espaco "INT|282787868|Internal Tools|manter" [--espaco "PO|370737187|Políticas|somente_leitura" …] \\
        --nota "<resposta literal da PM>"
    tia.sh configurar criar --perfil gpm --time "<grupo>" --site <url> --cloud-id <id> \\
        --portfolio "Cadastro|CAD" --portfolio "Pagamentos|PAG|42" … [--espaco …] --nota "<resposta literal>"
        # GPM: times do grupo (nome|projeto|board opcional), sem fila; --jira opcional (padrão: projetos dos times)
    tia.sh configurar atualizar                       # lista modelos desatualizados, com diff
    tia.sh configurar atualizar --aplicar <arquivo> --nota "<resposta literal da PM>"

`criar` só cria o que não existe (nunca sobrescreve). Se o projeto já tem CLAUDE.md, a parte do time vai para
tia/CLAUDE.md e o CLAUDE.md da raiz ganha a linha `@tia/CLAUDE.md` (só acrescenta). Cada arquivo copiado
leva `modelo_versao`; `atualizar` compara com o modelo do plugin, mostra o diff e só troca com o sim da PM
(guarda cópia em .tia/cache/backup/).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELOS, REL, atomic_write_text, is_workspace, now_iso  # noqa: E402

VERSAO_RE = re.compile(r"modelo_versao:\s*(\d+)")
POLITICAS = ("manter", "somente_leitura")
GITIGNORE_BLOCO = """# Tia: máquina e pessoal fora do git (config, ledger e monitoramento ficam versionados)
.tia/logs/
.tia/cache/
tia/memoria/pessoal/
tia/demandas/*/packet.md
tia/demandas/*/metrics.json
**/.*.tmp
"""
PASTAS = [".tia/monitoramento", ".tia/logs", ".tia/cache", "tia/demandas", "tia/relatorios", "tia/propostas",
          "tia/memoria/time", "tia/memoria/pessoal", "tia/kb/fontes", "tia/kb/padroes"]
# destino no workspace → modelo no plugin (copiados uma vez; depois só a humana edita; `atualizar` compara)
MODELOS_COPIADOS = {
    ".tia/config.yaml": "config.time.yaml",
    "tia/demandas.yaml": "demandas.yaml",
    "tia/demandas.exemplo.yaml": "demandas.exemplo.yaml",
    "tia/kb/README.md": "kb-README.md",
    "tia/kb/padroes/epico.md": "padroes/epico.md",
    "tia/kb/padroes/historia.md": "padroes/historia.md",
    "tia/kb/apontamentos.md": "apontamentos.md",
    "tia/kb/prefixos.md": "prefixos.md",
    "tia/memoria/pessoal/pessoal.md": "pessoal.md",
}
SEM_VERSAO = {"tia/demandas.yaml", "tia/kb/apontamentos.md", "tia/kb/prefixos.md"}  # viram conteúdo do time
# Perfil da pasta (ver PERFIS em _common.py; aqui só biblioteca padrão). GPM não tem fila de demandas.
PERFIS = ("pm", "gpm")
SO_PM = {"tia/demandas", "tia/demandas.yaml", "tia/demandas.exemplo.yaml"}
PERFIL_RE = re.compile(r"(?m)^perfil:\s*['\"]?\s*([A-Za-z]+)")


def pastas(perfil: str = "pm") -> list[str]:
    return [p for p in PASTAS if perfil == "pm" or p not in SO_PM]


def modelos_copiados(perfil: str = "pm") -> dict[str, str]:
    if perfil == "pm":
        return dict(MODELOS_COPIADOS)
    out = {d: m for d, m in MODELOS_COPIADOS.items() if d not in SO_PM}
    out[".tia/config.yaml"] = "config.time.gpm.yaml"
    return out


def claude_modelo(perfil: str = "pm") -> str:
    return "CLAUDE.md" if perfil == "pm" else "CLAUDE.gpm.md"


def perfil_de(root: Path) -> str:
    """Perfil do config do time (sem PyYAML); sem config ou sem a chave = `pm`; valor inválido também (o doctor acusa)."""
    f = root / ".tia" / "config.yaml"
    m = PERFIL_RE.search(f.read_text(encoding="utf-8")) if f.exists() else None
    v = m.group(1).lower() if m else "pm"
    return v if v in PERFIS else "pm"


def versao(texto: str) -> int | None:
    m = VERSAO_RE.search(texto or "")
    return int(m.group(1)) if m else None


def claude_md_destino(root: Path) -> str:
    """CLAUDE.md da raiz, ou tia/CLAUDE.md se o projeto já tinha um que não é da Tia."""
    raiz = root / "CLAUDE.md"
    if (root / "tia" / "CLAUDE.md").exists():
        return "tia/CLAUDE.md"
    if raiz.exists() and versao(raiz.read_text(encoding="utf-8")) is None:
        return "tia/CLAUDE.md"
    return "CLAUDE.md"


def parse_espaco(s: str) -> tuple[str, dict]:
    partes = [p.strip() for p in s.split("|")]
    if len(partes) != 4 or not partes[0] or partes[3] not in POLITICAS:
        raise SystemExit(f"--espaco inválido: {s!r}. Formato: \"CHAVE|id|Nome|manter|somente_leitura\"")
    chave, sid, nome, pol = partes
    return chave, {"id": sid, "nome": nome, "politica": pol}


JIRA_CHAVE_RE = re.compile(r"^[A-Z][A-Z0-9]+$")


def parse_time(s: str) -> dict:
    """Time do portfólio do GPM: "Nome|CHAVE" ou "Nome|CHAVE|board"."""
    partes = [p.strip() for p in s.split("|")]
    if len(partes) not in (2, 3) or not partes[0] or not JIRA_CHAVE_RE.match(partes[1]):
        raise SystemExit(f"--portfolio inválido: {s!r}. Formato: \"Nome do time|CHAVE_DO_JIRA\" ou \"Nome|CHAVE|board\"")
    t = {"nome": partes[0], "jira_projeto": partes[1]}
    if len(partes) == 3 and partes[2]:
        t["board"] = partes[2]
    return t


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _jira_lista(jira) -> list[str]:
    return [j for j in ([jira] if isinstance(jira, str) else list(jira or [])) if str(j).strip()]


def render_config(time_: str, site: str, cloud_id: str, jira, espacos: list[tuple[str, dict]],
                  perfil: str = "pm", times: list[dict] | None = None) -> str:
    """`jira`: a chave do projeto (PM, exatamente um) ou a lista de projetos dos times (GPM, zero ou mais).
    `times` (só GPM): times do portfólio; sem `jira`, os projetos vêm dos times."""
    if perfil not in PERFIS:
        raise SystemExit(f"--perfil inválido: {perfil!r}. Use {' ou '.join(PERFIS)}")
    mantidos = [k for k, v in espacos if v["politica"] == "manter"]
    if len(mantidos) > 1:
        raise SystemExit(f"só um espaço pode ser `manter` (veio: {', '.join(mantidos)})")
    projetos = _jira_lista(jira)
    times = list(times or [])
    if times and perfil != "gpm":
        raise SystemExit("--portfolio é só do perfil GPM")
    vistos: set[str] = set()
    for tm in times:
        if tm["jira_projeto"] in vistos:
            raise SystemExit(f"projeto {tm['jira_projeto']} repetido no portfólio: um time por projeto")
        vistos.add(tm["jira_projeto"])
    if perfil == "gpm" and not projetos:
        projetos = [tm["jira_projeto"] for tm in times]
    if perfil == "pm" and len(projetos) != 1:
        raise SystemExit("perfil PM: informe exatamente um projeto do Jira (--jira CHAVE)")
    bloco = "\n".join(f"    {k}: {{id: {_q(v['id'])}, nome: {_q(v['nome'])}, politica: {v['politica']}}}"
                      for k, v in espacos) or "    {}"
    t = (MODELOS / modelos_copiados(perfil)[".tia/config.yaml"]).read_text(encoding="utf-8")
    t = t.replace("{site}", site).replace("{cloud_id}", cloud_id)
    if perfil == "pm":
        t = t.replace("{jira_projeto}", projetos[0])
    else:
        t = t.replace("{jira_lista}", "[" + ", ".join(_q(j) for j in projetos) + "]")
    t = t.replace("{espacos_lista}", "[" + ", ".join(k for k, _ in espacos) + "]")
    t = t.replace("{espacos_bloco}", bloco)
    if perfil == "gpm":
        tb = "\n".join("    - {" + ", ".join(f"{k}: {_q(v)}" for k, v in tm.items()) + "}" for tm in times)
        t = t.replace("{times_bloco}", tb or "    []")
    return t.replace("# Configuração DO TIME (workspace).", f"# Configuração DO TIME ({time_}).", 1)


def render_claude_md(time_: str, site: str, jira, espacos: list[tuple[str, dict]], perfil: str = "pm") -> str:
    linhas = []
    for k, v in espacos:
        if v["politica"] == "manter":
            linhas.append(f"| **{k}** · {v['nome']} (nosso espaço) | livre | só com **C1** por página | o que precisa ser documentado |")
        else:
            linhas.append(f"| **{k}** · {v['nome']} | quando necessário | **nunca** (nem comentário) | quando algo gerar dúvida |")
    projetos = ", ".join(_jira_lista(jira)) or "[a definir]"
    t = (MODELOS / claude_modelo(perfil)).read_text(encoding="utf-8")
    return (t.replace("{time}", time_).replace("{jira_projeto}", projetos).replace("{jira_projetos}", projetos)
            .replace("{site}", site).replace("{tabela_espacos}", "\n".join(linhas)))


def status(root: Path, perfil: str | None = None) -> dict:
    """Perfil: o do config do time, se já existe; senão o informado (padrão `pm`)."""
    perfil = perfil_de(root) if is_workspace(root) else (perfil or "pm")
    out = {"workspace": is_workspace(root), "perfil": perfil, "faltando": [], "desatualizados": [],
           "claude_md": claude_md_destino(root)}
    for p in pastas(perfil):
        if not (root / p).is_dir():
            out["faltando"].append(p + "/")
    alvos = modelos_copiados(perfil)
    alvos[out["claude_md"]] = claude_modelo(perfil)
    for dest, modelo in alvos.items():
        f = root / dest
        if not f.exists():
            out["faltando"].append(dest)
            continue
        if dest in SEM_VERSAO:
            continue
        atual, novo = versao(f.read_text(encoding="utf-8")), versao((MODELOS / modelo).read_text(encoding="utf-8"))
        if novo is not None and (atual is None or atual < novo):
            out["desatualizados"].append({"arquivo": dest, "versao": atual, "versao_plugin": novo})
    gi = root / ".gitignore"
    if not gi.exists() or ".tia/cache/" not in gi.read_text(encoding="utf-8"):
        out["faltando"].append(".gitignore (bloco da Tia)")
    return out


def criar(root: Path, time_: str, site: str, cloud_id: str, jira, espacos: list[str], nota: str,
          perfil: str = "pm", portfolio: list[str] | None = None) -> list[str]:
    if not (nota or "").strip():
        raise SystemExit("informe --nota com a resposta literal da humana aprovando a configuração")
    if is_workspace(root):
        perfil = perfil_de(root)          # só cria o que falta: o perfil já escolhido não muda
    esp = [parse_espaco(s) for s in espacos]
    # Valida antes de criar qualquer coisa. Config que já existe não é reescrito (nem conferido de novo).
    times = [parse_time(s) for s in portfolio or []]
    config = None if is_workspace(root) else render_config(time_, site, cloud_id, jira, esp, perfil, times)
    if perfil == "gpm" and not _jira_lista(jira):
        jira = [tm["jira_projeto"] for tm in times]
    copiados = modelos_copiados(perfil)
    feitos: list[str] = []

    def escreve(rel: str, texto: str) -> None:
        f = root / rel
        if f.exists():
            return
        atomic_write_text(f, texto)
        feitos.append(rel)

    for p in pastas(perfil):
        if not (root / p).is_dir():
            (root / p).mkdir(parents=True, exist_ok=True)
            feitos.append(p + "/")
    if config is not None:
        escreve(".tia/config.yaml", config)
    for dest, modelo in copiados.items():
        if dest != ".tia/config.yaml":
            escreve(dest, (MODELOS / modelo).read_text(encoding="utf-8"))
    destino = claude_md_destino(root)
    escreve(destino, render_claude_md(time_, site, jira, esp, perfil))
    if destino == "tia/CLAUDE.md":
        raiz = root / "CLAUDE.md"
        txt = raiz.read_text(encoding="utf-8") if raiz.exists() else ""
        if "@tia/CLAUDE.md" not in txt:
            atomic_write_text(raiz, txt.rstrip("\n") + ("\n\n" if txt.strip() else "") + "@tia/CLAUDE.md\n")
            feitos.append("CLAUDE.md (+ @tia/CLAUDE.md)")
    gi = root / ".gitignore"
    txt = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".tia/cache/" not in txt:
        atomic_write_text(gi, txt.rstrip("\n") + ("\n\n" if txt.strip() else "") + GITIGNORE_BLOCO)
        feitos.append(".gitignore")
    log = root / REL["logs"] / "configurar.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"em": now_iso(), "acao": "criar", "perfil": perfil, "nota": nota.strip(),
                             "criados": feitos}, ensure_ascii=False) + "\n")
    return feitos


def diff(root: Path, dest: str) -> str:
    perfil = perfil_de(root)
    modelo = claude_modelo(perfil) if dest.endswith("CLAUDE.md") else modelos_copiados(perfil).get(dest)
    if not modelo:
        raise SystemExit(f"{dest} não é um modelo copiado pela Tia")
    atual = (root / dest).read_text(encoding="utf-8").splitlines(keepends=True)
    novo = (MODELOS / modelo).read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(atual, novo, f"{dest} (seu)", f"{dest} (modelo do plugin)"))


def aplicar(root: Path, dest: str, nota: str) -> Path:
    if not (nota or "").strip():
        raise SystemExit("informe --nota com a resposta literal da PM")
    alvo = {d["arquivo"] for d in status(root)["desatualizados"]}
    if dest not in alvo:
        raise SystemExit(f"{dest} não está desatualizado")
    if dest == ".tia/config.yaml" or dest.endswith("CLAUDE.md"):
        raise SystemExit(f"{dest} tem dados do time: aplique o diff à mão (a Tia mostra) e suba `modelo_versao`")
    bak = root / REL["cache"] / "backup" / f"{dest.replace('/', '__')}.{now_iso()[:10]}"
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / dest, bak)
    atomic_write_text(root / dest, (MODELOS / modelos_copiados(perfil_de(root))[dest]).read_text(encoding="utf-8"))
    return bak


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("criar")
    c.add_argument("--time", required=True)
    c.add_argument("--site", required=True)
    c.add_argument("--cloud-id", required=True)
    c.add_argument("--perfil", choices=PERFIS, default="pm")
    c.add_argument("--jira", action="append", default=[],
                   help="projeto do Jira: um no perfil PM; no GPM, repita para cada time (ou omita e pergunte depois)")
    c.add_argument("--espaco", action="append", default=[])
    c.add_argument("--portfolio", action="append", default=[], metavar="NOME|CHAVE[|board]",
                   help="só GPM: um por time do grupo")
    c.add_argument("--nota", required=True)
    u = sub.add_parser("atualizar")
    u.add_argument("--aplicar", metavar="ARQUIVO")
    u.add_argument("--nota")
    a = ap.parse_args(argv)
    import os

    root = (a.root or Path(os.environ.get("TIA_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())).resolve()

    if a.cmd == "status":
        st = status(root)
        if a.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            print(("Workspace da Tia" if st["workspace"] else "Ainda não é workspace da Tia") + f": {root}"
                  + (f" (perfil {st['perfil'].upper()})" if st["workspace"] else ""))
            for f in st["faltando"]:
                print(f"  falta: {f}")
            for d in st["desatualizados"]:
                print(f"  desatualizado: {d['arquivo']} (v{d['versao']} → v{d['versao_plugin']})")
        return 0
    if a.cmd == "criar":
        feitos = criar(root, a.time, a.site, a.cloud_id, a.jira, a.espaco, a.nota, a.perfil, a.portfolio)
        print(f"Criados ({len(feitos)}): " + (", ".join(feitos) if feitos else "nada; tudo já existia"))
        return 0
    if a.cmd == "atualizar":
        if a.aplicar:
            bak = aplicar(root, a.aplicar, a.nota or "")
            print(f"{a.aplicar} atualizado; cópia do anterior em {bak.relative_to(root).as_posix()}")
            return 0
        desat = status(root)["desatualizados"]
        if not desat:
            print("Modelos em dia.")
        for d in desat:
            print(f"## {d['arquivo']} (v{d['versao']} → v{d['versao_plugin']})\n")
            print(diff(root, d["arquivo"]) or "(sem diferença de texto)")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
