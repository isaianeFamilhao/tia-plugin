import json

import pytest

import ledger
import packet
from conftest import result


def L(proj):
    return ledger.Ledger(proj)


def test_ciclo_completo(proj, entrega):
    led = L(proj)
    led.sync()
    assert led.get("D-001")["state"] == "valid"
    led.g1("D-001", True, "ok")
    with pytest.raises(ledger.LedgerError):
        L(proj).iniciar("D-002", "sessao-xyz")  # D-002 sem G1
    led = L(proj)
    led.iniciar("D-001", "sessao-123")
    assert led.active() == "D-001"
    with pytest.raises(ledger.LedgerError):
        led.g1("D-002", True, None)  # uma por vez
    led.coletar("D-001")
    assert led.get("D-001")["state"] == "delivered"
    led.g2("D-001", "accept", "boa")
    led.k1("D-001", ["RN-ITR-004"], "RC-01 vira regra")
    with pytest.raises(ledger.LedgerError):
        led.g3("D-001", "")
    led.g3("D-001", "pode publicar")
    led.publicada("D-001", ["IT-70"])
    assert L(proj).get("D-001")["state"] == "published"


def test_coletar_recusa_cobertura_reprovada(proj, entrega):
    (entrega / "result.json").write_text(json.dumps(result(fora_do_escopo=[])), encoding="utf-8")
    led = L(proj)
    led.sync()
    led.g1("D-001", True, None)
    led.iniciar("D-001", "sessao-123")
    with pytest.raises(ledger.LedgerError, match="cobertura"):
        led.coletar("D-001")
    assert L(proj).get("D-001")["state"] == "running"


def test_retrabalho_exige_motivo_e_tem_limite(proj, entrega):
    led = L(proj)
    led.sync()
    led.g1("D-001", True, None)
    for _ in range(2):
        led.iniciar("D-001", "sessao-123")
        led.coletar("D-001")
        with pytest.raises(ledger.LedgerError):
            led.g2("D-001", "rework", "")
        led.g2("D-001", "rework", "faltou critério negativo")
    led.iniciar("D-001", "sessao-123")
    led.coletar("D-001")
    with pytest.raises(ledger.LedgerError, match="retrabalhos"):
        led.g2("D-001", "rework", "de novo")


def test_pedido_mudou_depois_do_g1(proj):
    led = L(proj)
    led.sync()
    led.g1("D-001", True, None)
    p = proj / "ada" / "demandas.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("tamanho: P", "tamanho: M"), encoding="utf-8")
    led = L(proj)
    led.sync()
    assert led.get("D-001")["state"] == "valid"


def test_pacote_traz_epico_regras_e_lacunas(proj):
    text, meta = packet.build(proj, "D-001")
    assert "IT-39" in text and "RN-ITR-001" in text
    assert "Lacunas conhecidas" in text
    assert meta["dentro_do_teto"]


def test_pacote_traz_motivo_de_retrabalho(proj, entrega):
    led = L(proj)
    led.sync()
    led.g1("D-001", True, None)
    led.iniciar("D-001", "s-123456")
    led.coletar("D-001")
    led.g2("D-001", "rework", "faltou o critério de vedação")
    text, _ = packet.build(proj, "D-001")
    assert "faltou o critério de vedação" in text
