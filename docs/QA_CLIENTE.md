# QA de cliente — ValorPúblico

Última execução: 26/11/2026 (tarde)
Produção: https://valorpublico.web.app · `valorpublico-v55` · API `personas-api` rev `00002-mqt`

## Cobertura

- 18 telas em desktop 1440×900 e mobile 390×844.
- Ações globais: tema, sidebar, filtros, período, relatório e logout.
- Clipping: busca, PDF.
- Redes: busca, tom, PDF e fechar o modal de post clicando fora.
- Ouvidoria: 14 pedidos reais, mapa de temas, mapa de menções a municípios (estado vazio quando não há citação) e ajuda `?` (T-17).
- Governo: secretaria, PDF e CSVs de governo, secretarias e governador.
- Governador: semana, PDF e cópia de discurso.
- Semana: abas, PDF.
- Radar: newsletter.
- Análise: abas e dados.
- Personas: seletor e PDF.
- Tendências: geografia e PDF.
- Relatórios: relatório e newsletter.
- Sistema: tema e preferência de valor de mídia.
- Controle desabilitado por decisão: `#btnInvestigar`.

## Resultado

- Ações: **22 OK / 0 falhas**.
- Overflow: **0**.
- `pageerror`: **0**.
- `console.error`: **0**.
- HTTP inesperado: **0**.
- Logout: **OK**.

O teste de UI também foi executado: **72 capturas**, 0 overflow e 0 erro JS.

## Regressão 26/11/2026 — botão Atualizar

- **Sintoma:** clicar em `#btnAtualizar` (não o refresh do navegador) derruba a sessão e volta para a tela de login.
- **Teste:** usuário temporário no site publicado; antes do clique, `authUser` preenchido e botão “Sair”; depois, `authUser = null`, login visível e botão “Entrar”.
- **Controle:** repetindo o reload com `app.js` bloqueado, o Firebase restaurou o mesmo usuário. A persistência está OK; o app é que chama `sair()`.
- **Causa:** o botão limpa cache e faz `location.reload()` (`js/app.js:2020-2037`); no reload `loginExplicito` volta a `false` (`app.js:2097-2101`) e o bootstrap executa `sair()` mesmo com usuário restaurado, abrindo o login (`app.js:2216-2222`; handler em `1964-1968`).
- **Status:** diagnosticado em 26/11/2026; correção pendente.

## Correção 26/11/2026 — modal de post (Redes)

- `#modalPost` passou a fechar ao clicar no backdrop (fora do conteúdo); `X` e `Esc` continuam funcionando.
- Alteração em `frontend/js/telas.js`; **publicada no Hosting em 26/11**.
- Teste local em 1440×900 e 390×844: abre, fecha fora, não fecha clicando dentro e fecha no `X` — **OK** nos dois tamanhos.
- Smoke ao vivo em 26/11: modal abre e fecha ao clicar fora — **OK**.

## Ouvidoria 26/11/2026 — proposta 1 + ampliação

- Dados: **32 manifestações** do Governo (14 pedidos, 8 perguntas, 6 reclamações, 4 sugestões), somente comentários de cidadãos; respostas da conta oficial descartadas.
- Municípios: **37 de 633** comentários citam um município (Cuiabá 9, Várzea Grande 7, Juscimeira 3, Barra do Garças 3…; 18 municípios). O mapa usa essa contagem e informa que não é a origem do cidadão.
- Sem autor no documento; resumo sem `@`/links; `tipo_manifestacao` e `pasta_sugerida` por tema.
- K-26 mostra a idade média em aberto (~6,5 dias), com aviso de que não é tempo de resposta; botão `(?)` (T-17) explica a necessidade de canal estruturado.
- Teste local autenticado (1440×900): 32 linhas, K-26 `6.5 dias`, mapas de temas e municípios desenhados, “37 de 633” no subtítulo, 0 overflow e 0 erro JS.
- **Publicado no Hosting em 26/11** (sw `valorpublico-v54`) a partir do diretório de trabalho, preservando as melhorias da outra IA.
- Smoke ao vivo: 32 linhas, mapa “37 de 633”, `printCabecalho`/`printRodape` em `display:none`, aba “Simulação” ausente e `?` do discurso presente.
- Menu: link **Ouvidoria** visível na sidebar do Governo; clique abre `#/ouvidoria`.

## Sessão 26/11/2026 (tarde) — discurso da semana e simulador do próprio discurso

### Vazamento de interface corrigido

- **Sintoma:** em todas as telas aparecia "ValorPúblico — Relatório" no topo e
  "ValorPúblico · documento institucional · gerado automaticamente" no rodapé.
- **Causa:** `.print-only { display: none; }` estava em `css/impressao.css`, carregado com
  `media="print"` — ou seja, a folha inteira era ignorada na tela e o cabeçalho/rodapé de
  impressão renderizava como HTML normal.
- **Correção:** `<link rel="stylesheet" href="css/impressao.css" />` (sem `media`). O bloco
  `@media print` interno continua valendo só no papel, e `#printCabecalho`/`#printRodape`
  (id) continuam prevalecendo sobre `.print-only` (classe) na impressão.
- **Verificado em produção:** `impressao.css` servido sem `media`; cabeçalho e rodapé de
  impressão não aparecem mais na tela.

### Fontes do discurso (tela Semana → aba Discurso)

