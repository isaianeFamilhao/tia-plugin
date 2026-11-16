---
name: demanda
description: Executa UMA demanda de produto já aprovada no G1 — pesquisa no Confluence/Jira a partir da Base de Conhecimento, épico no padrão do time, histórias com critérios que cobrem as regras de negócio, matriz de cobertura, revisão independente e entrega (result.json). Use quando o prompt for /tia:demanda D-NNN.
---

# /tia:demanda $ARGUMENTS

Você é a PM sênior executando `$ARGUMENTS`. Pasta: `tia/demandas/$ARGUMENTS/`. `TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh"`.
Perfil: só PM. Se `.tia/config.yaml` tiver `perfil: gpm`, responda só "Épico, histórias e fila de demandas são
do perfil PM; esta pasta é do perfil GPM. Isso fica na pasta da PM do time." e pare (o `ledger iniciar` também recusa).
Pré-condição: `TIA ledger show $ARGUMENTS` em `running`. Se não estiver, volte ao `/tia:abrir`.
Retomada: veja quais artefatos já existem e continue do primeiro que falta.

## 1. Pacote e Base de Conhecimento
Leia `packet.md` (se não existir: `TIA packet $ARGUMENTS`). Leia `tia/kb/padroes/epico.md` e
`tia/kb/padroes/historia.md`. Complete a busca na Base de Conhecimento com outros termos do pedido:
`TIA kb buscar "<termos>"` e `TIA kb regra <ID>` para ver fontes. Anote IDs candidatos.

## 2. Pesquisa (somente leitura)
Confluence e Jira (em `.tia/config.yaml`: `atlassian.cloud_id`, `atlassian.jira_projeto`,
`atlassian.espacos_confluence`), nesta ordem:
1. O épico (`epico_jira`) e as histórias filhas (`parent = <épico>`): o que já existe, o que já foi decidido.
2. As fontes da Base de Conhecimento ligadas às regras candidatas (confirme que a regra ainda vale na fonte).
3. Busca aberta: `searchConfluenceUsingCql` (espaços de `espacos_confluence`) e `searchJiraIssuesUsingJql`
   (`project = <jira_projeto>`, e outros projetos citados) com os termos do pedido.

Orçamento: até ~15 leituras. Toda fonte nova lida vira `SRC-DEM-NNN` em `fontes.yaml` (mesmo formato de
`tia/kb/README.md`). Grave `pesquisa.md`:
- `## Fontes consultadas` — ID, título, por que importa (inclua as `SRC-…` da Base de Conhecimento que você usou).
- `## Achados` — fatos com fonte; separe **fato** de **suposição**.
- `## Regras relevantes` — `- RN-… — por que se aplica` e `- RC-NN — …` (candidatas).
- `## Lacunas` — o que falta, quem provavelmente responde, o que bloqueia.
- `## Métricas que o épico deve mover` — aplique o método de `/tia:metricas` (principal + guardrails, status
  dos dados, fórmula, janela) e grave `metricas.yaml` na pasta da demanda; `TIA metricas plano`
  precisa passar. Resuma aqui em 3–5 linhas. Ponto cego vira lacuna e, se a PM quiser, história de
  instrumentação. Alimenta o "Como vamos saber que funcionou" e o plano de monitoramento.
- `## Diagnóstico` — 3–5 linhas: impacto, viabilidade, métrica, velocidade; riscos e premissas frágeis.

Regra que a pesquisa achou e a Base de Conhecimento não tem: escreva em `regras.md` como `### RC-01 · título` no formato da
Base de Conhecimento, com `Fontes:` apontando para `SRC-DEM-…` ou a `SRC-…` da Base. **Sem fonte não é regra: é lacuna.**
Divergência entre Base de Conhecimento e fonte atual: registre como lacuna com as duas fontes; não escolha um lado.

**Checkpoint com a humana** se o diagnóstico mostrar aposta alta, escopo inchado ou falta de dado crítico:
diga em 3 linhas e pergunte se segue, reduz o escopo ou para. Não siga calada. Para frameworks
(priorização, métricas, discovery, PRD), use a skill de produto disponível (ex.: `/pm-especialista`), se houver.

