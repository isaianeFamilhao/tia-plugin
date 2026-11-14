"""Fixtures: um projeto mínimo em tmp_path, com kb, fila e uma entrega completa da D-001.

Os testes nunca dependem da kb real nem das demandas reais do repositório (lição R-T1 do harness-lean).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "scripts"
sys.path.insert(0, str(BIN))

RULES = """# Reprocessamento
Escopo: teste.

### RN-ITR-001 · Reprocessar só com pagamento confirmado
- **Regra:** O reprocessamento só pode ser executado quando o pagamento do pacote está confirmado.
- **Status:** confirmada
- **Fontes:** SRC-IT-001
- **Atualizado:** 2026-11-13

### RN-ITR-002 · Limite mensal por área
- **Regra:** Cada área tem um limite mensal de reprocessamentos; acima dele a ação é bloqueada.
- **Status:** a confirmar
- **Fontes:** SRC-IT-001
- **Atualizado:** 2026-11-13

### RN-ITR-003 · Vedação de conta própria
- **Regra:** É vedado reprocessar conta própria, de familiar ou de colaborador.
- **Status:** confirmada
- **Fontes:** SRC-IT-001
- **Atualizado:** 2026-11-13

## Lacunas

- Valor do limite mensal por área não definido.
"""

SOURCES = """- id: SRC-IT-001
  titulo: Política de reprocessamento
  tipo: confluence
  ref: https://exemplo.atlassian.net/wiki/x/1
  lido_em: 2026-11-13
  confiabilidade: media
"""

DEMANDAS = """- id: D-001
  titulo: Reprocessamento pelo atendimento
  pedido: O atendimento N1 depende de chamado para regularizar pacote com pagamento confirmado e quer resolver no primeiro contato.
  solicitante: CX
  tipo: refinar_epico
  epico_jira: IT-39
  tamanho: P
  termos: [reprocessamento, limite, pagamento]
- id: D-002
  titulo: Outra demanda qualquer
  pedido: Jurídico precisa auditar sorteios com acesso controlado e registrado por perfil autorizado.
  solicitante: Jurídico
  tipo: novo_epico
  tamanho: M
"""

EPICO = """# Épico 3.2: Atendimento resolve sozinho pedidos simples sem depender de engenharia

## Em uma frase

O atendimento passa a regularizar pacotes no primeiro contato.

## Por que isso importa

Hoje cada caso vira chamado.

## O que muda no dia a dia

| Situação | Hoje | Depois |
| --- | --- | --- |
| Pacote não entregue | Chamado | Atendente resolve |

## Como vamos saber que funcionou

O sucesso é resolver no primeiro contato. Vamos acompanhar um número:

- **Autonomia:** % resolvido no N1 [a levantar].

## Escopo

- **Testar:** com o CX.

## Fora do escopo

- Estornos: épico 4.2.

## O que precisamos combinar

- **Qualidade:** [a definir].
"""

HISTORIAS = """# Histórias · D-001

## H-01 · Solicitar reprocessamento com pagamento confirmado

**Contexto:** hoje vira chamado.

**História:** Como atendente N1 do CX, quero solicitar o reprocessamento, para resolver no primeiro contato.

**Cobre:** RN-ITR-001, RN-ITR-002, RC-01

### Critérios de aceite

- **CA-01** [RN-ITR-001]: Dado pagamento confirmado, quando o atendente solicita, então o reprocessamento é executado.
- **CA-02** [RN-ITR-001]: Dado pagamento não confirmado, quando o atendente solicita, então a ação é bloqueada e a tela mostra "pagamento ainda não confirmado".
- **CA-03** [RN-ITR-002]: Dado a área no limite mensal, quando o atendente solicita, então a ação é bloqueada.
- **CA-04** [RC-01]: Dado um reprocessamento concluído, quando o caso fecha, então o ticket registra o código da causa.