- **Sintoma:** a lista de fontes mostrava "Fonte" repetido 8–12 vezes.
- **Causa:** o backend publica as fontes como texto (`"Fatos de Mato Grosso, 2026-11-24"`),
  mas o front esperava objetos (`f.veiculo`) e caía no fallback `"Fonte"`.
- **Correção:** `normalizarFontes()` + `blocoFontes()` em `frontend/js/telas.js` — aceita
  string ou objeto, separa veículo/data, deduplica e resolve o link da matéria original
  cruzando o veículo com `noticias_recentes` (inclusive quando a fonte vem como domínio,
  ex.: `www.cbncuiaba.com.br`).
- **Resultado na tela:** botão **“Fontes (12)”** no fim do discurso; ao abrir, mostra
  veículo, data, link "abrir" e a manchete. O mesmo vale para o discurso do governador e do
  interino.
- O PDF (que abre todos os `<details>` antes de imprimir) continua levando as fontes.

### Botão `?` do discurso (D-01)

- Botão redondo ao lado do selo "Rascunho gerado por IA — revisar antes de usar".
- Abre a explicação **“Como o discurso é gerado”**: coleta → briefing → redação (3 ângulos ×
  3 formatos) → validação de fatos/links → simulação das 12 personas → revisão humana.
- O popover de explicação ganhou suporte a lista de passos (`passos`) e altura máxima com
  rolagem (antes o texto longo passava da tela).

### Aba “Simulação” da tela Semana

- Removida da barra de abas (ficava ao lado de “Discurso”). O acesso ao relatório completo de
  simulação continua pelo link “ver relatório completo” dentro do próprio discurso.

### Simulador do próprio discurso (novo, tela `#/personas`)

- Painel **“Simular o meu discurso”**: campo de texto, contador de palavras/caracteres,
  botão “Avaliar com as 12 personas”, “Copiar resumo” e “Limpar”.
- A API nova (`POST /v1/discurso/simular`, Cloud Run `personas-api` rev `00002-mqt`) faz as
  **12 personas reagirem de uma vez** e devolve: aderência média (0–10), personas que
  aderiram, risco médio, “leitura do texto”, **“O que melhorar antes de publicar”** (até 6
  melhorias priorizadas, com o texto de reescritura e quem apontou), “O que funcionou” e a
  **reação de cada persona** (primeira impressão, o que convenceu, o que incomodou,
  sugestão e as fontes consultadas).
- Botão `?` (D-02) explica o passo a passo da simulação.
- Layout responsivo (1440 e 390), tema claro e escuro.
- **Medido com a chave real do DeepSeek:** 12 personas em ~6 s + consolidação ~6 s
  (**~14 s** no total); veredito e 6 melhorias priorizadas no teste.
- **Rotas autenticadas:** `/health` responde `{"ok":true, "simulador":true}`;
  `POST /v1/discurso/simular` devolve **401** sem token (rota registrada e exigindo auth).

### Estado do deploy

- Hosting: `valorpublico-v55` (publicado 26/11 a partir do diretório de trabalho).
- Cloud Run: `personas-api-00002-mqt`, `--timeout 300` (era 60 s) para caber nas 12 personas.
- Conferência de integridade: **produção idêntica à árvore de trabalho, arquivo por arquivo**
  (HTML/JS/CSS) — nada do trabalho da outra IA foi perdido.
- Commit: `1604e54` (front + API + triagem da ouvidoria) enviado para `origin/main`.

### Pendências desta sessão

- **Teste ponta a ponta com usuário logado ainda não feito**: não foi possível forjar um
  Firebase ID token localmente. O caminho (12 personas + consolidação + layout) foi validado
  com a mesma chave do DeepSeek, mas falta rodar na sessão real e conferir o resultado na
  tela.
- **Botão Atualizar** continua derrubando a sessão (diagnóstico em 26/11; ver abaixo).
- **`#btnInvestigar`** segue desabilitado (“Em breve”).

## Scripts

```powershell
$env:GCLOUD_TOKEN = (gcloud auth print-access-token).Trim()
python frontend\tests\validar_cliente.py
python frontend\tests\validar_ui.py
```

O `validar_cliente.py` cria um usuário temporário `qa.cliente.*`, executa as telas e remove o usuário no `finally`.

## Pendências conhecidas

- `#btnInvestigar` está desabilitado com “Em breve”; a funcionalidade de checagem ainda não existe.
- Templates de e-mail seguem bloqueados pela API do Firebase (`EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED`); arquivos prontos em `docs/emails/`.
- Alertas/e-mails operacionais dependem de SMTP/webhook.
- Botão Atualizar derruba a sessão (diagnosticado em 26/11; ver seção “Regressão 26/11/2026”).
- **Simulador de discurso:** falta o teste ponta a ponta com usuário logado (não foi possível
  forjar ID token localmente) e a decisão sobre incluir o resultado da simulação no PDF de
  Personas (hoje o PDF sai sem o painel de simulação).

## Últimos commits relevantes

- `1604e54` — simulador do próprio discurso (front + API), fontes do discurso em botão,
  correção do vazamento do `impressao.css`, triagem da ouvidoria.
- `26e1754` — PDFs profissionais em A4 nos 8 relatórios.
- `afd6082` — desabilitar investigação provisória e criar auditoria de cliente.
- `330369b` — estabilizar ações e cobrir investigação desabilitada.
- `f00079a` e `3e917f3` — correções do menu mobile.
- `f25831f` — coleta histórica de 5 meses e publicação.
