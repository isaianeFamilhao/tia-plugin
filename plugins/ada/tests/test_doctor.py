"""Item 9: doctor com mensagens de primeira instalação, ambiente do plugin, proxy e modelos."""
from __future__ import annotations

import subprocess
import sys

import configurar
import doctor
from conftest import BIN


def por_nome(res):
    return {c["nome"]: c for c in res}


def test_fora_de_workspace_convida_a_configurar(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("ADA_PLUGIN_DATA", raising=False)
    r = por_nome(doctor.run_checks(tmp_path))
    assert r["workspace"]["nivel"] == "AVISO" and "Ada, configurar" in r["workspace"]["correcao"]
    assert r["ambiente"]["nivel"] == "OK"
    assert "kb" not in r


def test_workspace_sem_caminho_dos_dados(proj, monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("ADA_PLUGIN_DATA", raising=False)
    r = por_nome(doctor.run_checks(proj))
    assert r["ambiente"]["nivel"] == "FALHA" and "feche e abra" in r["ambiente"]["correcao"]


def test_workspace_sem_venv_com_bloqueio_de_proxy(proj, tmp_path, monkeypatch):
    data = tmp_path / "plugin-data"
    data.mkdir()
    (data / "bootstrap.log").write_text("ERROR: ProxyError('Cannot connect to proxy.')", encoding="utf-8")
    monkeypatch.setenv("ADA_PLUGIN_DATA", str(data))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    r = por_nome(doctor.run_checks(proj))
    assert r["ambiente"]["nivel"] == "FALHA"
    assert "bootstrap" in r["ambiente"]["correcao"] and "proxy" in r["ambiente"]["correcao"]


def test_variavel_nao_substituida_e_ignorada(proj, monkeypatch):
    monkeypatch.setenv("ADA_PLUGIN_DATA", "${CLAUDE_PLUGIN_DATA}")
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    assert doctor.plugin_data(proj) is None


def test_checa_conteudo_e_modelos(proj, monkeypatch):
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    r = por_nome(doctor.run_checks(proj))
    assert r["kb"]["nivel"] == "OK" and r["demandas"]["nivel"] == "OK"
    assert r["estrutura"]["nivel"] == "AVISO"                  # fixture não tem tudo o que o configurar cria
    p = proj / ".ada" / "config.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "escopo_escrita: {caminhos: ['**']}\n", encoding="utf-8")
    assert "escopo_escrita" in por_nome(doctor.run_checks(proj))["config"]["msg"]


def test_modelo_desatualizado(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    configurar.criar(ws, "T", "s", "c", "J", ["X|1|x|manter"], "sim")
    f = ws / "ada" / "kb" / "padroes" / "epico.md"
    f.write_text(f.read_text(encoding="utf-8").replace("modelo_versao: 1", "modelo_versao: 0"), encoding="utf-8")
    monkeypatch.setattr(doctor, "venv_python", lambda data: None)
    r = por_nome(doctor.run_checks(ws))
    assert "ada/kb/padroes/epico.md" in r["modelos"]["msg"] and "atualiza a configuração" in r["modelos"]["correcao"]


def test_roda_sem_pyyaml(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    configurar.criar(ws, "T", "s", "c", "J", ["X|1|x|manter"], "sim")
    code = ("import sys; sys.modules['yaml'] = None; sys.path.insert(0, sys.argv[1]); import doctor; "
            "doctor.main(['--root', sys.argv[2]])")
    r = subprocess.run([sys.executable, "-c", code, str(BIN), str(ws)], capture_output=True, text=True, encoding="utf-8")
    assert "Traceback" not in r.stderr, r.stderr
    assert "depois que o ambiente existir" in r.stdout
