"""Item 3: config em camadas, inegociáveis, padrão de épico; item 2: resolução do workspace."""
from __future__ import annotations

import _common
import coverage
import kb
from conftest import REPO


def test_merge_padrao_e_time(proj):
    cfg = _common.load_config(proj)
    assert cfg["atlassian"]["jira_projeto"] == "IT"                 # do time
    assert cfg["tamanhos"]["P"]["max_historias"] == 3              # padrão do plugin
    assert cfg["confluence"]["espacos"]["INT"]["politica"] == "manter"
    assert cfg["confluence"]["c1_validade_horas"] == 24


def test_time_sobrepoe_default(proj):
    p = proj / ".tia" / "config.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "max_retrabalho: 4\ntamanhos:\n  P: {max_historias: 2}\n"
                 "cobertura:\n  palavras_vagas: [bonito]\n", encoding="utf-8")
    cfg = _common.load_config(proj)
    assert cfg["max_retrabalho"] == 4
    assert cfg["tamanhos"]["P"]["max_historias"] == 2
    assert cfg["tamanhos"]["P"]["max_criterios_por_historia"] == 5   # deep merge preserva o resto
    assert cfg["tamanhos"]["M"]["max_historias"] == 6
    assert cfg["cobertura"]["palavras_vagas"] == ["bonito"]           # lista substitui


def test_inegociavel_nao_e_sobreposto(proj):
    p = proj / ".tia" / "config.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "escopo_escrita:\n  caminhos: ['**']\n"
                 "dados:\n  escrita_regex: 'nunca'\n  clis: [meucli]\nconfluence:\n  padrao: manter\n", encoding="utf-8")
    cfg = _common.load_config(proj)
    assert cfg["escopo_escrita"]["caminhos"] == ["tia/**"]
    assert "insert" in cfg["dados"]["escrita_regex"]
    assert cfg["dados"]["clis"] == ["meucli"]                          # default ajustável
    assert cfg["confluence"]["padrao"] == "somente_leitura"
    assert set(_common.config_sobreposicoes_ignoradas(proj)) == {"escopo_escrita", "dados.escrita_regex",
                                                                   "confluence.padrao"}


def test_secoes_epico_vem_do_padrao_do_workspace(proj):
    assert _common.secoes_epico(proj)[0] == "Em uma frase"
    f = proj / "tia" / "kb" / "padroes" / "epico.md"
    f.write_text(f.read_text(encoding="utf-8").replace('  - "Em uma frase"\n', ""), encoding="utf-8")
    assert "Em uma frase" not in _common.secoes_epico(proj)
    assert kb.validate_kb(proj)["ok"]


def test_secoes_epico_conflito_config_e_padrao(proj, entrega):
    p = proj / ".tia" / "config.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "cobertura:\n  secoes_epico: [Resumo]\n", encoding="utf-8")
    rep = kb.validate_kb(proj)
    assert not rep["ok"] and any(e["id"] == "PADRAO-EPICO" for e in rep["erros"])


def test_cobertura_usa_secoes_do_padrao(proj, entrega):
    assert coverage.evaluate("D-001", proj)["ok"]
    f = proj / "tia" / "kb" / "padroes" / "epico.md"
    f.write_text(f.read_text(encoding="utf-8").replace('secoes_epico:\n', 'secoes_epico:\n  - "Riscos"\n'),
                 encoding="utf-8")
    rep = coverage.evaluate("D-001", proj)
    assert not rep["ok"] and any("Riscos" in e for e in rep["erros"])


def test_fonte_com_sigla_do_time(proj):
    assert _common.SOURCE_ID_RE.match("SRC-FIN-001") and not _common.SOURCE_ID_RE.match("SRC-X-001")


def test_resolucao_do_workspace(tmp_path, monkeypatch):
    for v in ("TIA_ROOT", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    ws = tmp_path / "ws"
    (ws / ".tia").mkdir(parents=True)
    (ws / ".tia" / "config.yaml").write_text("modelo_versao: 1\n", encoding="utf-8")
    (ws / "tia" / "sub").mkdir(parents=True)
    assert _common.find_data_root(ws / "tia" / "sub") == ws.resolve()      # cwd sobe as pastas
    assert _common.find_data_root(tmp_path) is None
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))                # sem marcador: não é workspace
    assert _common.find_data_root(ws) is None
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ws))
    assert _common.find_data_root(tmp_path) == ws
    monkeypatch.setenv("TIA_ROOT", str(tmp_path))                          # explícito vence
    assert _common.find_data_root() == tmp_path


def test_codigo_no_plugin():
    assert _common.CODE_ROOT == REPO and _common.SCHEMA_DEMANDAS.exists()
