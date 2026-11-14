"""Diagnóstico do harness de produto. Roda no início de cada /ada.

    python .harness/bin/doctor.py [--json]

FALHA = pare e corrija; AVISO = siga, mas mencione ao humano.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb as kbmod  # noqa: E402
import validate  # noqa: E402
from _common import REPO_ROOT, read_json  # noqa: E402

MIN_PY = (3, 12)
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def check(nivel: str, nome: str, msg: str, correcao: str = "") -> dict:
    return {"nivel": nivel, "nome": nome, "msg": msg, "correcao": correcao}


def hooks_enabled(root: Path) -> bool:
    data = read_json(root / ".claude" / "settings.json") or {}
    return bool((data.get("hooks") or {}).get("PreToolUse"))


def run_checks(root: Path = REPO_ROOT) -> list[dict]:
    out = []
    v = sys.version_info
    if v[:2] < MIN_PY:
        out.append(check("FALHA", "python", f"Python {v.major}.{v.minor} < 3.12", "instale o Python 3.12 e recrie o .venv"))
    else:
        out.append(check("OK", "python", f"Python {v.major}.{v.minor}"))
    has_venv = any(p.exists() for p in (root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"))
    if not has_venv:
        out.append(check("FALHA", "venv", ".venv ausente: com hooks ligados, toda ferramenta é negada (fail-closed)",
                         "python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt"))
    if not hooks_enabled(root):
        out.append(check("AVISO", "hooks", "hooks desligados em .claude/settings.json: escopo, G3 e Stop não são fiscalizados",
                         "a humana roda: .venv/Scripts/python.exe .harness/bin/manutencao.py off"))
    else:
        bash = shutil.which("bash") or (str(GIT_BASH) if GIT_BASH.exists() else None)
        if not bash:
            out.append(check("FALHA", "bash", "Git Bash não encontrado: os hooks não rodam", "instale o Git for Windows"))
        else:
            try:
                r = subprocess.run([bash, str(root / ".harness" / "bin" / "hook.sh"), "session_start"],
                                   input='{"session_id":"doctor"}', capture_output=True, text=True, timeout=40,
                                   encoding="utf-8", errors="replace", cwd=root)
                ok = "Harness de produto" in r.stdout and "ALERTA" not in r.stdout
                out.append(check("OK" if ok else "FALHA", "hooks",
                                 "hook SessionStart responde" if ok else f"hook não respondeu: {r.stdout[:200]} {r.stderr[:200]}",
                                 "" if ok else "confira o .venv"))
            except (OSError, subprocess.TimeoutExpired) as e:
                out.append(check("FALHA", "hooks", f"chamada de teste ao hook falhou: {e}"))
    rep = kbmod.validate_kb(root)
    if rep["regras"] == 0:
        out.append(check("AVISO", "kb", "Base de Conhecimento sem regras: rode /base-atualizar antes da primeira demanda"))
    elif not rep["ok"]:
        out.append(check("FALHA", "kb", f"Base de Conhecimento inválida: {len(rep['erros'])} erro(s)", "python .harness/bin/kb.py validar"))
    else:
        out.append(check("OK", "kb", f"Base de Conhecimento: {rep['regras']} regras, {rep['fontes']} fontes"))
    dpath = root / ".harness" / "demandas.yaml"
    if dpath.exists():
        vr = validate.validate(dpath, root)
        out.append(check("OK" if vr["ok"] else "FALHA", "demandas",
                         f"fila: {len(vr['demandas'])} demanda(s), {len(vr['erros'])} erro(s), {len(vr['avisos'])} aviso(s)",
                         "" if vr["ok"] else "python .harness/bin/validate.py"))
    else:
        out.append(check("AVISO", "demandas", "fila .harness/demandas.yaml ausente", "crie a partir de .harness/demandas.exemplo.yaml"))
    import memoria
    import metricas

    merr = metricas.validate(root)
    out.append(check("OK" if not merr else "FALHA", "monitoramento",
                     f"{len([m for m in metricas.load_monitors(root) if m.get('status') == 'ativo'])} monitor(es) ativo(s)"
                     if not merr else f"{len(merr)} erro(s): {merr[0]}", "" if not merr else ".venv/Scripts/python.exe .harness/bin/metricas.py validar"))
    mem = [e for e in memoria.parse(root) if e["campos"].get("Status", "").lower() == "ativa"]
    out.append(check("OK", "memoria", f"Memória da PM: {len(mem)} aprendizado(s) ativo(s)"))
    led = read_json(root / ".harness" / "ledger.json") or {}
    running = [k for k, d in (led.get("demandas") or {}).items() if d.get("state") == "running"]
    if running:
        out.append(check("AVISO", "ativa", f"demanda em andamento: {', '.join(running)} (retomar ou abandonar)"))
    if os.environ.get("HARNESS_DEV") == "1":
        out.append(check("AVISO", "dev", "HARNESS_DEV=1: hooks de escopo desligados (modo manutenção)"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = run_checks()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for c in res:
            print(f"{c['nivel']:5} {c['nome']}: {c['msg']}" + (f"  -> {c['correcao']}" if c["correcao"] else ""))
    return 1 if any(c["nivel"] == "FALHA" for c in res) else 0


if __name__ == "__main__":
    sys.exit(main())
