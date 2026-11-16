<!-- modelo_versao: 1 · perfil GPM · criado pelo "Tia, configurar". Parte DO GRUPO: a humana edita. Os princípios
da Tia vêm do plugin (injetados no início da sessão) e não se repetem aqui. Se o repositório já tem um CLAUDE.md,
este arquivo fica em tia/CLAUDE.md e o CLAUDE.md da raiz ganha a linha `@tia/CLAUDE.md`. -->
# {time} · como a Tia trabalha nesta pasta (perfil GPM)

Esta pasta usa a **Tia** (plugin `tia`) no perfil **GPM** (Group Product Manager). Comece com "Tia, bom dia" ou
`/tia:abrir`; "Tia, ajuda" lista os comandos do perfil. A Tia escreve só em `tia/`; este arquivo é editado por gente.

## O grupo

- **Grupo:** {time} · **Projetos Jira dos times:** {jira_projetos} · **Site:** {site}
- **Missão do grupo em uma linha:** [a definir]
- **Times do grupo:** [a definir: time → projeto do Jira]

## O que muda no perfil GPM

- Épico, histórias e fila de demandas ficam na pasta de cada PM: aqui não há `tia/demandas.yaml`.
- A Tia desta pasta não acessa a Tia de nenhuma PM. Ela vê o portfólio pelas fontes que alcança: Jira e
  Confluence (só leitura, salvo o espaço `manter`), fontes de dados conectadas e esta pasta.

## Confluence: política por espaço

| Espaço | Consultar | Alterar | Apontar |
|---|---|---|---|
{tabela_espacos}
| Outros espaços | quando necessário | **nunca** | dúvida, se relevante |

Alterar = só no espaço marcado `manter` (se houver), com **C1** por página, e cada escrita ainda pede confirmação.
Apontar = propor um bloco em `tia/kb/apontamentos.md` (`documentar` no espaço `manter`; `duvida` nos demais).

## Skills de apoio (opcionais)

Use a skill disponível que couber, sem esperar ser mandada, e diga em uma linha qual usou e por quê.
- Produto e priorização: [ex.: `/pm-especialista`, `/pm-advisor`]
- Dados: [ex.: `databricks:*`, conector do Looker]

## Combinados do grupo

- [a definir: cadência de relatório, rituais com as PMs, o que vai para a diretoria]
