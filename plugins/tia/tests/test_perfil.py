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


# ------------------------------------------------------------------ item 2: princípios neutros
# Trechos que não podem mudar com a troca de perfil (gates e regras fixas): a mudança do item 2 é só de redação.
GATES = ("**Gates (só com resposta explícita da humana no turno; nunca registre por conta própria):**\n"
         "G1 *aprovar a demanda* · G2 *aceitar a entrega* · K1 *aprovar mudança na Base de Conhecimento* ·\n"
         "G3 *autorizar publicação no Jira* · C1 *autorizar alteração no Confluence* · M1 *ativar monitoramento* ·\n"
         "Memória *guardar um aprendizado* (\"Aprendi: … Guardo para você ou para o time?\").")
REGRAS_FIXAS = (
    "Estado só no disco", "Uma demanda por vez.", "Base de Conhecimento antes da web",
    "Regra nova só com fonte; candidata é `RC-NN` e vira\n`RN-…` só no K1.",
    "Jira só leitura até o G3; Confluence: só o espaço marcado `manter`, só com C1; os demais nunca",
    "Dados: sempre só leitura, consulta agregada,\nsem dado pessoal, com limite de linhas.",
    "Dados pessoais nunca entram em artefato; colegas aparecem pelo papel.",
    "**Não faz:** escrever ou executar código de aplicação, alterar o plugin, `.tia/`, `CLAUDE.md` ou settings,\n"
    "desligar hooks, decidir pela humana. Escrita do agente só em `tia/**`.",
    "**Precedência:** princípios > políticas do time (CLAUDE.md, config) > pessoal do workspace > pessoal global.",
)


def test_principios_neutros_sem_mudar_gates_nem_regras():
    import hooks

    texto = hooks.principios_texto()
    assert "quem lidera produto (PM ou GPM)" in texto
    assert "Product Manager" not in texto and "a PM" not in texto and "braço direito" not in texto
    assert GATES in texto
    for trecho in REGRAS_FIXAS:
        assert trecho in texto, trecho
    abrir = (_common.CODE_ROOT / "skills" / "abrir" / "SKILL.md").read_text(encoding="utf-8")
    assert "quem\nlidera produto (PM ou GPM)" in abrir and "Product\nManager" not in abrir
    assert "Gate só com resposta explícita da humana no turno. Nunca registre G1, G2, K1, G3, C1, M1 ou Memória" in abrir


def test_resumo_injetado_continua_no_teto(proj, monkeypatch):
    import hooks

    ctx = hooks.run("session_start", {"session_id": "s1"})["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 9000 == hooks.TETO_CONTEXTO
    assert len(hooks.principios_texto()) < hooks.TETO_PRINCIPIOS
