# Decisões de desenho (continuação de D-PM-01…15 do harness-cowork)

- **D-PM-16** Ada vira plugin do Claude Code (`ada@ada-marketplace`). Casa: Claude Code; Cowork só apoio.
  **Motor no plugin, conteúdo no workspace:** o plugin traz skills, scripts, hooks, avaliadores e `modelos/`;
  o projeto guarda `ada/` (conteúdo que gente lê e revisa) e `.ada/` (máquina, só scripts). Sem `bin/` no topo
  do plugin: scripts em `scripts/`.
- **D-PM-17** Marcador único: `.ada/config.yaml` em `$CLAUDE_PROJECT_DIR`. O `hook.sh` testa o marcador antes de
  chamar Python e, sem ele, sai em silêncio (exit 0), mesmo sem venv. Exceção: "Ada, …" no início da mensagem
  recebe o convite para configurar (ou a skill `configurar`). Fail-closed só dentro de workspace.
- **D-PM-18** Configuração em três categorias. Inegociável (só no plugin, reposto depois do merge):
  `escopo_escrita`, regex de escrita no Jira/Confluence, `confluence.padrao`, `dados.escrita_regex`,
  `cobertura.exigir_regra_coberta`, `cobertura.formato_criterio`. Padrão com ajuste por deep merge (lista
  substitui lista). Do time: copiado no configurar com `modelo_versao`; depois só a humana edita.
  Decisão desta fase: a regex que barra SQL de escrita e a política "fora do `manter` é somente leitura" ficaram
  inegociáveis por serem proteção, embora "regex de dados" estivesse na categoria 2 do desenho.
- **D-PM-19** Princípios: o plugin não carrega CLAUDE.md. O SessionStart injeta `modelos/principios.md` (resumo)
  + índice da Memória + `pessoal.md`, com teto de 9.000 caracteres (o Claude Code guarda em arquivo o contexto
  acima de 10.000 e injeta só uma prévia). Texto completo na skill `abrir`. O `CLAUDE.md` do workspace só tem a
  parte do time.
- **D-PM-20** Memória: um `.md` por aprendizado (frontmatter `nome`, `descricao`, `status`…) em
  `ada/memoria/time/`, `ada/memoria/pessoal/` e `~/.ada/memoria/`. O hook injeta só nome e descrição. Gate
  *Memória* ("Guardo para você ou para o time?") registrado pelo `--nota` do `memoria.py gravar`. Revogar =
  `status: revogada`. `pessoal.md` escrito pela PM, sem gate, vale em estilo e nunca em política.
  Precedência: princípios > time > pessoal do workspace > pessoal global.
- **D-PM-21** Skills pelo verbo (`abrir`, `demanda`, `base`, `confluence`, `metricas`, `okr`, `report`,
  `configurar`, `ajuda`); sai `pm-init`. Hook UserPromptSubmit reconhece `^\s*Ada,\s*<frase>` (tabela do plugin
  + atalhos do `pessoal.md`) e injeta "invoque a skill ada:<skill>". Pedido "Ada, …" sem atalho conhecido segue
  a tabela de pedidos da `abrir`, sem rodar a abertura. Skills de apoio do time (`/epico-internal-tools`,
  `/pm-especialista`, `/pm-advisor`) ficaram opcionais.
- **D-PM-22** Python do plugin: venv em `${CLAUDE_PLUGIN_DATA}/venv`, criado pelo `bootstrap.sh` no SessionStart
  (ou `ada.sh bootstrap`) a partir de `requirements-runtime.txt`; recriado quando o hash dos requisitos muda.
  Até existir, escrita e shell negados dentro do workspace (exceto `doctor`, `configurar`, `bootstrap`).
  As variáveis do plugin não chegam ao Bash do agente (documentado): o hook deixa o caminho dos dados em
  `.ada/cache/plugin-data` e as skills chamam `bash "${CLAUDE_PLUGIN_ROOT}/scripts/ada.sh" <script>`; a
  substituição de `${CLAUDE_PLUGIN_ROOT}` e `${CLAUDE_PLUGIN_DATA}` no corpo da skill foi confirmada ao vivo
  (CLI 2.1.322, `--plugin-dir`).
- **D-PM-23** Proteções: escrita do agente só em `ada/**` (md/yaml/yml/json), exceto `ada/demandas.yaml` e
  `ada/kb/README.md`; `ada/kb/**` pede K1, `ada/memoria/**` pede o gate Memória. Negados: `.ada/**` direto,
  `CLAUDE.md`, `.claude/`, cache e dados do plugin, e desligar a fiscalização (`claude plugin
  disable|uninstall|remove`, `enabledPlugins`, `disableAllHooks`, `HARNESS_DEV`, `ADA_DEV`, `hook.sh`,
  `hooks.json`). Manutenção do plugin: `ADA_DEV=1` no terminal de quem abre o Claude Code.
- **D-PM-24** Generalização para outros times: fontes `SRC-<2 a 4 letras>-NNN`; prefixos de domínio na
  `ada/kb/prefixos.md` do time; `epicos.md` em qualquer área da Base; seções do épico no frontmatter
  `secoes_epico` do padrão do workspace (o `kb.py validar` acusa divergência com o config).
- **D-PM-25** `/ada:configurar` só cria o que não existe; propõe site, projeto e espaços pelo conector Atlassian;
  aceita um único espaço `manter`. `atualizar` mostra diff por `modelo_versao` e troca com backup; config e
  `CLAUDE.md` têm dados do time e nunca são trocados por script.
