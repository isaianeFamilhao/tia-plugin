import copy

import okr

BOM = [{
    "ciclo": "2026-Q3", "time": "Onboarding", "horizonte": "trimestre", "momento": "crescimento",
    "modo": "comprometido", "status": "rascunho", "alinhamento": "Crescer base ativa",
    "objetivos": [{
        "titulo": "Novos usuários chegam ao primeiro valor sem frustração",
        "krs": [
            {"texto": "Aumentar a conclusão do cadastro de 42% para 58%", "tipo": "outcome", "metrica": "conclusão",
             "baseline": 42, "meta": 58, "unidade": "%", "status_dados": "mensuravel_hoje"},
            {"texto": "Mapear 100% das etapas do funil em 2 semanas e reduzir o abandono na etapa crítica em 30%",
             "tipo": "learning", "status_dados": "ponto_cego"},
            {"texto": "Manter contas com dados inválidos abaixo de 3%", "tipo": "guardrail", "baseline": 2.1,
             "meta": 3, "unidade": "%", "status_dados": "mensuravel_hoje"},
        ],
        "iniciativas": ["Instrumentar o funil etapa a etapa", "Simplificar validação de documentos"],
    }],
}]


def test_okr_bom_passa():
    rep = okr.validar(BOM)
    assert rep["ok"], rep["erros"]
    assert any("instrumentação" in a for a in rep["avisos"])


def test_kr_que_e_entrega_reprova():
    c = copy.deepcopy(BOM)
    c[0]["objetivos"][0]["krs"][0] = {"texto": "Entregar 5 features", "tipo": "outcome", "meta": 5}
    c[0]["objetivos"][0]["krs"].append({"texto": "Lançar app v2", "tipo": "outcome", "meta": 1})
    erros = " | ".join(okr.validar(c)["erros"])
    assert "Lançar app v2" in erros and "é entrega" in erros


def test_outcome_sem_meta_reprova_e_sem_baseline_avisa():
    c = copy.deepcopy(BOM)
    kr = c[0]["objetivos"][0]["krs"][0]
    kr.pop("meta"); kr.pop("baseline")
    rep = okr.validar(c)
    assert any("sem meta" in e for e in rep["erros"])
    assert any("sem baseline" in a for a in rep["avisos"])


def test_avisos_pragmaticos():
    c = copy.deepcopy(BOM)
    c[0]["momento"] = "descoberta"
    c[0]["objetivos"][0]["krs"][2]["tipo"] = "outcome"
    c[0]["objetivos"][0]["krs"][0]["texto"] = "Aumentar a receita por conta de 10 para 12"
    c[0]["objetivos"] = c[0]["objetivos"] * 4
    c[0]["alinhamento"] = ""
    avisos = " | ".join(okr.validar(c)["avisos"])
    for trecho in ("acima de 3", "nenhum guardrail", "momento de descoberta", "sem alinhamento"):
        assert trecho in avisos, trecho


def test_milestone_tecnico_e_permitido():
    c = copy.deepcopy(BOM)
    c[0]["momento"] = "fundacao"
    c[0]["objetivos"][0]["krs"][1] = {"texto": "Migrar a API e reduzir a latência p95 de 800 ms para < 200 ms",
                                      "tipo": "milestone"}
    assert okr.validar(c)["ok"]
