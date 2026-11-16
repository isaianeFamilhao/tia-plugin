"""Hooks da Tia (plugin), chamados por hook.sh só DENTRO de um workspace (com .tia/config.yaml).
Lê o JSON do evento no stdin, imprime a decisão.

    <json> | python hooks.py <session_start|prompt|pretool|posttool|stop>

Política (README do plugin, "Proteções"):
- PreToolUse: escrita do agente só em tia/** (md/yaml/yml/json), exceto tia/demandas.yaml e tia/kb/README.md;
  .tia/** só por script; CLAUDE.md, settings e dados do plugin negados; pasta de outra demanda negada enquanto
  uma está ativa; tia/kb/** pede confirmação (K1); tia/memoria/** pede confirmação (gate Memória);
  escrita no Jira/Confluence negada sem G3 (e com G3 pede confirmação a cada chamada); Confluence por espaço;
  fontes de dados só leitura; shell: nega gravar em .tia/, CLAUDE.md e settings e nega desligar a fiscalização
  (claude plugin disable|uninstall, definir TIA_DEV, gravar em hooks e settings); ler ou citar
  esses nomes passa, e mensagens de commit (-m/-F) e texto entre aspas não contam; pergunta o que é perigoso.
- UserPromptSubmit: "Tia, <verbo>" no início vira "invoque a skill tia:<skill>" (aliases.py).
- PostToolUse: métricas da sessão e da demanda ativa; marca Base de Conhecimento alterada.
- Stop: com demanda ativa nesta sessão, só encerra com entrega aprovada pela cobertura (ou `blocked` com motivo);
  com Base alterada, só encerra com `kb.py validar` OK. Máx. 3 bloqueios.
- SessionStart: princípios e gates, índice da Memória, pessoal.md, session_id, demanda ativa.
Fail-closed (só dentro do workspace): erro inesperado nega a ação (PreToolUse), salvo TIA_DEV=1.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (CODE_ROOT, REPO_ROOT, P, find_data_root, is_workspace, load_config, norm_path, now_iso, path_allowed,  # noqa: E402
                     read_json, rel_to_root, transcript_usage, write_json)

EVENTS = ("session_start", "prompt", "pretool", "posttool", "stop")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
STOP_MAX_BLOCKS = 3
PREFIX = "[tia]"
SAFE_SHELL_RE = re.compile(
    r"""(?ix)^(?:&\s*)?TIA_SCRIPT\b"""
    r"""|^git\s+(?:status|log|diff|show|ls-files|branch)\b"""
    r"""|^(?:ls|dir|pwd|cd|cat|type|head|tail|wc|sort|uniq|echo|grep|rg|findstr|Get-ChildItem|Get-Content"""
    r"""|Get-Location|Set-Location|Select-String|Select-Object|Sort-Object|Measure-Object|Write-Output|Test-Path)\b""")
# Substituição de comando ou redirecionamento para arquivo: nunca é "seguro" (o descarte de stderr é).
UNSAFE_SHELL_RE = re.compile(r"`|\$\(|(?<![0-9])>(?!\s*&\s*1)|[0-9]>(?!&1|\s*\$null|\s*/dev/null)")
ENV_PREFIX_RE = re.compile(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)+")          # VAR=valor comando (bash)
PS_ENV_RE = re.compile(r"(?i)^\$env:PYTHON[A-Z]*\s*=\s*\S+$")         # $env:PYTHONIOENCODING='utf-8'
# Lançador da Tia: `bash "<plugin>/scripts/tia.sh" <script> ...` (aspas opcionais; `&` do PowerShell aceito).
LAUNCH_RE = re.compile(r"""(?i)(?:bash(?:\.exe)?\s+)?(?:"(?P<q>[^"]*?tia\.sh)"|'(?P<s>[^']*?tia\.sh)'|(?P<p>[^"'\s]*?tia\.sh))(?=\s|$)""")
# Desligar a fiscalização: só a humana, fora da sessão. Só o que desliga (ler esses arquivos ou citar os nomes passa).
# Comandos que desligam o plugin ou os hooks, ou gravam a variável de manutenção no ambiente do usuário.
DISABLE_CMD_RE = re.compile(
    r"(?i)\bclaude(?:\.exe)?\s+plugins?\s+(?:disable|uninstall|remove|rm)\b"
    r"|\bclaude(?:\.exe)?\s+config\s+(?:set|add)\b.*\b(?:disableAllHooks|enabledPlugins)\b"
    r"|\bsetx\s+(?:/m\s+)?TIA_DEV\b|SetEnvironmentVariable\s*\(\s*['\"]?TIA_DEV\b"
    r"|\breg(?:\.exe)?\s+add\b.*\bTIA_DEV\b")