**Pendências:** valor do limite.
"""

REGRAS_DEM = """### RC-01 · Código da causa no fechamento
- **Regra:** Todo reprocessamento concluído fecha o ticket com o código da causa preenchido.
- **Status:** a confirmar
- **Fontes:** SRC-DEM-001
- **Atualizado:** 2026-11-13
"""

FONTES_DEM = """- id: SRC-DEM-001
  titulo: IT-55
  tipo: jira
  ref: IT-55
  lido_em: 2026-11-13
  confiabilidade: alta
"""

PESQUISA = """# Pesquisa · D-001
## Fontes consultadas
- SRC-IT-001, SRC-DEM-001
## Regras relevantes
- RN-ITR-001, RN-ITR-002, RN-ITR-003, RC-01
"""


CONFIG_TIME = """modelo_versao: 1
atlassian:
  site: https://exemplo.atlassian.net
  cloud_id: 00000000-0000-0000-0000-000000000000
  jira_projeto: IT
  espacos_confluence: [INT, PO, PLAYBOOKS]
confluence:
  espacos:
    INT: {id: "282787868", nome: Internal Tools, politica: manter}
    PO: {id: "370737187", nome: Políticas, politica: somente_leitura}
    PLAYBOOKS: {id: "322895878", nome: Playbooks, politica: somente_leitura}
modelos:
  permitidos: [opus, sonnet, haiku]
  esforco: medium
"""


def result(**over) -> dict:
    r = {"demanda_id": "D-001", "status": "delivered", "historias": ["H-01"],
         "regras_relevantes": ["RN-ITR-001", "RN-ITR-002", "RN-ITR-003", "RC-01"],
         "fora_do_escopo": [{"regra": "RN-ITR-003", "motivo": "identificação de conta própria ainda não existe"}],
         "lacunas": ["Valor do limite mensal: a levantar"], "fontes": ["SRC-IT-001", "SRC-DEM-001"],
         "summary": "Épico 3.2 refinado com uma história.", "open_questions": [], "blocked_reason": None}
    r.update(over)
    return r


@pytest.fixture
def proj(tmp_path, monkeypatch) -> Path:
    m = tmp_path / ".ada"
    m.mkdir()
    (m / "config.yaml").write_text(CONFIG_TIME, encoding="utf-8")
    a = tmp_path / "ada"
    a.mkdir()
    (a / "demandas.yaml").write_text(DEMANDAS, encoding="utf-8")
    kb = a / "kb"
    (kb / "internal-tools" / "regras").mkdir(parents=True)
    shutil.copytree(REPO / "modelos" / "padroes", kb / "padroes")
    (kb / "fontes").mkdir()
    (kb / "internal-tools" / "regras" / "reprocessamento-ajustes.md").write_text(RULES, encoding="utf-8")
    (kb / "fontes" / "internal-tools.yaml").write_text(SOURCES, encoding="utf-8")
    (kb / "internal-tools" / "epicos.md").write_text("# Épicos\n\n## IT-39 · 3.2 Atendimento resolve sozinho\n\nDetalhe.\n",
                                                    encoding="utf-8")
    monkeypatch.setenv("HARNESS_ROOT", str(tmp_path))
    monkeypatch.setenv("ADA_HOME", str(tmp_path / "home-ada"))      # nunca toca o ~/.ada real
    monkeypatch.delenv("HARNESS_DEV", raising=False)
    monkeypatch.delenv("ADA_DEV", raising=False)          # manutenção ligada na máquina não vale nos testes
    return tmp_path


@pytest.fixture
def entrega(proj) -> Path:
    d = proj / "ada" / "demandas" / "D-001"
    d.mkdir(parents=True)
    (d / "epico.md").write_text(EPICO, encoding="utf-8")
    (d / "historias.md").write_text(HISTORIAS, encoding="utf-8")
    (d / "regras.md").write_text(REGRAS_DEM, encoding="utf-8")
    (d / "fontes.yaml").write_text(FONTES_DEM, encoding="utf-8")
    (d / "pesquisa.md").write_text(PESQUISA, encoding="utf-8")
    (d / "result.json").write_text(json.dumps(result(), ensure_ascii=False), encoding="utf-8")
    return d
