# Estudo Técnico Preliminar (ETP) — modelo

> Modelo para contratar o ValorPúblico pela Lei 14.133/2021. Preencha os campos
> entre `[ ]` com os dados da Casa. Base: art. 18, §1º, da Lei 14.133/2021.

## 1. Descrição da necessidade

A `[Câmara Municipal de ... / Assembleia Legislativa de ...]` precisa acompanhar,
de forma contínua e auditável, o que a imprensa, o rádio, a TV e as redes sociais
publicam sobre a Casa, seus órgãos e seus membros, para: (i) informar a Mesa e a
Secretaria de Comunicação; (ii) embasar o relatório de gestão da comunicação;
(iii) atender à Lei de Acesso à Informação (Lei 12.527/2011) e ao dever de
transparência; (iv) transformar comentários e mensagens da população em demandas
agregadas para a Ouvidoria e as comissões.

Hoje o acompanhamento é `[manual / por contrato de clipping / inexistente]`, com
custo de `[R$ ... / mês]` e sem padronização de métricas.

## 2. Área requisitante

`[Secretaria de Comunicação / Presidência]` — fiscal do contrato: `[nome, cargo]`.

## 3. Estimativa da quantidade

| Item | Quantidade estimada |
|---|---|
| Veículos de imprensa monitorados | `[...]` |
| Publicações oficiais monitoradas (radar) | `[Diário Oficial, sites da Casa, portais]` |
| Membros cobertos | `[n]` |
| Usuários do painel | `[n]` (Secom, Presidência, Ouvidoria, Controle, Transparência, leitura) |

## 4. Levantamento de mercado

Soluções gratuitas e de código aberto avaliadas (ver `plano/05`–`08` do projeto):
SearXNG, RSSHub, trafilatura, yt-dlp, GDELT, Wikipédia, rainette/IRaMuTeQ. Nenhuma
delas entrega, pronta, o conjunto de telas, métricas e conformidade exigido — por
isso a contratação é de **serviço** (operação + evolução), não de licença de software.

## 5. Requisitos da contratação

Ver `docs/comercial/TR.md` (requisitos funcionais RF-01…RF-12 e não funcionais
RNF-01…RNF-08).

## 6. Estimativa do valor

Pesquisa de preços em `docs/comercial/PESQUISA_PRECOS.md`. Estimativa:
**R$ `[valor]`/mês** para o pacote `[Clipping / Comunicação / Transparência]`.

## 7. Justificativa para o parcelamento (ou não)

O objeto é **divisível** em três pacotes (Clipping, Comunicação, Transparência &
Ouvidoria). Recomenda-se contratar o pacote **Clipping** primeiro (menor risco e
menor valor) e ampliar por aditivo ou novo pregão.

## 8. Alinhamento com o planejamento da Casa

`[Plano de comunicação / plano de governo digital / metas da Mesa]`.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Dependência de plataformas de terceiros | múltiplas fontes (SearXNG, RSS, APIs oficiais) e "print com data" como prova |
| Vazamento de dados | projeto Firebase próprio, muralha de dados, cláusulas LGPD no TR |
| Continuidade do serviço | plano de saída com exportação total dos dados (CSV/JSON) |
| Mudança de layout dos sites | receitas versionadas + auto-reparo + teste semanal |

## 10. Declaração de viabilidade

`[ ]` A contratação é viável e adequada ao interesse público, com estimativa de
`R$ [valor]/mês`, prazo de `[12]` meses, e não há solução gratuita equivalente que
atenda aos requisitos de auditoria e conformidade exigidos.

Local e data: `[...]` — Responsável: `[nome, cargo, matrícula]`
