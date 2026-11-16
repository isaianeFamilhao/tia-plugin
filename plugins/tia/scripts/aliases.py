"""Aliases "Tia, <frase>" → skill do plugin (usado pelo hook UserPromptSubmit).

    tia.sh aliases "Tia, roda o semanal"      # mostra a skill e o argumento reconhecidos
    tia.sh aliases --listar

Só dispara quando "Tia," abre a mensagem ("garantia, …", "notícia, …" e o antigo "Ada, …" não disparam). Tabela do plugin em
modelos/aliases.yaml + atalhos do pessoal.md (seção "Atalhos": `- frase → skill [argumento]`), workspace antes
do global. Vence a frase mais longa; empate: pessoal antes do plugin. Pedido "Tia, …" sem alias conhecido vira
("abrir", ENCAMINHAR): a Tia segue a tabela de pedidos em linguagem natural, sem rodar a abertura.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELOS, load_yaml  # noqa: E402

SKILLS = ("abrir", "demanda", "portfolio", "base", "confluence", "metricas", "okr", "report", "configurar", "ajuda")
ENCAMINHAR = "encaminhar"
CHAMADO_RE = re.compile(r"^\s*tia\s*,\s*(.*)$", re.IGNORECASE | re.DOTALL)
ATALHO_RE = re.compile(r"^\s*[-*]\s*(.+?)\s*(?:→|->|=>)\s*([a-z]+)(?:\s+(\S.*?))?\s*$")
DEMANDA_RE = re.compile(r"\bD-\d{3}\b", re.IGNORECASE)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", s)).strip()


def tabela_plugin() -> list[tuple[str, str, str | None, int]]:
    """(frase normalizada, skill, argumento, prioridade). Prioridade 1 = plugin."""
    data = load_yaml(MODELOS / "aliases.yaml") or {}
    out = []
    for skill, frases in (data.get("aliases") or {}).items():
        for f in frases or []:
            frase, _, arg = str(f).partition("=>")
            out.append((norm(frase), skill, arg.strip() or None, 1))
    return out


def tabela_pessoal(root: Path | None = None) -> list[tuple[str, str, str | None, int]]:
    """Atalhos dos pessoal.md (prioridade 3 = workspace, 2 = global)."""
    import memoria

    out = []
    for (rot, p), prio in zip(memoria.pessoal_paths(root), (3, 2)):
        txt = memoria.pessoal_texto(p)
        dentro = False
        for line in txt.splitlines():
            if line.startswith("#"):
                dentro = "atalho" in norm(line)
                continue
            m = ATALHO_RE.match(line) if dentro else None
            if m and m.group(2) in SKILLS and not m.group(1).startswith("["):
                out.append((norm(m.group(1)), m.group(2), (m.group(3) or "").strip() or None, prio))
    return out


def resolver(texto: str, root: Path | None = None) -> tuple[str, str | None] | None:
    m = CHAMADO_RE.match(texto or "")
    if not m:
        return None
    resto_raw = m.group(1)
    resto = norm(resto_raw)
    try:
        pessoais = tabela_pessoal(root)
    except Exception:  # noqa: BLE001 — pessoal.md quebrado não derruba o alias
        pessoais = []
    melhor = None
    for frase, skill, arg, prio in pessoais + tabela_plugin():
        if frase and (resto == frase or resto.startswith(frase + " ")):
            chave = (len(frase), prio)
            if melhor is None or chave > melhor[0]:
                melhor = (chave, skill, arg)
    if melhor is None:
        return ("abrir", ENCAMINHAR) if resto else ("abrir", None)
    _, skill, arg = melhor
    if skill == "demanda" and not arg:
        d = DEMANDA_RE.search(resto_raw)
        arg = d.group(0).upper() if d else None
    return skill, arg


def intencao(texto: str) -> str | None:
    """Habilidade de um pedido "Tia, …" sem atalho (seção `intencoes` de modelos/aliases.yaml), ou None."""
    m = CHAMADO_RE.match(texto or "")
    if not m:
        return None
    resto = norm(m.group(1))
    data = load_yaml(MODELOS / "aliases.yaml") or {}
    for skill, frases in (data.get("intencoes") or {}).items():
        for f in frases or []:
            frase = norm(str(f))
            if frase and (resto == frase or resto.startswith(frase + " ")):
                return skill
    return None


def fora_do_perfil(texto: str, resolvido: tuple[str, str | None], perfil: str) -> str | None:
    """Habilidade pedida que não existe no perfil desta pasta (atalho ou intenção), ou None."""
    from _common import habilidade_disponivel

    skill, arg = resolvido
    if not habilidade_disponivel(skill, perfil):
        return skill
    if arg == ENCAMINHAR:
        alvo = intencao(texto)
        if alvo and not habilidade_disponivel(alvo, perfil):
            return alvo
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("texto", nargs="?")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args(argv)
    if a.listar or not a.texto:
        for frase, skill, arg, prio in sorted(tabela_pessoal() + tabela_plugin(), key=lambda x: (x[1], x[0])):
            print(f"- Tia, {frase} → {skill}{' ' + arg if arg else ''}{' (pessoal)' if prio > 1 else ''}")
        return 0
    r = resolver(a.texto)
    print("sem chamado da Tia" if r is None else f"tia:{r[0]}{' ' + r[1] if r[1] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
