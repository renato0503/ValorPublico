/**
 * Menu principal do ValorPúblico.
 *
 * O menu é gerado por configuração, não por HTML duplicado. Cada frente tem
 * um conjunto primário e um conjunto secundário (dropdown "Mais"), o que evita
 * a barra estourar e itens sumirem.
 *
 * Rotas antigas continuam funcionando; a rota ativa é lida de
 * `document.documentElement.dataset.rota`, preenchida pelo router.
 */

const ITENS = {
  edicao: { rotulo: "Edição do dia", icone: "i-painel", rota: "edicao" },
  governo: { rotulo: "Visão do Governo", icone: "i-painel", rota: "governo" },
  governador: { rotulo: "Governador", icone: "i-painel", rota: "governador" },
  clipping: { rotulo: "Clipping", icone: "i-painel", rota: "clipping" },
  imagem: { rotulo: "Imagem", icone: "i-midia", rota: "imagem" },
  parlamentares: { rotulo: "Parlamentares", icone: "i-parlamentares", rota: "parlamentares" },
  ouvidoria: { rotulo: "Ouvidoria", icone: "i-concorrencia", rota: "ouvidoria" },
  semana: { rotulo: "Semana & Discurso", icone: "i-analise", rota: "semana" },
  redes: { rotulo: "Redes", icone: "i-mencoes", rota: "redes" },
  conformidade: { rotulo: "Conformidade", icone: "i-inteligencia", rota: "conformidade" },
  analise: { rotulo: "Análise", icone: "i-analise", rota: "analise" },
  simulacao: { rotulo: "Simulação", icone: "i-analise", rota: "simulacao" },
  personas: { rotulo: "Personas", icone: "i-parlamentares", rota: "personas" },
  tendencias: { rotulo: "Tendências", icone: "i-analise", rota: "tendencias" },
  relatorios: { rotulo: "Relatórios", icone: "i-relatorios", rota: "relatorios" },
  sistema: { rotulo: "Sistema", icone: "i-sistema", rota: "sistema" },
};

const MENUS = {
  "governo-mt": {
    principal: ["governo", "governador", "semana", "analise", "simulacao", "personas", "relatorios"],
    mais: ["clipping", "imagem", "conformidade", "tendencias", "redes", "sistema"],
  },
  default: {
    principal: ["edicao", "clipping", "semana", "analise", "relatorios"],
    mais: ["imagem", "parlamentares", "ouvidoria", "redes", "conformidade", "tendencias", "sistema"],
  },
};

// Rotas antigas -> rota canônica usada no menu.
const ALIASES = {
  painel: "edicao",
  midia: "imagem",
  inteligencia: "analise",
};

function rotaCanonica() {
  const rota = document.documentElement.dataset.rota || "edicao";
  return ALIASES[rota] || rota;
}

function link(item, ativo) {
  return (
    `<a href="#/${item.rota}" data-rota="${item.rota}" ` +
    `class="nav-jornal-link${ativo ? " ativo" : ""}"` +
    `${ativo ? ' aria-current="page"' : ""}>` +
    `<svg aria-hidden="true"><use href="#${item.icone}"/></svg>` +
    `<span>${item.rotulo}</span></a>`
  );
}

function htmlPrincipal(itens, ativo) {
  return itens.map((chave) => link(ITENS[chave], chave === ativo)).join("");
}

function htmlMais(itens, ativo) {
  if (!itens.length) return "";
  const temAtivo = itens.includes(ativo);
  const entradas = itens.map((chave) => link(ITENS[chave], chave === ativo)).join("");
  return (
    `<div class="nav-mais" data-nav-mais>` +
    `<button class="nav-mais-btn nav-jornal-link${temAtivo ? " ativo" : ""}" type="button" ` +
    `aria-expanded="false" aria-controls="navMaisPainel" data-nav-mais-btn>` +
    `<span>Mais</span><span class="nav-mais-seta" aria-hidden="true">▾</span>` +
    `</button>` +
    `<div class="nav-mais-painel" id="navMaisPainel" hidden data-nav-mais-painel>` +
    entradas +
    `</div></div>`
  );
}

function fecharMais() {
  document.querySelectorAll("[data-nav-mais]").forEach((caixa) => {
    const botao = caixa.querySelector("[data-nav-mais-btn]");
    const painel = caixa.querySelector("[data-nav-mais-painel]");
    if (botao) botao.setAttribute("aria-expanded", "false");
    if (painel) painel.hidden = true;
  });
}

function ligarMais(nav) {
  const caixa = nav.querySelector("[data-nav-mais]");
  if (!caixa) return;
  const botao = caixa.querySelector("[data-nav-mais-btn]");
  const painel = caixa.querySelector("[data-nav-mais-painel]");
  if (!botao || !painel) return;

  botao.addEventListener("click", (evento) => {
    evento.stopPropagation();
    const aberto = botao.getAttribute("aria-expanded") === "true";
    fecharMais();
    botao.setAttribute("aria-expanded", String(!aberto));
    painel.hidden = aberto;
  });

  painel.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => fecharMais());
  });
}

// Fecha o "Mais" ao clicar fora ou apertar Esc (uma vez por página).
if (typeof document !== "undefined") {
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest("[data-nav-mais]")) fecharMais();
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") fecharMais();
  });
}

/** Renderiza o menu da frente. `orgao` vazio mostra o menu padrão. */
export function renderMenu(orgao) {
  const nav = document.getElementById("navPrincipal");
  if (!nav) return;
  const config = MENUS[orgao] || MENUS.default;
  const ativo = rotaCanonica();
  nav.innerHTML =
    htmlPrincipal(config.principal, ativo) + htmlMais(config.mais, ativo);
  ligarMais(nav);
}

/** Atualiza só o estado ativo (usado em `rota:changed`). */
export function marcarAtivo() {
  const ativo = rotaCanonica();
  document.querySelectorAll("#navPrincipal [data-rota]").forEach((a) => {
    const on = a.dataset.rota === ativo;
    a.classList.toggle("ativo", on);
    if (on) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-nav-mais]").forEach((caixa) => {
    const botao = caixa.querySelector("[data-nav-mais-btn]");
    if (!botao) return;
    botao.classList.toggle(
      "ativo",
      !!caixa.querySelector(".nav-mais-painel a.ativo")
    );
  });
}
