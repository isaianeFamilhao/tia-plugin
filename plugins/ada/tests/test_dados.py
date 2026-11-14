"""Fontes de dados só leitura; relatórios e propostas no escopo; monitores só pelo script."""
import tempfile
from pathlib import Path

import pytest

import hooks


def decision(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


def mcp(tool, **ti):
    return decision(hooks.run("pretool", {"tool_name": f"mcp__srv__{tool}", "tool_input": ti}))


def sh(cmd):
    return decision(hooks.run("pretool", {"tool_name": "Bash", "tool_input": {"command": cmd}}))


@pytest.mark.parametrize("tool,q", [
    ("databricks_execute_sql", "SELECT dt, avg(x) FROM gold.checkout GROUP BY dt"),
    ("looker_run_query", "explore: funil; fields: [taxa]"),
    ("bigquery_query", "select count(*) from `p.d.t` where deleted_at is null"),
])
def test_consulta_de_leitura_passa(proj, tool, q):
    assert mcp(tool, statement=q) is None


@pytest.mark.parametrize("q", [
    "DELETE FROM gold.checkout WHERE 1=1",
    "insert into t values (1)",
    "CREATE OR REPLACE TABLE x AS SELECT 1",
    "DROP TABLE gold.x",
    "UPDATE t SET a = 1",
    "MERGE INTO t USING s ON ...",
])
def test_consulta_que_altera_e_negada(proj, q):
    assert mcp("databricks_execute_sql", statement=q) == "deny"
    assert sh(f'databricks experimental aitools tools query "{q}"') == "deny"


def test_acao_que_cria_ou_roda_pergunta(proj):
    assert mcp("databricks_create_job", name="x") == "ask"
    assert mcp("databricks_run_now", job_id=1) == "ask"
    assert sh("databricks jobs run-now 123") == "ask"
    assert sh("databricks clusters list") in (None, "allow")


def test_ferramenta_que_nao_e_de_dados_nao_e_afetada(proj):
    assert mcp("getJiraIssue", jql="project = IT AND status = 'Delete me'") is None


def test_escopo_relatorios_propostas_e_monitoramento(proj):
    w = lambda rel: decision(hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(proj / rel)}}))
    assert w("ada/relatorios/2026-11-14-diario.md") is None
    assert w("ada/propostas/checkout.yaml") is None
    assert w(".ada/monitoramento/monitores.yaml") == "deny"
    assert sh("echo x >> .ada/monitoramento/leituras.jsonl") == "deny"


def test_rascunho_temporario_fora_do_projeto(proj):
    tmp = Path(tempfile.gettempdir()) / "claude" / "artifact.json"
    out = hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(tmp)}})
    assert decision(out) is None
    assert decision(hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": "D:/outro-repo/app.py"}})) == "deny"
