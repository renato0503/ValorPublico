# Estratégia de compras públicas — como o governo compra o ValorPúblico

> Pesquisa de 26/11/2026 (fontes primárias: Planalto, base aberta de normativos e
> jurisprudência do TCU, PNCP/Compras.gov.br, portais de compras estaduais).
> Objetivo: definir **por qual via** o Governo compra a plataforma e **o que precisa
> existir** (documento, certificação, registro) para isso.
> Relacionados: `ETP.md`, `TR.md`, `PESQUISA_PRECOS.md`, `PACOTES.md`.

---

## 1. Resumo executivo (decisão)

1. **Não há "decreto do TCU"** que obrigue a prestar contas do atingimento de
   público-alvo, e **nenhuma Instrução Normativa do TCU trata de publicidade
   institucional** (varri os 103 atos do tipo IN). A obrigação **existe, mas é
   indireta** — vem do Relatório de Gestão (TCU) e da auditoria (TCU), e, para o
   Executivo federal, de decreto da Presidência. Ver §4.
2. **A via de entrada NÃO é inexigibilidade.** Para um SaaS de BI/monitoramento,
   inexigibilidade é frágil e cara de sustentar (§3.2). O caminho defensável é:
   **pregão eletrônico** (vencendo por mérito e prova de conceito) → **adesão a ARP
   federal** → **dispensa por valor** para piloto.
3. **O ativo mais subutilizado é a margem de preferência do art. 26, §2º da Lei
   14.133** (serviço nacional com desenvolvimento tecnológico no País = **20%** de
   vantagem) — mais forte que qualquer argumento de exclusividade.
4. **O ativo mais barato e de melhor custo-benefício é o registro do software no
   INPI** (publicação em até 10 dias, validade de 50 anos, 176 países da Convenção
   de Berna). Ele **prova titularidade**, não exclusividade de mercado.
5. **Em Mato Grosso o espaço de exclusividade em comunicação já está ocupado**
   (SEFAZ/MT compra o BROADCAST da Agência Estado por inexigibilidade, R$ 831.797,28;
   a SEPLAG mantém a IONEWS/IOMATNet por inexigibilidade). A porta de entrada
   Competitive é o **pregão**, não a dispensa.
6. **O TCU cria o produto, não só a obrigação:** o item 6.2(b) da Decisão Normativa
   TCU 134/2013 pede "demonstração dos principais resultados das ações de
   publicidade e propaganda". É isso que o ValorPúblico deve entregar: **prova de
   atingimento**, não painel de métrica.

---

## 2. Vias de venda (mapa)

| Via | Quando se aplica | Quem decide | Documento | Prazo | Risco |
|---|---|---|---|---|---|
| **Pregão eletrônico** (serviço comum) | Padrão para SaaS/BI com especificação objetiva | Órgão demandante + pregoeiro; adjudicação pela autoridade competente | Edital + TR no PNCP + DOE + portal do Estado; proposta e habilitação (art. 63) | ~45–60 dias | **Médio**: barra de prova de conceito, atestado e queda de preço de 50–70% |
| **Dispensa por valor** (art. 75, II) | Até **R$ 65.492,11** (limite 2026, Decreto 12.807/2025); somatório do exercício por mesma natureza | Ordenador de despesa | Aviso prévio de 3 dias úteis (art. 75, §3º) + cotação + pesquisa de preços (IN 65, art. 5º) | 7–20 dias | **Baixo/médio** — bom para piloto |
| **Adesão a ARP federal** (art. 86) | Se houver item do seu CATSER registrado em ata federal | Órgão carona + gerenciador + fornecedor | Requerimento de adesão; vantagem demonstrada; aceite do fornecedor | 30–90 dias | **Médio-baixo** — exige estar na ata |
| **Cotação eletrônica** (dispensa eletrônica) | Órgão federal abre cotação a fornecedores | Órgão + SICAF | Proposta no Compras.gov.br | 15–30 dias | Baixo |
| **Contrato de eficiência** (art. 39) | Remuneração pela economia comprovada (o BI de mídia gera economia mensurável) | Órgão | Edital com parâmetro objetivo de medição | 60–120 dias | Médio |
| **Diálogo competitivo** (art. 32) | Requisitos não precisáveis de antemão (IA) | Órgão | Edital com fases de diálogo | 90–150 dias | Médio |
| **Concurso (art. 30) / P&D com cessão de PI (art. 93)** | R&D em parceria com IP cedido ao Estado | Autoridade + comissão | Edital + cessão de direitos patrimoniais | 90–180 dias | **Alto** — bom para P&D, ruim para SaaS proprietário |
| **Convênio / termo de cooperação** (art. 184 + Lei 13.019/2014) | Apenas vitrine técnica | Convenente | Termo + plano de trabalho | 45–120 dias | **Alto** — **não é canal de venda** (cooperação sem quid pro quo) |
| **Inexigibilidade** (art. 74, I) | Só se o Estado já for dependente da solução | Autoridade competente + PGE (parecer prévio) | Atestado de exclusividade + ETP comparando alternativas | 20–60 dias (parecer é o gargalo) | **Alto** — ver §3.2 |

