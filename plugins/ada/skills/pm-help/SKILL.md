---
name: pm-help
description: Lista os comandos do harness de produto (skills, skills de apoio, gates e scripts) com uma descrição breve de cada. Use quando a humana digitar /pm-help ou perguntar "quais comandos existem", "o que o harness faz" ou "como uso isso".
---

# /pm-help

1. Rode `.venv/Scripts/python.exe .harness/bin/ajuda.py` (a lista de skills é lida de `.claude/skills` na hora).
2. Mostre a saída **como está**, sem resumir nem acrescentar comandos que não apareceram.
3. Termine com uma linha: o próximo passo mais útil agora, a partir de `.venv/Scripts/python.exe .harness/bin/ledger.py status`
   (ex.: "D-002 aguarda G2: rode /ada" ou "fila vazia: escreva uma demanda em .harness/demandas.yaml").