# Definir a variável de manutenção na sessão (export, set, $env:, VAR=). Conferido no texto sem aspas.
DEV_ASSIGN_RE = re.compile(r"(?i)(?:^|[\s;&|(])(?:export\s+|set\s+|\$env:)?TIA_DEV\s*=")
# Arquivos que ligam a fiscalização: gravar neles pelo shell é negado (somado a PROTECTED_PATH_RE).
HOOK_FILES_RE = re.compile(r"(?i)\bhooks?\.(?:sh|json|py)\b|\bsettings(?:\.local)?\.json\b")
# Texto livre que não é comando: argumentos de -m/-F/--message/--file e corpo de heredoc.
MSG_ARG_RE = re.compile(r"""(?:^|(?<=\s))(?:-[A-Za-z]*[mF]|--message|--file)(?:\s+|=)"""
                        r"""(?:"(?:[^"\\]|\\.)*"|'[^']*'|\S+)""")
HEREDOC_RE = re.compile(r"""<<-?\s*(['"]?)(\w+)\1[^\n]*\n.*?\n\s*\2[ \t]*(?=\n|$)""", re.S)
QUOTED_RE = re.compile(r"""@'.*?'@|@".*?"@|"(?:[^"\\]|\\.)*"|'[^']*'""", re.S)


def sem_mensagem(cmd: str) -> str:
    """Tira mensagens de commit/tag (-m, -F) e corpos de heredoc: são texto, não comando."""
    return MSG_ARG_RE.sub(" MSG", HEREDOC_RE.sub("<<MSG", cmd))


# Aspas logo depois disto são código (bash -c, python -c, powershell -Command, eval…): o conteúdo fica.
CODIGO_ANTES_RE = re.compile(r"(?i)(?:\s-c|\s-Command|\s/c|\s-e|\beval|\bInvoke-Expression|\biex)\s*$")


def sem_aspas(cmd: str) -> str:
    """Tira o conteúdo entre aspas (e here-strings do PowerShell): `->` numa string não é redirecionamento.
    Exceção: aspas que são código de outro interpretador (`bash -c "…"`, `python -c "…"`) continuam."""
    def rep(m: re.Match) -> str:
        return m.group(0) if CODIGO_ANTES_RE.search(cmd[:m.start()]) else '""'
    return QUOTED_RE.sub(rep, cmd)


# Política de shell = lista do que é PERIGOSO (o resto fica com as permissões do Claude Code).
# 1) Gravar em .tia/, CLAUDE.md, settings ou no plugin pelo shell: negado (Write/Edit já são negados fora do escopo).
SHELL_WRITE_RE = re.compile(
    r"(?ix)(?<![0-9&])>{1,2}(?!\s*&)|\btee\b|\bsed\s+(?:-[a-z]*\s+)*-i|\b(?:cp|mv|rm|del|rmdir|touch|mkdir|ln)\b"
    r"|\b(?:Out-File|Set-Content|Add-Content|Copy-Item|Move-Item|Remove-Item|New-Item|Rename-Item)\b"
    r"|\bgit\s+(?:checkout|restore|rm|mv|reset|clean|stash)\b|open\([^)]*['\"][wa]")
PROTECTED_PATH_RE = re.compile(
    r"(?i)(?:^|[\s\"'/\\=])\.tia(?:[/\\]|\b)|tia[/\\]demandas\.yaml|tia[/\\]kb[/\\]README\.md|\.claude[/\\]|CLAUDE\.md"
    r"|plugins[/\\](?:cache|data)[/\\]")