> **Erros que queimam a empresa em diligência** (não usar em proposta): "homologação
> de fornecedor federal" (não existe como etapa do SRP), "Suprimento.gov.br" /
> "Ambiente de Fornecedores" (não existem), "IN 65 art. 35" (a IN 65 tem 11 artigos),
> "art. 30 = P&D/PPP" (art. 30 é **concurso**; PPP é art. 10; P&D é art. 6º, LV e
> art. 75, IV, "c"), "margem de preço federal" (não existe), "CertCloud" /
> "Certificado de Operador de Serviço de Nuvem" / "RFFN" (não confirmados em norma
> federal), "IN SEGES/ME 177/2021 sobre software livre" (não confirmada).

### 2.1 Regras de Mato Grosso

- **Norma:** Lei 14.133/2021 (federal) + **Decreto Estadual nº 1.525, de 23/11/2022**
  (regulamenta a LCC no Estado; MT foi o 2º Estado a fazê-lo). Contratos em curso sob
  a Lei 11.805/2022 seguem o regime antigo até o fim.
  Fontes: https://www.pge.mt.gov.br/-/23040972-governo-de-mt-regulamenta-aplicacao-da-nova-lei-de-compras-publicas
  · https://leisestaduais.com.br/mt/decreto-n-1525-2022-mato-grosso-regulamenta-a-lei-federal-no-14-133-de-1o-de-abril-de-2021-no-ambito-da-administracao-publica-estadual-direta-autarquica-e-fundacional-do-estado-de-mato-grosso
- **Portal oficial:** SIAG/SEPLAG — https://aquisicoes.seplag.mt.gov.br/licitacao-pub/#/consulta-licitacoes
  (licitações), `/compra-direta/` (contratação direta), `/home/index.php?pg=ver&c=2` (atas).
  Transparência: http://consultas.transparencia.mt.gov.br/compras/licitacao/ ·
  DOE: https://www.iomat.mt.gov.br/ · TCE-MT (atas auditadas):
  https://servicos.tce.mt.gov.br/fiscalizado/arp
- **Publicidade:** PNCP (inteiro teor) + DOE + portal próprio (prática do Estado);
  o TCE-MT fiscaliza com o "Manual de Análise de Editais" (jan/2026).
- **Habilitação exigida no edital-modelo** (Pregão Eletrônico 001/2026, CGE/MT —
  "serviços continuados de clipping jornalístico online"):
  **amostra/prova de conceito** (item 10.1, avaliada pelo pregoeiro),
  **Cadastro Geral de Fornecedores do Estado** (item 11.4.3),
  **atestado de capacidade técnica** (11.5.5.3 — atestador fora do grupo
  empresarial, soma de atestados admitida, atestado de matriz via filial),
  regularidade fiscal/trabalhista/jurídica/econômico-financeira (11.5.1–11.5.3),
  9 declarações complementares (11.5.4.1–11.5.4.20), incluindo **declaração de
  ME/EPP** (LC 123/2006, item 11.5.4.9) — que é onde a startup ganha faixa e preço.
  Página do processo: http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=CGE&licitacao=5544&edital=001/2026
  ⚠️ O edital analisado **não traz cláusula LGPD expressa** — o risco de dados é
  nosso e precisa ser endereçado no TR (ver `TR.md` §9).

---

## 3. Inexigibilidade: o que sustenta e o que não sustenta

### 3.1 O que a lei exige

- **Art. 74, I e §1º da Lei 14.133/2021**: é inexigível quando "só possam ser
  fornecidos por produtor, empresa ou representante comercial exclusivos"; a
  Administração demonstra a inviabilidade de competição "mediante atestado de
  exclusividade, contrato de exclusividade, declaração do fabricante ou outro
  documento idôneo capaz de comprovar que o objeto é fornecido ou prestado por
  produtor, empresa ou representante comercial exclusivos, **vedada a preferência por
  marca específica**".
