import json

import coverage
from conftest import HISTORIAS, result


def ev(proj):
    return coverage.evaluate("D-001", proj)


def write_result(d, **over):
    (d / "result.json").write_text(json.dumps(result(**over), ensure_ascii=False), encoding="utf-8")


def test_entrega_completa_ok(proj, entrega):
    rep = ev(proj)
    assert rep["ok"], rep["erros"]
    sit = {m["regra"]: m["situacao"] for m in rep["matriz"]}
    assert sit == {"RN-ITR-001": "coberta", "RN-ITR-002": "coberta", "RN-ITR-003": "fora do escopo", "RC-01": "coberta"}
    assert any("a confirmar" in a for a in rep["avisos"])


def test_regra_sem_cobertura_reprova(proj, entrega):
    write_result(entrega, fora_do_escopo=[])
    rep = ev(proj)
    assert not rep["ok"]
    assert any("RN-ITR-003 sem critério" in e for e in rep["erros"])


def test_regra_inexistente(proj, entrega):
    write_result(entrega, regras_relevantes=["RN-ITR-001", "RN-ITR-002", "RN-ITR-003", "RC-01", "RN-ITR-099"])
    assert any("RN-ITR-099" in e for e in ev(proj)["erros"])


def test_criterio_fora_do_formato(proj, entrega):
    (entrega / "historias.md").write_text(HISTORIAS.replace("Dado pagamento confirmado, quando o atendente solicita, então",
                                                            "Com pagamento confirmado"), encoding="utf-8")
    assert any("Dado/Quando/Então" in e for e in ev(proj)["erros"])


def test_cobre_sem_criterio(proj, entrega):
    (entrega / "historias.md").write_text(HISTORIAS.replace("**Cobre:** RN-ITR-001, RN-ITR-002, RC-01",
                                                            "**Cobre:** RN-ITR-001, RN-ITR-002, RN-ITR-003, RC-01"),
                                          encoding="utf-8")
    assert any("sem nenhum critério" in e for e in ev(proj)["erros"])


def test_epico_sem_secao(proj, entrega):
    p = entrega / "epico.md"
    p.write_text(p.read_text(encoding="utf-8").replace("## Fora do escopo", "## Fora"), encoding="utf-8")
    erros = ev(proj)["erros"]
    assert any("Fora do escopo" in e for e in erros)


def test_a_confirmar_sem_lacuna(proj, entrega):
    write_result(entrega, lacunas=[], open_questions=[])
    assert any("a confirmar" in e for e in ev(proj)["erros"])


def test_fonte_nao_registrada(proj, entrega):
    write_result(entrega, fontes=["SRC-IT-001", "SRC-DEM-009"])
    assert any("SRC-DEM-009" in e for e in ev(proj)["erros"])


def test_candidata_sem_fonte(proj, entrega):
    (entrega / "regras.md").write_text((entrega / "regras.md").read_text(encoding="utf-8").replace("SRC-DEM-001", "SRC-DEM-002"),
                                       encoding="utf-8")
    assert any("regras.md RC-01" in e for e in ev(proj)["erros"])


def test_limite_de_historias(proj, entrega):
    extra = "\n".join(HISTORIAS.split("\n")[2:]).replace("H-01", "H-0{n}")
    text = HISTORIAS + "".join("\n" + extra.replace("{n}", str(n)) for n in (2, 3, 4))
    (entrega / "historias.md").write_text(text, encoding="utf-8")
    write_result(entrega, historias=["H-01", "H-02", "H-03", "H-04"])
    assert any("dividir a demanda" in e for e in ev(proj)["erros"])


def test_regra_revogada_reprova(proj, entrega):
    f = proj / "kb/internal-tools/regras/reprocessamento-ajustes.md"
    t = f.read_text(encoding="utf-8")
    i = t.index("### RN-ITR-003")
    f.write_text(t[:i] + t[i:].replace("- **Status:** confirmada", "- **Status:** revogada", 1), encoding="utf-8")
    assert any("RN-ITR-003 está revogada" in e for e in ev(proj)["erros"])


def test_blocked_com_motivo_ok(proj, entrega):
    write_result(entrega, status="blocked", blocked_reason="dono do processo indefinido")
    rep = ev(proj)
    assert rep["ok"] and rep["status"] == "blocked"


def test_blocked_sem_motivo(proj, entrega):
    write_result(entrega, status="blocked", blocked_reason=None)
    assert not ev(proj)["ok"]


def test_render_e_main(proj, entrega):
    assert coverage.main(["D-001", "--root", str(proj)]) == 0
    assert "Matriz regra × critério" in (entrega / "cobertura.md").read_text(encoding="utf-8")