# 2) Perigoso em qualquer lugar: pede confirmação a cada vez.
SHELL_RISKY = [
    (re.compile(r"(?i)\b(?:rm|del|rmdir|Remove-Item|rd)\b|\bgit\s+clean\b|\bgit\s+reset\s+--hard\b"), "apaga arquivos"),
    (re.compile(r"(?i)\b(?:pip|pip3|npm|npx|yarn|pnpm|winget|choco|scoop|apt|brew)\s+(?:install|i|add|update|upgrade)\b"
                r"|\bInstall-(?:Module|Package)\b"), "instala pacotes"),
    (re.compile(r"(?i)\bgit\s+(?:push|commit|merge|rebase|tag)\b|\bgh\s+(?:pr|release|repo)\s+(?:create|merge|delete)\b"),
     "altera o histórico do git ou o GitHub"),
    (re.compile(r"(?i)\b(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b.*(?:-X\s*(?:POST|PUT|PATCH|DELETE)"
                r"|--data|\s-d\s|-F\s|--upload|-T\s|-Method\s+(?:Post|Put|Patch|Delete)|-Body)"
                r"|\b(?:scp|sftp|rsync|ssh)\b"), "envia dados para fora da máquina"),
]


def is_launcher(path: str) -> bool:
    """O `tia.sh` deste plugin (não um homônimo qualquer)."""
    return norm_path(path).lower() == norm_path(CODE_ROOT / "scripts" / "tia.sh").lower()


def strip_launcher(cmd: str) -> str:
    """Troca as chamadas ao lançador da Tia por TIA_SCRIPT (executar script não é gravar em .tia/)."""
    def rep(m: re.Match) -> str:
        path = m.group("q") or m.group("s") or m.group("p")
        return "TIA_SCRIPT" if is_launcher(path) else m.group(0)
    return LAUNCH_RE.sub(rep, cmd)


def shell_is_safe(cmd: str) -> bool:
    """Seguro = cada parte (separada por ; && || |) é script da Tia ou leitura simples."""
    cmd = strip_launcher(cmd.replace("2>&1", ""))
    if not cmd.strip() or UNSAFE_SHELL_RE.search(cmd):
        return False
    for seg in re.split(r"&&|\|\||;|\||\r?\n", cmd):
        seg = ENV_PREFIX_RE.sub("", seg.strip())
        if not seg or PS_ENV_RE.match(seg):
            continue
        if "&" in re.sub(r"^&\s*", "", seg):  # `&` solto (bash: segundo plano) só vale como operador de chamada no início
            return False
        if not SAFE_SHELL_RE.match(seg):
            return False
    return True


def root_of(data: dict) -> Path:
    """Workspace: TIA_ROOT > CLAUDE_PROJECT_DIR > cwd do evento (sobe as pastas)."""
    return find_data_root(data.get("cwd")) or Path(data.get("cwd") or REPO_ROOT)


def ledger(root: Path) -> dict:
    return read_json(P(root, "ledger")) or {}


def active_demand(root: Path) -> tuple[str | None, dict]:
    for did, d in (ledger(root).get("demandas") or {}).items():
        if d.get("state") == "running":
            return did, d
    return None, {}


def pre(kind: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind,
                                   "permissionDecisionReason": f"{PREFIX} {reason}"}}


def block(reason: str) -> dict:
    return {"decision": "block", "reason": f"{PREFIX} {reason}"}


