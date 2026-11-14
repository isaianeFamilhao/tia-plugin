import json

import pytest

import memoria
import metricas

PLANO = """monitores:
  - nome: Taxa de abandono do checkout
    origem: IT-42
    fonte: databricks
    consulta: "SELECT avg(abandono) FROM gold.checkout WHERE dt >= current_date - 1"
    unidade: "%"
    direcao: menor_melhor
    baseline: 30
    alerta: {variacao_pct: 10}
    critico: {limite: 40}
    cadencia: diaria
    janela_dias: 7
  - nome: Conversão do funil
    origem: KR-1
    fonte: looker
    consulta: explore funil_cadastro
    unidade: "%"
    direcao: maior_melhor
    alerta: {variacao_pct: 15}
    cadencia: semanal
    janela_dias: 30
"""


@pytest.fixture
def plano(proj):
    p = proj / ".harness" / "demandas" / "plano.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(PLANO, encoding="utf-8")
    return p


def test_ativar_exige_nota_e_gera_ids(proj, plano):
    with pytest.raises(metricas.MetricasError):
        metricas.ativar(proj, plano, "")
    novos = metricas.ativar(proj, plano, "pode monitorar")
    assert [m["id"] for m in novos] == ["M-001", "M-002"]
    assert metricas.validate(proj) == []


def test_consulta_que_altera_e_recusada(proj, plano):
    plano.write_text(PLANO.replace("SELECT avg", "DELETE FROM x; SELECT avg"), encoding="utf-8")
    with pytest.raises(metricas.MetricasError, match="só leitura"):
        metricas.ativar(proj, plano, "ok")


def test_avaliador_por_limite_e_variacao(proj, plano):
    metricas.ativar(proj, plano, "ok")
    assert metricas.avaliar(proj, "M-001", 31)["status"] == "ok"          # +3,3% < 10%
    assert metricas.avaliar(proj, "M-001", 34)["status"] == "alerta"      # +13% contra baseline 30
    assert metricas.avaliar(proj, "M-001", 41)["status"] == "critico"     # ≥ limite 40
    assert metricas.avaliar(proj, "M-002", 20)["status"] == "sem_referencia"
    assert metricas.avaliar(proj, "M-002", 19)["status"] == "ok"          # -5% < 15%
    assert metricas.avaliar(proj, "M-002", 15)["status"] == "alerta"      # -21% contra a anterior
    nomes = {a["monitor"] for a in metricas.alertas(proj)}
    assert nomes == {"M-001", "M-002"}


def test_ativos_marca_devido_e_encerrar(proj, plano):
    metricas.ativar(proj, plano, "ok")
    assert all(r["devido"] for r in metricas.ativos(proj))
    metricas.avaliar(proj, "M-001", 30)
    devidos = {r["id"]: r["devido"] for r in metricas.ativos(proj)}
    assert devidos == {"M-001": False, "M-002": True}
    metricas.encerrar(proj, "M-002", "fim do ciclo")
    assert [r["id"] for r in metricas.ativos(proj)] == ["M-001"]
    with pytest.raises(metricas.MetricasError):
        metricas.avaliar(proj, "M-002", 10)


MEM = """# Memória

### PM-001 · Linguagem humana
- **Aprendi:** citar pelo nome
- **Evidência:** "não sei o que é RN" (2026-11-13)
- **Aplicar em:** conversa
- **Status:** ativa
- **Desde:** 2026-11-13
"""


def test_memoria_valida_e_proximo(proj):
    (proj / "kb" / "memoria-pm.md").write_text(MEM, encoding="utf-8")
    assert memoria.validate(proj) == []
    assert memoria.proximo(proj) == "PM-002"


def test_memoria_revogada_exige_motivo(proj):
    (proj / "kb" / "memoria-pm.md").write_text(MEM.replace("ativa", "revogada"), encoding="utf-8")
    assert any("Motivo" in e["erro"] for e in memoria.validate(proj))
    (proj / "kb" / "memoria-pm.md").write_text(MEM.replace("conversa", "planeta"), encoding="utf-8")
    assert any("Aplicar em" in e["erro"] for e in memoria.validate(proj))


PLANO_OK = {
    "iniciativa": "Busca com IA",
    "problema": "usuário não acha o produto de primeira",
    "objetivo_negocio": "aumentar receita por sessão",
    "output": "busca com IA lançada",
    "metricas": [
        {"nome": "Conversão pós-busca IA", "camada": "product_outcome", "papel": "principal",
         "formula": "sessões com busca IA e add_to_cart em 5 min / sessões com busca IA × 100",
         "janela": "coorte diária", "direcao": "maior_melhor", "hipotese": "achar mais rápido aumenta compra",
         "status_dados": "ponto_cego",
         "tracking": [{"evento": "search_ai_triggered", "gatilho": "ao enviar a busca", "propriedades": ["query_len"]}]},
        {"nome": "Receita por sessão de busca", "camada": "business_outcome", "papel": "apoio",
         "formula": "receita atribuída / sessões com busca", "janela": "semanal", "direcao": "maior_melhor",
         "status_dados": "sem_acesso", "acesso": "conector do checkout"},
        {"nome": "Abandono pós-busca", "camada": "product_outcome", "papel": "guardrail",
         "formula": "sessões que saem após busca / sessões com busca", "janela": "diária",
         "direcao": "menor_melhor", "status_dados": "mensuravel_hoje", "baseline": 34.2},
    ],
}


def test_plano_completo_ok():
    rep = metricas.validar_plano(PLANO_OK)
    assert rep["ok"], rep["erros"]
    assert rep["monitoraveis"] == ["Abandono pós-busca"]
    assert any("ponto cego" in w for w in rep["avisos"])


def test_plano_reprova_vaidade_absoluto_e_ponto_cego_sem_tracking():
    import copy
    p = copy.deepcopy(PLANO_OK)
    p["metricas"][0]["tracking"] = []
    p["metricas"][1]["formula"] = "total de downloads"
    p["metricas"].append(dict(p["metricas"][2], nome="Tickets", papel="guardrail"))
    p["metricas"].append(dict(p["metricas"][2], nome="Chargeback", papel="guardrail"))
    p["problema"] = ""
    rep = metricas.validar_plano(p)
    erros = " | ".join(rep["erros"])
    assert not rep["ok"]
    assert "tracking spec" in erros and "número absoluto" in erros and "1 a 2 guardrails" in erros and "problema" in erros
    assert any("vaidade" in w for w in rep["avisos"])


def test_plano_sem_business_outcome_reprova():
    import copy
    p = copy.deepcopy(PLANO_OK)
    p["metricas"][1]["camada"] = "product_outcome"
    assert any("business outcome" in e for e in metricas.validar_plano(p)["erros"])
