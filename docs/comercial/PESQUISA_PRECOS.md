# Pesquisa de preços (IN SEGES/ME 65/2021) — método e planilha

> Preencher antes da 1ª reunião com o órgão. Fontes **gratuitas** e oficiais.

## 1. Metodologia (art. 5º da IN 65/2021)

1. **Painel de Preços / PNCP** — contratos de serviço de clipping e monitoramento
   de mídia de outras câmaras e assembleias.
2. **Pesquisa em mídia especializada / sítios de fornecedores** — preços
   publicados.
3. **Pesquisa direta com 3 fornecedores** — proposta formal.
4. **Parâmetros** — quando não houver amostra suficiente (art. 6º).

## 2. O que consultar no PNCP (API pública)

```
GET https://pncp.gov.br/api/consulta/v1/contratos
    ?dataInicial=20250101&dataFinal=20261231
    &codigoModalidadeContratacao=<pregão>
```

Filtros de texto (busca): "clipping", "monitoramento de mídia", "assessoria de
imprensa", "comunicação institucional".

Registrar por amostra: **órgão, objeto, valor mensal, vigência, link do contrato,
data da consulta**. (Regra: nunca preencher de memória — copiar do contrato.)

## 3. Planilha de referência (preencher)

| # | Órgão | Objeto | Valor mensal (R$) | Vigência | Link | Data consulta |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

**Média / mediana:** R$ `[ ]` / R$ `[ ]`
**Valor de referência adotado:** R$ `[ ]` (justificar se abaixo da mediana).

## 4. Comparação de escopo (cuidado)

Contratos de "assessoria de imprensa" (produção de conteúdo) **não** são
comparáveis a "monitoramento de mídia" (coleta e análise). Separar as amostras:
- **Monitoramento/clipping** (comparável ao nosso objeto);
- **Assessoria de imprensa** (produção — referência apenas para o valor de mercado
  da comunicação).

## 5. Justificativa do preço proposto

`[Descrever: valor proposto, comparação com a mediana, escopo incluído, o que
justifica o preço — ex.: custo zero de licença, operação em nuvem gratuita,
equipe local, SLA contratual.]`

## 6. Sem fontes suficientes?

Se não houver 3 amostras comparáveis, usar o art. 6º da IN 65/2021:
média de preços de mercado de **serviços similares** + dificuldade de comparação
documentada, ou **pesquisa direta** com fornecedores (proposta formal anexa).

## 7. Custos internos (para saber a margem)

| Item | Custo mensal |
|---|---|
| GitHub Actions (repo público) | R$ 0 |
| Firestore Spark | R$ 0 (dentro da cota) |
| Ollama local (energia) | ~R$ `[20–40]` |
| Domínio/Hosting | R$ 0 (Firebase Hosting no Spark) |
| API de personas (Cloud Run) | ⚠️ **exige Blaze** — ver `ESTRATEGIA_COMPRAS_GOVERNO.md` §10.5 |
| Tempo do dono (horas/mês) | `[ ]` h × R$ `[ ]` |

➡️ **Custo direto ≈ R$ 0–40/mês.** O preço pode ser definido pela entrega, não
pelo custo.

---

## 8. Amostras reais coletadas (26/11/2026)

Benchmark do mesmo objeto, levantado na base aberta do PNCP e nos portais de
compras. Valor anual contratado (sem levar em conta vigência acima de 12 meses).