- **Art. 40, §3º, III**: a exclusividade pode decorrer de **processo de padronização**
  (arts. 43 e 47, I) — é a via legal para tornar uma solução padronizada.
- **IN SEGES/ME 65/2021, art. 7º, §3º**: "Fica vedada a contratação direta por
  inexigibilidade caso a justificativa de preços demonstre a possibilidade de
  competição." → publicar preço para outros fecha esta porta.
- **IN SEGES/ME 67/2021, art. 7º** e **Lei 14.133, art. 23, §4º**: a justificativa de
  preço em inexigibilidade vem de NF-e/contratos idênticos ou semelhantes nos 12
  meses anteriores (ou, se nunca vendeu, de objetos semelhantes).
- Manual do TCU (5.10.1.1): https://licitacoesecontratos.tcu.gov.br/5-10-1-1-fornecedor-exclusivo-inciso-i/

### 3.2 O que tem (e não tem) valor jurídico

| Ativo | Serve para | **Não** serve para | Valor |
|---|---|---|---|
| **Atestado de exclusividade** (emissor idôneo: sindicato/federação/confederação; ABES emite para Associadas) | Prova de contexto | **Não** substitui a demonstração do art. 74, §1º. **TCU: "a demonstração de exclusividade de marca não comprova, por si só, o requisito de inviabilidade de competição"** (Acórdão 6875/2021-2ªC) | Baixo |
| **Registro de software no INPI** | Prova de autoria/titularidade; publicado em até 10 dias após pagamento; validade de 50 anos; válido no Brasil + 176 países (Convenção de Berna) | **Não** comprova exclusividade de mercado; **não** habilita dispensa | **Alto, e o mais barato** — https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-basico |
| **Patente** (invenção ou modelo de utilidade) | Exclusividade técnica **real**, se cobrir o objeto e não houver licenciados/alternativas | Software "em si" **não** é patenteável (Lei 9.279/1996, art. 10, V); licença compulsória é **não exclusiva** (arts. 71, 72); **TCU: é irregular contratar detentor de patente por inexigibilidade se há outras empresas autorizadas a commercializar** (Acórdão 2950/2020-Plenário) | Baixo-médio (risco alto de inadmissibilidade no caso de IA) |
| **"Certificado de dependência"** | Documento **do órgão público** atestando dependência do *seu* sistema legado | Não é exclusividade sua; e a **IN SGD/ME 94/2022, item 1.4.1** manda *minimizar* a dependência tecnológica (padrões abertos, migração) | **Prejudica a sua tese** |
| **Software livre / padrões abertos** | — | Uso de componente substituível **destrói** a alegação de exclusividade | — |

**Conclusão:** para sustentar inexigibilidade de software, o que tem mais valor é um
**conjunto probatório**: (i) pesquisa de mercado que demonstre inexistência de
alternativa (IN 65, art. 5º), (ii) padronização/compatibilidade com sistemas já
adotados pelo Estado, (iii) licença/patente **sem** licenciados ou alternativas.
**Nunca** um selo isolado.

### 3.3 Regras de risco (TCU)

- **Súmula 255-TCU**: é dever do agente público confirmar a veracidade da
  documentação de exclusividade.
- **Acórdão 2.993/2018-Plenário** e **ON AGU 17/2011**: preço de inexigibilidade se
  justifica comparando o preço com o praticado pelo contratado junto a outros
  entes públicos e privados.
- **Acórdão 555/2016-Plenário**: contrato por inexigibilidade **não** deve ser
  prorrogado sem reavaliar a inviabilidade de competição.
- **Acórdão 3412/2012-1ªC**: o gestor deve ir além do atestado e verificar se de fato
  não há solução concorrente.
- **Acórdão 1.508/2017-1ªC**: irregularidade em "pagamentos por serviços cuja
  execução não ficou demonstrada" (publicidade).
- **Art. 73 da Lei 14.133**: contratação direta indevida → **responsabilidade
  solidária** do contratado e do agente público pelo dano ao erário.
- **IN SGD/ME 94/2022, art. 5º, XII**: é **vedado aceitar autodeclaração de
  exclusividade** como prova suficiente (aceitável como elemento, não como
  demonstração).

---

## 4. A obrigação do TCU sobre o atingimento de público-alvo (a pergunta "do decreto do TCU")

**Resposta: existe, mas é indireta, e não existe decreto do TCU.** Três camadas:

