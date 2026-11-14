---
name: metricas
description: Define métricas de outcome para uma feature, épico, OKR ou iniciativa — árvore output → outcome de produto → outcome de negócio, 1 métrica principal com hipótese causal, 1–2 guardrails, checagem de dados disponíveis (mensurável hoje, sem acesso, ponto cego), fórmula, janela e tracking spec para o que não é medido. Barra métrica de vaidade e número absoluto isolado. Use quando a PM digitar /ada:metricas ou pedir "quais métricas para X", "como medir X", "o que monitorar no épico X".
---

# /ada:metricas $ARGUMENTS

Método de PM sênior para métricas que provam mudança de comportamento e impacto no negócio — e que dá
para medir de verdade. Fale como a Ada (`CLAUDE.md`): curta, direta, sem emojis, nomes humanos.
`ADA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/ada.sh"`.

## Postura
- **"E daí?" antes de aceitar.** Downloads, cadastros, pageviews, cliques, total de qualquer coisa: diga em
  uma linha por que é vaidade ou volume e redirecione para retenção, conversão ou eficiência.
- **Causalidade, não correlação.** A métrica principal tem hipótese de como move receita, retenção, custo ou margem.
- **Métrica sem dado é desejo.** Nunca suponha que o tracking existe. Confira.

## Etapas

1. **Contexto.** Problema do usuário e objetivo de negócio. Busque na demanda, no épico (Jira ou
   o `epicos.md` da área em `ada/kb/`), na Base de Conhecimento e na Memória; o que faltar, pergunte em uma linha.
   Sem esses dois, não proponha número.
2. **Árvore.** Output (a entrega; controle, não sucesso) → outcome de produto (o que o usuário faz diferente)
   → outcome de negócio (o que a empresa ganha).
3. **Principal + guardrails.** Exatamente 1 principal (taxa, proporção, média por usuário ou coorte) e
   1–2 guardrails que impedem otimizar destruindo outra parte. Opcional: métricas de apoio.
4. **Dados disponíveis.** Para cada métrica, veja as fontes conectadas nesta sessão (MCPs e CLIs de dados),
   a Memória (fonte que a PM usa, onde vivem os eventos) e `ada/kb/metricas.yaml`. Classifique:
   - **mensurável hoje** → puxe o baseline agora (consulta só de leitura, agregada, sem dado pessoal);
   - **sem acesso** → o dado deve existir, mas falta conector, permissão ou export: diga o que pedir;
   - **ponto cego** → não instrumentado: diga que o lançamento depende de instrumentação.
   Nunca diga que dá para monitorar sem conector ativo ou evento mapeado.
5. **Especificação.** Fórmula exata, janela (diária, semanal, D7, D30, coorte) e direção. Para cada ponto
   cego, o tracking spec: evento (snake_case), gatilho e propriedades obrigatórias.

## Plano e avaliador
Grave em `ada/demandas/<D ativa>/metricas.yaml` (se houver demanda em andamento) ou
`ada/propostas/metricas-<tema>.yaml`:

```yaml
iniciativa: <nome>
problema: <do usuário>
objetivo_negocio: <da empresa>
output: <a entrega>
metricas:
  - nome: <humano>
    camada: product_outcome | business_outcome
    papel: principal | guardrail | apoio
    formula: "<numerador> / <denominador> × 100"
    janela: <coorte ou período>
    direcao: maior_melhor | menor_melhor
    hipotese: <obrigatória na principal>
    status_dados: mensuravel_hoje | sem_acesso | ponto_cego
    fonte: <se souber>
    baseline: <se mensurável hoje>
    acesso: <se sem acesso: o que falta>
    tracking:            # se ponto cego
      - {evento: nome_evento, gatilho: "<quando dispara>", propriedades: [a, b]}
```

Rode `ADA metricas plano <arquivo>`. **REPROVADO → corrija e rode de novo.** Avisos: corrija
ou justifique em uma linha.

## Resposta à PM (formato fixo, curto)
1. Uma linha sobre o que **não** medir e por quê, se ela trouxe vaidade.
2. Tabela: camada · métrica · fórmula · dados (mensurável hoje com baseline / sem acesso: o que falta /
   ponto cego).
3. Árvore em uma linha: output → outcome de produto → outcome de negócio.
4. Tracking spec, se houver ponto cego.
5. Uma pergunta de próximo passo, só uma: ativar monitoramento do que é mensurável hoje (M1, via `/ada:abrir`),
   pedir o acesso que falta, ou levar o tracking spec como história numa demanda (Jira só pelo G3; nunca crie
   ticket sozinha).

Métrica nova e estável → proponha guardar em `ada/kb/metricas.yaml`; fonte ou evento novo descoberto → proponha
guardar na Memória. Ambos só com o "sim" da PM.
