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


# ------------------------------------------------------------------ item 3: habilidades por perfil
def test_tabela_cobre_as_skills_do_plugin():
    nomes = {p.parent.name for p in (_common.CODE_ROOT / "skills").glob("*/SKILL.md")}
    assert set(_common.HABILIDADES) == nomes
    assert all(set(v) <= set(_common.PERFIS) and v for v in _common.HABILIDADES.values())
    assert _common.HABILIDADES["demanda"] == ("pm",)


def test_ajuda_lista_so_as_do_perfil():
    import ajuda

    pm = {s["nome"] for s in ajuda.skills(_common.CODE_ROOT, "pm")}
    gpm = {s["nome"] for s in ajuda.skills(_common.CODE_ROOT, "gpm")}
    assert "demanda" in pm and "demanda" not in gpm and gpm == pm - {"demanda"}
    texto = ajuda.render(_common.CODE_ROOT, "gpm")
    assert "/tia:demanda" not in texto and "**G1**" not in texto and "coverage D-NNN" not in texto
    assert "perfil GPM" in texto and "**K1**" in texto and "**M1**" in texto
    assert "**G1**" in ajuda.render(_common.CODE_ROOT, "pm")


def test_ajuda_le_o_perfil_da_pasta(proj, monkeypatch, capsys):
    import ajuda

    monkeypatch.setattr(_common, "DATA_ROOT", proj)
    assert ajuda.perfil_da_pasta() == "pm"
    com_perfil(proj, "gpm")
    assert ajuda.perfil_da_pasta() == "gpm"
    ajuda.main([])
    assert "/tia:demanda" not in capsys.readouterr().out


@pytest.mark.parametrize("texto", ["Tia, escreve um épico sobre reprocessamento", "Tia, demanda D-001",
                                   "Tia, histórias para o cadastro", "Tia, refina o épico IT-39"])
def test_atalho_de_outro_perfil_recebe_uma_linha(proj, texto):
    import hooks

    com_perfil(proj, "gpm")
    ctx = hooks.run("prompt", {"prompt": texto, "session_id": "s"})["hookSpecificOutput"]["additionalContext"]
    assert "não invoque skill" in ctx and "perfil PM" in ctx and "perfil GPM" in ctx
    assert "tia:demanda" not in ctx


def test_perfil_pm_segue_igual(proj):
    import aliases
    import hooks

    ctx = hooks.run("prompt", {"prompt": "Tia, escreve um épico sobre X"})["hookSpecificOutput"]["additionalContext"]
    assert "tia:abrir" in ctx and "Pedidos em linguagem natural" in ctx         # proposta de demanda, como antes
    ctx = hooks.run("prompt", {"prompt": "Tia, demanda D-002"})["hookSpecificOutput"]["additionalContext"]
    assert "tia:demanda" in ctx and "D-002" in ctx
    assert aliases.fora_do_perfil("Tia, escreve um épico", ("abrir", aliases.ENCAMINHAR), "pm") is None


def test_gpm_mantem_as_outras_habilidades(proj):
    import hooks

    com_perfil(proj, "gpm")
    ctx = hooks.run("prompt", {"prompt": "Tia, roda o semanal"})["hookSpecificOutput"]["additionalContext"]
    assert "tia:report" in ctx and "semanal" in ctx
    ctx = hooks.run("prompt", {"prompt": "Tia, puxa no Looker o funil"})["hookSpecificOutput"]["additionalContext"]
    assert "tia:abrir" in ctx
    ctx = hooks.run("session_start", {"session_id": "s1"})["hookSpecificOutput"]["additionalContext"]
    assert "Perfil desta pasta: GPM" in ctx and len(ctx) <= hooks.TETO_CONTEXTO


# ------------------------------------------------------------------ item 4: fila só no perfil PM
def test_ledger_iniciar_recusa_no_gpm(proj, entrega):
    import ledger

    led = ledger.Ledger(proj)
    led.sync()
    led.g1("D-001", True, "ok")
    com_perfil(proj, "gpm")
    with pytest.raises(ledger.LedgerError, match="perfil PM; esta pasta é do perfil GPM"):
        ledger.Ledger(proj).iniciar("D-001", "sessao-123")
    assert ledger.Ledger(proj).get("D-001")["state"] == "approved"            # nada mudou no disco
    assert ledger.main(["--root", str(proj), "iniciar", "D-001", "--session-id", "sessao-123"]) == 1
    com_perfil(proj, "pm")
    ledger.Ledger(proj).iniciar("D-001", "sessao-123")
    assert ledger.Ledger(proj).get("D-001")["state"] == "running"


def test_skill_demanda_recusa_no_gpm():
    texto = (_common.CODE_ROOT / "skills" / "demanda" / "SKILL.md").read_text(encoding="utf-8")
    assert "perfil: gpm" in texto and "e pare" in texto


def test_doctor_gpm_sem_fila_nao_avisa(proj, monkeypatch):
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    (proj / "tia" / "demandas.yaml").unlink()
    assert por_nome(doctor.run_checks(proj))["demandas"]["nivel"] == "AVISO"   # PM sem fila: avisa, como antes
    com_perfil(proj, "gpm")
    assert "demandas" not in por_nome(doctor.run_checks(proj))
