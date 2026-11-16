import ajuda
from conftest import REPO


def test_lista_todas_as_skills_do_projeto():
    nomes = {p.parent.name for p in (REPO / "skills").glob("*/SKILL.md")}
    por_perfil = {pf: {s["nome"] for s in ajuda.skills(REPO, pf)} for pf in ("pm", "gpm")}
    assert por_perfil["pm"] | por_perfil["gpm"] == nomes          # cada skill aparece em algum perfil
    assert {s["nome"] for s in ajuda.skills(REPO)} == por_perfil["pm"]   # padrão: perfil PM
    assert [s["nome"] for s in ajuda.skills(REPO)][:2] == ["abrir", "demanda"]


def test_skill_nova_aparece_sozinha(tmp_path):
    d = tmp_path / "skills" / "nova"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: nova\ndescription: Faz algo novo. Use quando pedirem.\n---\n# x\n",
                                encoding="utf-8")
    s = ajuda.skills(tmp_path)
    assert s == [{"nome": "nova", "uso": "/tia:nova", "descricao": "Faz algo novo."}]


def test_tabela_sem_pipe_solto():
    for line in ajuda.render(REPO).splitlines():
        if line.startswith("| `"):
            assert line.replace("\\|", "").count("|") in (3, 4), line
