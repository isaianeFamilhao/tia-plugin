"""Política por espaço do Confluence: INT só com C1; PO, PLAYBOOKS e outros, nunca."""
import pytest

import hooks
import kb
import ledger

INT, PO, PLAYBOOKS = "282787868", "370737187", "322895878"


def decision(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


def call(tool, **ti):
    return decision(hooks.run("pretool", {"tool_name": f"mcp__abc__{tool}", "tool_input": ti}))


def test_criar_fora_do_int_sempre_negado(proj):
    ledger.c1_authorize(proj, "INT", "novo", "pode criar")
    assert call("createConfluencePage", spaceId=PO, title="x") == "deny"
    assert call("createConfluencePage", spaceId=PLAYBOOKS, title="x") == "deny"
    assert call("createConfluencePage", spaceId="999", title="x") == "deny"
    assert call("createConfluencePage", title="sem espaço") == "deny"


def test_criar_no_int_exige_c1(proj):
    assert call("createConfluencePage", spaceId=INT, title="x") == "deny"
    ledger.c1_authorize(proj, "INT", "novo", "pode criar a página de estornos")
    assert call("createConfluencePage", spaceId=INT, title="x") == "ask"


def test_alterar_e_comentar_exigem_c1_da_pagina(proj):
    for tool in ("updateConfluencePage", "createConfluenceFooterComment", "createConfluenceInlineComment"):
        assert call(tool, pageId="111") == "deny", tool
    ledger.c1_authorize(proj, "INT", "111", "pode atualizar a 111")
    assert call("updateConfluencePage", pageId="111") == "ask"
    assert call("updateConfluencePage", pageId="222") == "deny"  # C1 vale para uma página só


def test_c1_recusa_espaco_somente_leitura(proj):
    for esp in ("PO", "PLAYBOOKS", "XYZ"):
        with pytest.raises(ledger.LedgerError, match="somente leitura"):
            ledger.c1_authorize(proj, esp, "111", "pode")
    with pytest.raises(ledger.LedgerError):
        ledger.c1_authorize(proj, "INT", "111", "")


def test_c1_expira(proj):
    led = ledger.Ledger(proj)
    ledger.c1_authorize(proj, "INT", "111", "ok")
    led = ledger.Ledger(proj)
    led.data["c1"][-1]["valido_ate"] = "2000-01-01T00:00:00-03:00"
    led.save()
    assert call("updateConfluencePage", pageId="111") == "deny"


def test_leitura_livre(proj):
    assert hooks.run("pretool", {"tool_name": "mcp__abc__getConfluencePage", "tool_input": {"pageId": "1"}}) is None
    assert hooks.run("pretool", {"tool_name": "mcp__abc__searchConfluenceUsingCql", "tool_input": {}}) is None


AP_OK = """# Apontamentos

```markdown
### AP-001 · exemplo no bloco de código não conta
- **Tipo:** qualquer
```

### AP-001 · Página proposta tratada como vigente
- **Tipo:** duvida
- **Espaço:** PO
- **Página:** https://x/1
- **O quê:** proposta usada como base
- **Status:** aberto
- **Aberto em:** 2026-11-13
"""


def test_apontamentos_validos(proj):
    (proj / "ada" / "kb" / "apontamentos.md").write_text(AP_OK, encoding="utf-8")
    assert kb.validate_apontamentos(proj) == []
    assert len(kb.parse_apontamentos(proj)) == 1


def test_documentar_so_no_int(proj):
    (proj / "ada" / "kb" / "apontamentos.md").write_text(AP_OK.replace("**Tipo:** duvida", "**Tipo:** documentar"),
                                                 encoding="utf-8")
    assert any("só vale para espaço" in e["erro"] for e in kb.validate_apontamentos(proj))


def test_fechar_exige_resolucao(proj):
    (proj / "ada" / "kb" / "apontamentos.md").write_text(AP_OK.replace("aberto\n", "resolvido\n"), encoding="utf-8")
    assert any("Resolução" in e["erro"] for e in kb.validate_apontamentos(proj))