def context(event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


# ------------------------------------------------------------------ PreToolUse
def check_write(root: Path, cfg: dict, path: str) -> dict | None:
    esc = cfg.get("escopo_escrita") or {}
    rel = rel_to_root(root, path)
    if rel is None:
        import tempfile

        tmp = norm_path(tempfile.gettempdir()).lower()
        if tmp and norm_path(path).lower().startswith(tmp + "/"):
            return None  # rascunho temporário (ex.: artifact baixado): segue as permissões normais
        return pre("deny", f"escrita fora do projeto negada: {path}")
    low = rel.lower()
    if low.startswith(".tia/monitoramento/"):
        return pre("deny", "monitores e leituras mudam só pelo script `metricas` (ativar, avaliar, encerrar)")
    if low == ".tia" or low.startswith(".tia/"):
        return pre("deny", f"{rel}: .tia/ é da máquina e muda só pelos scripts da Tia (o config, só a humana edita)")
    if low == "claude.md" or low.endswith("/claude.md") or low.startswith(".claude/"):
        return pre("deny", f"{rel}: instruções e settings do projeto são editados só pela humana")
    if path_allowed(rel, esc.get("somente_humano") or []):
        return pre("deny", f"{rel} é editado só pelo humano: proponha a mudança na conversa")
    if not path_allowed(rel, esc.get("caminhos") or []):
        return pre("deny", f"escrita fora do escopo ({', '.join(esc.get('caminhos') or [])}) negada: {rel}. "
                           "A Tia não escreve código nem altera o próprio plugin.")
    ext = Path(rel).suffix.lower()
    if ext not in [e.lower() for e in esc.get("extensoes") or []]:
        return pre("deny", f"extensão {ext or '(nenhuma)'} não permitida em {rel}")
    m = re.match(r"^tia/demandas/(D-\d{3})/", rel, re.IGNORECASE)
    if m:
        did, _ = active_demand(root)
        if did is None:
            return pre("deny", f"nenhuma demanda em andamento: rode `tia.sh ledger iniciar {m.group(1)}` depois do G1")
        if m.group(1).upper() != did:
            return pre("deny", f"{did} está em andamento: não edite a pasta de {m.group(1)}")
        if rel.endswith(("/packet.md", "/cobertura.md", "/cobertura.json", "/metrics.json")):
            return pre("deny", f"{rel} é gerado por script; não edite à mão")
    if low.startswith("tia/kb/"):
        return pre("ask", f"K1: alteração na Base de Conhecimento ({rel}). Confirme se a humana aprovou este lote.")
    if low.startswith("tia/memoria/"):
        return pre("ask", f"Memória: gravar aprendizado ({rel}). Confirme que a humana disse sim e onde guardar.")
    return None


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return []


def check_dados(cfg: dict, tool: str, ti: dict) -> dict | None:
    """Fontes de dados são só leitura: nega SQL que altera; pede confirmação para criar/rodar algo."""
    d = cfg.get("dados") or {}
    text = "\n".join(_strings(ti))
    is_shell = tool in SHELL_TOOLS
    if is_shell:
        clis = d.get("clis") or []
        if not any(re.search(rf"(?i)(?:^|[\s;&|/\\\"']){re.escape(c)}(?:\.exe)?\b", text) for c in clis):
            return None
    elif not (tool.startswith("mcp__") and d.get("mcp_regex") and re.search(d["mcp_regex"], tool)):
        return None
    if d.get("escrita_regex") and re.search(d["escrita_regex"], text):
        return pre("deny", "fonte de dados é só leitura: a consulta altera dados (INSERT, UPDATE, DELETE, CREATE, "
                           "DROP…). Reescreva como SELECT agregado.")
    acao = d.get("acao_regex")
    name = tool if not is_shell else text
    if acao and re.search(acao, name.replace("__", " ").replace("_", " ")):
        return pre("ask", "ação em fonte de dados que cria, roda ou altera recurso (job, cluster, pipeline…): confirme.")
    return None


def check_confluence(root: Path, cfg: dict, tool: str, ti: dict) -> dict:
    """Política por espaço: `manter` (INT) só com C1 da página e confirmação; o resto, nunca."""
    from ledger import c1_valid, confluence_policy

    is_create = re.search(r"(?i)__createConfluencePage", tool) is not None
    if is_create:
        key, pol = confluence_policy(cfg, space_id=str(ti.get("spaceId") or ""))
        if pol != "manter":
            return pre("deny", f"criar página no espaço {key or ti.get('spaceId') or '(sem spaceId)'} é proibido: "
                               "fora do espaço marcado `manter` a Tia só lê. Registre o ponto em tia/kb/apontamentos.md.")
        reg = c1_valid(root, "novo")
        if not reg:
            return pre("deny", "criar página no INT exige C1 (`ledger.py c1 --espaco INT --pagina novo --nota "
                               "\"<resposta literal da humana>\"`). Mostre o rascunho antes.")
        return pre("ask", f"C1: criar a página \"{ti.get('title') or reg.get('titulo') or '?'}\" no INT. Confirme.")
    page = str(ti.get("pageId") or ti.get("contentId") or "")
    reg = c1_valid(root, page) if page else None
    if not reg:
        return pre("deny", f"alterar ou comentar a página {page or '(sem pageId)'} exige C1 dessa página no INT. "
                           "PO, PLAYBOOKS e outros espaços nunca são alterados: aponte a dúvida em tia/kb/apontamentos.md.")
    return pre("ask", f"C1: alterar a página {page} ({reg.get('titulo') or reg.get('espaco')}) com {tool}. "
                      "Confirme que é a página e o conteúdo mostrados na conversa.")


def pretool(data: dict) -> dict | None:
    root = root_of(data)
    cfg = load_config(root)
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    if tool in WRITE_TOOLS:
        return check_write(root, cfg, str(ti.get("file_path") or ti.get("notebook_path") or ""))
    dados = check_dados(cfg, tool, ti)
    if dados:
        return dados
    crx = (cfg.get("atlassian") or {}).get("confluence_escrita_regex")
    if crx and tool.startswith("mcp__") and re.search(crx, tool):
        return check_confluence(root, cfg, tool, ti)
    rx = (cfg.get("atlassian") or {}).get("ferramentas_escrita_regex")
    if rx and tool.startswith("mcp__") and re.search(rx, tool):
        led = ledger(root).get("demandas") or {}
        ok = [did for did, d in led.items() if d.get("state") == "publish_approved"]
        if not ok:
            return pre("deny", "escrita no Jira/Confluence exige o G3 da demanda (`ledger.py g3`). "
                               "Até lá, a Tia só lê.")
        return pre("ask", f"publicação de {', '.join(ok)} no Jira/Confluence ({tool}): confirme esta escrita.")
    if tool in SHELL_TOOLS:
        cmd = str(ti.get("command") or "")
        texto = sem_mensagem(strip_launcher(cmd))   # caminhos e argumentos (aspas mantidas, mensagens fora)
        ops = sem_aspas(texto)                       # operadores e palavras de comando
        if DISABLE_CMD_RE.search(texto) or DEV_ASSIGN_RE.search(ops):
            return pre("deny", "desligar ou contornar a fiscalização da Tia (desativar o plugin ou os hooks, "
                               "definir TIA_DEV) é decisão só da humana, no terminal dela.")
        # Executar um script da Tia não é gravar em .tia/: o lançador já saiu de `texto`.
        if SHELL_WRITE_RE.search(ops):
            if "ledger.json" in texto:
                return pre("deny", "o ledger só muda pelo script `ledger` (tia.sh ledger …)")
            if PROTECTED_PATH_RE.search(texto):
                return pre("deny", "o shell não grava em .tia/, na fila, no contrato da Base, em CLAUDE.md, em settings "
                                   "nem nos arquivos do plugin. Use os scripts da Tia ou proponha a mudança à humana.")
            if HOOK_FILES_RE.search(texto):
                return pre("deny", "gravar nos hooks ou nos settings pelo shell desliga a fiscalização da Tia: "
                                   "decisão só da humana, no terminal dela.")
        risky = next((why for rx, why in SHELL_RISKY if rx.search(cmd)), None)
        if risky:
            return pre("ask", f"{risky}: confirme este comando.")
        if shell_is_safe(cmd):
            return pre("allow", "script da Tia ou leitura simples")
        return None  # o resto segue as permissões normais do Claude Code ("permitir sempre" funciona)
    return None


# ------------------------------------------------------------------ PostToolUse
def usage_since(path: str | None, since_iso: str | None) -> dict:
    """Uso da transcrição a partir de `since_iso` (linhas com timestamp ≥ início da demanda)."""
    if not since_iso or not path or not Path(path).exists():
        return transcript_usage(path)
    from datetime import datetime

    t0 = datetime.fromisoformat(since_iso)
    import tempfile

    keep = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
                ts = datetime.fromisoformat(str(ev.get("timestamp")).replace("Z", "+00:00"))
            except (ValueError, TypeError, AttributeError):
                continue
            if ts >= t0:
                keep.append(line)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
        tmp.writelines(keep)
    try:
        return transcript_usage(tmp.name)
    finally:
        os.unlink(tmp.name)


def posttool(data: dict) -> dict | None:
    root = root_of(data)
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id") or "sem-sessao"))
    tp = data.get("transcript_path")
    u = transcript_usage(tp)
    write_json(P(root, "cache", "metrics", f"{sid}.json"), {"session_id": sid, "atualizado": now_iso(), **u})
    tool = str(data.get("tool_name") or "")
    path = str((data.get("tool_input") or {}).get("file_path") or "")
    if tool in WRITE_TOOLS and (rel_to_root(root, path) or "").lower().startswith("tia/kb/"):
        st = P(root, "cache", "state", f"kb-alterada-{sid}")
        st.parent.mkdir(parents=True, exist_ok=True)
        st.write_text(now_iso(), encoding="utf-8")
    did, d = active_demand(root)
    if did and (d.get("sessao") or {}).get("session_id") == data.get("session_id"):
        du = usage_since(tp, (d.get("sessao") or {}).get("inicio"))
        cfg = load_config(root)
        lim = int((cfg.get("metricas") or {}).get("alerta_saida_tokens_por_demanda") or 0)
        write_json(P(root, "demandas", did, "metrics.json"),
                   {"demanda": did, "tentativa": d.get("tentativa"), "atualizado": now_iso(), **du,
                    "alerta_saida": bool(lim and du.get("output_tokens", 0) > lim)})
    return None


# ------------------------------------------------------------------ Stop
def _count(root: Path, key: str) -> int:
    p = P(root, "cache", "state", f"stop-{key}")
    try:
        n = int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        n = 0
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(n + 1), encoding="utf-8")
    return n + 1


