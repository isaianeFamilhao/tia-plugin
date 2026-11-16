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
