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
| Tempo do dono (horas/mês) | `[ ]` h × R$ `[ ]` |

➡️ **Custo direto ≈ R$ 0–40/mês.** O preço pode ser definido pela entrega, não
pelo custo.
