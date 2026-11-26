# QA de cliente — ValorPúblico

Última execução: 25/11/2026
Produção: https://valorpublico.web.app · `valorpublico-v48`

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

## Últimos commits relevantes

- `afd6082` — desabilitar investigação provisória e criar auditoria de cliente.
- `330369b` — estabilizar ações e cobrir investigação desabilitada.
- `f00079a` e `3e917f3` — correções do menu mobile.
- `f25831f` — coleta histórica de 5 meses e publicação.
