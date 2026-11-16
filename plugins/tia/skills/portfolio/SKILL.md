---
name: portfolio
description: Situação do portfólio do grupo (perfil GPM) — por time, itens em andamento por etapa, travados (sinalizados, bloqueados ou parados) e entregas da janela, com causa provável e próximo passo. Lê o Jira só para consulta, agregado por time e sem pessoas; grava tia/relatorios/<data>-portfolio.md. Use quando a humana digitar /tia:portfolio ou pedir "como estão os times", "situação do portfólio", "o que está travado nos times".
---

# /tia:portfolio $ARGUMENTS

`$ARGUMENTS` (opcional): janela em dias (padrão 7) e/ou o nome de um time. `TIA` =
`bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`. Comandos a partir da raiz do projeto. Tudo é leitura, exceto os
arquivos em `tia/relatorios/`.

**Perfil: só GPM.** Se `.tia/config.yaml` não tiver `perfil: gpm`, responda só "/tia:portfolio é do perfil GPM;
esta pasta é do perfil PM." e pare.

## 1. Times

`TIA portfolio validar`. Erro → diga a correção em uma linha e pare. Nenhum time → ofereça propor os times a
partir do Jira (`/tia:configurar` mostra a proposta; a humana edita `portfolio.times`) e pare.

## 2. Consulta ao Jira (só leitura, agregada por time)

Para cada time de `portfolio.times`, uma chamada `searchJiraIssuesUsingJql` (`cloudId` da config) com:
- **JQL:** `project = <CHAVE> AND (statusCategory = "In Progress" OR (statusCategory = Done AND resolved >= -<janela>d)) ORDER BY updated DESC`.
  Time com `board` (quadro com sprint): acrescente `OR (project = <CHAVE> AND statusCategory = "To Do" AND sprint in openSprints())`
  para a coluna "A fazer"; sem `board`, "A fazer" não é consultado (diga isso no relatório).
- **fields, só estes:** `summary`, `status`, `issuetype`, `project`, `updated`, `resolutiondate`,
  `statuscategorychangedate`, `issuelinks` e o campo *Sinalizado* (Flagged) do site, se houver (em geral
  `customfield_10021`). **Nunca peça** `assignee`, `reporter`, `creator`, `comment`, `worklog`, `watches` nem
  qualquer campo de pessoa.
- `maxResults` 100; com mais páginas, siga até 300 itens por time e diga no relatório que cortou.

Grave o JSON bruto de cada resposta num arquivo **temporário fora do projeto** (pasta temporária do sistema,
ex.: `<TEMP>/tia-portfolio-<CHAVE>.json`). Nunca em `tia/`: resultado bruto não é artefato.

## 3. Agregação (o script descarta qualquer campo de pessoa)

`TIA portfolio agregar --entrada <arquivo do time 1> --entrada <arquivo do time 2> … --janela <N> --gravar --json`

Saída por time: em andamento por etapa, travados com motivo (sinalizado, bloqueado por item aberto, etapa de
bloqueio, sem movimento há N dias), concluídos na janela e projetos fora do portfólio. O resumo agregado vai
para `tia/relatorios/<data>-portfolio.json`.

## 4. Leitura e relatório

Para cada time: **situação** (no ritmo · atenção · travado), **causa provável** (marcada como hipótese:
dependência de outro time quando o bloqueio é de outro projeto, fila acumulada numa etapa, item parado sem
dono claro no processo) e **próximo passo** (uma ação concreta para a conversa com a PM do time). Não avalie
pessoas nem desempenho individual: o portfólio é por time.

Grave `tia/relatorios/<data>-portfolio.md`: a tabela do script (`TIA portfolio agregar … ` sem `--json`), um
bloco por time com causa e próximo passo, e a linha `Fonte: Jira (<projetos>), consulta em <data>, janela de N
dias`. Resumo de item que cite alguém pelo nome → use só a chave do item.

## 5. Resposta

Até 8 linhas: times travados primeiro (time, o que trava, próximo passo), depois atenção, depois no ritmo em
uma linha só. Termine com o caminho do relatório.

## Regras

- Jira só leitura: não comenta, não transiciona, não cria. Confluence não entra aqui.
- Nenhum dado de pessoa em consulta, arquivo ou resposta. Colegas aparecem pelo papel ("a PM do Cadastro").
- Sem número inventado: time sem resposta do Jira aparece como "não consultado" com o motivo.
