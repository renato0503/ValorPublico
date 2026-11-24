/**
 * Roteador por hash — ValorPúblico / "Newsroom" (plano 13 §4).
 *
 * Telas (V1–V11):
 *   V1 Edição do dia · V2 Clipping · V3 Imagem da Casa · V4 Parlamentares
 *   V5 Ouvidoria · V6 Semana da Casa · V7 Redes da Casa
 *   V8 Publicidade & Conformidade · V9 Tendências
 *   V10 Relatórios & Transparência · V11 Sistema
 *
 * As rotas antigas (painel, midia, inteligencia) continuam válidas e caem nas
 * telas novas correspondentes.
 *
 * A URL pode trazer filtros: `#/clipping?periodo=30d&canal=imprensa`
 * (o estado vive na URL — ver `js/filtros.js`).
 */

const TELAS = {
  edicao: {
    titulo: "Edição do dia",
    eyebrow: "O que saiu hoje sobre a Casa",
    pergunta: "O que saiu hoje sobre a Casa?",
  },
  clipping: {
    titulo: "Clipping",
    eyebrow: "Arquivo oficial da cobertura",
    pergunta: "Encontrar e arquivar o que saiu",
  },
  imagem: {
    titulo: "Imagem da Casa",
    eyebrow: "Reputação institucional",
    pergunta: "Como está a imagem institucional e para onde vai?",
  },
  parlamentares: {
    titulo: "Parlamentares",
    eyebrow: "Cobertura de cada membro",
    pergunta: "Como a mídia cobre cada membro?",
  },
  ouvidoria: {
    titulo: "Ouvidoria",
    eyebrow: "O que a cidade pede",
    pergunta: "O que a cidade pede à Casa?",
  },
  semana: {
    titulo: "Semana da Casa",
    eyebrow: "Relatório e discurso institucional",
    pergunta: "Como foi a semana e o que a Casa deve comunicar?",
  },
  redes: {
    titulo: "Redes da Casa",
    eyebrow: "Contas institucionais",
    pergunta: "Como vão as contas oficiais?",
  },
  conformidade: {
    titulo: "Publicidade & Conformidade",
    eyebrow: "Conformidade e risco",
    pergunta: "Estamos cumprindo as regras?",
  },
  governo: {
    titulo: "Governo de MT",
    eyebrow: "Executivo estadual",
    pergunta: "O que o governo fez e como a imprensa tratou?",
  },
  governador: {
    titulo: "Governador",
    eyebrow: "Cobertura da gestão",
    pergunta: "Como a mídia trata o governador?",
  },
  analise: {
    titulo: "Análise",
    eyebrow: "DSM e IRAMUTEQ",
    pergunta: "Quais são os mundos de sentido e os sinais de risco?",
    legado: "inteligencia",
  },
  simulacao: {
    titulo: "Simulação",
    eyebrow: "Recepção pelas 12 personas",
    pergunta: "Como as personas reagiram ao discurso?",
  },
  personas: {
    titulo: "Personas",
    eyebrow: "Chat com personas",
    pergunta: "O que cada persona perguntaria ou responderia?",
  },
  tendencias: {
    titulo: "Tendências",
    eyebrow: "Interesse da população",
    pergunta: "O que preocupa a cidade e o estado?",
  },
  relatorios: {
    titulo: "Relatórios & Transparência",
    eyebrow: "Prestação de contas",
    pergunta: "O que publicamos e prestamos contas?",
  },
  sistema: {
    titulo: "Sistema",
    eyebrow: "Acesso e operação",
    pergunta: "Quem acessa e como está a operação?",
  },
  // rotas antigas (links já publicados) -> caem nas telas novas
  painel: { titulo: "Edição do dia", eyebrow: "O que saiu hoje sobre a Casa", pergunta: "O que saiu hoje sobre a Casa?", legado: "edicao" },
  midia: { titulo: "Imagem da Casa", eyebrow: "Reputação institucional", pergunta: "Como está a imagem institucional?", legado: "midia" },
  inteligencia: { titulo: "Publicidade & Conformidade", eyebrow: "Conformidade e risco", pergunta: "Estamos cumprindo as regras?", legado: "inteligencia" },
};

const APP = "ValorPúblico";
const GOVMT_ONLY = new Set(["governo", "governador", "simulacao", "personas"]);

function rotaDoHash() {
  const bruta = (window.location.hash.replace(/^#\/?/, "").split("?")[0] || "").trim();
  return TELAS[bruta] ? bruta : "edicao";
}

function aplicar(rota) {
  let alvo = TELAS[rota] ? rota : "edicao";
  // As telas do Executivo só existem na frente Governo de MT.
  const orgao = document.body.dataset.orgao || "";
  if (GOVMT_ONLY.has(alvo) && orgao && orgao !== "governo-mt") {
    alvo = "edicao";
  }
  const info = TELAS[alvo];
  const telaId = info.legado || alvo;

  document.querySelectorAll(".tela").forEach((tela) => {
    tela.classList.toggle("ativa", tela.dataset.tela === telaId);
  });

  document.querySelectorAll("[data-rota]").forEach((link) => {
    const ativo = link.dataset.rota === alvo;
    link.classList.toggle("ativo", ativo);
    if (ativo) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  const titulo = document.getElementById("telaTitulo");
  const eyebrow = document.getElementById("telaEyebrow");
  if (titulo) titulo.textContent = info.titulo;
  if (eyebrow) eyebrow.textContent = info.eyebrow;
  const pergunta = document.getElementById("telaPergunta");
  if (pergunta) pergunta.textContent = info.pergunta || "";
  document.title = `${info.titulo} · ${APP}`;

  window.scrollTo({ top: 0 });
  document.documentElement.dataset.rota = alvo;
  document.dispatchEvent(new CustomEvent("rota:changed", { detail: { rota: alvo } }));
}

export function iniciarRouter() {
  const irPara = (rota) => {
    if (!TELAS[rota]) return;
    const consulta = window.location.hash.includes("?")
      ? window.location.hash.split("?")[1]
      : "";
    const hash = consulta ? `#/${rota}?${consulta}` : `#/${rota}`;
    if (window.location.hash === hash) aplicar(rota);
    else window.location.hash = hash;
  };

  window.addEventListener("hashchange", () => aplicar(rotaDoHash()));
  if (!window.location.hash) {
    history.replaceState(null, "", "#/" + rotaDoHash());
  }
  aplicar(rotaDoHash());

  document.getElementById("btnFiltros")?.addEventListener("click", (e) => {
    const aberto = document.querySelector(".masthead")?.classList.toggle("filtros-aberto");
    e.currentTarget.setAttribute("aria-expanded", String(!!aberto));
  });

  window.__router = { irPara, rotaAtual: rotaDoHash };
}
