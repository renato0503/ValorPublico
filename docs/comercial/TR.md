# Termo de Referência (TR) — modelo

> Modelo para o ValorPúblico pela Lei 14.133/2021. Preencha os campos `[ ]`.

## 1. Objeto

Contratação de serviço de **monitoramento de mídia e inteligência de comunicação**
para a `[Casa]`, incluindo clipping oficial, painel de imagem institucional,
gestão de demandas da Ouvidoria e relatórios de gestão, conforme especificações
abaixo.

## 2. Justificativa

Ver `docs/comercial/ETP.md`.

## 3. Especificação técnica (requisitos funcionais)

| ID | Requisito | Critério de aceite |
|---|---|---|
| RF-01 | Clipping diário de imprensa, TV/rádio, impresso e sites oficiais | ≥ 90% dos veículos da lista contratada com item quando houver publicação |
| RF-02 | Edição do dia com seleção editorial e envio de boletim | boletim gerado em < 1 min após a seleção |
| RF-03 | Painel de imagem institucional (saldo de opinião, série, projeção) | atualização diária; projeção com faixa de 80% |
| RF-04 | Análise lexical da Casa (grupos de assuntos, mapa de proximidade, rede de palavras) | relatório semanal com texto explicativo de cada gráfico |
| RF-05 | Parlamentares com **visibilidade equitativa** (sem ranking) | ordem alfabética por padrão; índice de equidade (K-43) exibido |
| RF-06 | Ouvidoria: demandas por tema e bairro, encaminhamento a comissões | demanda percorre nova → encaminhada → respondida |
| RF-07 | Redes institucionais (Página/Instagram/YouTube) com métricas e comentários | contas conectadas pela API oficial |
| RF-08 | Conformidade de publicidade institucional (art. 37 §1º CF, art. 73 Lei 9.504) | cada alerta cita o artigo; parecer exportável |
| RF-09 | Relatório de gestão mensal/anual (R-06) e de SLA (R-08) | PDF em A4, com "como ler este relatório" |
| RF-10 | Log de auditoria de acesso e exportação | consulta por usuário, data e tipo |
| RF-11 | Dados abertos (CSV/JSON) dos indicadores públicos | atualização mensal |
| RF-12 | Exportação total dos dados ao final do contrato | CSV/JSON + dicionário de campos |

## 4. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | Painel web responsivo (desktop 1440 px e celular 390 px), dois temas (claro/escuro) |
| RNF-02 | Contraste WCAG AA (≥ 4,5:1) em todo texto |
| RNF-03 | Tempo de disponibilização (SLA) mediano ≤ 60 min da publicação ao painel |
| RNF-04 | Disponibilidade mensal ≥ 99% (fora de manutenção programada) |
| RNF-05 | Custo de software de terceiros = R$ 0 (sem API paga) |
| RNF-06 | Dados hospedados em projeto dedicado da Casa, com backup |
| RNF-07 | Acessibilidade eMAG (Modelo de Acessibilidade em Governo Eletrônico) |
| RNF-08 | Suporte em horário comercial, com canal registrado |

## 5. Modelo de execução

Serviço continuado, com rotinas automáticas diárias (coleta e métricas) e
semanais (relatório e discurso institucional). A geração de texto por IA é
**assistiva**: todo material leva o selo "Rascunho gerado por IA — revisar antes
de usar" e a Casa mantém a decisão editorial.

## 6. Prazo

`[12]` meses, prorrogável por igual período, conforme art. 107 da Lei 14.133/2021.

## 7. SLA e relatório de SLA

| Indicador | Meta | Consequência |
|---|---|---|
| Disponibilização (RNF-03) | mediana ≤ 60 min | relatório mensal R-08 |
| Disponibilidade (RNF-04) | ≥ 99% | relatório mensal R-08 |
| Cobertura de veículos (K-61) | ≥ 90% da lista | relatório mensal |

## 8. Preço e pagamento

Valor mensal de **R$ `[valor]`**, pago após o relatório de SLA do mês, com nota
fiscal. Reajuste anual pelo IPCA.

## 9. Proteção de dados (LGPD)

- O **órgão é controlador**; a **contratada é operadora** (art. 5º, VI e VII, da LGPD).
- Finalidade: monitoramento de imagem institucional e atendimento à população.
- Dados de cidadãos em comentários: coletados apenas quando públicos; usados de
  forma agregada nos relatórios; excluídos a pedido (art. 18, VI).
- Retenção: 90 dias para o bruto; agregados sem identificação por prazo indeterminado.
- A contratada não usa os dados para finalidade própria nem os compartilha.
- Incidentes: comunicação ao órgão em até 24 h.
- Ao final do contrato: exportação total e exclusão dos dados, com termo.

## 10. Acessibilidade

Atendimento ao eMAG: navegação por teclado, contraste AA, textos alternativos,
respeito a `prefers-reduced-motion`.

## 11. Dados abertos (opcional)

Publicação mensal, no portal da transparência da Casa, dos indicadores públicos
de comunicação (cobertura, imagem, valor da mídia espontânea, SLA), em CSV/JSON,
sem dados pessoais.

## 12. Fiscalização

Fiscal do contrato: `[nome, cargo]`. Gestor: `[nome, cargo]`. Reunião mensal de
acompanhamento com o relatório de SLA.

## 13. Sanções

Conforme arts. 155–163 da Lei 14.133/2021.

Local e data: `[...]` — Responsável: `[nome, cargo]`
