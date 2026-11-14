---
name: confluence
description: Consulta e mantém o Confluence sob a política por espaço do time — o espaço marcado `manter` (alterar só com C1) e os demais somente leitura (nunca alterar; apontar dúvidas). Revisa apontamentos, propõe documentação no espaço do time e publica só com aprovação. Use quando a humana pedir para consultar, atualizar, revisar ou documentar algo no Confluence, ou digitar /ada:confluence.
---

# /ada:confluence $ARGUMENTS

`$ARGUMENTS`: `consultar <tema|url>`, `documentar <tema|AP-NNN>`, `revisar <url|espaço>`, `apontamentos`,
ou vazio (mostra os apontamentos abertos). `ADA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/ada.sh"`. cloudId e ids dos espaços em
`.ada/config.yaml` → `atlassian` e `confluence`.

## Política por espaço (inegociável)

Os espaços e a política de cada um estão em `.ada/config.yaml` → `confluence.espacos` (e no `CLAUDE.md` do
time). Abaixo, "espaço do time" = o marcado `politica: manter` (ex.: INT).

| Espaço | Consultar | Alterar | Apontar |
|---|---|---|---|
| **espaço do time** (`manter`) | livre | só com **C1** da página + confirmação a cada escrita | o que precisa ser documentado (`documentar`) |
| `somente_leitura` (ex.: PO, PLAYBOOKS) | quando necessário | **nunca** (inclui comentários) | o que gera dúvida (`duvida`) |
| outros | quando necessário | **nunca** | dúvida, se for relevante |

O hook nega qualquer escrita fora dessa política. Negação é regra, não erro a contornar.

## consultar
Leia com `getConfluencePage` (markdown) ou `searchConfluenceUsingCql` (`space = <chave>` etc.). Responda citando
título, espaço e link. Página de espaço `somente_leitura` em versão proposta, rascunho ou com `[definir]`: diga isso na
resposta. Achou algo que gera dúvida ou que falta no espaço do time: proponha o apontamento (passo "apontar").

## apontar
Proponha o bloco no formato de `ada/kb/apontamentos.md` (próximo `AP-NNN` livre). Tipo `documentar` só para o espaço do time;
nos demais é sempre `duvida`. Mostre e pergunte **"Registro este apontamento?"**. Com sim,
grave (o hook pede confirmação por ser `ada/kb/`) e rode `ADA kb validar`.
Ao fechar um apontamento: `Status: resolvido|descartado` + `Resolução:` com link. Nunca apague.

## documentar (só no espaço do time)
1. Leia a página atual (ou confirme que é nova) com `getConfluencePage` e **mostre espaço e título reais**.
   Se o espaço não for o `manter`: pare, explique a política e ofereça um apontamento `duvida`.
2. Escreva o rascunho em `ada/demandas/<demanda ativa>/confluence-<pagina>.md` se houver demanda ativa;
   senão, mostre o rascunho na conversa. Página existente: mostre o **diff** (o que entra, o que sai, o que muda).
   Linguagem de negócio, fonte para cada fato, sem dado pessoal.
3. Pergunte **"C1: publicar esta alteração na página <título> (<espaço>)?"**. Só com resposta explícita:
   `ADA ledger c1 --espaco <chave do espaço> --pagina <id|novo> --titulo "<título>" --nota "<resposta literal>"`.
4. Publique com `updateConfluencePage` (ou `createConfluencePage` com o `spaceId` do espaço do time). O hook pede
   confirmação: a humana confere página e conteúdo. Depois, feche o apontamento ligado, se houver.

## revisar (manutenção do espaço do time)
Para a página ou o espaço pedido: compare com o Jira (épicos e histórias do projeto do time) e com a Base de Conhecimento. Liste, em tabela:
página, o que está desatualizado ou faltando, fonte que mostra isso, sugestão. Cada item vira proposta de
apontamento `documentar`. Não altere nada nesse passo.

## Regras fixas
- Nunca altere espaço que não seja o marcado `manter`, nem por comentário, nem a pedido indireto.
- C1 vale para **uma** página e expira (`c1_validade_horas`). Outra página = outro C1.
- Página de outro espaço citada numa resposta: link, nunca cópia de trechos longos.
