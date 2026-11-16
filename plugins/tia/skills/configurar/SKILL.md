---
name: configurar
description: Prepara o projeto atual para a Tia — pergunta o perfil da pasta (PM ou GPM) e cria o marcador .tia/config.yaml (site, projeto(s) do Jira e espaços do Confluence, propostos a partir do conector Atlassian e aprovados pela humana), a pasta tia/ (fila, Base de Conhecimento, padrões, Memória), o CLAUDE.md do time e o .gitignore; ou, com "atualizar", compara os modelos copiados com os do plugin e mostra o diff. Use quando a humana digitar /tia:configurar, disser "Tia, configurar" ou aceitar o convite para configurar uma pasta que ainda não é workspace da Tia.
---

# /tia:configurar $ARGUMENTS

`TIA` = `bash "${CLAUDE_PLUGIN_ROOT}/scripts/tia.sh" --data "${CLAUDE_PLUGIN_DATA}"`. Comandos a partir da raiz do
projeto. Tom da Tia: objetiva, sem emojis. Nada é criado sem o sim da PM, e nada que já existe é sobrescrito.

## Sem argumento: configurar este projeto

1. **Estado:** `TIA configurar status`. Já é workspace e não falta nada → diga em uma linha e ofereça
   `/tia:abrir`. Falta algo → siga (só o que falta será criado; o perfil já escolhido não muda).
2. **Perfil** (pasta nova): pergunte **"Esta pasta é de PM (um time, com fila de demandas) ou de GPM (um grupo
   de times, sem fila)?"**. Sem resposta clara, não presuma: pergunte de novo. Quem tem os dois papéis usa
   duas pastas.
3. **Proposta a partir do conector Atlassian (só leitura):**
   - `getAccessibleAtlassianResources` → site e `cloud_id` (mais de um site: pergunte qual).
   - `getVisibleJiraProjects` → PM: proponha **o** projeto do time. GPM: proponha **os times do grupo**, cada um
     com nome e projeto do Jira (um projeto por time; board opcional). Na dúvida, pergunte. Sem nomes de pessoas.
   - `getConfluenceSpaces` → proponha os espaços que a Tia vai consultar, com o `id` de cada um. **No máximo
     um** pode ser `manter` (o espaço que o time ou o grupo mantém, alterado só com C1); no GPM pode não haver
     nenhum. Todos os outros são `somente_leitura`.
   - Sem conector: peça site, projeto(s) e espaços em uma pergunta e marque o que faltar como `[a definir]`.
4. Mostre a proposta numa tabela (perfil, time ou grupo, site, cloud_id, projeto Jira ou times do grupo com
   projeto, espaços com política)
   e a lista do que será criado: `.tia/config.yaml`, `tia/` (PM: fila e exemplo; ambos: Base de Conhecimento com
   contrato, padrões de épico e história, apontamentos, prefixos, Memória do time e pessoal com `pessoal.md`),
   `CLAUDE.md` do time ou do grupo (ou `tia/CLAUDE.md` + linha `@tia/CLAUDE.md`, se o projeto já tiver um) e o
   bloco no `.gitignore`. Pergunte **"Crio a configuração da Tia neste projeto?"**.
5. Só com o sim:
   - PM: `TIA configurar criar --time "<nome>" --site <url> --cloud-id <id> --jira <CHAVE> --espaco "CHAVE|id|Nome|manter" --espaco "CHAVE|id|Nome|somente_leitura" … --nota "<resposta literal>"`
   - GPM: `TIA configurar criar --perfil gpm --time "<grupo>" --site <url> --cloud-id <id> --portfolio "Nome do time|CHAVE" --portfolio "Outro time|CHAVE2|<board>" … --espaco "CHAVE|id|Nome|somente_leitura" … --nota "<resposta literal>"`
     (os projetos do Jira vêm dos times; `TIA portfolio validar` confere depois).
6. **Ambiente Python:** `TIA bootstrap` (cria o ambiente do plugin; leva até alguns minutos na primeira vez).
   Falhou → `TIA doctor` e explique a correção em linguagem simples (Python 3.12, Git for Windows, proxy).
7. **Fechamento:** `TIA doctor`. Diga em até 5 linhas o que foi criado e os próximos passos.
   PM: preencher o `CLAUDE.md` do time e o padrão de épico (`tia/kb/padroes/epico.md`), alimentar a Base
   (`/tia:base`), escrever a primeira demanda em `tia/demandas.yaml` (modelo em `tia/demandas.exemplo.yaml`).
   GPM: preencher o `CLAUDE.md` do grupo (missão e times → projeto do Jira) e alimentar a Base, se fizer sentido.
   Ambos: se quiser, o `pessoal.md` (estilo e atalhos). Sugira commitar `tia/`, `.tia/config.yaml` e o
   `CLAUDE.md` (git local basta; recomende backup da pasta).

## `atualizar`: modelos copiados × plugin

1. `TIA configurar atualizar` lista os arquivos com `modelo_versao` menor que o do plugin, com o diff.
2. Explique cada diff em linguagem de negócio (o que muda para o time) e pergunte arquivo a arquivo
   **"Atualizo <arquivo>?"**.
3. Com sim: `TIA configurar atualizar --aplicar <arquivo> --nota "<resposta literal>"` (guarda cópia em
   `.tia/cache/backup/`). `.tia/config.yaml` e `CLAUDE.md` têm dados do time: não são trocados pelo script;
   mostre o trecho a mudar para a humana editar e subir o `modelo_versao`.

## Regras

- `.tia/config.yaml`, `CLAUDE.md` e `tia/demandas.yaml` são da humana depois de criados: a Tia propõe, não edita.
- Não crie conta, token ou acesso em nome da PM. Conector Atlassian ausente: só pergunte.
- Nenhum dado pessoal em arquivo de configuração.
