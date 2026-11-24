# Pacotes e contratação — ValorPúblico (órgão)

> Planos 12 §6.2 e 06 §8 (E7). Contratação pela **Lei 14.133/2021**: serviço
> comum de TI/comunicação → pregão eletrônico, dispensa por valor (art. 75, II) ou
> adesão a ata de registro de preços.

## 1. Pacotes por casa

| Pacote | Inclui | Para quem |
|---|---|---|
| **Clipping** | edição diária (V1), clipping oficial (V2), boletim/newsletter (R-07), relatório de gestão (R-06) | Secom |
| **Comunicação** | + Imagem da Casa (V3), contas institucionais (V7), análise lexical da Casa (V6), discurso institucional, tendências (V9) | Secom + Presidência/Mesa |
| **Transparência & Ouvidoria** | + Ouvidoria (V5), WhatsApp da Ouvidoria, dados abertos (R-09), conformidade de publicidade (V8), relatório de SLA (R-08) | Ouvidoria + Controle Interno + Transparência |

## 2. Documentos que precisam existir antes da 1ª reunião

| Documento | Status | Onde |
|---|---|---|
| **ETP** (Estudo Técnico Preliminar) | ✅ modelo pronto | `docs/comercial/ETP.md` |
| **TR** (Termo de Referência) | ✅ modelo pronto | `docs/comercial/TR.md` |
| **Pesquisa de preços** (IN SEGES 65/2021) | ⏳ método pronto; contratos do PNCP a preencher | `docs/comercial/PESQUISA_PRECOS.md` |
| **Cláusulas LGPD** (órgão controlador, nós operadores) | ✅ no TR | `docs/comercial/TR.md` §9 |
| **Acessibilidade (eMAG)** | ✅ declarada | `docs/comercial/TR.md` §10 |
| **SLA e relatório de SLA** | ✅ definidos | `docs/comercial/TR.md` §7 |
| **Dados abertos** | ✅ opcional no pacote | `docs/comercial/TR.md` §11 |

## 3. O que o órgão precisa fornecer

1. CNPJ e dados da Casa (para o contrato).
2. Indicação do fiscal do contrato e do gestor da Secom.
3. Acesso à Ouvidoria (para o encaminhamento das demandas).
4. Número de WhatsApp institucional (Cloud API) — se contratar Transparência.
5. Contas institucionais (Página/Instagram) para conectar (V7).

## 4. Fontes de pesquisa de preços (gratuitas)

- **PNCP** — Portal Nacional de Contratações Públicas: contratos de clipping de
  outras casas. API pública em `https://pncp.gov.br/api/consulta`.
- **Compras.gov.br** — atas de registro de preços de comunicação.
- **Transparência das Câmaras** — contratos vigentes de assessoria de imprensa.
- Entrevistas com 3 fornecedores (IN 65/2021, art. 5º, III).

## 5. Diferenciais honestos

| Diferencial | Como provamos |
|---|---|
| Custo de software **R$ 0** | roda em GitHub Actions (grátis), Firestore Spark e Ollama local |
| Nada de API paga | sem Serper/SerpAPI/OpenAI no `.env`/secrets |
| Dados da Casa separados | projeto Firebase próprio + muralha de dados (plano 12 §5) |
| Auditoria completa | `auditoria/*` com quem viu/exportou o quê |
| Impessoalidade | sem discurso por membro, sem ranking, visibilidade equitativa (K-43) |

## 6. O que NÃO prometemos

- Inteligência individual de campanha para nenhum membro (cláusula contratual).
- Cobertura total de veículos.
- Substituir a assessoria jurídica na análise de conformidade: o alerta cita o
  artigo e pede revisão humana.