def stop(data: dict) -> dict | None:
    import coverage
    import kb as kbmod

    root = root_of(data)
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id") or "sem-sessao"))
    problems: list[str] = []
    did, d = active_demand(root)
    mine = did and (d.get("sessao") or {}).get("session_id") == data.get("session_id")
    if mine:
        ddir = P(root, "demandas", did)
        if not (ddir / "result.json").exists():
            problems.append(f"{did} em andamento sem result.json. Grave a entrega (ou status blocked com o motivo) "
                            "e rode `coverage.py " + did + "`.")
        else:
            rep = coverage.evaluate(did, root)
            if not rep["ok"]:
                problems.append(f"{did}: cobertura reprovada — " + "; ".join(rep["erros"][:6])
                                + (" …" if len(rep["erros"]) > 6 else ""))
    if P(root, "cache", "state", f"kb-alterada-{sid}").exists():
        rep = kbmod.validate_kb(root)
        if not rep["ok"]:
            problems.append("Base de Conhecimento inválida — " + "; ".join(f"{e['id']}: {e['erro']}" for e in rep["erros"][:6]))
    if not problems:
        return None
    key = f"{sid}-{did or 'kb'}-{(d or {}).get('tentativa', 0)}"
    n = _count(root, key)
    if n > STOP_MAX_BLOCKS:
        return None  # evita laço; a init vê a demanda ainda running e o humano decide
    return block(" | ".join(problems) + f" (bloqueio {n}/{STOP_MAX_BLOCKS})")


