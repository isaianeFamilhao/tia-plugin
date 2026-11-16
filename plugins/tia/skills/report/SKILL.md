---
name: report
description: Relatório da Tia cruzando entrega e dados — diário (pulso: alertas de métricas, anomalias pós-deploy, bloqueios do dia) ou semanal (visão de OKR: evolução das métricas dos épicos em andamento contra a meta e recomendações de ajuste de rota). No perfil GPM, o semanal é o de portfólio (tabela por time com WIP, travas e entregas, OKRs do grupo e recomendações) e há o relatório para a diretoria (situação, riscos, decisões pedidas). Use quando a humana digitar /tia:report diario|semanal|diretoria ou pedir "Tia, gera o diário", "roda o semanal", "report dos OKRs", "relatório para a diretoria".
---

# /tia:report $ARGUMENTS

`$ARGUMENTS`: `diario` (padrão), `semanal` ou `diretoria` (só GPM). `TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`. Tudo é leitura, exceto o
arquivo do relatório. Formato e cadência preferidos estão na Memória (`TIA memoria listar`):
siga-os.

## Coleta (sempre)
1. **Leituras devidas:** `TIA metricas ativos --json`; para cada monitor devido com fonte
   conectada, consulte (só leitura, agregada) e registre com `TIA metricas avaliar`. Fonte desconectada →
   "não checado" no relatório, sem inventar número.
2. **Entrega:** `TIA ledger status --json` e `TIA report`.
3. **Bloqueios:** demandas `blocked`/`rework`, perguntas em aberto e lacunas bloqueantes dos `result.json`,
   apontamentos abertos (`TIA kb apontamentos --abertos`).

## Diário — pulso rápido (até ~15 linhas)
- **Alertas críticos e alertas** (`TIA metricas alertas --dias 1`): métrica, valor, regra que
  disparou, origem (épico/OKR) e a hipótese mais provável — marcada como hipótese.
- **Pós-deploy:** monitores com menos de 7 dias de janela e como estão.
- **Bloqueios do dia:** o que espera decisão da PM (gates) e o que espera outra área.
- **Uma recomendação** para hoje.

## Semanal — visão de OKR
- `TIA metricas resumo --dias 7 --json` + `TIA okr listar --ativos` (se não houver,
  os OKRs que a Memória diz onde ficam — leia a fonte; sem fonte, diga que falta e ofereça `/tia:okr`).
- Tabela: OKR/épico · métrica · início → atual · meta · tendência · status (no caminho, em risco, fora).
- **Entrega da semana:** demandas aceitas, publicadas, em andamento e bloqueadas.
- **Ajuste de rota:** até 3 recomendações, cada uma com evidência (dado ou fato com fonte) e o *trade-off*.
  Use a skill de produto disponível (ex.: `/pm-especialista`) se um framework ajudar (ex.: priorização). Desafie meta irrealista ou *vanity metric*.

## Perfil GPM: semanal de portfólio

O perfil vem no início da sessão ("Perfil desta pasta") e em `.tia/config.yaml`. No perfil PM, nada desta
seção vale: diário e semanal seguem como acima. No GPM não há fila: na coleta, pule `ledger status`, `TIA report`
e os bloqueios de demandas (fique com métricas e apontamentos). `semanal` no GPM é o **semanal de portfólio**,
no lugar da visão de OKR do PM:

1. **Retrato do portfólio:** `TIA portfolio ultimo --resumo`. Se não houver retrato ou ele não for de hoje, rode
   a coleta da `/tia:portfolio` (passos 1 a 3: validar, JQL só leitura por time, `portfolio agregar --janela 7
   --gravar`). Jira indisponível → use o último retrato dizendo a data dele, ou "times não consultados: <motivo>"
   sem inventar número.
2. **Tabela por time:** `TIA portfolio ultimo --tabela` (WIP, travas, entregas da semana e situação por time,
   com a linha do grupo). Cole como está; abaixo, uma linha por time travado ou em atenção: o que trava (chave do
   item e motivo) e o próximo passo para a conversa com a PM do time.
3. **OKRs do grupo:** `TIA okr listar --ativos --nivel grupo` (só nível grupo; OKR de time não entra) e
   `TIA metricas resumo --dias 7 --json`. Tabela: objetivo · KR · início → atual · meta · tendência · status (no
   caminho, em risco, fora). KR sem leitura → "sem leitura", sem número. Sem OKR de grupo ativo: uma linha e
   ofereça `/tia:okr`.
4. **Ajuste de rota:** até 3 recomendações para o grupo, cada uma com **evidência** (número da tabela ou do KR,
   com a fonte) e o **trade-off** (o que se perde ou atrasa). Cruze portfólio e OKR: time travado num KR em risco
   vem primeiro. Sem evidência, não recomende.

Sem nomes de pessoas em nenhuma parte: times pelo nome, colegas pelo papel, itens pela chave. Fecha com
`Fonte: Jira (<projetos>), retrato de <data>; métricas e OKRs de <fonte>`. Arquivo:
`tia/relatorios/<AAAA-MM-DD>-semanal.md`.

## Diretoria (só perfil GPM)

No perfil PM, `diretoria` responde só "O relatório para a diretoria é do perfil GPM; esta pasta é do perfil PM."
e para. No GPM, é o formato executivo curto (cabe numa tela, até ~20 linhas), para quem não acompanha os times:

1. **Coleta:** a mesma do semanal de portfólio (retrato de hoje ou nova coleta; OKRs do grupo; métricas).
   `TIA portfolio ultimo --executivo` dá a linha do grupo e os times por situação; use-a como base.
2. **Situação** (3 a 5 linhas): a linha do grupo, os times por situação e os OKRs do grupo em uma linha cada
   (objetivo pelo título: no caminho, em risco, fora). Sem chave de item, sem etapa do Jira, sem jargão.
3. **Riscos** (até 3): risco · impacto (em OKR ou prazo) · o que já está sendo feito. Cada um com a evidência.
4. **Decisões pedidas à diretoria** (até 3): a decisão, as opções e a recomendação da GPM, com o *trade-off*.
   Só o que depende da diretoria (prioridade entre times, dependência de outra área, pessoas no sentido de
   capacidade, verba). Nada a pedir: escreva "Nenhuma decisão pedida nesta semana".

Grave em `tia/relatorios/<AAAA-MM-DD>-diretoria.md`, com a linha `Fonte:` do semanal. Sem nomes de pessoas,
avaliação individual nem dado pessoal: times pelo nome, colegas pelo papel. Mostre o texto e pare: **não envie
nem publique**. Só se a humana pedir, ofereça: documento (skill de documento do ambiente, como página ou
arquivo, sem compartilhar) ou página no espaço do Confluence marcado `manter` via `/tia:confluence` com o gate
C1. Nunca envie por e-mail, chat ou mensagem, nem publique em outro espaço.

## Saída
Grave em `tia/relatorios/<AAAA-MM-DD>-<diario|semanal>.md` (nomes humanos; códigos só em "Ref.") e mostre
o resumo na conversa. Para enviar a alguém, ofereça publicar como página ou documento; nunca publique sozinha.
Se a PM ajustar o formato, proponha guardar na Memória.
