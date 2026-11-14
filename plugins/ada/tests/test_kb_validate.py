import kb
import validate


def test_kb_valida(proj):
    rep = kb.validate_kb(proj)
    assert rep["ok"], rep["erros"]
    assert rep["regras"] == 3 and rep["fontes"] == 1


def test_kb_erros(proj):
    f = proj / "ada" / "kb" / "internal-tools" / "regras" / "reprocessamento-ajustes.md"
    f.write_text(f.read_text(encoding="utf-8") + """
### RN-ITR-001 · Duplicada
- **Regra:** Texto qualquer suficientemente longo para passar.
- **Status:** talvez
- **Fontes:** SRC-IT-999
""", encoding="utf-8")
    erros = [e["erro"] for e in kb.validate_kb(proj)["erros"]]
    assert any("duplicado" in e for e in erros)
    assert any("status inválido" in e for e in erros)
    assert any("não registrada" in e for e in erros)
    assert any("Atualizado" in e for e in erros)


def test_kb_yaml_invalido_vira_erro(proj):
    (proj / "ada" / "kb" / "fontes" / "ruim.yaml").write_text('- id: SRC-IT-002\n  titulo: "a" b\n', encoding="utf-8")
    rep = kb.validate_kb(proj)
    assert not rep["ok"] and any("YAML inválido" in e["erro"] for e in rep["erros"])


def test_busca_sem_acento(proj):
    hits = kb.search(proj, "vedacao conta propria")
    assert hits and hits[0]["id"] == "RN-ITR-003"


def test_lacunas(proj):
    assert any("limite mensal" in l["texto"] for l in kb.lacunas(proj))


def test_fila_valida(proj):
    rep = validate.validate(proj / "ada" / "demandas.yaml", proj)
    assert rep["ok"], rep["erros"]


def test_fila_refinar_sem_epico(proj):
    p = proj / "ada" / "demandas.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("  epico_jira: IT-39\n", ""), encoding="utf-8")
    rep = validate.validate(p, proj)
    assert not rep["ok"] and any("epico_jira" in e["erro"] for e in rep["erros"])


def test_fila_avisa_pedido_vago(proj):
    p = proj / "ada" / "demandas.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("quer resolver", "quer melhorar e resolver"), encoding="utf-8")
    rep = validate.validate(p, proj)
    assert rep["ok"] and any("vago" in a["aviso"] for a in rep["avisos"])
