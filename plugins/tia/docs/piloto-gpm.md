# Piloto do perfil GPM (0.3.0)

Roteiro para a PM conduzir o piloto do perfil GPM numa pasta real, com uma semana de uso (abertura, portfólio,
semanal). Quem roda é a PM; o agente só executa o que ela pedir na sessão. Cada passo tem o que conferir. Anote o
que não bater em `tia/propostas/piloto-gpm-notas.md` da pasta GPM (sem nomes de pessoas) e traga para a próxima
sessão de manutenção.

Regras do piloto: gates só com resposta explícita; Jira, Confluence e dados só leitura e agregados; nenhum nome de
pessoa em arquivo; nada é enviado nem publicado.

## 0. Atualizar o plugin instalado

No seu terminal, fora do Claude Code:

```bash
claude plugin marketplace update tia-marketplace
```

```bash
claude plugin update tia@tia-marketplace
```

Feche e abra o Claude Code de novo.

Conferir:

- [ ] `claude plugin list` mostra `tia@tia-marketplace` na versão 0.3.0.
- [ ] Existe `~/.claude/plugins/cache/tia-marketplace/tia/0.3.0/`.

## 1. Pasta GPM do zero

1. Crie uma pasta nova (ex.: `tia-gpm-<grupo>`), rode `git init` e instale o plugin nela com
   `--scope project` (README do plugin, "Adicionar o marketplace e instalar").
2. Abra o Claude Code na pasta e digite `/tia:configurar`.
3. Responda **GPM** quando a Tia perguntar o perfil.
4. Confira a proposta: times do grupo com o projeto do Jira de cada um (e o board, se houver), espaços do
   Confluence, zero ou um `manter`. Ajuste o que vier errado e só então diga sim.

Conferir:

- [ ] `.tia/config.yaml` tem `perfil: gpm` e `portfolio.times` com os dois (ou mais) times reais.
- [ ] Não foram criados `tia/demandas.yaml`, `tia/demandas.exemplo.yaml` nem `tia/demandas/`.
- [ ] O `CLAUDE.md` é o do GPM (grupo e times → projeto do Jira), não o da PM.
- [ ] O diagnóstico (`doctor`) sai sem `FALHA`: perfil GPM, portfólio sem erro, sem cobrança de fila. Com
      `TIA_DEV=1` ainda ligado, o `AVISO` do modo manutenção é esperado.
- [ ] `/tia:ajuda` lista `/tia:portfolio` e `report diario|semanal|diretoria`, e não lista `/tia:demanda` nem
      G1, G2 e G3.
- [ ] "Tia, escreve um épico" responde em uma linha que isso é do perfil PM.

## 2. Portfólio com dois times reais

Digite `/tia:portfolio` (janela padrão de 7 dias).

Conferir:

- [ ] O relatório em `tia/relatorios/<data>-portfolio.md` e o retrato em `.json` ao lado não têm nome de pessoa
      (procure por responsável, relator e nomes conhecidos). Resumo de item que cite alguém aparece só pela chave.
- [ ] Os números batem com o quadro do Jira de cada time, contando à mão: itens em andamento por etapa,
      travados (sinalizados, bloqueados ou parados há 5 dias ou mais) e concluídos nos últimos 7 dias. Anote
      qualquer diferença com a etapa e a chave do item.
- [ ] Cada time tem situação (no ritmo, atenção, travado), causa provável marcada como hipótese e um próximo
      passo concreto.
- [ ] A linha `Fonte:` diz Jira, os projetos, a data e a janela.
- [ ] Nenhuma escrita no Jira foi tentada.

## 3. Abertura do dia

Digite `/tia:abrir` ou "Tia, bom dia", de preferência em dias diferentes durante a semana.

Conferir:

- [ ] Ordem do briefing: alertas, times com travas (uma linha por time), OKRs do grupo em risco; depois o que
      espera decisão (K1, M1, Memória).
- [ ] Não aparece fila nem aprovação de demanda.
- [ ] Se o retrato do portfólio não for do dia, a Tia refaz a coleta antes de resumir.
- [ ] Sem OKR do grupo registrado, aparece uma linha dizendo isso e o convite para `/tia:okr`.

## 4. OKRs do grupo

Digite `/tia:okr` e peça os OKRs do grupo para o próximo ciclo.

Conferir:

- [ ] O rascunho vai para `tia/propostas/okrs-<ciclo>-grupo.yaml` com `nivel: grupo` e ids `OBJ-01`, `OBJ-02`….
- [ ] `okr validar` roda sem `REPROVADO` antes de a Tia pedir aprovação.
- [ ] Só com o seu "aprovar" o OKR vai para `tia/kb/okrs.yaml` com `status: ativo`.
- [ ] A abertura seguinte mostra esses OKRs em "OKRs do grupo em risco" (ou que estão no caminho).
- [ ] Pedido de consolidar os OKRs dos times recebe uma linha de que ainda não está disponível.

## 5. Semanal de portfólio e relatório para a diretoria

Digite `/tia:report semanal` e depois `/tia:report diretoria`.

Conferir:

- [ ] Semanal em `tia/relatorios/<data>-semanal.md`: tabela por time (WIP, travas, entregas, situação), OKRs do
      grupo e até 3 recomendações, cada uma com evidência e trade-off.
- [ ] Diretoria em `tia/relatorios/<data>-diretoria.md`: cabe numa tela; situação, até 3 riscos e até 3
      decisões pedidas (ou "Nenhuma decisão pedida nesta semana"); sem chave de item nem jargão do Jira.
- [ ] Nenhum dos dois tem nome de pessoa ou avaliação individual.
- [ ] A Tia mostra o texto e para: não envia, não publica e só oferece documento ou página no `manter` (com C1)
      se você pedir.

## 6. Pasta PM (`tia-harness-cowork`): nada mudou para a PM

Abra o Claude Code na pasta da PM, com o plugin já atualizado.

Conferir:

- [ ] `.tia/config.yaml` não tem a chave `perfil` (ou tem `pm`) e o `doctor` não mostra `FALHA` nova.
- [ ] `/tia:abrir` traz a fila e os gates como antes.
- [ ] `/tia:ajuda` lista `/tia:demanda`, G1, G2 e G3, e não lista `/tia:portfolio`.
- [ ] `/tia:portfolio` e `/tia:report diretoria` respondem em uma linha que são do perfil GPM.
- [ ] `/tia:report diario` e `/tia:report semanal` saem no formato de sempre.
- [ ] `/tia:configurar atualizar` mostra só o diff esperado dos modelos, se houver; nada é trocado sem o seu sim.
- [ ] `git status` na pasta PM não mostra mudança que você não pediu.

## 7. Fechar o piloto

1. Some as notas da semana em `tia/propostas/piloto-gpm-notas.md`: o que funcionou, números que não bateram,
   texto que confundiu, ajustes pedidos.
2. Ajustes no plugin entram numa sessão de manutenção própria, com `TIA_DEV=1` ligado por você.
3. Desligue o modo manutenção ao final, no seu terminal, e reabra o Claude Code:

```bash
setx TIA_DEV ""
```

Conferir:

- [ ] Num terminal novo, `echo $env:TIA_DEV` (PowerShell) sai vazio.
- [ ] O `doctor` não mostra mais o `AVISO` do modo manutenção.
