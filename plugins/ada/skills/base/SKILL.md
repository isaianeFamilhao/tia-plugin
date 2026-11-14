---
name: base
description: Atualiza a Base de Conhecimento (pasta ada/kb/) a partir do Confluence e do Jira — confere regras existentes contra a fonte, registra regras e fontes novas, marca conflitos e lacunas, sempre com aprovação K1. Use quando a humana pedir para atualizar, revisar ou ampliar a Base de Conhecimento (ou "Memória"), ou quando uma demanda mostrar que a Base de Conhecimento está desatualizada.
---

# /ada:base $ARGUMENTS

Escopo: `$ARGUMENTS` (domínio `RN-XXX`, página, épico, ou vazio = varredura das fontes mais antigas).
Contrato de formato: `ada/kb/README.md`. `ADA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/ada.sh"`.

1. **Estado:** `ADA kb stats` e `ADA kb lacunas`. Escolha o recorte (no máximo
   ~15 leituras por rodada) e diga qual é.
2. **Leitura (somente leitura):** para cada fonte do recorte, leia a versão atual no Confluence/Jira e compare
   com as regras que a citam (`grep` pelo `SRC-…` em `ada/kb/`). Classifique cada diferença:
   *regra nova*, *regra mudou*, *regra revogada*, *conflito entre fontes*, *lacuna resolvida*, *lacuna nova*.
3. **Proposta (K1):** mostre o lote como tabela (ID, tipo de mudança, enunciado novo, fonte). Pergunte
   **"K1: aplicar estas N mudanças na Base de Conhecimento?"** — *Aplicar*, *Aplicar só algumas*, *Não aplicar*.
4. **Aplicação (só com resposta):** regra nova recebe o próximo número livre do domínio; mudança edita o
   bloco e atualiza `Atualizado:` e `Notas:`; revogada vira `Status: revogada` com nota (nunca apague);
   fonte nova entra em `ada/kb/fontes/*.yaml` com `lido_em` de hoje; lacuna resolvida sai de `## Lacunas`.
5. **Validação:** `ADA kb validar` até OK. Resuma em 3 linhas o que mudou.

Regras: sem fonte não entra; `a confirmar` quando a fonte é rascunho, conversa ou derivada; divergência vira
`conflito` com as duas fontes na nota. Sem dados pessoais. Parafraseie, não copie trechos longos.
