"""Item 8: /ada:configurar cria o workspace, só o que falta, e `atualizar` mostra diff."""
from __future__ import annotations

import subprocess
import sys

import pytest

import _common
import configurar
import kb
import validate
from conftest import BIN

ESPACOS = ["INT|282787868|Internal Tools|manter", "PO|370737187|Políticas|somente_leitura"]


def criar(root, nota="sim, pode criar"):
    return configurar.criar(root, "Internal Tools", "https://exemplo.atlassian.net", "abc-123", "IT", ESPACOS, nota)


@pytest.fixture
def vazio(tmp_path, monkeypatch):
    ws = tmp_path / "projeto"
    ws.mkdir()
    monkeypatch.setenv("ADA_ROOT", str(ws))
    monkeypatch.setenv("ADA_HOME", str(tmp_path / "home-ada"))
    return ws


def test_cria_workspace_completo(vazio):
    assert not _common.is_workspace(vazio)
    feitos = criar(vazio)
    assert _common.is_workspace(vazio)
    for rel in (".ada/config.yaml", "ada/demandas.yaml", "ada/kb/README.md", "ada/kb/padroes/epico.md",
                "ada/memoria/pessoal/pessoal.md", "ada/memoria/time", "CLAUDE.md", ".gitignore", ".ada/monitoramento"):
        assert (vazio / rel).exists(), rel
    cfg = _common.load_config(vazio)
    assert cfg["confluence"]["espacos"]["INT"]["politica"] == "manter"
    assert cfg["confluence"]["espacos"]["PO"]["nome"] == "Políticas"
    assert cfg["atlassian"]["jira_projeto"] == "IT" and cfg["modelo_versao"] == 1
    assert cfg["escopo_escrita"]["caminhos"] == ["ada/**"]
    assert kb.validate_kb(vazio)["ok"]
    assert validate.validate(vazio / "ada" / "demandas.yaml", vazio)["ok"]
    claude = (vazio / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Internal Tools" in claude and "**INT**" in claude and "{" not in claude
    assert ".ada/cache/" in (vazio / ".gitignore").read_text(encoding="utf-8")
    assert configurar.status(vazio)["faltando"] == [] and configurar.status(vazio)["desatualizados"] == []
    assert "CLAUDE.md" in feitos


def test_so_cria_o_que_nao_existe(vazio):
    criar(vazio)
    (vazio / "ada" / "kb" / "padroes" / "epico.md").write_text("---\nmodelo_versao: 1\nsecoes_epico: [A]\n---\n# meu\n",
                                                                encoding="utf-8")
    assert criar(vazio, "de novo") == []
    assert "# meu" in (vazio / "ada" / "kb" / "padroes" / "epico.md").read_text(encoding="utf-8")


def test_claude_md_existente_ganha_import(vazio):
    (vazio / "CLAUDE.md").write_text("# Projeto\nRegras do repositório.\n", encoding="utf-8")
    (vazio / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    criar(vazio)
    raiz = (vazio / "CLAUDE.md").read_text(encoding="utf-8")
    assert raiz.startswith("# Projeto") and raiz.rstrip().endswith("@ada/CLAUDE.md")
    assert (vazio / "ada" / "CLAUDE.md").exists()
    gi = (vazio / ".gitignore").read_text(encoding="utf-8")
    assert gi.startswith("node_modules/") and "ada/memoria/pessoal/" in gi
    criar(vazio, "de novo")
    assert (vazio / "CLAUDE.md").read_text(encoding="utf-8").count("@ada/CLAUDE.md") == 1


def test_exige_nota_e_um_so_manter(vazio):
    with pytest.raises(SystemExit):
        criar(vazio, "")
    with pytest.raises(SystemExit):
        configurar.criar(vazio, "T", "s", "c", "J", ["A|1|a|manter", "B|2|b|manter"], "sim")
    with pytest.raises(SystemExit):
        configurar.criar(vazio, "T", "s", "c", "J", ["A|1|a|editar"], "sim")
    assert not _common.is_workspace(vazio)


def test_atualizar_mostra_diff_e_aplica_com_backup(vazio):
    criar(vazio)
    f = vazio / "ada" / "kb" / "padroes" / "historia.md"
    f.write_text(f.read_text(encoding="utf-8").replace("modelo_versao: 1", "modelo_versao: 0"), encoding="utf-8")
    st = configurar.status(vazio)
    assert [d["arquivo"] for d in st["desatualizados"]] == ["ada/kb/padroes/historia.md"]
    assert "modelo_versao: 0" in configurar.diff(vazio, "ada/kb/padroes/historia.md")
    with pytest.raises(SystemExit):
        configurar.aplicar(vazio, "ada/kb/padroes/historia.md", "")
    bak = configurar.aplicar(vazio, "ada/kb/padroes/historia.md", "sim, atualiza")
    assert bak.exists() and configurar.status(vazio)["desatualizados"] == []


def test_config_e_claude_md_nao_sao_trocados_pelo_script(vazio):
    criar(vazio)
    c = vazio / ".ada" / "config.yaml"
    c.write_text(c.read_text(encoding="utf-8").replace("modelo_versao: 1", "modelo_versao: 0"), encoding="utf-8")
    with pytest.raises(SystemExit):
        configurar.aplicar(vazio, ".ada/config.yaml", "sim")


def test_roda_sem_pyyaml(vazio):
    """configurar roda com o Python do sistema, antes do venv: só biblioteca padrão."""
    code = ("import sys; sys.modules['yaml'] = None; sys.path.insert(0, sys.argv[1]); import configurar; "
            "sys.exit(configurar.main(['--root', sys.argv[2], 'criar', '--time', 'T', '--site', 's', '--cloud-id', 'c',"
            " '--jira', 'J', '--espaco', 'X|1|x|manter', '--nota', 'sim']))")
    r = subprocess.run([sys.executable, "-c", code, str(BIN), str(vazio)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert _common.is_workspace(vazio)
