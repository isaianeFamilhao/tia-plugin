"""Item 7: "Tia, <verbo>" no início vira skill do plugin; "garantia", "notícia" e o chamado antigo "Ada," não disparam."""
from __future__ import annotations

import pytest

import aliases
import hooks


@pytest.mark.parametrize("texto, esperado", [
    ("Tia, bom dia", ("abrir", None)),
    ("tia,  Bom dia!", ("abrir", None)),
    ("Tia, roda o semanal", ("report", "semanal")),
    ("Tia, gera o diário", ("report", "diario")),
    ("Tia, relatório", ("report", None)),
    ("Tia, demanda D-002", ("demanda", "D-002")),
    ("Tia, toca a demanda d-007 agora", ("demanda", "D-007")),
    ("Tia, quais métricas para a busca com IA?", ("metricas", None)),
    ("Tia, fecha os OKRs do Q3", ("okr", None)),
    ("Tia, atualiza a base", ("base", None)),
    ("Tia, configurar", ("configurar", None)),
    ("Tia, atualiza a configuração", ("configurar", "atualizar")),
    ("Tia, ajuda", ("ajuda", None)),
    ("Tia, puxa no Looker o funil de cadastro", ("abrir", aliases.ENCAMINHAR)),
    ("Tia,", ("abrir", None)),
])
def test_reconhece(proj, texto, esperado):
    assert aliases.resolver(texto, proj) == esperado


@pytest.mark.parametrize("texto", [
    "nada, deixa assim", "cada, um por vez", "Nada, Tia, nada", "vamos, Tia, bom dia", "Adams, bom dia", "Ada, bom dia", "Ada, demanda D-001", "garantia, deixa assim", "notícia, saiu",
    "Titia, bom dia", "estratégia, Tia, bom dia",
    "a Tia, bom dia", "", "bom dia",
])
def test_nao_dispara(proj, texto):
    assert aliases.resolver(texto, proj) is None


def test_atalho_do_pessoal_md(proj):
    ws = proj / "tia" / "memoria" / "pessoal"
    ws.mkdir(parents=True)
    (ws / "pessoal.md").write_text("## Atalhos\n\n- começa o dia → abrir\n- pulso → report diario\n"
                                   "- [ex.: algo → abrir]\n- invalido → apagar-tudo\n\n## Estilo\n- bom → ajuda\n",
                                   encoding="utf-8")
    assert aliases.resolver("Tia, começa o dia", proj) == ("abrir", None)
    assert aliases.resolver("Tia, pulso", proj) == ("report", "diario")
    assert aliases.resolver("Tia, invalido", proj) == ("abrir", aliases.ENCAMINHAR)   # skill inexistente ignorada
    assert aliases.resolver("Tia, bom dia", proj) == ("abrir", None)                   # fora da seção Atalhos


def test_pessoal_workspace_vence_global_no_empate(proj, tmp_path, monkeypatch):
    home = tmp_path / "home-tia"
    home.mkdir(parents=True, exist_ok=True)
    (home / "pessoal.md").write_text("## Atalhos\n- pulso → ajuda\n", encoding="utf-8")
    ws = proj / "tia" / "memoria" / "pessoal"
    ws.mkdir(parents=True)
    (ws / "pessoal.md").write_text("## Atalhos\n- pulso → report diario\n", encoding="utf-8")
    assert aliases.resolver("Tia, pulso", proj) == ("report", "diario")


def test_hook_prompt_injeta_skill(proj):
    out = hooks.run("prompt", {"prompt": "Tia, roda o semanal", "session_id": "s"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "tia:report" in ctx and "semanal" in ctx
    for p in ("nada, deixa assim", "garantia, deixa assim", "Ada, bom dia"):
        assert hooks.run("prompt", {"prompt": p}) is None
    enc = hooks.run("prompt", {"prompt": "Tia, puxa no Looker o funil"})["hookSpecificOutput"]["additionalContext"]
    assert "tia:abrir" in enc and "não rode a abertura" in enc


def test_aliases_apontam_para_skills_que_existem():
    from conftest import REPO
    skills = {p.parent.name for p in (REPO / "skills").glob("*/SKILL.md")} | {"configurar"}
    assert {s for _, s, _, _ in aliases.tabela_plugin()} <= skills
    assert set(aliases.SKILLS) <= skills
