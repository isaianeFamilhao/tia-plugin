"""Fase 2 do plano 0.3.0: portfólio do GPM (times na config, agregação do Jira sem pessoas, /tia:portfolio)."""
from __future__ import annotations

import pytest

import _common
import configurar
import doctor
import portfolio


def por_nome(res):
    return {c["nome"]: c for c in res}


@pytest.fixture
def gpm(tmp_path, monkeypatch):
    ws = tmp_path / "grupo"
    ws.mkdir()
    monkeypatch.setenv("TIA_ROOT", str(ws))
    monkeypatch.setenv("TIA_HOME", str(tmp_path / "home-tia"))
    monkeypatch.delenv("TIA_DEV", raising=False)
    configurar.criar(ws, "Plataforma", "https://exemplo.atlassian.net", "abc", [],
                     ["PO|370737187|Políticas|somente_leitura"], "sim", "gpm",
                     ["Cadastro|CAD", "Pagamentos|PAG|42"])
    return ws


def cfg_com(times, jira=None):
    c = {"portfolio": {"times": times}}
    if jira is not None:
        c["atlassian"] = {"jira_projetos": jira}
    return c


# ------------------------------------------------------------------ item 6: times do portfólio
def test_configurar_grava_os_times(gpm):
    cfg = _common.load_config(gpm)
    assert portfolio.times(cfg) == [{"nome": "Cadastro", "jira_projeto": "CAD"},
                                    {"nome": "Pagamentos", "jira_projeto": "PAG", "board": "42"}]
    assert cfg["atlassian"]["jira_projetos"] == ["CAD", "PAG"]               # vêm dos times
    assert portfolio.validar_times(cfg) == {"erros": [], "avisos": [], "times": 2}
    assert portfolio.main(["--root", str(gpm), "validar"]) == 0
    assert "CAD, PAG" in (gpm / "CLAUDE.md").read_text(encoding="utf-8")
    r = por_nome(doctor.run_checks(gpm))
    assert r["portfolio"]["nivel"] == "OK" and "2 time" in r["portfolio"]["msg"]


def test_validador_acusa_time_sem_projeto_e_projeto_repetido():
    rep = portfolio.validar_times(cfg_com([{"nome": "A", "jira_projeto": "CAD"}, {"nome": "B"},
                                           {"nome": "C", "jira_projeto": "CAD"}, {"jira_projeto": "PAG"},
                                           {"nome": "D", "jira_projeto": "minusculo"}]))
    erros = " | ".join(rep["erros"])
    assert "(B): sem jira_projeto" in erros and "projeto CAD repetido" in erros
    assert "sem nome" in erros and "não é chave" in erros and len(rep["erros"]) == 4
    assert portfolio.validar_times(cfg_com("CAD"))["erros"]


def test_validador_avisa_pessoa_e_projeto_fora_da_lista():
    rep = portfolio.validar_times(cfg_com([{"nome": "A", "jira_projeto": "CAD", "pm": "Fulana"}], jira=["PAG"]))
    assert rep["erros"] == [] and any("pessoas" in a for a in rep["avisos"]) and any("CAD" in a for a in rep["avisos"])


def test_doctor_gpm_falha_com_portfolio_invalido(gpm, monkeypatch):
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    p = gpm / ".tia" / "config.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace('jira_projeto: "PAG"', 'jira_projeto: "CAD"'), encoding="utf-8")
    r = por_nome(doctor.run_checks(gpm))["portfolio"]
    assert r["nivel"] == "FALHA" and "repetido" in r["msg"]
    assert portfolio.main(["--root", str(gpm), "validar"]) == 1


def test_configurar_portfolio_invalido(tmp_path):
    ws = tmp_path / "x"
    ws.mkdir()
    with pytest.raises(SystemExit, match="repetido"):
        configurar.criar(ws, "G", "s", "c", [], [], "sim", "gpm", ["A|CAD", "B|CAD"])
    with pytest.raises(SystemExit, match="--portfolio inválido"):
        configurar.criar(ws, "G", "s", "c", [], [], "sim", "gpm", ["Sem projeto"])
    with pytest.raises(SystemExit, match="só do perfil GPM"):
        configurar.criar(ws, "G", "s", "c", ["IT"], [], "sim", "pm", ["A|CAD"])
    assert not _common.is_workspace(ws)