# ------------------------------------------------------------------ SessionStart
# O Claude Code guarda em arquivo o contexto acima de 10.000 caracteres e injeta só uma prévia: fica abaixo.
TETO_CONTEXTO = 9000
TETO_PRINCIPIOS = 5000


def launcher_cmd() -> str:
    return f'bash "{norm_path(CODE_ROOT / "scripts" / "tia.sh")}"'


def principios_texto() -> str:
    from _common import MODELOS, fit_tokens, frontmatter

    _, corpo = frontmatter(MODELOS / "principios.md")
    corpo = corpo.strip().replace('bash "<plugin>/scripts/tia.sh"', launcher_cmd())
    if len(corpo) > TETO_PRINCIPIOS:  # defesa: o teste garante que o arquivo cabe
        corpo = corpo[:TETO_PRINCIPIOS].rsplit("\n", 1)[0] + "\n[RECORTADO: texto completo na skill tia:abrir]"
    return corpo


def session_start(data: dict) -> dict | None:
    root = root_of(data)
    sid = str(data.get("session_id") or "")
    led = ledger(root).get("demandas") or {}
    did, d = active_demand(root)
    lines = [f"{PREFIX} session_id desta sessão: {sid or '(não informado)'} "
             f"(use em `{launcher_cmd()} ledger iniciar <D> --session-id <id>`)."]
    if did:
        owner = (d.get("sessao") or {}).get("session_id")
        lines.append(f"{PREFIX} Demanda em andamento: {did} (tentativa {d.get('tentativa')}, "
                     + ("NESTA sessão" if owner == sid else f"de outra sessão: {owner}") + ").")
    ready = [k for k, v in led.items() if v.get("state") in ("valid", "blocked", "abandoned")]
    g2 = [k for k, v in led.items() if v.get("state") == "delivered"]
    if ready or g2:
        lines.append(f"{PREFIX} Prontas para G1: {', '.join(ready) or '—'} · aguardando G2: {', '.join(g2) or '—'}.")
    try:
        from _common import NOME_PERFIL, perfil

        lines.append(f"{PREFIX} Perfil desta pasta: {NOME_PERFIL[perfil(root)]} (habilidades em /tia:ajuda).")
    except Exception:  # noqa: BLE001 — config ilegível não derruba a abertura (o doctor acusa)
        pass
    lines.append(f"{PREFIX} Sou a Tia: comece por /tia:abrir (ou 'Tia, bom dia'). Parte do time em CLAUDE.md.")
    blocos = [principios_texto(), "\n".join(lines)]
    try:
        import memoria

        extra = memoria.contexto_sessao(root)          # índice da Memória + pessoal.md, já em ordem de precedência
    except Exception as exc:  # noqa: BLE001 — a Memória nunca derruba a abertura
        extra = f"{PREFIX} Memória indisponível ({type(exc).__name__}): rode `tia.sh memoria validar`."
    if extra:
        resto = TETO_CONTEXTO - sum(len(b) + 2 for b in blocos)
        if len(extra) > resto:
            extra = extra[:max(0, resto - 120)].rsplit("\n", 1)[0] + (
                f"\n{PREFIX} [RECORTADO: Memória e pessoal passam de {TETO_CONTEXTO} caracteres; "
                "veja tudo com `tia.sh memoria listar`]")
        blocos.append(extra)
    return context("SessionStart", "\n\n".join(blocos))