### 4.1 Camada A — o TCU e o Relatório de Gestão

> **Decisão Normativa TCU nº 134/2013, item 6.2** (texto conferido no documento
> oficial do TCU; mesma redação na DN 127/2013):
> *"6.2. Informações sobre despesas com ações de publicidade e propaganda,
> contemplando: a) classificação em publicidade institucional, legal,
> mercadológica, de utilidade pública, incluindo os respectivos beneficiários, bem
> como os respectivos custos; **b) demonstração dos principais resultados das ações
> de publicidade e propaganda para os objetivos da unidade jurisdicionada**."*

Origem: **Acórdão 39/2003-Plenário, item 9.4(b)** — os Relatórios de Auditoria de
Gestão devem conter, em título específico, análise e avaliação da gestão da
política de comunicação social, destacando "a correta aplicação dos recursos
orçamentários e **o atingimento dos objetivos previstos**".

Vigência atual do item (conteúdo obrigatório do Relatório de Gestão):
**Portarias TCU 59/2017** e **65/2018** ("Informações sobre ações de publicidade e
propaganda"), **Portaria TCU 321/2015, item 9.14**, e o **Quadro A.6.2 – Despesas
com Publicidade** da **Portaria TCU 90/2014**.

Links:
- DN 134/2013 (item 6.2): https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/download?key=NORMA-20376
- DN 127/2013: https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/download?key=NORMA-20369
- Portaria TCU 90/2014: https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/download?key=NORMA-19181
- Portaria TCU 321/2015: https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/documento/download?key=NORMA-19249
- Portaria TCU 59/2017: https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/download?key=NORMA-18958
- Portaria TCU 65/2018: https://pesquisa.apps.tcu.gov.br/rest/publico/base/norma/documento/download?key=NORMA-19724
- Base aberta de normativos do TCU (texto integral): https://sites.tcu.gov.br/dados-abertos/normas/

### 4.2 Camada B — o TCU na fiscalização (o que se prova em auditoria)

- **Acórdão 2.062/2006-Plenário, itens 9.1.3.6 e 9.1.4**: implantar mecanismos
  efetivos de controle "para comprovar a execução dos serviços"; "estude a
  possibilidade de contratar serviços de auditoria independente com vistas a aferir
  a **efetiva execução quantitativa** dos serviços subcontratados, como, por
  exemplo, o número de veiculações, de tiragens etc., **ou crie mecanismos
  efetivos de prestação de contas da execução desses serviços**".
  Base: https://sites.tcu.gov.br/dados-abertos/jurisprudencia/arquivos/acordao-completo/acordao-completo-2006.csv
- **Acórdão 822/2014-Plenário**: procedimento de controle contra fraude em veículos
  "não monitorados por meio de **relatório de checagem**".
  Base: https://sites.tcu.gov.br/dados-abertos/jurisprudencia/arquivos/acordao-completo/acordao-completo-2014.csv
- **Acórdão 1.508/2017-1ªC**: "pagamentos por serviços cuja execução não ficou
  demonstrada".
  https://pesquisa.apps.tcu.gov.br/rest/publico/base/acordao/documento/download?key=ACORDAO-COMPLETO-2283405
- **Acórdão 1.965/2017-Plenário** (TC 017.652/2017-0): nulidade de concorrência da
  Secom/PR com item "1.1.3.3 **Clipping nacional**" — mostra o objeto em escala
  federal.
  https://pesquisa.apps.tcu.gov.br/rest/publico/base/acordao/documento/download?key=ACORDAO-COMPLETO-2280722

### 4.3 Camada C — o "decreto" (da Presidência, não do TCU; só Executivo federal)

- **Decreto 4.799/2003** (revogado pelo 6.555/2008), arts. 3º, VI e 7º, X:
  Secom deveria "coordenar o processo de **avaliação dos resultados** das ações de
  comunicação de governo e do desempenho das empresas contratadas".
  https://www.planalto.gov.br/ccivil_03/decreto/2003/d4799.htm
- **Decreto 6.555/2008, art. 10-D** (alterado pelo **Decreto 12.065/2024**): para
  **pagamento** das despesas de veiculação devem constar NF da agência, valor
  devido ao veículo, tabela de preços, descontos negociados, **os pedidos de
  inserção** e, "sempre que possível, **relatório de checagem a cargo de empresa
  independente**".
  https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/decreto/D6555.htm ·
  https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/decreto/D12065.htm
- **Lei 12.232/2010, art. 2º, §1º, I**: admite como atividade complementar
  "serviços especializados... de pesquisas e de outros instrumentos de avaliação e
  de geração de conhecimento sobre o mercado, **o público-alvo**, os meios de
  divulgação... **ou sobre os resultados**" → cria o objeto licitável
  "medição/estudo de público-alvo".
  https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12232.htm

### 4.4 O que isso significa para o produto

O TCU pede **literalmente** o que o ValorPúblico já produz em outro formato. Para
virar "prova de atingimento" (e justificar preço acima da média de clipping), o
produto precisa entregar:

1. **Item 6.2(b) pronto**: relatório de gestão da publicidade institucional
   exportável (PDF/CSV), no formato do Quadro A.6.2, com ementa legal ao pé.
2. **Comprovação de execução quantitativa**: pedido de inserção (AI) ↔ veiculação ↔
   audiência/tiragem ↔ tabela de preços e descontos ↔ nota fiscal — o rol do
   art. 10-D — para **liberação de pagamento**.
3. **Trilha de auditoria imutável** e % de veiculações com checagem (Acórdão
   822/2014-P).
4. **Benchmark de atingimento** entre órgãos de mesmo porte: sem parâmetro
   comparativo, "atingimento" não é aferível.
5. **Rótulo permanente de hipótese**: simulação (IA) não é pesquisa — o que o TCU
   audita é a veiculação real, não a reação das personas.

---

## 5. Certificações e registros (plano priorizado, 12 meses)

| # | Item | Custo aprox. | Prazo | Quem pede / para que serve |
|---|---|---|---|---|
| 1 | **ISO/IEC 27001:2022** | R$ 25–60 mil | 6–12 meses | **Exigível** em contrato de nuvem/SaaS: IN SGD/ME 94/2022, item 4.2.1 ("certificações de normas de segurança da informação aplicáveis ao objeto", com justificativa prévia, na assinatura do contrato). Critério de julgamento em editais de SaaS/BI. *Valores são estimativas de mercado — cotar com 3 certificadoras acreditadas (INMETRO/RBC).* |
| 2 | **Pacote LGPD** (DPA controlador–operador, RIPD, encarregado nomeado e publicado, política de privacidade, política de retenção) | baixo (horas) | 1–2 meses | **Obrigatório** em todo edital de TI: LGPD arts. 39, 41 e 46; IN SGD/ME 94/2022, item 7.1 ("requisitos e obrigações de Segurança da Informação e Privacidade — SIP") |
| 3 | **Registro do software no INPI** (app + módulo de IA) | tabela INPI | **até 10 dias** | Prova de titularidade em due diligence, negociação de preço e disputa de autoria |
| 4 | **ISO/IEC 27701** | R$ 15–40 mil | 4–8 meses | Privacidade (monitora dados de cidadãos e de comentários) |
| 5 | **eMAG / ABNT NBR 17225** (acessibilidade) | baixo-médio | 2–4 meses | Requisito de homologação; risco de impugnação |
| 6 | **ISO/IEC 20000-1** (ITSM) | R$ 20–45 mil | 4–8 meses | SLA, suporte e garantia de atendimento |
| 7 | **ISO/IEC 42001** (gestão de IA) | R$ 30–70 mil | 5–9 meses | Diferenciação comercial do produto com IA; alinha à política pública de IA |
| 8 | ISO 22301 / ISO 9001 / ISO 14001 | R$ 15–45 mil cada | 4–9 meses | Score de qualidade; 14001 tem retorno baixo para este objeto |

**Não priorizar:** ISO 27017/27018 como projeto separado (usar como evidência
complementar do 27001) e ISO 14001.

**Margem de preferência (art. 26, §2º da Lei 14.133):** serviços nacionais
resultantes de **desenvolvimento e inovação tecnológica no País** têm 20% de
preferência. Dossiê mínimo: memória de desenvolvimento no Brasil (repositório,
commits, equipe, PI), nota fiscal de cliente público brasileiro e enquadramento
como "serviço nacional".
https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/margem-de-preferencia

**Normas de TIC que valem mais que selo** (o que o órgão realmente lê):
- **IN SGD/ME 94/2022** (contratação de soluções de TIC): item 4.2.1 (certificações
  de segurança), item 7.1 (SIP no TR), item 5º (vedações: homem-hora, referência a
  regras do fabricante, entidade certificadora específica, autodeclaração de
  exclusividade), item 1.4.1 (minimizar dependência tecnológica).
  https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/processo-de-contratacao-de-solucoes-de-tic-regido-pela-lei-ndeg-14-133-de-2021
- **IN SEGES/ME 65/2021** (pesquisa de preços): art. 5º (parâmetros), art. 6º
  (método), art. 7º, §3º (vedação de inexigibilidade se o preço demonstrar
  competição), art. 8º (PMC-TIC/catálogo).
- **Portaria SGD/MGI 5.950/2023**: modelo de contratação de software e serviços de
  computação em nuvem no SISP (obrigatório desde 30/04/2024; Anexo I exige
  certificações de segurança da informação do provedor).
  https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/modelo-de-contratacao-de-software-e-servicos-em-nuvem/vigentes/portaria-sgd-mgi-no-5-950-de-26-de-outubro-de-2023
- **Diretrizes Gerais para Contratações de TIC (SGD, v.6)**: item 1.1.1 — não é
  aceitável justificar padronização pela restrição a um único fabricante sem ETP
  com pesquisa e comparação efetiva de alternativas (Acórdão 248/2017-Plenário).

---

## 6. Mercado real: licitações do mesmo objeto (benchmarks)

| Órgão | Objeto | Valor | Link |
|---|---|---|---|
| **CGE/MT** | "serviços continuados de clipping jornalístico online" | est. R$ 132.902,40 → **R$ 38.160,00** | http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=CGE&licitacao=5544&edital=001/2026 |
| **SEFAZ/MT** (inexigibilidade) | BROADCAST (Agência Estado S/A) — conteúdo informacional em tempo real | R$ 831.797,28 | http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=SEFAZ&licitacao=6065&processo=SEFAZ-PRO-2026/03704 |
| **SEPLAG/MT** (inexigibilidade) | IONEWS / IOMATNet | — | http://consultas.transparencia.mt.gov.br/compras/licitacao/resultado_2.php?ano=2026&orgao=SEPLAG&licitacao=6936&processo=SEPLAG-PRO-2026/19307 |
| **TST — 11ª Região** | clipping + monitoramento e **mensuração** | R$ 54.000,00 | https://pncp.gov.br/app/contratacoes/00509968000148-1-001376/2026 |
| **TRF 5ª Região** | "monitoramento de mídia – Clipping Eletrônico e Mensuração" | R$ 40.590,00 | https://pncp.gov.br/app/contratacoes/00508903000188-1-000274/2026 |
| **TCU** | clipping de matérias | R$ 47.520,00 | https://pncp.gov.br/app/contratacoes/00414607000118-1-000040/2025 |
| **IF São Paulo** | clipping + monitoramento + gestão estratégica + análise de conteúdo | est. R$ 63.879,48 → R$ 22.776,00 | https://pncp.gov.br/app/contratacoes/10784782000150-1-000427/2026 |
| **ANVISA** | monitoramento de matérias jornalísticas | est. R$ 62.725,56 → R$ 33.240,00 | https://pncp.gov.br/app/contratacoes/03112386000111-1-000001/2026 |
| **Prefeitura de São Luís/MA** | clipping e monitoramento de mídia (impresso, rádio, TV, digitais) | R$ 334.800,00 | https://buscarlicitacao.com.br/licitacao/ma/sao-luis/06307102000130-1-000080/2026/edital-no-90018-2026 |
| **TJMS** | monitoramento de mídia e redes sociais | ~R$ 147 mil (SUSPENSO em 21/09/2026) | https://www.jd1noticias.com/transparencia/2026/09/21/tjms-suspende-licitacao-de-r-147-mil-para-monitorar-midia-e-redes-sociais.html |
| **FUNHESP/MG** | clipping institucional e monitoramento de mídia | est. R$ 163.200,00 → R$ 60.000,00 | https://querolicitacao.com.br/licitacoes/contratacao-de-servicos-especializados-de-clipping-institucional-e-monitoramento-de-midia/19843929000100-1-000668/2026 |

**Leitura de preço:** faixa de **R$ 22 mil a R$ 335 mil** por contrato anual, com
desconto de **50–70%** entre estimado e homologado. O serviço de "prova de
atingimento" é comprado quase sempre por dispensa e na faixa de R$ 12 mil–R$ 65 mil:
**não existe, na prática, um mercado grande de mensuração** — quem fatura é a
agência de propaganda (contrato-mãe) ou o clipping, e o TCU aceita relatório de
checagem de terceiro (art. 10-D).

**Duas conclusões estratégicas:**
1. O objeto de IA/monitoramento **já é o que a CGE-MT comprou** — o diferencial não
   é o objeto, é a execução (prova de conceito, SLA, relatório que já serve ao
   Relatório de Gestão).
2. Em MT, **exclusividade em comunicação já está ocupada** por incumbentes
   contratados por inexigibilidade. Disputar exclusividade é_axes para o lugar
   errado.

---

## 7. Plano de 90 dias

| Prazo | Ação | Fundamento |
|---|---|---|
| **Dias 1–30** | Habilitação: Cadastro Geral de Fornecedores do Estado de MT + cadastro no SIAG + SICAF (Níveis I–II) + kit de 9 declarações + **2 atestados de capacidade técnica** + **dossiê de prova de conceito** (item 10.1 do edital da CGE) | edital CGE/MT 001/2026 |
| **Dias 1–30** | Publicar o pacote LGPD (DPA, RIPD, encarregado, política de privacidade) e registrar o software no INPI | IN SGD/ME 94 item 7.1; INPI |
| **Dias 15–45** | Mapear seu SaaS para 1–2 CATSER e verificar 3 ARPs federais com item de BI/analítica; se houver, entrar como fornecedor; se não, se candidatar ao próximo Pregão Nacional/SRP | art. 86; Decreto 11.462/2023 |
| **Dias 15–45** | Montar o **price book** no formato do art. 3º da IN 65 (mediana do Painel de Preços + 3 contratos similares + 3 orçamentos + NF-e), com memòria de cálculo | IN 65 arts. 3º, 5º, 6º — ver `PESQUISA_PRECOS.md` |
| **Dias 30–60** | Mapear 20 editais-alvo (PNCP + SIAG) e extrair a matriz real de requisitos → backlog de certificação | IN 94 item 4.2.1 |
| **Dias 30–60** | Dossiê da margem de preferência do art. 26, §2º (desenvolvimento no Brasil + NF de cliente público) | art. 26 |
| **Dias 45–75** | Assumir o TCU como proposta de valor: protótipo do "relatório de atingimento" (item 6.2(b) DN TCU 134/2013) + trilha de auditoria + reconciliação AI ↔ veiculação ↔ NF (art. 10-D) | §4 |
| **Dias 60–90** | Replicar o playbook em MS e MA (modelos TJMS e São Luís) e propor contrato de eficiência (art. 39) / diálogo competitivo (art. 32) a um órgão com despesa recorrente de mídia | benchmarks §6 |
| **Contínuo** | Monitorar PNCP + atas do Estado/região; reconstruir o price book a cada trimestre | IN 65 art. 5º |

---

## 8. Riscos e o que não fazer

- **Não** sustentar tese de exclusividade com selo, marca ou registro de INPI.
- **Não** publicar preço de forma que demonstre competição se a via pretendida for
  inexigibilidade (IN 65, art. 7º, §3º).
- **Não** usar convênio como canal de venda.
- **Não** citar em proposta: "homologação de fornecedor federal", "CertCloud",
  "IN 65 art. 35", "art. 30 = P&D", "margem de preço federal".
- **Não** deixar a proposta depender da exclusividade: ela depende de
  **prova de conceito** e de **case público**.
- **Não** prometer "relatório de eficiência" com nome que não existe na norma: o
  termo legal é "**demonstração dos principais resultados das ações de publicidade
  e propaganda**" (item 6.2(b) da DN TCU 134/2013).
- **Risco de dados:** o edital da CGE/MT não traz cláusula LGPD expressa — o risco é
  nosso; o TR (`TR.md` §9) precisa endereçar controlador/operador, retenção e
  exclusão.

---

## 9. Fontes

**Lei e decreto**
- Lei 14.133/2021: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm
- Decreto 12.807/2025 (limites 2026): https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/D12807.htm
- Decreto 11.462/2023 (SRP/IRP): https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/D11462.htm
- Decreto 6.555/2008 (art. 10-D) e Decreto 12.065/2024: https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/decreto/D6555.htm
- Decreto 4.799/2003: https://www.planalto.gov.br/ccivil_03/decreto/2003/d4799.htm
- Lei 12.232/2010 (publicidade): https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12232.htm
- Lei 13.709/2018 (LGPD): https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm

**TCU**
- Manual de Licitações e Contratos — 5.10.1.1 Fornecedor exclusivo: https://licitacoesecontratos.tcu.gov.br/5-10-1-1-fornecedor-exclusivo-inciso-i/
- Dados abertos de normativos (texto integral): https://sites.tcu.gov.br/dados-abertos/normas/
- Dados abertos de jurisprudência (1992–2026): https://sites.tcu.gov.br/dados-abertos/jurisprudencia/
- Pesquisa integrada: https://pesquisa.apps.tcu.gov.br/pesquisa/acordao-completo
- Manual de Análise de Editais (TCE-MT, jan/2026): https://www.tce.mt.gov.br/noticias/tce-mt-divulga-manual-de-analise-de-editais-para-orientar-contratacoes-publicas/61808

**Governo federal (TIC)**
- IN SGD/ME 94/2022: https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/processo-de-contratacao-de-solucoes-de-tic-regido-pela-lei-ndeg-14-133-de-2021
- IN SEGES/ME 65/2021: https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-65-de-7-de-julho-de-2021
- Portaria SGD/MGI 5.950/2023 (nuvem): https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/modelo-de-contratacao-de-software-e-servicos-em-nuvem/vigentes/portaria-sgd-mgi-no-5-950-de-26-de-outubro-de-2023
- Diretrizes Gerais para Contratações de TIC (v.6): https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/todos-os-modelos-diretrizes-e-orientacoes-para-contratacao-de-solucoes-de-tic
- Catálogos de Soluções de TIC com Condições Padronizadas: https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/catalogos-de-solucoes-de-tic-com-condicoes-padronizadas-para-licenciamento-de-software
- Catálogo CATSER/CATMAT: https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/catalogo
- SICAF Digital: https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/sicaf-digital
- Pesquisa de Preços / Painel de Preços: https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/pesquisa-de-precos
- Margem de preferência: https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/margem-de-preferencia
- PNCP: https://pncp.gov.br/app/editais · API: https://compras.dados.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133

**Propriedade intelectual e certificações**
- INPI — registro de programas de computador: https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-basico
- INPI — custos: https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/custos
- ISO/IEC 27001: https://www.iso.org/standard/27001 · ISO/IEC 42001: https://www.iso.org/standard/81230.html
- ANPD: https://www.gov.br/anpd/pt-br/assuntos/regulacao

**Mato Grosso**
- Decreto Estadual 1.525/2022: https://leisestaduais.com.br/mt/decreto-n-1525-2022-mato-grosso-regulamenta-a-lei-federal-no-14-133-de-1o-de-abril-de-2021-no-ambito-da-administracao-publica-estadual-direta-autarquica-e-fundacional-do-estado-de-mato-grosso
- SIAG/SEPLAG: https://aquisicoes.seplag.mt.gov.br/ · Transparência MT: http://consultas.transparencia.mt.gov.br/compras/licitacao/
- DOE-MT: https://www.iomat.mt.gov.br/

**Setor**
- ABES — "A contratação de empresas de tecnologia por inexigibilidade de licitação"
  (Daniella Caverni, 10/07/2024): https://abes.org.br/a-contratacao-de-empresas-de-tecnologia-por-inexigibilidade-de-licitacao/
- ABES — Guia de Compras Públicas para Startups: https://abes.org.br/compras-publicas-startups/

---

## 10. Pendências

1. 👤 **Decisão do dono sobre a via prioritária**: pregão primeiro (com prova de
   conceito) ou ARP federal como entrada (sem disputa)? Depende de haver ou não
   case público — sem case, a amostra/prova de conceito é a barreira.
2. 👤 **Concluir a habilitação** (Cadastro Geral de Fornecedores do Estado,
   SICAF, atestados, prova de conceito) — sem isso nenhuma licitação é ganhabil.
3. 👤 **Cotar as certificações** (3 certificadoras acreditadas INMETRO/RBC) e
   decidir a ordem: 27001 primeiro.
4. 👤 **Decidir o escopo do módulo "prova de atingimento"** (item 6.2(b) da DN TCU
   134/2013): quanto disso entra no produto e quanto vira serviço.
5. 👤 **API de personas fora do ar — decisão tomada.** O plano **Blaze** foi desligado em 26/11/2026
   e o Cloud Run da `personas-api` responde **500** (simulador de discurso e chat com as personas).
   **Decisão do dono: manter desligado até resolver a venda** — não religar o Blaze, não migrar
   agora. Quando o negócio for decidido, as opções continuam sendo: religar o Blaze com alerta de
   orçamento, migrar para **Cloud Functions do Firebase (Spark)** (a RAG pesa 0,3 MB) ou Render Free.
   Antes de qualquer demonstração a um cliente: desligar o botão com mensagem honesta (ou remover a
   meta `personas-api` do `frontend/index.html`), para não haver clique que só devolve erro.