def test_pm_sem_portfolio_nao_muda(proj, monkeypatch):
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    assert "portfolio" not in por_nome(doctor.run_checks(proj))


# ------------------------------------------------------------------ item 7: agregação sem pessoas
import json  # noqa: E402

from conftest import REPO  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "jql_portfolio.json"
PESSOAS = ("Maria", "Souza", "João", "Pereira", "Ana Lima", "Carla", "Dias", "@", "accountId", "557058",
           "assignee", "reporter", "creator", "displayName", "emailAddress")
TIMES = [{"nome": "Cadastro", "jira_projeto": "CAD"}, {"nome": "Pagamentos", "jira_projeto": "PAG", "board": "42"}]


def rep_fixture():
    return portfolio.agregar(portfolio.carregar([str(FIXTURE)]), TIMES, janela_dias=7, parado_dias=5, hoje="2026-11-16")


def test_issue_limpa_descarta_pessoas():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["issues"][0]
    limpa = portfolio.issue_limpa(raw)
    assert set(limpa) == {"key", "projeto", "tipo", "resumo", "etapa", "categoria", "atualizado", "concluido",
                          "sinalizado", "bloqueado_por"}
    texto = json.dumps(limpa, ensure_ascii=False)
    assert not [p for p in PESSOAS if p in texto]


def test_saida_sem_nenhum_nome():
    rep = rep_fixture()
    for texto in (json.dumps(rep, ensure_ascii=False), portfolio.render(rep)):
        assert not [p for p in PESSOAS if p in texto], texto


def test_contagens_batem_com_a_fixture():
    rep = rep_fixture()
    cad, pag = rep["times"]
    assert rep["issues"] == 9 and rep["fora_do_portfolio"] == {"OUT": 1}
    assert cad["em_andamento"] == {"Em desenvolvimento": 2, "Em revisão": 1} and cad["total_em_andamento"] == 3
    assert cad["concluidos_janela"] == 1 and cad["a_fazer"] == 0
    assert {t["key"]: t["motivos"] for t in cad["travados"]} == {
        "CAD-2": ["sem movimento há 11 dias"], "CAD-3": ["sinalizado"]}
    assert pag["em_andamento"] == {"Em desenvolvimento": 1, "Bloqueado": 1} and pag["a_fazer"] == 1
    assert pag["concluidos_janela"] == 0
    assert {t["key"]: t["motivos"] for t in pag["travados"]} == {
        "PAG-10": ["bloqueado por PLAT-7"], "PAG-11": ["etapa \"Bloqueado\""]}


def test_cli_agrega_e_grava_sem_pessoas(gpm, capsys):
    assert portfolio.main(["--root", str(gpm), "agregar", "--entrada", str(FIXTURE), "--hoje", "2026-11-16",
                           "--gravar"]) == 0
    out = capsys.readouterr().out
    assert "| Cadastro (CAD) | 3 | 2 | 1 | 0 |" in out and "| Pagamentos (PAG) | 2 | 2 | 0 | 1 |" in out
    gravado = gpm / "tia" / "relatorios" / "2026-11-16-portfolio.json"
    texto = gravado.read_text(encoding="utf-8")
    assert not [p for p in PESSOAS if p in texto]
    assert json.loads(texto)["times"][0]["nome"] == "Cadastro"


def test_cli_recusa_sem_times(tmp_path, monkeypatch):
    ws = tmp_path / "g"
    ws.mkdir()
    configurar.criar(ws, "G", "s", "c", ["CAD"], [], "sim", "gpm")
    assert portfolio.main(["--root", str(ws), "agregar", "--entrada", str(FIXTURE)]) == 1
