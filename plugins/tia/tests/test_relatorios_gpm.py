"""Fase 4 do plano 0.3.0: relatórios do GPM (semanal de portfólio e relatório para a diretoria)."""
from __future__ import annotations

import _common
import portfolio
from test_portfolio import FIXTURE, PESSOAS, gpm  # noqa: F401  (fixture do pytest)

SKILL = _common.CODE_ROOT / "skills" / "report" / "SKILL.md"


def gravar_retrato(ws, capsys):
    portfolio.main(["--root", str(ws), "agregar", "--entrada", str(FIXTURE), "--hoje", "2026-11-16", "--gravar"])
    capsys.readouterr()


# ------------------------------------------------------------------ item 12: semanal de portfólio
def test_situacao_por_time():
    assert portfolio.situacao({"total_em_andamento": 4, "travados": []}) == "no ritmo"
    assert portfolio.situacao({"total_em_andamento": 4, "travados": [{}]}) == "atenção"
    assert portfolio.situacao({"total_em_andamento": 4, "travados": [{}, {}]}) == "travado"
    assert portfolio.situacao({"total_em_andamento": 0, "travados": [{}]}) == "travado"


def test_tabela_do_semanal_a_partir_do_retrato(gpm, capsys):
    gravar_retrato(gpm, capsys)
    assert portfolio.main(["--root", str(gpm), "ultimo", "--tabela"]) == 0
    out = capsys.readouterr().out
    assert "| Time | WIP (em andamento) | Travas | Entregas | Situação |" in out
    assert "| Cadastro | 3 | 2 | 1 | travado |" in out and "| Pagamentos | 2 | 2 | 0 | travado |" in out
    assert "| **Grupo** | 5 | 4 | 1 | |" in out and "últimos 7 dias" in out
    assert not [p for p in PESSOAS if p in out]


def test_roteiro_semanal_gpm():
    texto = SKILL.read_text(encoding="utf-8")
    ramo = texto[texto.index("## Perfil GPM: semanal de portfólio"):texto.index("## Saída")]
    assert "portfolio ultimo --tabela" in ramo and "portfolio ultimo --resumo" in ramo
    assert "okr listar --ativos --nivel grupo" in ramo and "até 3 recomendações" in ramo
    assert "**evidência**" in ramo and "**trade-off**" in ramo
    assert "tia/relatorios/<AAAA-MM-DD>-semanal.md" in ramo and "Sem nomes de pessoas" in ramo
    for proibido in ("createJira", "editJira", "transitionJira", "addComment", "assignee"):
        assert proibido not in ramo


def test_semanal_e_diario_do_pm_nao_mudam():
    texto = SKILL.read_text(encoding="utf-8")
    pm = texto[:texto.index("## Perfil GPM")]
    assert "## Diário — pulso rápido (até ~15 linhas)" in pm and "## Semanal — visão de OKR" in pm
    assert "`TIA metricas resumo --dias 7 --json` + `TIA okr listar --ativos`" in pm
    assert "--nivel" not in pm and "portfolio" not in pm
    assert "No perfil PM, nada desta\nseção vale" in texto


# ------------------------------------------------------------------ item 13: relatório para a diretoria
def test_executivo_da_diretoria(gpm, capsys):
    assert portfolio.main(["--root", str(gpm), "ultimo", "--executivo"]) == 0
    assert "Nenhum retrato" in capsys.readouterr().out
    gravar_retrato(gpm, capsys)
    assert portfolio.main(["--root", str(gpm), "ultimo", "--executivo"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Retrato de 2026-11-16: 2 time(s) · 5 em andamento · 4 travado(s) · 1 entrega(s) em 7 dias")
    assert "- Travado: Cadastro, Pagamentos" in out and "Dependência de fora do grupo: PLAT" in out
    assert "CAD-" not in out and "PAG-" not in out                      # sem detalhe de item
    assert not [p for p in PESSOAS if p in out]


def test_executivo_agrupa_por_situacao():
    rep = {"gerado_em": "2026-11-16", "janela_dias": 7, "times": [
        {"nome": "A", "jira_projeto": "A", "total_em_andamento": 4, "travados": [], "concluidos_janela": 2},
        {"nome": "B", "jira_projeto": "B", "total_em_andamento": 4, "concluidos_janela": 0,
         "travados": [{"motivos": ["bloqueado por A-1"]}]}]}
    out = portfolio.executivo(rep)
    assert "- Atenção: B" in out and "- No ritmo: A" in out and "Travado" not in out
    assert "Dependência" not in out                                    # bloqueio dentro do grupo


def test_roteiro_diretoria():
    texto = SKILL.read_text(encoding="utf-8")
    ramo = texto[texto.index("## Diretoria (só perfil GPM)"):texto.index("## Saída")]
    assert "O relatório para a diretoria é do perfil GPM; esta pasta é do perfil PM." in ramo
    assert ramo.index("**Situação**") < ramo.index("**Riscos**") < ramo.index("**Decisões pedidas à diretoria**")
    assert "portfolio ultimo --executivo" in ramo and "tia/relatorios/<AAAA-MM-DD>-diretoria.md" in ramo
    assert "**não envie\nnem publique**" in ramo and "`manter`" in ramo and "C1" in ramo
    assert "Sem nomes de pessoas" in ramo
    for proibido in ("createConfluencePage", "updateConfluencePage", "slack_send", "assignee"):
        assert proibido not in ramo
    assert "diario|semanal|diretoria" in texto


def test_atalho_diretoria():
    import aliases

    assert aliases.resolver("Tia, relatório para a diretoria", None) == ("report", "diretoria")


def test_ajuda_report_por_perfil():
    import ajuda

    gpm_txt = ajuda.render(_common.CODE_ROOT, "gpm")
    pm_txt = ajuda.render(_common.CODE_ROOT, "pm")
    assert r"/tia:report diario\|semanal\|diretoria" in gpm_txt and "diretoria" not in pm_txt
    assert r"/tia:report diario\|semanal`" in pm_txt
