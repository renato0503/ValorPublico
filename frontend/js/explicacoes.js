/**
 * Explicações para leigos (plano 17).
 *
 * Um objeto por código K- (KPIs), G- (gráficos), T- (tabelas) e R- (relatórios).
 * Cada entrada tem:
 *   nome        — nome amigável (o técnico vai no subtítulo/tooltip)
 *   oQueE       — 1 frase: o que é
 *   comoLer     — 1 frase: como ler
 *   porque      — 1 frase: por que importa
 *   valor       — texto alternativo quando o app é o Valor Público ("a Casa")
 *   formula     — "como calculamos" (opcional, entra no nível 3 do cartão)
 *
 * Regras do plano 17 §12:
 *   - frases de até 20 palavras; total ≤ 300 caracteres;
 *   - sem sigla sem explicação (SoV, AVE, CHD, AFC, IC, SLA, KPI).
 *
 * Uso:
 *   import { explicacao, nomeAmigavel, registrarExplicacoes } from "./explicacoes.js";
 *   explicacao("K-03");   // -> { nome, oQueE, comoLer, porque, ... }
 */

export const PRODUTO = (() => {
  try {
    return document.body?.dataset?.produto === "valor" ? "valor" : "assessor";
  } catch {
    return "assessor";
  }
})();

