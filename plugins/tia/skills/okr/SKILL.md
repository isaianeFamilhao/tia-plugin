---
name: okr
description: Cria, revisa ou desdobra OKRs com pragmatismo — calibra pelo momento e maturidade do time, objetivo qualitativo, 2–4 KRs "de X para Y", adaptações quando o clássico não encaixa (KR de baseline, de aprendizado, de marco técnico, comprometido ou aspiracional), tensão saudável, checagem de dados e iniciativas separadas dos KRs. Use quando a PM digitar /tia:okr ou pedir "fechar os OKRs", "revisar esse OKR", "desdobrar o OKR da empresa para o time".
---

# /tia:okr $ARGUMENTS

Método de estratégia para OKRs claros e mensuráveis, sem dogma. Fale como a Tia (`CLAUDE.md`): curta,
direta, sem emojis. Boa prática existe para dar clareza, não burocracia. `TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`.

## Postura
- **Pragmatismo antes de dogma.** Descoberta, produto novo ou fundação técnica não pedem KR financeiro
  maduro: adapte e diga por quê em uma linha.
- **Resultado, não entrega.** "Lançar app v2" é iniciativa; o KR é o que muda por causa dela.
- **Nunca critique sem a versão melhor.** OKR ruim → reescreva na hora e pergunte se cabe no contexto.
- **Dados reais.** KR sem fonte para o check-in semanal é sinalizado na hora.

## Etapas

1. **Calibragem.** Busque na Memória, em `tia/kb/okrs.yaml` (OKR superior ou anterior), no Confluence e no
   roadmap: horizonte, momento do time (crescimento, retenção, descoberta, eficiência, fundação) e objetivo
   superior. O que faltar: até 3 perguntas curtas, de uma vez. Pergunte também, se a Memória não souber:
   comprometido (100% esperado) ou aspiracional (70% já é sucesso)?
2. **Objetivo.** 1 ou 2 opções qualitativas, memoráveis, sem jargão e sem número, que digam a mudança de
   estado. Se a cultura do time preferir objetivo direto e operacional, adapte o tom.
3. **KRs.** 2 a 4 por objetivo: verbo de impacto + métrica + de baseline para meta. Use o cardápio quando o
   clássico não encaixar:
   - sem baseline → KR de **baseline** ("medir nas 2 primeiras semanas e atingir X") ou ciclo curto antes da meta;
   - descoberta ou produto novo → KR de **aprendizado** (validar com N clientes, ativação > X%);
   - fundação ou infraestrutura → KR de **marco técnico** com valor mensurável (p95 de 800 ms para < 200 ms);
   - comprometido ou aspiracional → calibre a ambição dos números.
4. **Saúde e dados.** Tensão saudável: ao menos um guardrail (qualidade, margem, suporte) contra crescimento
   destrutivo. Para cada KR de outcome ou guardrail, aplique a checagem da `/tia:metricas` (fórmula,
   mensurável hoje / sem acesso / ponto cego / manual) e puxe o baseline se a fonte estiver conectada.
5. **Iniciativas.** Tudo que é projeto, feature ou tarefa sai dos KRs e vai para **Iniciativas**, como meio
   para mover os KRs e que pode mudar no ciclo.

Foco: mais de 3 objetivos ou fora de 2 a 4 KRs por objetivo → diga em uma linha e sugira priorizar.

## Registro e avaliador
Rascunho em `tia/propostas/okrs-<ciclo>-<time>.yaml`:

```yaml
- ciclo: 2026-Q3
  time: <time>
  horizonte: trimestre
  momento: crescimento | retencao | descoberta | eficiencia | fundacao
  modo: comprometido | aspiracional
  alinhamento: <objetivo superior>
  status: rascunho
  objetivos:
    - titulo: <mudança de estado>
      krs:
        - texto: "Aumentar <métrica> de 42% para 58%"
          tipo: outcome | learning | milestone | baseline | guardrail
          metrica: <nome>
          baseline: 42
          meta: 58
          unidade: "%"
          fonte: <se souber>
          status_dados: mensuravel_hoje | sem_acesso | ponto_cego | manual
      iniciativas: [<meio 1>, <meio 2>]
```

Rode `TIA okr validar <arquivo>`. **REPROVADO → corrija e rode de novo.** Avisos: resolva ou
justifique em uma linha — aviso é conversa, não bloqueio.

## Resposta à PM (curta)
1. Uma linha de calibragem: o momento do time e a adaptação escolhida.
2. Alinhamento → objetivo → KRs (com tipo, baseline, meta e dados) → iniciativas.
3. Uma pergunta só: aprovar, ajustar a ambição ou trocar uma adaptação.

Com "aprovar": copie para `tia/kb/okrs.yaml` com `status: ativo` e rode `TIA okr validar`.
Depois ofereça monitorar os KRs mensuráveis hoje (M1, via `/tia:abrir`). Preferência que se repete (modo, tom dos
objetivos, cadência de check-in) → proponha guardar na Memória. Os OKRs ativos alimentam o `/tia:report semanal`.
