---
modelo_versao: 1
---
# Padrão de história e critério de aceite do time

Ponto de partida do plugin; o time pode ajustar o texto. É o formato de `historias.md` de uma demanda;
o `coverage.py` confere a estrutura.

## Formato (um bloco por história, nesta ordem)

```markdown
# Histórias · D-001 · <título da demanda>

## H-01 · <verbo no infinitivo + objeto + condição de negócio>

**Contexto:** 2–3 frases. O que acontece hoje, quem sofre, o que muda com esta história.

**História:** Como <papel concreto, ex.: atendente N1 do CX>, quero <ação>, para <resultado de negócio>.

**Cobre:** RN-ITR-003, RN-ITA-002, RC-01

**Leia:** [Política de reprocessamento](https://…) · RN-ITR-003

### Critérios de aceite

- **CA-01** [RN-ITR-003]: Dado <situação>, quando <ação>, então <resultado observável>.
- **CA-02** [RN-ITR-005]: Dado <situação proibida>, quando <ação>, então <o que acontece no lugar>.

**Pendências:** o que falta definir, quem responde e qual critério fica bloqueado. "Nenhuma" se for o caso.
```

## Regras de redação

- **Título:** verbo no infinitivo + objeto + condição ("Solicitar reprocessamento de pacote dentro do
  limite mensal da área"). Descreve o que o usuário faz, não a tela.
- **Papel concreto.** "Atendente N1 do CX", "analista de Operações", "jurídico". Nunca "usuário" genérico.
- **Um critério, um comportamento.** Se o critério junta duas coisas com "e", são dois.
- **Todo critério cita a regra** que sustenta, entre colchetes: `[RN-…]` da kb ou `[RC-…]` candidata da
  demanda. Critério sem regra é aceito só para comportamento de interface e gera aviso.
- **Escreva o "não".** Toda regra de vedação, limite ou permissão tem pelo menos um critério negativo
  (o que acontece quando a condição não é atendida).
- **Observável.** "então a ação é bloqueada e a tela mostra 'pagamento ainda não confirmado'" — sim.
  "então funciona corretamente" — não. Palavras vagas geram aviso.
- **Rastreabilidade.** Ação que altera dado do participante tem critério de registro (quem, quando, o
  quê, motivo) quando a kb exigir (RN-ITA-…).
- **Tamanho.** Cabe numa sprint de um engenheiro. Mais de 6 critérios: provavelmente são duas histórias.
- **Sem solução técnica.** Nada de endpoint, tabela ou componente. O "como" é do time de engenharia.
- **Lacuna explícita.** Regra a confirmar vira critério marcado e pendência; nunca suposição silenciosa.

## Cobertura (o que o harness exige)

- Toda regra em `regras_relevantes` do `result.json` precisa de pelo menos um critério que a cite, ou estar
  em `fora_do_escopo` com motivo.
- A linha **Cobre:** lista exatamente as regras citadas pelos critérios da história.
- Regra `a confirmar` ou `conflito` usada exige lacuna ou pergunta em aberto registrada.