const EXPLICACOES = {
  /* ---------------- KPIs (plano 14 §2 · plano 17 §6) ---------------- */
  "K-01": {
    nome: "Menções",
    oQueE: "Quantas vezes você apareceu na mídia e nas redes no período.",
    comoLer: "A seta compara com o período anterior.",
    porque: "Mostra se a sua presença está crescendo ou sumindo.",
    valor: {
      nome: "Matérias sobre a Casa",
      oQueE: "Quantas matérias sobre a Casa saíram no período.",
      comoLer: "A seta compara com o período anterior.",
      porque: "Mostra o tamanho da cobertura da Casa.",
    },
  },
  "K-02": {
    nome: "Citações diretas",
    oQueE: "Parte das menções em que seu nome aparece de forma clara, não só de passagem.",
    comoLer: "Quanto maior, mais a notícia é sobre você.",
    porque: "Separa protagonismo de citação indireta.",
  },
  "K-03": {
    nome: "Saldo de opinião",
    oQueE: "Notícias e posts positivos menos os negativos, de −100 a +100.",
    comoLer: "Acima de 0, há mais elogio que crítica.",
    porque: "Resume o clima em um número.",
    valor: {
      nome: "Saldo de opinião da Casa",
      oQueE: "Notícias e posts positivos menos os negativos sobre a Casa.",
      comoLer: "Acima de 0, há mais elogio que crítica.",
      porque: "Resume a reputação institucional em um número.",
    },
  },
  "K-04": {
    nome: "Protagonismo",
    oQueE: "Em quantas menções você é o personagem principal.",
    comoLer: "40% = em 4 de cada 10 você é o centro da notícia.",
    porque: "Ser protagonista pesa mais que ser citado.",
  },
  "K-05": {
    nome: "Alcance estimado",
    oQueE: "Quantas pessoas podem ter visto o que saiu, somando audiência dos veículos e das redes.",
    comoLer: "É uma estimativa, não contagem exata.",
    porque: "Mede o tamanho da vitrine.",
  },
  "K-06": {
    nome: "Grandes veículos",
    oQueE: "Parte das menções feita pelos veículos de maior audiência.",
    comoLer: "Mais alto = mais visibilidade de qualidade.",
    porque: "Uma matéria grande vale mais que várias pequenas.",
  },
  "K-07": {
    nome: "Fatia da conversa",
    oQueE: "Do total de menções dos parlamentares do grupo, quanto é seu.",
    comoLer: "15% = 15 de cada 100 menções.",
    porque: "Mostra seu espaço frente aos colegas.",
    valor: {
      nome: "Participação na cobertura",
      oQueE: "Do total de menções dos membros, quanto é de cada um.",
      comoLer: "15% = 15 de cada 100 menções.",
      porque: "Mostra a distribuição de visibilidade entre os membros.",
    },
  },
  "K-08": {
    nome: "Valor da mídia espontânea",
    oQueE: "Quanto custaria comprar, como anúncio, o espaço que você ganhou de graça.",
    comoLer: "Valor estimado pela tabela dos veículos.",
    porque: "Traduz a exposição em reais.",
    valor: {
      nome: "Valor da mídia espontânea da Casa",
      oQueE: "Quanto custaria comprar o espaço conquistado pela Casa na mídia.",
      comoLer: "Valor estimado pela tabela dos veículos.",
      porque: "Traduz a exposição institucional em reais.",
    },
  },
  "K-10": {
    nome: "Seguidores",
    oQueE: "Total de seguidores da conta conectada e quanto mudou.",
    comoLer: "Ganhos menos perdas no período.",
    porque: "Mostra se a audiência própria cresce.",
    valor: {
      nome: "Seguidores das contas da Casa",
      oQueE: "Total de seguidores das contas oficiais conectadas.",
      comoLer: "Ganhos menos perdas no período.",
      porque: "Mostra se a audiência institucional cresce.",
    },
  },
  "K-11": {
    nome: "Engajamento",
    oQueE: "De cada 100 pessoas alcançadas, quantas curtiram, comentaram ou compartilharam.",
    comoLer: "Acima de 3% é bom para perfis políticos.",
    porque: "Alcance sem engajamento não convence.",
  },
  "K-12": {
    nome: "Comentários",
    oQueE: "Comentários recebidos e a parte negativa.",
    comoLer: "Muitos negativos de uma vez merecem atenção.",
    porque: "É a voz direta do público.",
  },
  "K-13": {
    nome: "Seguidores dos rivais",
    oQueE: "Seguidores das contas profissionais dos rivais escolhidos.",
    comoLer: "Compare com o seu número de seguidores.",
    porque: "Mostra o tamanho da audiência de cada um.",
  },
  "K-20": {
    nome: "Alertas abertos",
    oQueE: "Situações que pedem ação e ainda não foram tratadas.",
    comoLer: "Vermelho = urgente.",
    porque: "Resolver cedo evita crise.",
  },
  "K-21": {
    nome: "Riscos de regra",
    oQueE: "Pontos que podem ferir a lei eleitoral ou a publicidade institucional.",
    comoLer: "Cada alerta cita o artigo da lei.",
    porque: "Evita multa e problema jurídico.",
    valor: {
      nome: "Riscos de regra",
      oQueE: "Pontos que podem ferir a regra de publicidade institucional.",
      comoLer: "Cada alerta cita o artigo da lei.",
      porque: "Evita apontamento de órgão de controle.",
    },
  },
  "K-22": {
    nome: "Anúncios políticos em MT",
    oQueE: "Anúncios sobre política e temas sociais ativos no estado.",
    comoLer: "Veja quem paga e quanto.",
    porque: "Revela quem está investindo para ser visto.",
  },
  "K-23": {
    nome: "Gasto estimado dos rivais",
    oQueE: "Soma aproximada do que os rivais gastam em anúncios.",
    comoLer: "A biblioteca de anúncios mostra faixas, então é aproximado.",
    porque: "Mostra a força da campanha paga deles.",
  },
  "K-24": {
    nome: "Demandas novas",
    oQueE: "Pedidos de cidadãos que chegaram por comentário, mensagem ou WhatsApp.",
    comoLer: "Agrupados por tema.",
    porque: "É a pauta que a população está pedindo.",
    valor: {
      nome: "Pedidos novos da Ouvidoria",
      oQueE: "Pedidos da população que chegaram à Ouvidoria da Casa.",
      comoLer: "Agrupados por tema.",
      porque: "É a pauta que a população está pedindo.",
    },
  },
  "K-25": {
    nome: "Demandas em aberto",
    oQueE: "Pedidos ainda sem resposta.",
    comoLer: "Quanto menor, melhor.",
    porque: "Mostra o que está pendente.",
    valor: {
      nome: "Pedidos em aberto",
      oQueE: "Pedidos da Ouvidoria ainda sem resposta.",
      comoLer: "Quanto menor, melhor.",
      porque: "Mostra o que está pendente.",
    },
  },
  "K-26": {
    nome: "Tempo de resposta",
    oQueE: "Quanto tempo, em média, se leva para responder um pedido.",
    comoLer: "Em horas.",
    porque: "Resposta rápida gera confiança.",
    valor: {
      nome: "Tempo de resposta",
      oQueE: "Quanto tempo, em média, a Ouvidoria leva para responder um pedido.",
      comoLer: "Em horas.",
      porque: "Resposta rápida gera confiança.",
    },
  },
  "K-27": {
    nome: "Taxa de resposta",
    oQueE: "De cada 100 pedidos, quantos foram respondidos.",
    comoLer: "Meta: acima de 80%.",
    porque: "Mede o compromisso com a base.",
    valor: {
      nome: "Taxa de resposta",
      oQueE: "De cada 100 pedidos, quantos foram respondidos.",
      comoLer: "Meta: acima de 80%.",
      porque: "Mede o compromisso da Ouvidoria com a população.",
    },
  },
  "K-28": {
    nome: "Alerta de crise",
    oQueE: "Avisa quando as menções negativas ficam muito acima do normal.",
    comoLer: "Aparece só quando é fora do comum.",
    porque: "Ajuda a agir antes da crise crescer.",
    valor: {
      nome: "Alerta de crise institucional",
      oQueE: "Avisa quando as menções negativas à Casa ficam muito acima do normal.",
      comoLer: "Aparece só quando é fora do comum.",
      porque: "Ajuda a Secom a agir antes da crise crescer.",
    },
  },
  "K-30": {
    nome: "Interesse nas buscas",
    oQueE: "Quanto as pessoas de MT procuram seu nome no Google, de 0 a 100.",
    comoLer: "100 = o pico do período.",
    porque: "Mostra curiosidade do público, mesmo sem notícia.",
    valor: {
      nome: "Interesse nos temas da pauta",
      oQueE: "Quanto as pessoas de MT procuram os temas da pauta da Casa.",
      comoLer: "100 = o pico do período.",
      porque: "Mostra o interesse da população pelos temas legislative.",
    },
  },
  "K-31": {
    nome: "Fatia das buscas",
    oQueE: "Das buscas pelos nomes do grupo, quanto é por você.",
    comoLer: "Comparável à fatia da conversa.",
    porque: "Buscas costumam antecipar intenção.",
  },
  "K-32": {
    nome: "Pico de atenção",
    oQueE: "Avisa quando o interesse do dia passa muito da média.",
    comoLer: "Mostra quantas vezes acima do normal.",
    porque: "Bom momento para se posicionar.",
  },
  "K-33": {
    nome: "Tendência para as próximas semanas",
    oQueE: "Projeção estatística de menções e saldo de opinião para 4 semanas.",
    comoLer: "A faixa sombreada é a margem.",
    porque: "Ajuda a planejar, não é garantia.",
  },
  "K-40": {
    nome: "Variedade de assuntos",
    oQueE: "Se a conversa sobre você se concentra em um tema ou se espalha por vários (0 a 1).",
    comoLer: "Perto de 0 = um assunto só.",
    porque: "Ajuda a ver se a agenda está ampla ou focada demais.",
  },
  "K-41": {
    nome: "Sintonia com a população",
    oQueE: "Quanto os assuntos que você fala batem com o que a população pede e procura (0 a 1).",
    comoLer: "Perto de 1 = muita sintonia.",
    porque: "Falar do que importa às pessoas.",
  },
  "K-42": {
    nome: "Imagem da Casa",
    oQueE: "Saldo de opinião sobre a instituição, dando mais peso a veículos maiores.",
    comoLer: "Acima de 0 é favorável.",
    porque: "Resume a reputação institucional.",
  },
  "K-43": {
    nome: "Equilíbrio da cobertura",
    oQueE: "Se a mídia cobre os parlamentares de forma equilibrada (0 = igual; 1 = concentrada).",
    comoLer: "Informativo, não é ranking.",
    porque: "Transparência sobre a visibilidade.",
  },
  "K-44": {
    nome: "Encaminhadas às comissões",
    oQueE: "Parte das demandas enviada à comissão responsável.",
    comoLer: "Quanto maior, mais a Ouvidoria movimenta a Casa.",
    porque: "Mostra demanda virando ação.",
  },
  "K-45": {
    nome: "Peças com promoção pessoal",
    oQueE: "Peças institucionais com nome, foto ou símbolo pessoal de autoridades.",
    comoLer: "A Constituição proíbe promoção pessoal na publicidade oficial.",
    porque: "Evita apontamento de órgãos de controle.",
  },
  "K-46": {
    nome: "Dias até as vedações eleitorais",
    oQueE: "Quantos dias faltam para começarem as restrições de publicidade do período eleitoral.",
    comoLer: "Contagem regressiva.",
    porque: "Planeja a comunicação a tempo.",
  },
  "K-50": {
    nome: "Aprovação simulada",
    oQueE: "Nota média (1 a 7) que personas criadas por IA deram ao discurso, com margem.",
    comoLer: "É simulação, não pesquisa.",
    porque: "Serve para comparar versões do discurso.",
  },
  "K-51": {
    nome: "Rejeição simulada",
    oQueE: "Parte das personas simuladas que reagiu mal.",
    comoLer: "É simulação, não pesquisa.",
    porque: "Aponta versões arriscadas.",
  },
  "K-52": {
    nome: "Acerto da simulação",
    oQueE: "Em quantas semanas a versão escolhida teve, na vida real, reação melhor que a média.",
    comoLer: "Calculado depois de publicar.",
    porque: "Diz se vale confiar na simulação.",
  },
  "K-60": {
    nome: "Tempo até aparecer aqui",
    oQueE: "Tempo médio entre a notícia sair e chegar ao app.",
    comoLer: "Em minutos.",
    porque: "Quanto menor, mais cedo você sabe.",
    valor: {
      nome: "Tempo até aparecer aqui",
      oQueE: "Tempo médio entre a notícia sair e chegar ao painel da Secom.",
      comoLer: "Em minutos.",
      porque: "Quanto menor, mais cedo a Secom sabe.",
    },
  },
  "K-61": {
    nome: "Veículos com notícia",
    oQueE: "Parte dos veículos monitorados que publicou algo no período.",
    comoLer: "Mostra o alcance da coleta.",
    porque: "Garante que nada importante ficou de fora.",
  },

  /* ---------------- KPIs das imagens (plano 18 §7) ---------------- */
  "K-70": {
    nome: "Posts com imagem analisada",
    oQueE: "Posts com imagem analisada pelo app.",
    comoLer: "Divide pelo total de posts com imagem.",
    porque: "Mostra quanto do material visual já foi lido.",
  },
  "K-71": {
    nome: "Presença do agente nas imagens",
    oQueE: "Imagens em que o rosto do agente foi reconhecido.",
    comoLer: "Divide pelas imagens analisadas.",
    porque: "Mostra em quantas imagens você aparece.",
  },
  "K-72": {
    nome: "Cards com texto",
    oQueE: "Parte das imagens que são cards com texto grande.",
    comoLer: "Divide pelo total de imagens.",
    porque: "Mostra o peso das peças de campanha.",
  },
  "K-73": {
    nome: "Engajamento por tipo de peça",
    oQueE: "Média de interações de cada tipo de peça nas suas contas.",
    comoLer: "Compare os tipos entre si.",
    porque: "Mostra qual formato rende mais.",
  },
  "K-74": {
    nome: "Imagens recicladas",
    oQueE: "Imagens que já circulavam há mais de 30 dias.",
    comoLer: "Contagem de peças antigas reusadas.",
    porque: "Mostra o quanto de conteúdo é requentado.",
  },
  "K-75": {
    nome: "Alertas vindos de imagem",
    oQueE: "Alertas de regra que vieram da análise de uma imagem.",
    comoLer: "Contagem por tipo de alerta.",
    porque: "Mostra o risco que está na imagem, não só no texto.",
  },

  /* ---------------- Gráficos (plano 14 §3 · plano 17 §7) ---------------- */
  "G-01": {
    nome: "Minigráfico",
    oQueE: "A evolução do número nos últimos dias.",
    comoLer: "Subindo para a direita = crescendo.",
    porque: "Mostra a tendência num olhar.",
  },
  "G-02": {
    nome: "Ranking",
    oQueE: "Barras do maior para o menor.",
    comoLer: "Barra mais longa = mais menções.",
    porque: "Mostra quem mais fala de você.",
  },
  "G-03": {
    nome: "Linha do tempo da opinião",
    oQueE: "Menções por dia, separadas em positivas, neutras e negativas.",
    comoLer: "Picos mostram dias de muita repercussão.",
    porque: "Liga números a acontecimentos.",
  },
  "G-04": {
    nome: "Opinião por canal",
    oQueE: "Cada barra é um canal dividido em positivo, neutro e negativo.",
    comoLer: "Compare as cores entre as barras.",
    porque: "Mostra onde você é bem ou mal recebido.",
  },
  "G-05": {
    nome: "Painel de pequenos gráficos",
    oQueE: "Um mini gráfico por pessoa ou assunto, todos na mesma escala.",
    comoLer: "Compare as formas, não só o tamanho.",
    porque: "Permite comparar muitos de uma vez sem confusão.",
  },
  "G-06": {
    nome: "Evolução dos assuntos",
    oQueE: "Quanto cada grupo de assuntos ocupou da conversa nas últimas 12 semanas.",
    comoLer: "Linha subindo = assunto ganhando espaço.",
    porque: "Antecipa pautas que estão crescendo.",
  },
  "G-07": {
    nome: "O que mudou",
    oQueE: "Palavras que apareceram muito mais ou muito menos do que o normal.",
    comoLer: "Barras longas = mudança forte.",
    porque: "Revela a novidade da semana.",
  },
  "G-08": {
    nome: "Mapa de horários",
    oQueE: "Dias da semana × horas do dia; quanto mais escuro, mais engajamento.",
    comoLer: "Procure os quadrados mais escuros.",
    porque: "Mostra a melhor hora para publicar.",
  },
  "G-09": {
    nome: "Quadrante de posição",
    oQueE: "Cada bolha é um parlamentar: à direita = mais visível; acima = mais positivo.",
    comoLer: "O melhor lugar é o canto superior direito.",
    porque: "Mostra sua posição frente aos rivais.",
  },
  "G-10": {
    nome: "Sobe e desce do ranking",
    oQueE: "Posição de cada um na fatia da conversa, semana a semana.",
    comoLer: "Linha subindo = ganhando posições.",
    porque: "Mostra quem cresce e quem perde espaço.",
  },
  "G-11": {
    nome: "Quem fala de quê",
    oQueE: "Linhas são pessoas, colunas são temas; cor mais forte = mais menções.",
    comoLer: "Procure as células mais escuras.",
    porque: "Mostra a especialidade de cada um.",
  },
  "G-12": {
    nome: "Tendência com margem",
    oQueE: "Linha do que já aconteceu e projeção com faixa de margem.",
    comoLer: "Quanto mais larga a faixa, maior a incerteza.",
    porque: "Ajuda a se preparar.",
  },
  "G-13": {
    nome: "Mapa de temas",
    oQueE: "Retângulos proporcionais ao número de pedidos de cada tema.",
    comoLer: "Retângulo maior = tema mais pedido.",
    porque: "Mostra as prioridades da população.",
  },
  "G-14": {
    nome: "Mapa por bairro",
    oQueE: "Bairros coloridos pelo número de pedidos.",
    comoLer: "Mais escuro = mais demandas.",
    porque: "Mostra onde a população mais precisa.",
  },
  "G-15": {
    nome: "Linha do tempo da crise",
    oQueE: "Sequência dos fatos e das reações, hora a hora.",
    comoLer: "Leia da esquerda para a direita.",
    porque: "Ajuda a entender como a crise começou e cresceu.",
  },
  "G-16": {
    nome: "Calendário do ano",
    oQueE: "Cada quadrado é um dia; mais escuro = mais menções.",
    comoLer: "Procure as semanas mais escuras.",
    porque: "Mostra a sazonalidade da presença na mídia.",
  },
  "G-17": {
    nome: "Funil das redes",
    oQueE: "De quantos viram → quantos interagiram → quantos comentaram → quantos pediram.",
    comoLer: "Cada degrau mostra quanto se perde.",
    porque: "Mostra onde melhorar a conversa.",
  },
  "G-20": {
    nome: "Grupos de assuntos",
    oQueE: "Os textos da semana divididos em grupos que usam as mesmas palavras.",
    comoLer: "Cada cor é um assunto; palavras maiores são as mais típicas.",
    porque: "Mostra de que se fala de verdade, sem depender de palavras-chave.",
  },
  "G-21": {
    nome: "Mapa de proximidade",
    oQueE: "Palavras e grupos perto uns dos outros aparecem juntos nos textos.",
    comoLer: "Olhe os agrupamentos, não as distâncias exatas.",
    porque: "Revela quais ideias andam juntas.",
  },
  "G-22": {
    nome: "Rede de palavras",
    oQueE: "Palavras ligadas por linhas quando aparecem juntas.",
    comoLer: "Os nós centrais ligam os assuntos.",
    porque: "Mostra como o discurso se conecta.",
  },
  "G-23": {
    nome: "Nuvem de palavras",
    oQueE: "As palavras mais usadas; maior = mais frequente.",
    comoLer: "Só uma visão geral.",
    porque: "Dá o tom da conversa em um olhar.",
  },
  "G-24": {
    nome: "Curva das palavras",
    oQueE: "Como poucas palavras se repetem muito e muitas aparecem pouco.",
    comoLer: "Fica no rodapé técnico.",
    porque: "Confere a qualidade do material analisado.",
  },
  "G-25": {
    nome: "Comparação das versões do discurso",
    oQueE: "Nota simulada de cada versão (ponto) com a margem (traço).",
    comoLer: "Se os traços se sobrepõem, a diferença pode ser acaso.",
    porque: "Ajuda a escolher a versão mais segura.",
  },
  "G-30": {
    nome: "Engajamento por tipo de peça",
    oQueE: "Barras com a média de interações de cada tipo de peça.",
    comoLer: "Barra mais alta = rende mais.",
    porque: "Mostra qual formato funciona melhor.",
  },
  "G-31": {
    nome: "Imagens que mais circularam",
    oQueE: "Lista das imagens que mais apareceram, com número de posts e redes.",
    comoLer: "Mais posts = mais circulação.",
    porque: "Mostra o que o público mais repassou.",
  },
  "G-32": {
    nome: "Presença do agente por semana",
    oQueE: "Linha com o percentual de imagens em que o agente aparece, por semana.",
    comoLer: "Linha subindo = mais presença visual.",
    porque: "Mostra a evolução da sua presença nas peças.",
  },

  /* ---------------- Tabelas (plano 17 §8) ---------------- */
  "T-01": {
    nome: "Últimas menções",
    oQueE: "As notícias e posts mais recentes sobre você.",
    comoLer: "O selo mostra se a citação é direta ou indireta.",
    porque: "Mostra o que está circulando agora.",
  },
  "T-02": {
    nome: "Clipping",
    oQueE: "Tudo o que saiu sobre a Casa.",
    comoLer: "Filtre, selecione para o boletim ou exporte.",
    porque: "Serve de arquivo oficial da cobertura.",
    valor: {
      nome: "Clipping",
      oQueE: "Tudo o que saiu sobre a Casa no período.",
      comoLer: "Filtre, selecione para o boletim ou exporte.",
      porque: "Serve de arquivo oficial da cobertura.",
    },
  },
  "T-03": {
    nome: "Top posts",
    oQueE: "Seus posts com mais engajamento no período.",
    comoLer: "Use como referência do que funciona.",
    porque: "Mostra o formato que rende mais.",
  },
  "T-04": {
    nome: "Comentários",
    oQueE: "Comentários recebidos com o tom e o assunto.",
    comoLer: "O nome de quem comentou aparece quando a rede o expõe.",
    porque: "Mostra o que o público está dizendo de você.",
  },
  "T-05": {
    nome: "Fila de demandas",
    oQueE: "Cada linha é um pedido de cidadão.",
    comoLer: "Mude o status quando responder ou encaminhar.",
    porque: "Mostra o que ainda falta atender.",
  },
  "T-06": {
    nome: "Comparativo de rivais",
    oQueE: "Você e os rivais escolhidos lado a lado.",
    comoLer: "Verde = você está melhor naquele indicador.",
    porque: "Mostra onde você está à frente.",
  },
  "T-07": {
    nome: "Parlamentares",
    oQueE: "Todos os membros, em ordem alfabética, com a cobertura de cada um.",
    comoLer: "Não é ranking.",
    porque: "Transparência sobre a visibilidade de cada um.",
  },
  "T-08": {
    nome: "Anúncios políticos",
    oQueE: "Anúncios ativos em MT: quem pagou, faixa de gasto e período.",
    comoLer: "Fonte: biblioteca de anúncios da Meta.",
    porque: "Mostra quem está investindo em anúncio político.",
  },
  "T-09": {
    nome: "Alertas de regra",
    oQueE: "Cada alerta traz o artigo da lei e o que fazer.",
    comoLer: "Marque como tratado ao resolver.",
    porque: "Mostra o que corrigir antes de publicar.",
  },
  "T-10": {
    nome: "Fontes que mais falam",
    oQueE: "Os veículos e perfis que mais publicaram sobre você no período.",
    comoLer: "Ordenado do maior para o menor.",
    porque: "Mostra de onde vem a sua exposição.",
  },
  "T-11": {
    nome: "Em alta em MT",
    oQueE: "Os assuntos mais buscados em Mato Grosso hoje, com as notícias ligadas.",
    comoLer: "Clique no assunto para ver as notícias.",
    porque: "Mostra o que a população está procurando agora.",
  },
  "T-12": {
    nome: "Usuários e papéis",
    oQueE: "Quem tem acesso e o que cada um pode ver ou fazer.",
    comoLer: "Cada linha é uma pessoa com um papel.",
    porque: "Mostra quem responde pelo quê.",
  },
  "T-13": {
    nome: "Registro de acessos",
    oQueE: "Quem acessou ou exportou o quê, e quando.",
    comoLer: "Ordenado do mais recente para o mais antigo.",
    porque: "Exigência de transparência do órgão.",
  },
  "T-14": {
    nome: "Histórico de coleta",
    oQueE: "Quando os dados foram atualizados e quantos itens entraram em cada coleta.",
    comoLer: "Cada linha é uma coleta.",
    porque: "Mostra se o monitoramento está atualizado.",
  },

  /* ---------------- Relatórios (plano 17 §9) ---------------- */
  "R-01": {
    nome: "Resumo do dia",
    oQueE: "O que você precisa saber hoje em 1 minuto.",
    comoLer: "Destaques, críticas e o que responder.",
    porque: "É o briefing da manhã.",
  },
  "R-02": {
    nome: "Relatório da semana",
    oQueE: "Como foi a sua semana na mídia e nas redes.",
    comoLer: "Os assuntos, o que mudou, a opinião e o que fazer.",
    porque: "É o relatório que você leva para a reunião.",
  },
  "R-03": {
    nome: "Discurso da semana",
    oQueE: "Três versões de discurso baseadas nos dados da semana, com a fonte de cada afirmação.",
    comoLer: "É um rascunho feito por IA: revise antes de usar.",
    porque: "Dá a você o que falar, com lastro.",
  },
  "R-04": {
    nome: "Teste do discurso",
    oQueE: "Como personas criadas por IA reagiram a cada versão.",
    comoLer: "É uma simulação para comparar versões, não uma pesquisa de opinião.",
    porque: "Ajuda a escolher a versão mais segura.",
  },
  "R-05": {
    nome: "Prestação de contas do mandato",
    oQueE: "O mês do mandato em números: presença na mídia, pedidos atendidos e temas trabalhados.",
    comoLer: "Pronto para enviar à sua base.",
    porque: "Mostra o que o mandato entregou.",
  },
  "R-06": {
    nome: "Relatório de gestão da comunicação",
    oQueE: "Resultados da comunicação da Casa no mês ou ano.",
    comoLer: "Cobertura, imagem, valor da mídia espontânea e atendimento da Ouvidoria.",
    porque: "É o relatório que o órgão apresenta ao controle e ao TCE.",
  },
  "R-07": {
    nome: "Boletim",
    oQueE: "As principais matérias do período, selecionadas e prontas.",
    comoLer: "Pronto para e-mail ou WhatsApp.",
    porque: "É o material que sai para a imprensa.",
  },
  "R-08": {
    nome: "Relatório de prazo de serviço",
    oQueE: "Mostra se o serviço contratado cumpriu os prazos e a cobertura combinados.",
    comoLer: "Comparado com o que está no contrato.",
    porque: "Prova o cumprimento do contrato.",
  },
  "R-09": {
    nome: "Dados abertos",
    oQueE: "Os indicadores públicos da comunicação da Casa em planilha.",
    comoLer: "Baixe em CSV ou JSON.",
    porque: "Permite que qualquer cidadão consulte os números.",
  },
  "R-10": {
    nome: "Exportação",
    oQueE: "Os dados da tela, exatamente com os filtros que estão ativos.",
    comoLer: "CSV ou PDF.",
    porque: "Serve para planilha, prestação de contas ou auditoria.",
  },
};

