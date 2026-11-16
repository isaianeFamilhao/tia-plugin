"""Lista os comandos da Tia: skills do plugin (lidas de skills/ na hora), aliases, skills de apoio,
gates e scripts. Usado pela skill /tia:ajuda. Zero tokens. Lista só o que existe no perfil desta pasta
(`perfil` no config do time; sem a chave, PM).

    tia.sh ajuda [--json] [--perfil pm|gpm]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CODE_ROOT as REPO_ROOT  # noqa: E402
from _common import NOME_PERFIL, PERFIL_PADRAO, PERFIS, habilidade_disponivel  # noqa: E402

# Gates e scripts da fila de demandas: só no perfil PM (a habilidade `demanda` é só do PM).
SO_PM = {"G1", "G2", "G3", "ledger status", "coverage D-NNN"}
# Scripts do portfólio: só no perfil GPM.
SO_GPM = {"portfolio validar|agregar|ultimo"}

# Ordem de uso no dia a dia; skill nova que não estiver aqui entra no fim, em ordem alfabética.
ORDER = ("abrir", "demanda", "portfolio", "metricas", "okr", "report", "base", "confluence", "configurar", "ajuda")
USAGE = {
    "abrir": "/tia:abrir  ·  \"Tia, bom dia\"",
    "demanda": "/tia:demanda D-NNN",
    "portfolio": "/tia:portfolio [janela em dias] [time]",
    "metricas": "/tia:metricas <feature|épico|OKR>",
    "okr": "/tia:okr <ciclo e time | OKR a revisar>",
    "report": "/tia:report diario|semanal",
    "base": "/tia:base <domínio|página|épico>",
    "confluence": "/tia:confluence [consultar|documentar|revisar|apontamentos] <tema>",
    "configurar": "/tia:configurar [atualizar]",
    "ajuda": "/tia:ajuda",
}
# Resumo curto das skills conhecidas; skill nova usa a 1ª frase da própria descrição.
SUMMARY = {
    "ajuda": "Esta lista: skills, atalhos, skills de apoio, gates e scripts.",
    "configurar": "Prepara o projeto para a Tia (.tia/ e tia/) ou atualiza os modelos copiados, com diff e o seu sim.",
    "abrir": "Abre o dia: Memória, fontes de dados conectadas, alertas de métricas, fila e gates; entende \"Tia, …\".",
    "metricas": "Métricas de outcome: principal + guardrails, dados disponíveis e tracking spec; barra vaidade.",
    "okr": "OKRs pragmáticos: calibra pelo momento do time, KRs de X para Y, adaptações, guardrail e iniciativas à parte.",
    "report": "Diário (alertas, pós-deploy, bloqueios) ou semanal (OKRs contra a meta e ajuste de rota).",
    "portfolio": "Situação dos times do grupo no Jira: em andamento, travados e entregas, com causa e próximo passo; sem pessoas.",
    "demanda": "Executa uma demanda aprovada: pesquisa, épico, histórias, cobertura, revisor cético e entrega.",
    "confluence": "Consulta o Confluence; mantém o espaço do time (com C1); os demais só leitura; registra apontamentos.",
    "base": "Confere a Base de Conhecimento contra Confluence/Jira e propõe mudanças (K1).",
}
SUPPORT = [
    ("/pm-especialista, /pm-advisor", "Frameworks de produto (RICE, JTBD, OKR, North Star, discovery, PRD), se instalados. Opcionais."),
    ("skill de épico do time (ex.: /epico-internal-tools)", "Texto do épico no padrão do time, se o padrão indicar. Opcional."),
]
GATES = [
    ("G1", "Aprovar a demanda antes de começar", "/tia:abrir"),
    ("G2", "Aceitar, pedir retrabalho (com motivo) ou rejeitar a entrega", "/tia:abrir"),
    ("K1", "Aprovar mudança na Base de Conhecimento", "/tia:abrir, /tia:base"),
    ("G3", "Autorizar publicação no Jira (cada escrita ainda pede confirmação)", "/tia:abrir"),
    ("C1", "Autorizar alteração de UMA página do espaço do time no Confluence (24 h)", "/tia:confluence"),
    ("M1", "Ativar monitoramento de métricas (plano com limites e janela)", "/tia:abrir"),
    ("Memória", "Guardar um aprendizado, para você ou para o time", "/tia:abrir, qualquer conversa"),
]
SCRIPTS = [
    ("kb buscar \"<termos>\"", "Busca regras na Base (sem acento, por relevância)"),
    ("kb regra RN-XXX-NNN", "Regra completa com as fontes"),
    ("kb apontamentos --abertos", "Pauta do Confluence (documentar/duvida)"),
    ("ledger status", "Estado das demandas e dos gates"),
    ("okr validar|listar", "Avalia OKRs (entrega disfarçada, meta, foco, tensão, dados) e lista os ativos"),
    ("metricas plano <arquivo>", "Avalia o plano de métricas (principal, guardrails, dados, tracking)"),
    ("metricas ativos|alertas|resumo", "Monitores, alertas e base dos relatórios"),
    ("memoria listar|contexto", "O que a Tia aprendeu (time, pessoal, global) e o que entra no início da sessão"),
    ("aliases --listar", "Atalhos \"Tia, …\" do plugin e do seu pessoal.md"),
    ("coverage D-NNN", "Avaliador: matriz regra × critério da entrega"),
    ("portfolio validar|agregar|ultimo", "Times do grupo, agregação do Jira por time (sem pessoas) e último retrato"),
    ("report", "Relatório de demandas, cobertura e consumo"),
    ("doctor", "Diagnóstico: Python, Git Bash, ambiente do plugin, workspace, modelos, Base e fila"),
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
    return {"nome": meta["name"], "uso": USAGE.get(meta["name"], f"/tia:{meta['name']}"),
            "descricao": SUMMARY.get(meta["name"], first)}


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def skills(root: Path = REPO_ROOT, perfil: str = PERFIL_PADRAO) -> list[dict]:
    found = [s for p in sorted((root / "skills").glob("*/SKILL.md"))
             if (s := read_skill(p)) and habilidade_disponivel(s["nome"], perfil)]
    rank = {n: i for i, n in enumerate(ORDER)}
    return sorted(found, key=lambda s: (rank.get(s["nome"], len(ORDER)), s["nome"]))


def apoio(perfil: str = PERFIL_PADRAO) -> list[tuple[str, str]]:
    return [s for s in SUPPORT if perfil == "pm" or "épico" not in s[0]]


def gates(perfil: str = PERFIL_PADRAO) -> list[tuple[str, str, str]]:
    return [g for g in GATES if perfil == "pm" or g[0] not in SO_PM]


def scripts(perfil: str = PERFIL_PADRAO) -> list[tuple[str, str]]:
    return [s for s in SCRIPTS if (perfil == "pm" or s[0] not in SO_PM) and (perfil == "gpm" or s[0] not in SO_GPM)]


def perfil_da_pasta() -> str:
    try:
        from _common import DATA_ROOT, is_workspace, perfil

        return perfil(DATA_ROOT) if is_workspace(DATA_ROOT) else PERFIL_PADRAO
    except Exception:  # noqa: BLE001 — sem PyYAML ou config ilegível: lista o perfil padrão (o doctor acusa)
        return PERFIL_PADRAO


def render(root: Path = REPO_ROOT, perfil: str = PERFIL_PADRAO) -> str:
    resumo = ("transforma pedidos em épicos e histórias que cobrem as regras de negócio e acompanha nos dados se a "
              "entrega moveu as métricas." if perfil == "pm" else
              "copiloto de quem lidera um grupo de produto: métricas, OKRs, relatórios, Base de Conhecimento e "
              "Confluence; épico, histórias e fila de demandas ficam na pasta de cada PM.")
    quem = "Tia" if perfil == PERFIL_PADRAO else f"Tia (perfil {NOME_PERFIL[perfil]})"
    out = ["# Comandos da Tia", "", f"{quem} — {resumo}", "", "## Skills da Tia", "",
           "| Comando | O que faz |", "|---|---|"]
    out += [f"| `{cell(s['uso'])}` | {cell(s['descricao'])} |" for s in skills(root, perfil)]
    out += ["", "## Skills de apoio (da conta)", "", "| Comando | O que faz |", "|---|---|"]
    out += [f"| `{c}` | {d} |" for c, d in apoio(perfil)]
    out += ["", "## Gates (só com a sua resposta)", "", "| Gate | Decisão | Onde |", "|---|---|---|"]
    out += [f"| **{g}** | {d} | {w} |" for g, d, w in gates(perfil)]
    out += ["", '## Scripts (`bash "<plugin>/scripts/tia.sh" <script>`)', "", "| Script | Para quê |", "|---|---|"]
    out += [f"| `{cell(c)}` | {cell(d)} |" for c, d in scripts(perfil)]
    out += ["", "## Exemplos", "",
            "- \"Tia, bom dia\" → alertas, o que espera decisão sua" + (", fila." if perfil == "pm" else "."),
            "- \"Tia, puxa no Looker como foi o funil de cadastro na última semana\" → diagnóstico a partir dos dados.",
            "- \"Tia, quais métricas para a busca com IA?\" → /tia:metricas: o que medir, o que dá para medir hoje e o tracking que falta.",
            "- \"Tia, vou fechar o épico X. O que monitorar?\" → plano de monitoramento para ativar (M1).",
            "- \"Tia, fecha os OKRs do Q3 do Onboarding\" → /tia:okr: calibragem, objetivo, KRs adaptados ao momento e iniciativas.",
            "- \"Tia, roda o semanal dos OKRs\" → /tia:report semanal.",
            "- \"Tia, o que você sabe sobre mim?\" → Memória.",
            "", "Pergunta rápida de produto (\"qual a regra de X?\") não precisa de comando: responda direto, com fonte."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--perfil", choices=PERFIS, help="padrão: o perfil desta pasta")
    a = ap.parse_args(argv)
    pf = a.perfil or perfil_da_pasta()
    if a.json:
        print(json.dumps({"perfil": pf, "skills": skills(perfil=pf), "apoio": apoio(pf), "gates": gates(pf),
                          "scripts": scripts(pf)}, ensure_ascii=False, indent=2))
    else:
        print(render(perfil=pf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