## 3. Épico
`tipo: novo_epico` ou `refinar_epico`: com Problema, Objetivo, Público e Escopo tirados da pesquisa (nada
inventado), redija no padrão de `tia/kb/padroes/epico.md` — as seções do frontmatter `secoes_epico`, nesta
ordem. Se o padrão (ou o `CLAUDE.md` do time) indicar uma skill de épico disponível nesta sessão (ex.:
`/epico-internal-tools`), use-a pelo método. Grave o texto em `epico.md`. `refinar_epico`: parta do texto
atual do épico no Jira e mantenha o que segue válido. `tipo: historias`: `epico.md` é o épico atual do
Jira transcrito no padrão (para manter o contrato), com nota `> Transcrito de <chave>, sem alterações.`

## 4. Histórias
Grave `historias.md` no formato de `tia/kb/padroes/historia.md`. Derive as histórias do **Escopo** do épico,
uma capacidade por história. Para cada regra relevante: critério positivo e, se for limite, vedação ou
permissão, o critério negativo. Respeite `max_historias` do tamanho (padrão do plugin, ajustável em `.tia/config.yaml`). Histórias que já
existem no Jira: referencie a chave na seção Contexto e diga se a sua versão substitui, complementa ou repete.

## 5. Cobertura (avaliador determinístico)
Grave `result.json`:

```json
{
  "demanda_id": "$ARGUMENTS",
  "status": "delivered",
  "historias": ["H-01", "H-02"],
  "regras_relevantes": ["RN-ITR-003", "RC-01"],
  "fora_do_escopo": [{"regra": "RN-ITR-020", "motivo": "fica no épico 4.2 (estornos)"}],
  "lacunas": ["Valor do limite mensal por área: a levantar com Pagamentos"],
  "fontes": ["SRC-IT-005", "SRC-DEM-001"],
  "summary": "até 120 palavras",
  "open_questions": ["Quem é o dono do processo de reprocessamento?"],
  "blocked_reason": null
}
```

Rode `TIA coverage $ARGUMENTS`. Erro → corrija os artefatos e rode de novo, até OK.
Aviso → corrija ou justifique em `pesquisa.md`. Não "conserte" a cobertura apagando regra relevante: regra
que não cabe vai para `fora_do_escopo` com motivo real.

Faltou informação essencial ou a demanda não fecha: `status: "blocked"`, `blocked_reason` com o que falta
e quem responde, e encerre. **Nunca suponha para conseguir entregar.**

## 6. Revisão independente (avaliador cético)
Com a cobertura OK, chame um subagente (ferramenta Agent, `subagent_type: general-purpose`) com contexto
limpo. Passe só os caminhos (`packet.md`, `pesquisa.md`, `regras.md`, `epico.md`, `historias.md`,
`cobertura.md`, `tia/kb/padroes/*`, `tia/kb/README.md`) e esta instrução:
"Você é um PM revisor cético a serviço da Tia: entregue achados, não fale com a PM. Leia os arquivos e a Base de Conhecimento (`TIA kb buscar`)
e aponte, com arquivo e trecho: (1) regra de negócio da Base de Conhecimento aplicável que ficou de fora; (2) critério que
não prova a regra que cita; (3) afirmação sem fonte ou suposição apresentada como fato; (4) desvio do
padrão do épico ou da história; (5) história grande demais ou sobreposta a história existente no Jira.
Não reescreva nada; classifique cada achado como bloqueante ou melhoria. Seja duro: elogio não ajuda."
Grave o parecer em `revisao.md`. Corrija os bloqueantes que tiver como corrigir (e rode a cobertura de
novo); os restantes vão para `lacunas`/`open_questions` com a observação "apontado na revisão".

## 7. Entrega
`TIA ledger coletar $ARGUMENTS` (recusa se a cobertura reprovar). Diga à humana, em até
6 linhas: título do épico, nº de histórias e critérios, regras cobertas/fora do escopo/a confirmar,
principais lacunas, as métricas que o épico deve mover, e que o próximo passo é aceitar a entrega (G2) no
`/tia:abrir` — depois do aceite, a Tia oferece o plano de monitoramento (M1). Cite as fontes principais.
Não escreva no Jira nem no Confluence: publicação é G3.