/** Devolve a entrada da explicação, já adaptada ao produto. */
export function explicacao(codigo) {
  const base = EXPLICACOES[codigo];
  if (!base) return null;
  if (PRODUTO === "valor" && base.valor) {
    return { ...base, ...base.valor, codigo };
  }
  const { valor, ...resto } = base;
  return { ...resto, codigo };
}

/** Nome amigável de um código (para o título do cartão). */
export function nomeAmigavel(codigo) {
  const item = explicacao(codigo);
  return item ? item.nome : codigo;
}

/** Texto completo (o que é · como ler · por que importa) em uma frase. */
export function textoExplicacao(codigo) {
  const item = explicacao(codigo);
  if (!item) return "";
  return `${item.oQueE} ${item.comoLer} ${item.porque}`;
}

/** Todos os códigos com explicação. */
export function todosOsCodigos() {
  return Object.keys(EXPLICACOES);
}

/**
 * Liga os botões ⓘ do front: cada elemento com `data-explicacao="K-01"`
 * ganha um clique que abre a explicação (popover no desktop, bottom sheet no celular).
 */
export function registrarExplicacoes(raiz = document) {
  raiz.querySelectorAll("[data-explicacao]").forEach((el) => {
    if (el.dataset.explicacaoPronto === "1") return;
    el.dataset.explicacaoPronto = "1";
    el.setAttribute("tabindex", "0");
    el.setAttribute("role", "button");
    el.setAttribute("aria-label", "Explicação deste item");
    const abrir = (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      mostrarExplicacao(el.dataset.explicacao, el);
    };
    el.addEventListener("click", abrir);
    el.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") abrir(evento);
    });
  });
}

