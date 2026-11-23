# Valor Público – Plataforma de Assessoria ao Agente Público

## Visão Geral
Esta documentação reúne todas as informações essenciais da **Versão 100 % focada em assessoria a agentes públicos** da plataforma Valor Público. Ela descreve a stack tecnológica, os objetivos de negócio, o fluxo de trabalho (workflow) geral e as principais funcionalidades que serão implementadas.

---

## Objetivos Principais
1. **Ingestão e Indexação** de clippings, notícias e posts de redes sociais, associados a cada agente público (vereador, prefeito, deputado, senador, governador, etc.).
2. **Análises Lexicais Avançadas**:
   - Nuvem de palavras e grafo de co‑ocorrência.
   - Visualização interativa das relações entre termos.
   - Cada insight aponta a **fonte original** (URL, documento, data) para auditoria.
3. **KPIs de Sentimento** – cálculo automático de sentimento (positivo, neutro, negativo) por agente, com indicadores de tendência temporal.
4. **Release Automático** – geração de relatórios resumidos (diário, semanal, 30 dias, histórico) contendo os principais destaques, gráficos e trechos de origem.
5. **Segurança & Autorização** – agentes veem apenas seus próprios dados; todo acesso é auditável.

---

## Stack Tecnológica (proposta atual)
| Camada | Tecnologia | Comentário |
|--------|------------|------------|
| **Front‑end** | HTML + vanilla JS + CSS (Sem framework) – utiliza **Chart.js** para gráficos e **Google Fonts – Inter** para tipografia premium. | UI responsiva, micro‑animações, tema escuro; fácil integração com API REST. |
| **Back‑end** | Node.js + Express | Servidor RESTful que expõe endpoints para ingestão, análise e relatórios. |
| **Banco de Dados** | MongoDB (ou PostgreSQL com full‑text search) | Armazena documentos normatizados (`source`, `agent_id`, `timestamp`, `content`) e resultados de análises. |
| **NLP / Sentimento** | Bibliotecas Python (NLTK + VADER) ou HuggingFace Transformers (`distilbert-base‑sentiment‑analysis`). A escolha será confirmada com o usuário. |
| **Scheduler** | `node‑cron` (ou Celery beat) | Executa jobs para gerar releases automáticos nos períodos especificados. |
| **Deploy** | Docker containers (frontend, backend, DB) – opcional para produção. |

---

## Fluxo de Trabalho (Workflow) Geral
1. **Coleta de Dados**
   - Scripts/crawlers (APIs de notícias, Twitter, Facebook, etc.) armazenam os documentos na base de dados, já associados ao `agent_id`.
2. **Processamento Lexical**
   - Pipeline NLP tokeniza, lematiza e calcula frequência de termos.
   - Gera grafo de co‑ocorrência (n‑gramas) e nuvem de palavras.
   - Cada token mantém referência ao `document_id` para auditoria.
3. **Análise de Sentimento**
   - Modelo de sentimento classifica cada documento.
   - KPI por agente = média ponderada dos scores, exibido como gauge (positivo/neurto/negativo).
4. **Armazenamento de Resultados**
   - Resultados são persistidos em coleções auxiliares (`lexical_analysis`, `sentiment_kpis`).
5. **Frontend**
   - Usuário seleciona um agente → chamadas API retornam análises, gráficos e lista de fontes.
   - UI mostra nuvem de palavras, grafo, gauge de sentimento e botão para baixar o release.
6. **Release Automático**
   - Scheduler dispara job no período selecionado, compila um HTML (ou PDF) com:
     * Resumo de sentimento.
     * Principais termos e gráficos.
     * Trechos de textos com hyperlinks para as fontes originais.
   - O release é armazenado e pode ser enviado por e‑mail ou visualizado no portal.

---

## Principais Endpoints da API (esboço)
- `POST /api/ingest` – recebe novos clippings/notícias.
- `GET /api/agents` – lista agentes públicos disponíveis.
- `GET /api/analysis/:agentId` – devolve análise lexical e KPI.
- `GET /api/release/:agentId?period=day|week|30d|all` – gera/retorna release.
- `GET /api/source/:docId` – retorna documento original para auditoria.

---

## Considerações de UI/UX
- Tema **dark** com gradientes sutis e cores douradas (#ffd700) para destacar títulos.
- Tipografia **Inter** (Google Font) para leitura confortável.
- Micro‑animações de hover nos links de navegação e botões.
- **Responsivo**: layout adapta‑se a desktop, tablet e mobile.
- Cada gráfico tem tooltip que mostra a quantidade e um link “ver fonte”.

---

## Próximas Etapas (após aprovação)
1. Confirmar as tecnologias de back‑end e de análise de sentimento (responder às perguntas do plano).
2. Gerar o esqueleto do projeto Node.js (package.json, server.js) dentro de `backend/`.
3. Implementar rotas API iniciais e conectar ao banco de dados.
4. Finalizar o front‑end (`index.html`, `style.css`, `app.js`).
5. Desenvolver o pipeline NLP e integrar ao back‑end.
6. Configurar o scheduler para releases automáticos.
7. Testes unitários e de integração; validação manual da UI.

---

> **Nota**: Esta documentação foi criada como artefato para que você possa revisá‑la, compartilhá‑la com a equipe e mantê‑la atualizada ao longo do desenvolvimento.
