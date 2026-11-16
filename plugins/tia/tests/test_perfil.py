"""Perfis PM e GPM (Fase 1 do plano 0.3.0): mesmo motor, habilidades por perfil, perfil escolhido por pasta."""
from __future__ import annotations

import pytest

import _common
import doctor
from conftest import CONFIG_TIME


def por_nome(res):
    return {c["nome"]: c for c in res}


def com_perfil(proj, valor: str) -> None:
    (proj / ".tia" / "config.yaml").write_text(f"perfil: {valor}\n" + CONFIG_TIME, encoding="utf-8")


# ------------------------------------------------------------------ item 1: chave `perfil`
def test_config_sem_a_chave_vale_pm(proj):
    assert "perfil" not in _common.config_workspace(proj)          # workspace da Internal Tools, como está hoje
    assert _common.perfil(proj) == "pm"
    cfg = _common.load_config(proj)
    assert cfg["perfil"] == "pm" and cfg["atlassian"]["jira_projeto"] == "IT"
    assert _common.config_sobreposicoes_ignoradas(proj) == []


@pytest.mark.parametrize("valor, esperado", [("gpm", "gpm"), ("GPM", "gpm"), (" pm ", "pm"), ("pm", "pm")])
def test_perfil_do_time(proj, valor, esperado):
    com_perfil(proj, f'"{valor}"')
    assert _common.perfil(proj) == esperado


def test_perfil_invalido_falha_no_doctor_e_vale_pm(proj, monkeypatch):
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    assert por_nome(doctor.run_checks(proj))["perfil"]["nivel"] == "OK"
    com_perfil(proj, "diretor")
    r = por_nome(doctor.run_checks(proj))["perfil"]
    assert r["nivel"] == "FALHA" and "diretor" in r["msg"] and "gpm" in r["correcao"]
    assert _common.perfil(proj) == "pm"                              # nada muda de comportamento em silêncio
    com_perfil(proj, "gpm")
    r = por_nome(doctor.run_checks(proj))["perfil"]
    assert r["nivel"] == "OK" and "GPM" in r["msg"]