| # | Órgão | Objeto | Estimado | Homologado | Link |
|---|---|---|---|---|---|
| 1 | CGE/MT | serviços continuados de clipping jornalístico online | R$ 132.902,40 | **R$ 38.160,00** | http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=CGE&licitacao=5544&edital=001/2026 |
| 2 | TST — 11ª Região | clipping + monitoramento e **mensuração** | R$ 54.000,00 | — | https://pncp.gov.br/app/contratacoes/00509968000148-1-001376/2026 |
| 3 | TRF 5ª Região | "monitoramento de mídia – Clipping Eletrônico e Mensuração" | R$ 40.590,00 | — | https://pncp.gov.br/app/contratacoes/00508903000188-1-000274/2026 |
| 4 | TCU | clipping de matérias | R$ 47.520,00 | R$ 47.520,00 | https://pncp.gov.br/app/contratacoes/00414607000118-1-000040/2025 |
| 5 | IF São Paulo | clipping + monitoramento + gestão estratégica + análise de conteúdo | R$ 63.879,48 | R$ 22.776,00 | https://pncp.gov.br/app/contratacoes/10784782000150-1-000427/2026 |
| 6 | ANVISA | monitoramento de matérias jornalísticas | R$ 62.725,56 | R$ 33.240,00 | https://pncp.gov.br/app/contratacoes/03112386000111-1-000001/2026 |
| 7 | ANAC | clipping e monitoramento em tempo real | R$ 42.000,00 | — | https://pncp.gov.br/app/contratacoes/07947821000189-1-000210/2024 |
| 8 | Prefeitura de São Luís/MA | clipping e monitoramento de mídia (impresso, rádio, TV, digitais) | R$ 334.800,00 | — | https://buscarlicitacao.com.br/licitacao/ma/sao-luis/06307102000130-1-000080/2026/edital-no-90018-2026 |
| 9 | TJMS | monitoramento de mídia e redes sociais | ~R$ 147.000,00 | **suspenso em 21/09/2026** | https://www.jd1noticias.com/transparencia/2026/09/21/tjms-suspende-licitacao-de-r-147-mil-para-monitorar-midia-e-redes-sociais.html |
| 10 | FUNHESP/MG | clipping institucional e monitoramento de mídia | R$ 163.200,00 | R$ 60.000,00 | https://querolicitacao.com.br/licitacoes/contratacao-de-servicos-especializados-de-clipping-institucional-e-monitoramento-de-midia/19843929000100-1-000668/2026 |
| 11 | SEFAZ/MT (inexigibilidade) | BROADCAST — conteúdo informacional em tempo real (Agência Estado) | R$ 831.797,28 | — | http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=SEFAZ&licitacao=6065&processo=SEFAZ-PRO-2026/03704 |

**Leitura:** faixa de **R$ 22 mil a R$ 335 mil** por contrato anual, com desconto
de **50–70%** entre estimado e homologado. Objeto simples (clipping) fica na
faixa de R$ 22–63 mil; o que estoura a faixa é **decisão editorial, análise por IA,
relatório de gestão e ouvidoria** — é aí que o ValorPúblico precisa mostrar
diferença (e usar o item 6.2(b) da DN TCU 134/2013 como prova de valor).

**Atenção:** publicar preço para outros fecha a porta da **inexigibilidade**
(IN SEGES/ME 65/2021, art. 7º, §3º). Se a via pretendida for pregão/adesão, isso
não é problema — e é o preço de mercado que sustenta a nossa margem.

## 9. Memória de cálculo (formato do art. 3º da IN 65/2021)

Para anexar ao processo: descrição do objeto · agentes responsíveis · fontes com
data e hora de acesso · série de preços · método (art. 6º) · justificativas ·
memória de cálculo.

Método (art. 6º): média, mediana **ou menor** dos valores, desde que incida sobre
**3 ou mais preços**, descartando inexequíveis, inconsistentes e excessivamente
elevados. Parâmetros em ordem de prioridade (art. 5º): I) mediana do Painel de
Preços; II) contratações similares em até 1 ano; III) mídia especializada;
IV) pesquisa direta com **mínimo 3 fornecedores**; V) base nacional de NF-e.

> Próxima etapa: preencher a tabela da §3 com 3 amostras comparáveis do **mesmo
> escopo** (monitoramento + IA + relatório de gestão) e fixar a mediana.

