"""Lista os comandos do harness: skills do projeto (lidas de .claude/skills na hora), skills de apoio,
gates e scripts. Usado pela skill /pm-help. Zero tokens.

    python .harness/bin/ajuda.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CODE_ROOT as REPO_ROOT  # noqa: E402

# Ordem de uso no dia a dia; skill nova que não estiver aqui entra no fim, em ordem alfabética.
ORDER = ("ada", "ada-metricas", "ada-okr", "ada-report", "pm-help", "pm-demanda", "confluence", "base-atualizar")
USAGE = {
    "pm-help": "/pm-help",
    "ada": "/ada  ·  ou \"Ada, …\"",
    "ada-metricas": "/ada-metricas <feature|épico|OKR>",
    "ada-okr": "/ada-okr <ciclo e time | OKR a revisar>",
    "ada-report": "/ada-report diario|semanal",
    "pm-init": "/pm-init (atalho antigo)",
    "pm-demanda": "/pm-demanda D-NNN",
    "confluence": "/confluence [consultar|documentar|revisar|apontamentos] <tema>",
    "base-atualizar": "/base-atualizar <domínio|página|épico>",
}
# Resumo curto das skills conhecidas; skill nova usa a 1ª frase da própria descrição.
SUMMARY = {
    "pm-help": "Esta lista: skills, skills de apoio, gates e scripts.",
    "pm-init": "Atalho antigo para /ada; sai em breve.",
    "ada": "Abre o dia: Memória, fontes de dados conectadas, alertas de métricas, fila e gates; entende \"Ada, …\".",
    "ada-metricas": "Métricas de outcome: principal + guardrails, dados disponíveis e tracking spec; barra vaidade.",
    "ada-okr": "OKRs pragmáticos: calibra pelo momento do time, KRs de X para Y, adaptações, guardrail e iniciativas à parte.",
    "ada-report": "Diário (alertas, pós-deploy, bloqueios) ou semanal (OKRs contra a meta e ajuste de rota).",
    "pm-demanda": "Executa uma demanda aprovada: pesquisa, épico, histórias, cobertura, revisor cético e entrega.",
    "confluence": "Consulta o Confluence; mantém o INT (com C1); PO e PLAYBOOKS só leitura; registra apontamentos.",
    "base-atualizar": "Confere a Base de Conhecimento contra Confluence/Jira e propõe mudanças (K1).",
}
SUPPORT = [
    ("/pm-especialista", "Frameworks de produto (RICE, JTBD, OKR, North Star, discovery, PRD). Chamado pelo harness quando a demanda pede."),
    ("/epico-internal-tools", "Texto do épico no padrão de épico da squad. Chamado pelo /pm-demanda."),
]
GATES = [
    ("G1", "Aprovar a demanda antes de começar", "/ada"),
    ("G2", "Aceitar, pedir retrabalho (com motivo) ou rejeitar a entrega", "/ada"),
    ("K1", "Aprovar mudança na Base de Conhecimento", "/ada, /base-atualizar"),
    ("G3", "Autorizar publicação no Jira (cada escrita ainda pede confirmação)", "/ada"),
    ("C1", "Autorizar alteração de UMA página do Confluence INT (24 h)", "/confluence"),
    ("M1", "Ativar monitoramento de métricas (plano com limites e janela)", "/ada"),
    ("Memória", "Guardar um aprendizado sobre como você trabalha", "/ada, qualquer conversa"),
]
SCRIPTS = [
    ("kb.py buscar \"<termos>\"", "Busca regras na base (sem acento, por relevância)"),
    ("kb.py regra RN-XXX-NNN", "Regra completa com as fontes"),
    ("kb.py apontamentos --abertos", "Pauta do Confluence (documentar/duvida)"),
    ("ledger.py status", "Estado das demandas e dos gates"),
    ("okr.py validar|listar", "Avalia OKRs (entrega disfarçada, meta, foco, tensão, dados) e lista os ativos"),
    ("metricas.py plano <arquivo>", "Avalia o plano de métricas (principal, guardrails, dados, tracking)"),
    ("metricas.py ativos|alertas|resumo", "Monitores, alertas e base dos relatórios"),
    ("memoria.py listar", "O que a Ada aprendeu sobre você"),
    ("coverage.py D-NNN", "Avaliador: matriz regra × critério da entrega"),
    ("report.py", "Relatório de demandas, cobertura e consumo"),
    ("doctor.py", "Diagnóstico do ambiente, hooks, Base de Conhecimento e fila"),
    ("manutencao.py on|off", "Liga/desliga a fiscalização — só a humana, no terminal dela"),
]


def read_skill(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"(?s)^---\n(.*?)\n---", text)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep:
            meta[k.strip()] = v.strip().strip('"')
    if not meta.get("name"):
        return None
    desc = meta.get("description", "")
    desc = re.split(r"\s+Use (?:quando|SEMPRE)\b", desc)[0].strip()   # tira o gatilho
    first = re.split(r"(?<=\.)\s", desc, maxsplit=1)[0]
    first = (first if len(first) <= 160 else first[:157] + "…").rstrip(".") + "."
    return {"nome": meta["name"], "uso": USAGE.get(meta["name"], f"/{meta['name']}"),
            "descricao": SUMMARY.get(meta["name"], first)}


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def skills(root: Path = REPO_ROOT) -> list[dict]:
    found = [s for p in sorted((root / "skills").glob("*/SKILL.md")) if (s := read_skill(p))]
    rank = {n: i for i, n in enumerate(ORDER)}
    return sorted(found, key=lambda s: (rank.get(s["nome"], len(ORDER)), s["nome"]))


def render(root: Path = REPO_ROOT) -> str:
    out = ["# Comandos da Ada", "", "Ada — transforma pedidos em épicos e histórias que cobrem as regras de negócio e acompanha nos dados se a entrega moveu as métricas.", "", "## Skills do harness", "", "| Comando | O que faz |", "|---|---|"]
    out += [f"| `{cell(s['uso'])}` | {cell(s['descricao'])} |" for s in skills(root)]
    out += ["", "## Skills de apoio (da conta)", "", "| Comando | O que faz |", "|---|---|"]
    out += [f"| `{c}` | {d} |" for c, d in SUPPORT]
    out += ["", "## Gates (só com a sua resposta)", "", "| Gate | Decisão | Onde |", "|---|---|---|"]
    out += [f"| **{g}** | {d} | {w} |" for g, d, w in GATES]
    out += ["", "## Scripts (`.venv/Scripts/python.exe .harness/bin/<script>`)", "", "| Script | Para quê |", "|---|---|"]
    out += [f"| `{cell(c)}` | {cell(d)} |" for c, d in SCRIPTS]
    out += ["", "## Exemplos", "",
            "- \"Ada, bom dia\" → alertas, o que espera decisão sua, fila.",
            "- \"Ada, puxa no Looker como foi o funil de cadastro na última semana\" → diagnóstico a partir dos dados.",
            "- \"Ada, quais métricas para a busca com IA?\" → /ada-metricas: o que medir, o que dá para medir hoje e o tracking que falta.",
            "- \"Ada, vou fechar o épico X. O que monitorar?\" → plano de monitoramento para ativar (M1).",
            "- \"Ada, fecha os OKRs do Q3 do Onboarding\" → /ada-okr: calibragem, objetivo, KRs adaptados ao momento e iniciativas.",
            "- \"Ada, roda o semanal dos OKRs\" → /ada-report semanal.",
            "- \"Ada, o que você sabe sobre mim?\" → Memória.",
            "", "Pergunta rápida de produto (\"qual a regra de X?\") não precisa de comando: responda direto, com fonte."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.json:
        print(json.dumps({"skills": skills(), "apoio": SUPPORT, "gates": GATES, "scripts": SCRIPTS},
                         ensure_ascii=False, indent=2))
    else:
        print(render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
