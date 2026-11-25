# QA de cliente — ValorPúblico

Última execução: 25/11/2026
Produção: https://valorpublico.web.app · `valorpublico-v48`

## Cobertura

- 18 telas em desktop 1440×900 e mobile 390×844.
- Ações globais: tema, sidebar, filtros, período, relatório e logout.
- Clipping: busca, PDF.
- Redes: busca, tom, PDF.
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

## Últimos commits relevantes

- `afd6082` — desabilitar investigação provisória e criar auditoria de cliente.
- `330369b` — estabilizar ações e cobrir investigação desabilitada.
- `f00079a` e `3e917f3` — correções do menu mobile.
- `f25831f` — coleta histórica de 5 meses e publicação.
