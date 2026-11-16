import copy

import pytest

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


# ------------------------------------------------------------------ nível (grupo | time) e id do objetivo
def grupo_q3(ids=("OBJ-01", "OBJ-02")):
    c = copy.deepcopy(BOM[0])
    c.update({"time": "Plataforma", "nivel": "grupo", "alinhamento": "Meta da diretoria: crescer base ativa"})
    o = c["objetivos"][0]
    c["objetivos"] = []
    for i in ids:
        oi = copy.deepcopy(o)
        oi["id"] = i
        c["objetivos"].append(oi)
    return c


def time_alinhado(ref="OBJ-02"):
    c = copy.deepcopy(BOM[0])
    c["alinhamento"] = ref
    return c


def test_arquivo_antigo_sem_nivel_nem_id_continua_valido():
    rep = okr.validar(copy.deepcopy(BOM))
    assert rep["ok"], rep["erros"]
    assert okr.nivel(BOM[0]) == "time"
    assert any("texto livre" in a for a in rep["avisos"])          # texto livre vale, com aviso


def test_okr_de_grupo_com_ids_passa():
    rep = okr.validar([grupo_q3()])
    assert rep["ok"], rep["erros"]
    assert not any("texto livre" in a for a in rep["avisos"])      # grupo alinha à diretoria em texto


def test_alinhamento_com_id_do_grupo():
    assert okr.validar([grupo_q3(), time_alinhado("OBJ-02")])["ok"]
    assert okr.validar([time_alinhado("OBJ-01")], grupo_extra=[grupo_q3()])["ok"]


def test_referencia_a_objetivo_inexistente_reprova():
    rep = okr.validar([grupo_q3(), time_alinhado("OBJ-07")])
    assert not rep["ok"] and any("OBJ-07" in e and "não existe" in e for e in rep["erros"])
    rep = okr.validar([time_alinhado("OBJ-02 e OBJ-09")], grupo_extra=[grupo_q3()])
    assert any("OBJ-09" in e for e in rep["erros"]) and not any("cita OBJ-02" in e for e in rep["erros"])


def test_referencia_sem_grupo_conhecido_so_avisa():
    rep = okr.validar([time_alinhado("OBJ-02")])
    assert rep["ok"] and any("não conferido" in a for a in rep["avisos"])


@pytest.mark.parametrize("mexer, trecho", [
    (lambda c: c.update(nivel="diretoria"), "nivel deve ser"),
    (lambda c: c["objetivos"][0].update(id="OBJ-1"), "fora do formato"),
    (lambda c: c["objetivos"][1].update(id="OBJ-01"), "repetido no ciclo"),
])
def test_nivel_e_id_invalidos_reprovam(mexer, trecho):
    c = grupo_q3()
    mexer(c)
    assert any(trecho in e for e in okr.validar([c])["erros"])


def test_id_repetido_entre_okrs_do_grupo_no_mesmo_ciclo():
    rep = okr.validar([grupo_q3(), grupo_q3(("OBJ-02", "OBJ-03"))])
    assert any("já usado por outro OKR do grupo" in e for e in rep["erros"])
    outro = grupo_q3(("OBJ-01",))
    outro["ciclo"] = "2026-Q4"
    assert okr.validar([grupo_q3(), outro])["ok"]


def test_objetivo_do_grupo_sem_id_avisa():
    c = grupo_q3()
    del c["objetivos"][0]["id"]
    rep = okr.validar([c])
    assert rep["ok"] and any("sem id" in a for a in rep["avisos"])


def _escrever(path, ciclos):
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(ciclos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_cli_validar_com_grupo_e_listar_por_nivel(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(okr, "REPO_ROOT", tmp_path)
    grupo, rascunho = tmp_path / "grupo.yaml", tmp_path / "tia" / "propostas" / "okrs-q3.yaml"
    _escrever(grupo, [grupo_q3()])
    _escrever(rascunho, [time_alinhado("OBJ-05")])
    assert okr.main(["validar", str(rascunho)]) == 0                      # sem grupo conhecido: só aviso
    assert okr.main(["validar", str(rascunho), "--grupo", str(grupo)]) == 1
    assert "OBJ-05" in capsys.readouterr().out
    ativo_g, ativo_t = grupo_q3(), time_alinhado("OBJ-01")
    ativo_g["status"] = ativo_t["status"] = "ativo"
    _escrever(tmp_path / "tia" / "kb" / "okrs.yaml", [ativo_g, ativo_t])
    assert okr.main(["validar", str(rascunho)]) == 1                      # grupo vem da Base de Conhecimento
    capsys.readouterr()
    okr.main(["listar", "--ativos", "--nivel", "grupo"])
    out = capsys.readouterr().out
    assert "Plataforma [grupo]" in out and "OBJ-01 · " in out and "Onboarding" not in out
    okr.main(["listar", "--ativos"])
    out = capsys.readouterr().out
    assert "Onboarding (ativo, comprometido) → OBJ-01" in out              # sem `nivel`: linha como antes
    _escrever(tmp_path / "tia" / "kb" / "okrs.yaml", [ativo_t])
    okr.main(["listar", "--ativos", "--nivel", "grupo"])
    assert "Nenhum OKR do grupo registrado ativo." in capsys.readouterr().out