def prompt(data: dict) -> dict | None:
    """UserPromptSubmit: "Tia, <verbo>" no início da mensagem → invocar a skill do plugin."""
    import aliases

    from _common import aviso_fora_do_perfil, perfil

    texto = str(data.get("prompt") or "")
    root = root_of(data)
    skill = aliases.resolver(texto, root)
    if not skill:
        return None
    try:
        pf = perfil(root)
    except Exception:  # noqa: BLE001 — config ilegível: atalhos seguem como no perfil padrão (o doctor acusa)
        pf = "pm"
    outro = aliases.fora_do_perfil(texto, skill, pf)
    if outro:
        return context("UserPromptSubmit", f"{PREFIX} Pedido de outro perfil: não invoque skill. Responda em uma "
                                           f"linha: \"{aviso_fora_do_perfil(outro, pf)}\"")
    nome, arg = skill
    if arg == aliases.ENCAMINHAR:
        return context("UserPromptSubmit", f"{PREFIX} Chamado da Tia: invoque a skill tia:abrir e siga só a seção "
                                           "\"Pedidos em linguagem natural\" (não rode a abertura).")
    extra = f" com o argumento `{arg}`" if arg else ""
    return context("UserPromptSubmit", f"{PREFIX} Chamado da Tia: invoque a skill tia:{nome}{extra} antes de responder.")


HANDLERS = {"session_start": session_start, "prompt": prompt, "pretool": pretool, "posttool": posttool, "stop": stop}


def fail_closed(event: str, exc: BaseException) -> dict | None:
    if dev_mode():
        return None
    reason = f"erro no hook ({type(exc).__name__}: {str(exc)[:160]}): ação negada (fail-closed)."
    if event == "pretool":
        return pre("deny", reason)
    if event == "stop":
        return None  # nunca prende a sessão por defeito do próprio hook; o erro fica no log
    if event == "session_start":
        return context("SessionStart", f"{PREFIX} ALERTA: hooks com erro ({exc}). Rode doctor.py antes de seguir.")
    return None


def log(root: Path, event: str, data: dict, out: dict | None, err: str | None = None) -> None:
    try:
        p = P(root, "logs", f"hooks-{now_iso()[:10]}.jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        ti = data.get("tool_input") or {}
        rec = {"em": now_iso(), "evento": event, "tool": data.get("tool_name"), "sessao": data.get("session_id"),
               "comando": str(ti.get("command") or "")[:300] or None,
               "alvo": ti.get("file_path") or ti.get("pageId") or ti.get("spaceId"),
               "saida": out, "erro": err}
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def dev_mode() -> bool:
    return os.environ.get("TIA_DEV") == "1"


def run(event: str, data: dict) -> dict | None:
    if not is_workspace(root_of(data)):
        return None  # fora de workspace da Tia: silêncio (o hook.sh já filtra; aqui é a segunda trava)
    if dev_mode() and event in ("pretool", "stop"):
        return None
    try:
        out = HANDLERS[event](data)
        log(root_of(data), event, data, out)
        return out
    except Exception as exc:  # noqa: BLE001 — fail-closed
        out = fail_closed(event, exc)
        log(root_of(data), event, data, out, repr(exc))
        return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in EVENTS:
        print(json.dumps(pre("deny", f"evento de hook desconhecido: {argv}")))
        return 0
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    out = run(argv[0], data)
    print(json.dumps(out or {}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
