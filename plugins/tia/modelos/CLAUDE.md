<!-- modelo_versao: 1 · criado pelo "Tia, configurar". Parte DO TIME: a humana edita. Os princípios da Tia vêm
do plugin (injetados no início da sessão) e não se repetem aqui. Se o repositório já tem um CLAUDE.md, este
arquivo fica em tia/CLAUDE.md e o CLAUDE.md da raiz ganha a linha `@tia/CLAUDE.md`. -->
# {time} · como a Tia trabalha neste projeto

Este projeto usa a **Tia** (plugin `tia`). Comece com "Tia, bom dia" ou `/tia:abrir`; "Tia, ajuda" lista
os comandos. A Tia escreve só em `tia/`; a fila (`tia/demandas.yaml`) e este arquivo são editados por gente.

## O time

- **Time/squad:** {time} · **Projeto Jira:** {jira_projeto} · **Site:** {site}
- **Missão em uma linha:** [a definir pelo time]
- **Onde está o backlog e o padrão de épico:** `tia/kb/padroes/epico.md` (seções conferidas na entrega).

## Confluence: política por espaço

| Espaço | Consultar | Alterar | Apontar |
|---|---|---|---|
{tabela_espacos}
| Outros espaços | quando necessário | **nunca** | dúvida, se relevante |

Alterar = só no espaço marcado `manter`, com **C1** por página, e cada escrita ainda pede confirmação.
Apontar = propor um bloco em `tia/kb/apontamentos.md` (`documentar` no espaço `manter`; `duvida` nos demais).

## Skills de apoio do time (opcionais)

Use a skill disponível que couber, sem esperar ser mandada, e diga em uma linha qual usou e por quê.
- Texto do épico: [skill do time, ex.: `/epico-internal-tools`; sem ela, siga `tia/kb/padroes/epico.md`]
- Produto e priorização: [ex.: `/pm-especialista`, `/pm-advisor`]
- Dados: [ex.: `databricks:*`, conector do Looker]

## Combinados do time

- [a definir: cadência de relatório, quem aprova o quê, convenções de nome]
