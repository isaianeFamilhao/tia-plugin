---
modelo_versao: 1
secoes_epico:
  - "Em uma frase"
  - "Por que isso importa"
  - "O que muda no dia a dia"
  - "Como vamos saber que funcionou"
  - "Escopo"
  - "Fora do escopo"
  - "O que precisamos combinar"
---
# Padrão de épico do time

O time pode reescrever este padrão. O que o `coverage.py` confere são as seções do frontmatter
(`secoes_epico`), nesta ordem. Se o time tiver uma skill própria de épico (ex.: `/epico-internal-tools`),
indique aqui; sem ela, a Tia redige seguindo esta estrutura.

## Entrada da skill (extraída da pesquisa, nunca inventada)

1. **Problema:** o que acontece hoje e quem sofre (com fonte).
2. **Objetivo:** a mudança de comportamento da área.
3. **Público:** a área ou o time que muda.
4. **Escopo:** o que a squad faz e o que fica de fora (com o épico que cobre o que fica de fora, se houver).

Falta algum dos quatro: liste a lacuna e use `[a definir]` / `[a levantar]` no texto. Nunca invente números.

## Estrutura conferida pela Tia (frontmatter `secoes_epico`)

- H1: `# Épico X.Y: <quem> <verbo no presente> <o quê> sem depender de <quem ou o quê>` (X.Y = número
  do tema no backlog; épico novo sem número: `X.Y`).
- `## Em uma frase`, `## Por que isso importa`, `## O que muda no dia a dia` (tabela Situação | Hoje |
  Depois), `## Como vamos saber que funcionou`, `## Escopo`, `## Fora do escopo`,
  `## O que precisamos combinar` — nesta ordem, sem seções a mais.
- Sem histórias de usuário e sem critérios de aceite no épico: eles ficam em `historias.md`.

## Ligação com as regras

O épico é de negócio e não cita IDs de regra no texto. A rastreabilidade fica nas histórias e na matriz de
cobertura. Restrição de negócio relevante (limite, vedação, aprovação) aparece em linguagem de negócio em
"Escopo" ou "O que precisamos combinar".

## Numeração e temas

[a definir pelo time: tabela de temas e épicos do backlog, se houver]

Detalhe por épico em `tia/kb/<area>/epicos.md`.
