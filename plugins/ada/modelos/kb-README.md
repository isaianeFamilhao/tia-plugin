---
modelo_versao: 1
---
# Base de Conhecimento (ada/kb/)

Contrato da Base de Conhecimento da Ada. Este arquivo vem do plugin e não é editado pelo time: o formato
é o que os scripts conferem. Tudo aqui é versionado em git; a fonte primária continua sendo o Confluence e
o Jira. A Base é um **índice curado com citação**, não uma cópia: cada fato aponta para a fonte de onde veio.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `fontes/*.yaml` | Registro de fontes (`SRC-…`): título, tipo, URL, data de leitura. Toda regra cita pelo menos uma. |
| `empresa/` | Produto, glossário, políticas e regras de negócio da empresa (`empresa/regras/<domínio>.md`). |
| `<area>/` | Uma pasta por time ou área: visão, backlog, `epicos.md`, `decisoes.md`, `regras/<tema>.md`. |
| `apontamentos.md` | Pauta do Confluence: `documentar` (espaço marcado `manter`) e `duvida` (os demais). |
| `padroes/` | Padrão de épico (frontmatter `secoes_epico`), de história e de critério de aceite. Do time. |
| `prefixos.md` | Tabela de prefixos de domínio do time (`RN-XXX` → domínio → arquivo). Do time. |
| `metricas.yaml`, `okrs.yaml` | Opcionais, aprendidos com o uso. |

## Formato obrigatório de regra (lido por `kb.py`)

```markdown
### RN-CAD-001 · Título curto da regra
- **Regra:** enunciado objetivo e testável, uma regra por bloco.
- **Status:** confirmada | a confirmar | conflito
- **Fontes:** SRC-EMP-003, SRC-EMP-010
- **Atualizado:** 2026-11-13
- **Notas:** (opcional) contexto, exceções, conflito entre fontes.
```

- O ID nunca muda nem é reaproveitado. Regra revogada fica com `Status: revogada` e nota.
- `a confirmar` = só uma fonte fraca (conversa, rascunho, página desatualizada) ou inferência. `conflito` = fontes divergem; a nota diz quais.
- Sem fonte, não entra. Lacuna vira linha em `## Lacunas` no fim do arquivo do domínio, não regra.

### Prefixos de domínio

Três letras maiúsculas depois de `RN-` (ex.: `RN-CAD`, `RN-ITR`). A tabela de prefixos é do time e mora em
`ada/kb/prefixos.md`. Domínio novo: acrescente uma linha lá antes de criar o arquivo.

## Formato de fonte (`fontes/*.yaml`)

```yaml
- id: SRC-EMP-001            # SRC-<2 a 4 letras>-NNN: EMP (empresa), sigla do time (ex.: IT), DEM (só de uma demanda)
  titulo: Catálogo de regras de negócio
  apelido: Catálogo de regras   # nome curto para a conversa (até 60 caracteres); sem ele, usa o título
  tipo: confluence            # confluence | jira | local | conversa
  ref: https://empresa.atlassian.net/wiki/spaces/XYZ/pages/123   # URL, chave Jira ou caminho
  lido_em: 2026-11-13
  confiabilidade: alta        # alta (oficial/vigente) | media (rascunho, QA, derivado) | baixa (conversa, nota, desatualizado)
```

## Como o agente consulta

1. `ada.sh kb buscar "<termos>"` lista regras e trechos com ID, status e fontes.
2. `ada.sh kb regra RN-XXX-NNN` mostra uma regra completa.
3. Só depois disso pesquise Confluence e Jira: a Base de Conhecimento diz **onde** procurar (fontes) e o que já se sabe.

## Como o agente atualiza

- Só com a skill `/ada:base` ou no passo de fechamento de uma demanda (`/ada:demanda`), e só com
  **aprovação explícita do humano** (gate K1) para cada lote de regras novas ou alteradas.
- `ada.sh kb validar` precisa passar (IDs únicos, formato, fontes existentes) antes de
  encerrar. O hook `Stop` confere.
- Mudança de regra existente: edite o bloco, atualize `Atualizado:` e explique na nota. Nunca apague.
