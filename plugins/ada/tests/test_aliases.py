"""Item 7: "Ada, <verbo>" no início vira skill do plugin; "nada"/"cada" não disparam."""
from __future__ import annotations

import pytest

import aliases
import hooks


@pytest.mark.parametrize("texto, esperado", [
    ("Ada, bom dia", ("abrir", None)),
    ("ada,  Bom dia!", ("abrir", None)),
    ("Ada, roda o semanal", ("report", "semanal")),
    ("Ada, gera o diário", ("report", "diario")),
    ("Ada, relatório", ("report", None)),
    ("Ada, demanda D-002", ("demanda", "D-002")),
    ("Ada, toca a demanda d-007 agora", ("demanda", "D-007")),
    ("Ada, quais métricas para a busca com IA?", ("metricas", None)),
    ("Ada, fecha os OKRs do Q3", ("okr", None)),
    ("Ada, atualiza a base", ("base", None)),
    ("Ada, configurar", ("configurar", None)),
    ("Ada, atualiza a configuração", ("configurar", "atualizar")),
    ("Ada, ajuda", ("ajuda", None)),
    ("Ada, puxa no Looker o funil de cadastro", ("abrir", aliases.ENCAMINHAR)),
    ("Ada,", ("abrir", None)),
])
def test_reconhece(proj, texto, esperado):
    assert aliases.resolver(texto, proj) == esperado


@pytest.mark.parametrize("texto", [
    "nada, deixa assim", "cada, um por vez", "Nada, Ada, nada", "vamos, Ada, bom dia", "Adams, bom dia",
    "a Ada, bom dia", "", "bom dia",
])
def test_nao_dispara(proj, texto):
    assert aliases.resolver(texto, proj) is None


def test_atalho_do_pessoal_md(proj):
    ws = proj / "ada" / "memoria" / "pessoal"
    ws.mkdir(parents=True)
    (ws / "pessoal.md").write_text("## Atalhos\n\n- começa o dia → abrir\n- pulso → report diario\n"
                                   "- [ex.: algo → abrir]\n- invalido → apagar-tudo\n\n## Estilo\n- bom → ajuda\n",
                                   encoding="utf-8")
    assert aliases.resolver("Ada, começa o dia", proj) == ("abrir", None)
    assert aliases.resolver("Ada, pulso", proj) == ("report", "diario")
    assert aliases.resolver("Ada, invalido", proj) == ("abrir", aliases.ENCAMINHAR)   # skill inexistente ignorada
    assert aliases.resolver("Ada, bom dia", proj) == ("abrir", None)                   # fora da seção Atalhos


def test_pessoal_workspace_vence_global_no_empate(proj, tmp_path, monkeypatch):
    home = tmp_path / "home-ada"
    home.mkdir(parents=True, exist_ok=True)
    (home / "pessoal.md").write_text("## Atalhos\n- pulso → ajuda\n", encoding="utf-8")
    ws = proj / "ada" / "memoria" / "pessoal"
    ws.mkdir(parents=True)
    (ws / "pessoal.md").write_text("## Atalhos\n- pulso → report diario\n", encoding="utf-8")
    assert aliases.resolver("Ada, pulso", proj) == ("report", "diario")


def test_hook_prompt_injeta_skill(proj):
    out = hooks.run("prompt", {"prompt": "Ada, roda o semanal", "session_id": "s"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "ada:report" in ctx and "semanal" in ctx
    assert hooks.run("prompt", {"prompt": "nada, deixa assim"}) is None
    enc = hooks.run("prompt", {"prompt": "Ada, puxa no Looker o funil"})["hookSpecificOutput"]["additionalContext"]
    assert "ada:abrir" in enc and "não rode a abertura" in enc


def test_aliases_apontam_para_skills_que_existem():
    from conftest import REPO
    skills = {p.parent.name for p in (REPO / "skills").glob("*/SKILL.md")} | {"configurar"}
    assert {s for _, s, _, _ in aliases.tabela_plugin()} <= skills
    assert set(aliases.SKILLS) <= skills