/** Abre a explicação de um código (elemento opcional = âncora). */
export function mostrarExplicacao(codigo, ancora = null) {
  const item = explicacao(codigo);
  if (!item) return;
  const existente = document.getElementById("popupExplicacao");
  if (existente) existente.remove();

  const popup = document.createElement("div");
  popup.id = "popupExplicacao";
  popup.className = "popup-explicacao";
  popup.setAttribute("role", "dialog");
  popup.setAttribute("aria-label", `Explicação: ${item.nome}`);
  popup.innerHTML = `
    <p class="popup-explicacao-titulo">${item.nome}</p>
    <p class="popup-explicacao-linha"><strong>O que é:</strong> ${item.oQueE}</p>
    <p class="popup-explicacao-linha"><strong>Como ler:</strong> ${item.comoLer}</p>
    <p class="popup-explicacao-linha"><strong>Por que importa:</strong> ${item.porque}</p>
    ${item.formula ? `<p class="popup-explicacao-linha"><strong>Como calculamos:</strong> ${item.formula}</p>` : ""}
    <button class="popup-explicacao-fechar" type="button" aria-label="Fechar">×</button>
  `;
  document.body.appendChild(popup);
  popup.querySelector(".popup-explicacao-fechar")?.addEventListener("click", () => popup.remove());

  if (ancora) {
    const caixa = ancora.getBoundingClientRect();
    const topo = Math.max(8, caixa.top - 8 - popup.offsetHeight);
    popup.style.top = `${topo + window.scrollY}px`;
    popup.style.left = `${Math.min(caixa.left + window.scrollX, window.innerWidth - popup.offsetWidth - 12)}px`;
  }
  document.addEventListener("click", function fechar(evento) {
    if (!popup.contains(evento.target) && evento.target !== ancora) {
      popup.remove();
      document.removeEventListener("click", fechar);
    }
  });
}

export default { explicacao, nomeAmigavel, textoExplicacao, registrarExplicacoes, todosOsCodigos };
