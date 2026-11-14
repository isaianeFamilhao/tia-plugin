"""Diagnóstico da Tia. Roda na abertura (/tia:abrir) e sempre que algo falhar.

    tia.sh doctor [--json]

Funciona com o Python do sistema antes de o ambiente do plugin existir (as checagens que precisam de PyYAML
ficam para depois, com aviso). FALHA = pare e corrija; AVISO = siga, mas mencione à humana.
As mensagens são para quem não é técnico: dizem o que fazer, não só o que quebrou.
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
from _common import CODE_ROOT, DATA_ROOT, MARCADOR, P, is_workspace, read_json  # noqa: E402

MIN_PY = (3, 12)
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
LANCADOR = f'bash "{(CODE_ROOT / "scripts" / "tia.sh").as_posix()}"'
REDE = ("ProxyError", "SSLError", "CERTIFICATE_VERIFY_FAILED", "ConnectTimeout", "ConnectionError",
        "Could not find a version", "No matching distribution", "Temporary failure in name resolution",
        "getaddrinfo failed", "407")


def check(nivel: str, nome: str, msg: str, correcao: str = "") -> dict:
    return {"nivel": nivel, "nome": nome, "msg": msg, "correcao": correcao}


def plugin_data(root: Path) -> Path | None:
    for v in (os.environ.get("CLAUDE_PLUGIN_DATA"), os.environ.get("TIA_PLUGIN_DATA")):
        if v and "${" not in v:
            return Path(v)
    p = P(root, "cache", "plugin-data")
    if p.exists():
        txt = p.read_text(encoding="utf-8").strip()
        return Path(txt) if txt else None
    return None


def venv_python(data: Path | None) -> Path | None:
    if not data:
        return None
    for c in (data / "venv" / "Scripts" / "python.exe", data / "venv" / "bin" / "python"):
        if c.exists():
            return c
    return None


def find_bash() -> str | None:
    return shutil.which("bash") or (str(GIT_BASH) if GIT_BASH.exists() else None)


def req_hash_ok(data: Path) -> bool | None:
    """Hash dos requisitos do plugin × o gravado no venv (mesma conta do `cksum` do bootstrap)."""
    bash = find_bash()
    if not bash:
        return None
    try:
        r = subprocess.run([bash, "-c", 'cksum < "$1" | cut -d" " -f1', "_",
                            (CODE_ROOT / "requirements-runtime.txt").as_posix()],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    gravado = (data / "venv" / ".tia-req-hash")
    return gravado.exists() and gravado.read_text(encoding="utf-8").strip() == r.stdout.strip()


def diagnostico_rede(data: Path | None) -> str:
    log = (data / "bootstrap.log") if data else None
    if not log or not log.exists():
        return ""
    txt = log.read_text(encoding="utf-8", errors="replace")
    if any(k in txt for k in REDE):
        return ("O download dos pacotes Python foi bloqueado (rede corporativa ou proxy). Peça ao suporte para "
                "liberar pypi.org e files.pythonhosted.org, ou para configurar o proxy do pip (HTTPS_PROXY); "
                f"depois rode {LANCADOR} bootstrap. Detalhes em {log.as_posix()}.")
    return f"Veja o motivo em {log.as_posix()}."


def run_checks(root: Path | None = None) -> list[dict]:
    root = Path(root or DATA_ROOT)
    out: list[dict] = []
    v = sys.version_info
    if v[:2] < MIN_PY:
        out.append(check("FALHA", "python", f"Python {v.major}.{v.minor}: a Tia precisa do 3.12 ou mais novo",
                         "instale o Python 3.12 em python.org (marque \"Add python.exe to PATH\") e abra o Claude Code de novo"))
    else:
        out.append(check("OK", "python", f"Python {v.major}.{v.minor}"))
    bash = find_bash()
    out.append(check("OK", "git-bash", "Git Bash encontrado") if bash else
               check("FALHA", "git-bash", "Git Bash não encontrado: sem ele os hooks da Tia não rodam",
                     "instale o Git for Windows (git-scm.com) com as opções padrão e abra o Claude Code de novo"))

    ws = is_workspace(root)
    data = plugin_data(root)
    vpy = venv_python(data)
    if not ws:
        out.append(check("AVISO", "workspace", f"{root} ainda não é um workspace da Tia (falta {MARCADOR.as_posix()})",
                         "diga \"Tia, configurar\" para preparar este projeto"))
    else:
        out.append(check("OK", "workspace", f"workspace da Tia em {root}"))

    if vpy:
        ok_hash = req_hash_ok(data)
        out.append(check("OK", "ambiente", "ambiente Python da Tia pronto") if ok_hash is not False else
                   check("AVISO", "ambiente", "ambiente Python da Tia é de uma versão anterior do plugin",
                         f"abra uma sessão nova (recria sozinho) ou rode {LANCADOR} bootstrap --force"))
    elif ws:
        motivo = diagnostico_rede(data)
        if data is None:
            out.append(check("FALHA", "ambiente", "ainda não sei onde fica o ambiente do plugin (primeira sessão neste projeto)",
                             "feche e abra o Claude Code nesta pasta: o início da sessão prepara tudo sozinho"))
        else:
            out.append(check("FALHA", "ambiente", "o ambiente Python da Tia ainda não foi criado: até lá, escrita e comandos ficam negados",
                             f"rode {LANCADOR} bootstrap (leva alguns minutos na primeira vez). {motivo}".strip()))
    else:
        out.append(check("OK", "ambiente", "ambiente Python é criado depois do \"Tia, configurar\""))

    if not ws:
        return out

    if bash and vpy:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root), "CLAUDE_PLUGIN_DATA": str(data)}
        env.pop("TIA_ROOT", None)
        try:
            r = subprocess.run([bash, str(CODE_ROOT / "scripts" / "hook.sh"), "session_start"],
                               input='{"session_id":"doctor"}', capture_output=True, text=True, timeout=60,
                               encoding="utf-8", errors="replace", cwd=root, env=env)
            ok = "Você é a **Tia**" in r.stdout and "ALERTA" not in r.stdout
            out.append(check("OK" if ok else "FALHA", "hooks", "hooks da Tia respondem" if ok else
                             f"o hook de início de sessão não respondeu como esperado: {r.stdout[:200]} {r.stderr[:200]}",
                             "" if ok else f"rode {LANCADOR} bootstrap --force e abra uma sessão nova"))
        except (OSError, subprocess.TimeoutExpired) as e:
            out.append(check("FALHA", "hooks", f"chamada de teste ao hook falhou: {e}"))

    if os.environ.get("TIA_DEV") == "1":
        out.append(check("AVISO", "dev", "modo de desenvolvimento do plugin (TIA_DEV): fiscalização desligada"))

    try:
        import yaml  # noqa: F401
    except ImportError:
        out.append(check("AVISO", "base", "checagens da Base, da fila e dos monitores rodam depois que o ambiente existir"))
        import configurar
        _modelos(out, configurar.status(root))
        return out
    _conteudo(out, root)
    return out


def _modelos(out: list[dict], st: dict) -> None:
    falta = [f for f in st["faltando"]]
    if falta:
        out.append(check("AVISO", "estrutura", f"faltam no workspace: {', '.join(falta[:6])}" + (" …" if len(falta) > 6 else ""),
                         "diga \"Tia, configurar\" (só cria o que falta)"))
    if st["desatualizados"]:
        nomes = ", ".join(f"{d['arquivo']} (v{d['versao']}→v{d['versao_plugin']})" for d in st["desatualizados"])
        out.append(check("AVISO", "modelos", f"modelos copiados mais antigos que o plugin: {nomes}",
                         "diga \"Tia, atualiza a configuração\" para ver o diff e decidir"))


def _conteudo(out: list[dict], root: Path) -> None:
    import configurar
    import kb as kbmod
    import memoria
    import metricas
    import validate
    from _common import config_sobreposicoes_ignoradas

    _modelos(out, configurar.status(root))
    ign = config_sobreposicoes_ignoradas(root)
    if ign:
        out.append(check("AVISO", "config", f".tia/config.yaml tenta mudar regras inegociáveis (ignoradas): {', '.join(ign)}",
                         "retire essas chaves do config do time"))
    rep = kbmod.validate_kb(root)
    if not rep["ok"]:
        out.append(check("FALHA", "kb", f"Base de Conhecimento inválida: {len(rep['erros'])} erro(s): "
                         f"{rep['erros'][0]['onde']}: {rep['erros'][0]['erro']}", f"{LANCADOR} kb validar"))
    elif rep["regras"] == 0:
        out.append(check("AVISO", "kb", "Base de Conhecimento sem regras: rode /tia:base antes da primeira demanda"))
    else:
        out.append(check("OK", "kb", f"Base de Conhecimento: {rep['regras']} regras, {rep['fontes']} fontes"))
    dpath = P(root, "fila")
    if dpath.exists():
        vr = validate.validate(dpath, root)
        out.append(check("OK" if vr["ok"] else "FALHA", "demandas",
                         f"fila: {len(vr['demandas'])} demanda(s), {len(vr['erros'])} erro(s), {len(vr['avisos'])} aviso(s)",
                         "" if vr["ok"] else f"{LANCADOR} validate"))
    else:
        out.append(check("AVISO", "demandas", "fila tia/demandas.yaml ausente", "crie a partir de tia/demandas.exemplo.yaml"))
    merr = metricas.validate(root)
    out.append(check("OK" if not merr else "FALHA", "monitoramento",
                     f"{len([m for m in metricas.load_monitors(root) if m.get('status') == 'ativo'])} monitor(es) ativo(s)"
                     if not merr else f"{len(merr)} erro(s): {merr[0]}", "" if not merr else f"{LANCADOR} metricas validar"))
    mem = memoria.ativas(root)
    out.append(check("OK", "memoria", f"Memória: {len(mem)} aprendizado(s) ativo(s)"))
    led = read_json(P(root, "ledger")) or {}
    running = [k for k, d in (led.get("demandas") or {}).items() if d.get("state") == "running"]
    if running:
        out.append(check("AVISO", "ativa", f"demanda em andamento: {', '.join(running)} (retomar ou abandonar)"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", type=Path, default=None)
    a = ap.parse_args(argv)
    res = run_checks(a.root)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for c in res:
            print(f"{c['nivel']:5} {c['nome']}: {c['msg']}" + (f"  -> {c['correcao']}" if c["correcao"] else ""))
    return 1 if any(c["nivel"] == "FALHA" for c in res) else 0


if __name__ == "__main__":
    sys.exit(main())
