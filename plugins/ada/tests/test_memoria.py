"""Item 6: Memória com um arquivo por aprendizado, três escopos, precedência, revogação e migração."""
from __future__ import annotations

import pytest

import hooks
import kb
import memoria

ANTIGO = """# Memória do PM

```markdown
### PM-000 · Título curto
- **Aprendi:** exemplo
```

## Aprendizados

### PM-001 · Linguagem humana, sem códigos
- **Aprendi:** citar regras pelo nome; códigos só numa linha final "Ref.".
- **Evidência:** "não sei do que se trata" (2026-11-13)
- **Aplicar em:** geral
- **Status:** ativa
- **Desde:** 2026-11-13

### PM-002 · Relatório em tabela
- **Aprendi:** relatório semanal em tabela.
- **Evidência:** pediu (2026-11-14)
- **Aplicar em:** relatórios
- **Status:** revogada
- **Desde:** 2026-11-14
- **Revogada em:** 2026-11-20
- **Motivo:** mudou de ideia
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home-ada"
    monkeypatch.setenv("ADA_HOME", str(h))
    return h


def test_gravar_exige_nota_e_cria_arquivo(proj, home):
    with pytest.raises(SystemExit):
        memoria.gravar(proj, "pessoal", "tabela-no-semanal", "Semanal em tabela", "usar tabela", "pediu", ["relatórios"], "")
    p = memoria.gravar(proj, "pessoal", "tabela-no-semanal", "Semanal em tabela", "usar tabela",
                       "pediu em 2026-11-14", ["relatórios"], "sim, guarda para mim")
    assert p == proj / "ada" / "memoria" / "pessoal" / "tabela-no-semanal.md"
    assert memoria.validate(proj) == []
    assert [e["nome"] for e in memoria.ativas(proj)] == ["tabela-no-semanal"]


def test_tres_escopos_e_precedencia_no_contexto(proj, home):
    memoria.gravar(proj, "global", "curto", "Respostas curtas", "x", "y", ["conversa"], "sim, para mim")
    memoria.gravar(proj, "time", "epico-com-metrica", "Épico sempre com métrica", "x", "y", ["épicos"], "sim, para o time")
    memoria.gravar(proj, "pessoal", "sem-emoji", "Sem emoji nunca", "x", "y", ["geral"], "sim")
    ctx = memoria.contexto_sessao(proj)
    i_time, i_pes, i_glo = (ctx.index("epico-com-metrica"), ctx.index("sem-emoji"), ctx.index("curto"))
    assert i_time < i_pes < i_glo
    assert "**Aprendi:**" not in ctx                           # o hook injeta só nome e descrição


def test_revogada_sai_do_indice_e_exige_motivo(proj, home):
    memoria.gravar(proj, "pessoal", "sem-emoji", "Sem emoji", "x", "y", ["geral"], "sim")
    with pytest.raises(SystemExit):
        memoria.revogar(proj, "sem-emoji", "", "esquece")
    memoria.revogar(proj, "sem-emoji", "não precisa mais", "esquece isso")
    assert memoria.ativas(proj) == [] and "sem-emoji" not in memoria.contexto_sessao(proj)
    assert memoria.parse(proj)[0]["status"] == "revogada" and memoria.validate(proj) == []


def test_validacao(proj, home):
    d = proj / "ada" / "memoria" / "time"
    d.mkdir(parents=True)
    (d / "x.md").write_text("---\nnome: yy\ndescricao: a\nstatus: talvez\naplicar_em: [planeta]\n---\ncorpo\n", encoding="utf-8")
    (d / "z.md").write_text("sem frontmatter\n", encoding="utf-8")
    erros = " | ".join(e["erro"] for e in memoria.validate(proj))
    assert "diferente do arquivo" in erros and "status" in erros and "aplicar_em" in erros and "frontmatter" in erros
    assert not kb.validate_kb(proj)["ok"]                      # a Base valida a Memória junto


def test_pessoal_md_entra_no_contexto_sem_comentarios(proj, home):
    home.mkdir(parents=True)
    (home / "pessoal.md").write_text(memoria.modelo_pessoal().replace("- [ex.: começa o dia → abrir]", "- começa o dia → abrir"),
                                     encoding="utf-8")
    ws = proj / "ada" / "memoria" / "pessoal"
    ws.mkdir(parents=True)
    (ws / "pessoal.md").write_text("## Estilo\n- respostas curtas\n", encoding="utf-8")
    ctx = memoria.contexto_sessao(proj)
    assert ctx.index("respostas curtas") < ctx.index("começa o dia → abrir")
    assert "Comentários como este" not in ctx
    assert memoria.parse(proj) == []                            # pessoal.md não é aprendizado


def test_migrar_formato_antigo(proj, home, tmp_path):
    origem = tmp_path / "memoria-pm.md"
    origem.write_text(ANTIGO, encoding="utf-8")
    feitos = memoria.migrar(proj, origem, "pessoal", "sim, migra")
    assert [p.name for p in feitos] == ["linguagem-humana-sem-codigos.md", "relatorio-em-tabela.md"]
    assert memoria.validate(proj) == []
    assert [e["nome"] for e in memoria.ativas(proj)] == ["linguagem-humana-sem-codigos"]
    assert memoria.migrar(proj, origem, "pessoal", "de novo") == []      # idempotente
    assert origem.exists()


def test_session_start_injeta_principios_e_memoria(proj, home):
    memoria.gravar(proj, "time", "epico-com-metrica", "Épico sempre com métrica", "x", "y", ["épicos"], "sim")
    ctx = hooks.run("session_start", {"session_id": "s1"})["hookSpecificOutput"]["additionalContext"]
    assert "Você é a **Ada**" in ctx and "G1 *aprovar a demanda*" in ctx
    assert "epico-com-metrica: Épico sempre com métrica" in ctx and "s1" in ctx
    assert "<plugin>" not in ctx and "scripts/ada.sh" in ctx
    assert len(ctx) <= hooks.TETO_CONTEXTO


def test_session_start_respeita_teto(proj, home):
    for i in range(120):
        memoria.gravar(proj, "pessoal", f"regra-{i:03d}", "d" * 190, "x", "y", ["geral"], "sim")
    ctx = hooks.run("session_start", {"session_id": "s1"})["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= hooks.TETO_CONTEXTO and "RECORTADO" in ctx and "Você é a **Ada**" in ctx


def test_principios_cabem_no_teto():
    assert len(hooks.principios_texto()) < hooks.TETO_PRINCIPIOS
