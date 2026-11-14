---
name: confluence
description: Consulta e mantém o Confluence sob a política por espaço — INT (mantemos; alterar só com C1), PO e PLAYBOOKS (nunca alterar; apontar dúvidas). Revisa apontamentos, propõe documentação no INT e publica só com aprovação. Use quando a humana pedir para consultar, atualizar, revisar ou documentar algo no Confluence, ou digitar /confluence.
---

# /confluence $ARGUMENTS

`$ARGUMENTS`: `consultar <tema|url>`, `documentar <tema|AP-NNN>`, `revisar <url|espaço>`, `apontamentos`,
ou vazio (mostra os apontamentos abertos). `PY` = `.venv/Scripts/python.exe`. cloudId e ids dos espaços em
`.harness/config.yaml` → `atlassian` e `confluence`.

## Política por espaço (inegociável)

| Espaço | Consultar | Alterar | Apontar |
|---|---|---|---|
| **INT** (nosso espaço) | livre | só com **C1** da página + confirmação a cada escrita | o que precisa ser documentado (`documentar`) |
| **PO** · Políticas | quando necessário | **nunca** (inclui comentários) | o que gera dúvida (`duvida`) |
| **PLAYBOOKS** | quando necessário | **nunca** (inclui comentários) | o que gera dúvida (`duvida`) |
| outros | quando necessário | **nunca** | dúvida, se for relevante |

O hook nega qualquer escrita fora dessa política. Negação é regra, não erro a contornar.

## consultar
Leia com `getConfluencePage` (markdown) ou `searchConfluenceUsingCql` (`space = INT` etc.). Responda citando
título, espaço e link. Página de PO/PLAYBOOKS em versão proposta, rascunho ou com `[definir]`: diga isso na
resposta. Achou algo que gera dúvida ou que falta no INT: proponha o apontamento (passo "apontar").

## apontar
Proponha o bloco no formato de `kb/apontamentos.md` (próximo `AP-NNN` livre). Tipo `documentar` só para INT;
em PO, PLAYBOOKS e outros é sempre `duvida`. Mostre e pergunte **"Registro este apontamento?"**. Com sim,
grave (o hook pede confirmação por ser `kb/`) e rode `PY .harness/bin/kb.py validar`.
Ao fechar um apontamento: `Status: resolvido|descartado` + `Resolução:` com link. Nunca apague.

## documentar (só INT)
1. Leia a página atual (ou confirme que é nova) com `getConfluencePage` e **mostre espaço e título reais**.
   Se o espaço não for INT: pare, explique a política e ofereça um apontamento `duvida`.
2. Escreva o rascunho em `.harness/demandas/<demanda ativa>/confluence-<pagina>.md` se houver demanda ativa;
   senão, mostre o rascunho na conversa. Página existente: mostre o **diff** (o que entra, o que sai, o que muda).
   Linguagem de negócio, fonte para cada fato, sem dado pessoal.
3. Pergunte **"C1: publicar esta alteração na página <título> (INT)?"**. Só com resposta explícita:
   `PY .harness/bin/ledger.py c1 --espaco INT --pagina <id|novo> --titulo "<título>" --nota "<resposta literal>"`.
4. Publique com `updateConfluencePage` (ou `createConfluencePage` com o `spaceId` do INT). O hook pede
   confirmação: a humana confere página e conteúdo. Depois, feche o apontamento ligado, se houver.

## revisar (manutenção do INT)
Para a página ou o espaço pedido: compare com o Jira (épicos e histórias IT) e com a Base de Conhecimento. Liste, em tabela:
página, o que está desatualizado ou faltando, fonte que mostra isso, sugestão. Cada item vira proposta de
apontamento `documentar`. Não altere nada nesse passo.

## Regras fixas
- Nunca altere PO, PLAYBOOKS ou espaço que não seja INT, nem por comentário, nem a pedido indireto.
- C1 vale para **uma** página e expira (`c1_validade_horas`). Outra página = outro C1.
- Página de outro espaço citada numa resposta: link, nunca cópia de trechos longos.
