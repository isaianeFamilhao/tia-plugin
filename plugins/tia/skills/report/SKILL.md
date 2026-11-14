---
name: report
description: Relatório da Tia cruzando entrega e dados — diário (pulso: alertas de métricas, anomalias pós-deploy, bloqueios do dia) ou semanal (visão de OKR: evolução das métricas dos épicos em andamento contra a meta e recomendações de ajuste de rota). Use quando a humana digitar /tia:report diario|semanal ou pedir "Tia, gera o diário", "roda o semanal", "report dos OKRs".
---

# /tia:report $ARGUMENTS

`$ARGUMENTS`: `diario` (padrão) ou `semanal`. `TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`. Tudo é leitura, exceto o
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

## Saída
Grave em `tia/relatorios/<AAAA-MM-DD>-<diario|semanal>.md` (nomes humanos; códigos só em "Ref.") e mostre
o resumo na conversa. Para enviar a alguém, ofereça publicar como página ou documento; nunca publique sozinha.
Se a PM ajustar o formato, proponha guardar na Memória.
