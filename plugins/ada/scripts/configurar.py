"""Prepara um projeto para a Ada (cria o marcador .ada/config.yaml e a pasta ada/) ou atualiza os modelos copiados.
Só biblioteca padrão: roda com o Python do sistema antes de o ambiente do plugin existir.

    ada.sh configurar status [--json]
    ada.sh configurar criar --time "<nome>" --site <url> --cloud-id <id> --jira <CHAVE> \\
        --espaco "INT|282787868|Internal Tools|manter" [--espaco "PO|370737187|Políticas|somente_leitura" …] \\
        --nota "<resposta literal da PM>"
    ada.sh configurar atualizar                       # lista modelos desatualizados, com diff
    ada.sh configurar atualizar --aplicar <arquivo> --nota "<resposta literal da PM>"

`criar` só cria o que não existe (nunca sobrescreve). Se o projeto já tem CLAUDE.md, a parte do time vai para
ada/CLAUDE.md e o CLAUDE.md da raiz ganha a linha `@ada/CLAUDE.md` (só acrescenta). Cada arquivo copiado
leva `modelo_versao`; `atualizar` compara com o modelo do plugin, mostra o diff e só troca com o sim da PM
(guarda cópia em .ada/cache/backup/).
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
GITIGNORE_BLOCO = """# Ada: máquina e pessoal fora do git (config, ledger e monitoramento ficam versionados)
.ada/logs/
.ada/cache/
ada/memoria/pessoal/
ada/demandas/*/packet.md
ada/demandas/*/metrics.json
**/.*.tmp
"""
PASTAS = [".ada/monitoramento", ".ada/logs", ".ada/cache", "ada/demandas", "ada/relatorios", "ada/propostas",
          "ada/memoria/time", "ada/memoria/pessoal", "ada/kb/fontes", "ada/kb/padroes"]
# destino no workspace → modelo no plugin (copiados uma vez; depois só a humana edita; `atualizar` compara)
MODELOS_COPIADOS = {
    ".ada/config.yaml": "config.time.yaml",
    "ada/demandas.yaml": "demandas.yaml",
    "ada/demandas.exemplo.yaml": "demandas.exemplo.yaml",
    "ada/kb/README.md": "kb-README.md",
    "ada/kb/padroes/epico.md": "padroes/epico.md",
    "ada/kb/padroes/historia.md": "padroes/historia.md",
    "ada/kb/apontamentos.md": "apontamentos.md",
    "ada/kb/prefixos.md": "prefixos.md",
    "ada/memoria/pessoal/pessoal.md": "pessoal.md",
}
SEM_VERSAO = {"ada/demandas.yaml", "ada/kb/apontamentos.md", "ada/kb/prefixos.md"}  # viram conteúdo do time


def versao(texto: str) -> int | None:
    m = VERSAO_RE.search(texto or "")
    return int(m.group(1)) if m else None


def claude_md_destino(root: Path) -> str:
    """CLAUDE.md da raiz, ou ada/CLAUDE.md se o projeto já tinha um que não é da Ada."""
    raiz = root / "CLAUDE.md"
    if (root / "ada" / "CLAUDE.md").exists():
        return "ada/CLAUDE.md"
    if raiz.exists() and versao(raiz.read_text(encoding="utf-8")) is None:
        return "ada/CLAUDE.md"
    return "CLAUDE.md"


def parse_espaco(s: str) -> tuple[str, dict]:
    partes = [p.strip() for p in s.split("|")]
    if len(partes) != 4 or not partes[0] or partes[3] not in POLITICAS:
        raise SystemExit(f"--espaco inválido: {s!r}. Formato: \"CHAVE|id|Nome|manter|somente_leitura\"")
    chave, sid, nome, pol = partes
    return chave, {"id": sid, "nome": nome, "politica": pol}


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_config(time_: str, site: str, cloud_id: str, jira: str, espacos: list[tuple[str, dict]]) -> str:
    mantidos = [k for k, v in espacos if v["politica"] == "manter"]
    if len(mantidos) > 1:
        raise SystemExit(f"só um espaço pode ser `manter` (veio: {', '.join(mantidos)})")
    bloco = "\n".join(f"    {k}: {{id: {_q(v['id'])}, nome: {_q(v['nome'])}, politica: {v['politica']}}}"
                      for k, v in espacos) or "    {}"
    t = (MODELOS / "config.time.yaml").read_text(encoding="utf-8")
    t = t.replace("{site}", site).replace("{cloud_id}", cloud_id).replace("{jira_projeto}", jira)
    t = t.replace("{espacos_lista}", "[" + ", ".join(k for k, _ in espacos) + "]")
    t = t.replace("{espacos_bloco}", bloco)
    return t.replace("# Configuração DO TIME (workspace).", f"# Configuração DO TIME ({time_}).", 1)


def render_claude_md(time_: str, site: str, jira: str, espacos: list[tuple[str, dict]]) -> str:
    linhas = []
    for k, v in espacos:
        if v["politica"] == "manter":
            linhas.append(f"| **{k}** · {v['nome']} (nosso espaço) | livre | só com **C1** por página | o que precisa ser documentado |")
        else:
            linhas.append(f"| **{k}** · {v['nome']} | quando necessário | **nunca** (nem comentário) | quando algo gerar dúvida |")
    t = (MODELOS / "CLAUDE.md").read_text(encoding="utf-8")
    return (t.replace("{time}", time_).replace("{jira_projeto}", jira).replace("{site}", site)
            .replace("{tabela_espacos}", "\n".join(linhas)))


def status(root: Path) -> dict:
    out = {"workspace": is_workspace(root), "faltando": [], "desatualizados": [], "claude_md": claude_md_destino(root)}
    for p in PASTAS:
        if not (root / p).is_dir():
            out["faltando"].append(p + "/")
    alvos = dict(MODELOS_COPIADOS)
    alvos[out["claude_md"]] = "CLAUDE.md"
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
    if not gi.exists() or ".ada/cache/" not in gi.read_text(encoding="utf-8"):
        out["faltando"].append(".gitignore (bloco da Ada)")
    return out


def criar(root: Path, time_: str, site: str, cloud_id: str, jira: str, espacos: list[str], nota: str) -> list[str]:
    if not (nota or "").strip():
        raise SystemExit("informe --nota com a resposta literal da PM aprovando a configuração")
    esp = [parse_espaco(s) for s in espacos]
    feitos: list[str] = []

    def escreve(rel: str, texto: str) -> None:
        f = root / rel
        if f.exists():
            return
        atomic_write_text(f, texto)
        feitos.append(rel)

    for p in PASTAS:
        if not (root / p).is_dir():
            (root / p).mkdir(parents=True, exist_ok=True)
            feitos.append(p + "/")
    escreve(".ada/config.yaml", render_config(time_, site, cloud_id, jira, esp))
    for dest, modelo in MODELOS_COPIADOS.items():
        if dest != ".ada/config.yaml":
            escreve(dest, (MODELOS / modelo).read_text(encoding="utf-8"))
    destino = claude_md_destino(root)
    escreve(destino, render_claude_md(time_, site, jira, esp))
    if destino == "ada/CLAUDE.md":
        raiz = root / "CLAUDE.md"
        txt = raiz.read_text(encoding="utf-8") if raiz.exists() else ""
        if "@ada/CLAUDE.md" not in txt:
            atomic_write_text(raiz, txt.rstrip("\n") + ("\n\n" if txt.strip() else "") + "@ada/CLAUDE.md\n")
            feitos.append("CLAUDE.md (+ @ada/CLAUDE.md)")
    gi = root / ".gitignore"
    txt = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".ada/cache/" not in txt:
        atomic_write_text(gi, txt.rstrip("\n") + ("\n\n" if txt.strip() else "") + GITIGNORE_BLOCO)
        feitos.append(".gitignore")
    log = root / REL["logs"] / "configurar.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"em": now_iso(), "acao": "criar", "nota": nota.strip(), "criados": feitos},
                            ensure_ascii=False) + "\n")
    return feitos


def diff(root: Path, dest: str) -> str:
    modelo = "CLAUDE.md" if dest.endswith("CLAUDE.md") else MODELOS_COPIADOS.get(dest)
    if not modelo:
        raise SystemExit(f"{dest} não é um modelo copiado pela Ada")
    atual = (root / dest).read_text(encoding="utf-8").splitlines(keepends=True)
    novo = (MODELOS / modelo).read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(atual, novo, f"{dest} (seu)", f"{dest} (modelo do plugin)"))


def aplicar(root: Path, dest: str, nota: str) -> Path:
    if not (nota or "").strip():
        raise SystemExit("informe --nota com a resposta literal da PM")
    alvo = {d["arquivo"] for d in status(root)["desatualizados"]}
    if dest not in alvo:
        raise SystemExit(f"{dest} não está desatualizado")
    if dest == ".ada/config.yaml" or dest.endswith("CLAUDE.md"):
        raise SystemExit(f"{dest} tem dados do time: aplique o diff à mão (a Ada mostra) e suba `modelo_versao`")
    bak = root / REL["cache"] / "backup" / f"{dest.replace('/', '__')}.{now_iso()[:10]}"
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / dest, bak)
    atomic_write_text(root / dest, (MODELOS / MODELOS_COPIADOS[dest]).read_text(encoding="utf-8"))
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
    c.add_argument("--jira", required=True)
    c.add_argument("--espaco", action="append", default=[])
    c.add_argument("--nota", required=True)
    u = sub.add_parser("atualizar")
    u.add_argument("--aplicar", metavar="ARQUIVO")
    u.add_argument("--nota")
    a = ap.parse_args(argv)
    import os

    root = (a.root or Path(os.environ.get("ADA_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())).resolve()

    if a.cmd == "status":
        st = status(root)
        if a.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            print(("Workspace da Ada" if st["workspace"] else "Ainda não é workspace da Ada") + f": {root}")
            for f in st["faltando"]:
                print(f"  falta: {f}")
            for d in st["desatualizados"]:
                print(f"  desatualizado: {d['arquivo']} (v{d['versao']} → v{d['versao_plugin']})")
        return 0
    if a.cmd == "criar":
        feitos = criar(root, a.time, a.site, a.cloud_id, a.jira, a.espaco, a.nota)
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
