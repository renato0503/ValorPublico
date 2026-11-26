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
  governo: { rotulo: "Visão do Governo", icone: "i-governo", rota: "governo" },
  governador: { rotulo: "Governador", icone: "i-governador", rota: "governador" },
  clipping: { rotulo: "Clipping", icone: "i-clipping", rota: "clipping" },
  imagem: { rotulo: "Imagem", icone: "i-midia", rota: "imagem", beta: true },
  parlamentares: { rotulo: "Parlamentares", icone: "i-parlamentares", rota: "parlamentares" },
  ouvidoria: { rotulo: "Ouvidoria", icone: "i-concorrencia", rota: "ouvidoria" },
  semana: { rotulo: "Semana & Discurso", icone: "i-calendario", rota: "semana" },
  redes: { rotulo: "Redes", icone: "i-mencoes", rota: "redes" },
  conformidade: { rotulo: "Conformidade", icone: "i-inteligencia", rota: "conformidade" },
  radar: { rotulo: "Radar & Alertas", icone: "i-radar", rota: "radar" },
  analise: { rotulo: "Análise do discurso", icone: "i-analise", rota: "analise" },
  simulacao: { rotulo: "Simulação", icone: "i-simulacao", rota: "simulacao", beta: true },
  personas: { rotulo: "Personas", icone: "i-parlamentares", rota: "personas", beta: true },
  tendencias: { rotulo: "Tendências", icone: "i-tendencia", rota: "tendencias" },
  relatorios: { rotulo: "Relatórios", icone: "i-relatorios", rota: "relatorios" },
  sistema: { rotulo: "Sistema", icone: "i-sistema", rota: "sistema" },
};

const GRUPOS = {
  "governo-mt": [
    { rotulo: "Painel", itens: ["governo"] },
    { rotulo: "Mídia", itens: ["clipping", "redes", "tendencias", "imagem"] },
    { rotulo: "Ouvidoria", itens: ["ouvidoria"] },
    { rotulo: "Inteligência", itens: ["semana", "radar", "analise", "conformidade", "relatorios"] },
    { rotulo: "Laboratório", itens: ["simulacao", "personas"] },
  ],
  default: [
    { rotulo: "Painel", itens: ["edicao", "semana"] },
    { rotulo: "Mídia", itens: ["clipping", "imagem", "redes", "tendencias"] },
    { rotulo: "Ouvidoria", itens: ["ouvidoria"] },
    { rotulo: "Inteligência", itens: ["radar", "analise", "conformidade", "relatorios"] },
    { rotulo: "Laboratório", itens: ["simulacao", "personas"] },
  ],
};

const MENUS = {
  "governo-mt": {
    principal: ["governo", "semana", "analise", "simulacao", "personas", "relatorios"],
    mais: ["clipping", "ouvidoria", "radar", "imagem", "conformidade", "tendencias", "redes", "sistema"],
  },
  default: {
    principal: ["edicao", "clipping", "semana", "analise", "relatorios"],
    mais: ["radar", "imagem", "parlamentares", "ouvidoria", "redes", "conformidade", "tendencias", "sistema"],
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
    `<span>${item.rotulo}</span>${item.beta ? '<span class="nav-beta">Beta</span>' : ""}</a>`
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
    `<svg aria-hidden="true"><use href="#i-mais"/></svg>` +
    `<span>Mais</span><svg class="nav-mais-seta" aria-hidden="true"><use href="#i-seta-baixo"/></svg>` +
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
function linkSidebar(item, ativo) {
  return (
    `<a href="#/${item.rota}" data-rota="${item.rota}" title="${item.rotulo}" ` +
    `class="sidebar-link${ativo ? " ativo" : ""}"` +
    `${ativo ? ' aria-current="page"' : ""}>` +
    `<svg aria-hidden="true"><use href="#${item.icone}"/></svg>` +
    `<span class="sidebar-rotulo">${item.rotulo}</span>` +
    `${item.beta ? '<span class="nav-beta">Beta</span>' : ""}` +
    `</a>`
  );
}

function renderSidebar(orgao, ativo) {
  const aside = document.getElementById("appSidebar");
  if (!aside) return;
  const grupos = GRUPOS[orgao] || GRUPOS.default;
  const sistema = ITENS.sistema;
  aside.innerHTML =
    `<div class="sidebar-topo">
      <span class="sidebar-eyebrow">Navegação</span>
    </div>` +
    grupos
      .map(
        (grupo) =>
          `<div class="sidebar-grupo">
            <h3>${grupo.rotulo}</h3>
            ${grupo.itens.map((chave) => linkSidebar(ITENS[chave], chave === ativo)).join("")}
          </div>`
      )
      .join("") +
    `<div class="sidebar-rodape">
      <button type="button" class="sidebar-link" id="sidebarFiltros">
        <svg aria-hidden="true"><use href="#i-filtro"/></svg><span class="sidebar-rotulo">Filtros</span>
      </button>
      ${linkSidebar(sistema, ativo === "sistema")}
    </div>`;
}
export function renderMenu(orgao) {
  const nav = document.getElementById("navPrincipal");
  if (!nav) return;
  const config = MENUS[orgao] || MENUS.default;
  const ativo = rotaCanonica();
  const nav2 = document.documentElement.dataset.ux === "nav2";
  const grupos = GRUPOS[orgao] || GRUPOS.default;
  const acoesMobile = `<div class="nav-mobile-acoes">
      <a href="#/sistema" data-rota="sistema" class="nav-jornal-link">
        <svg aria-hidden="true"><use href="#i-sistema"/></svg><span>Sistema</span>
      </a>
      <button type="button" class="nav-jornal-link" id="navOrgaoMobile">
        <svg aria-hidden="true"><use href="#i-orgao"/></svg><span>Trocar órgão</span>
      </button>
      <button type="button" class="nav-jornal-link" id="navAuthMobile">
        <svg aria-hidden="true"><use href="#i-entrar"/></svg><span>Conta / Sair</span>
      </button>
    </div>`;
  nav.innerHTML = nav2
    ? `<div class="nav-mobile-cabecalho"><span>Menu</span><button type="button" class="nav-mobile-fechar" id="navFecharMobile" aria-label="Fechar menu">Fechar</button></div>` +
      grupos
        .map(
          (grupo) =>
            `<div class="nav-mobile-grupo">
              <span class="nav-mobile-titulo">${grupo.rotulo}</span>
              ${grupo.itens.map((chave) => link(ITENS[chave], chave === ativo)).join("")}
            </div>`
        )
        .join("") + acoesMobile
    : htmlPrincipal(config.principal, ativo) +
      htmlMais(config.mais, ativo) +
      acoesMobile;
  ligarMais(nav);
  renderSidebar(orgao, ativo);
  const fecharMenuMobile = () => {
    document.body.classList.remove("menu-aberto");
    document.getElementById("btnMenu")?.setAttribute("aria-expanded", "false");
  };
  nav.querySelectorAll("a[data-rota]").forEach((a) =>
    a.addEventListener("click", fecharMenuMobile)
  );
  nav.querySelector("#navOrgaoMobile")?.addEventListener("click", () => {
    fecharMais();
    fecharMenuMobile();
    document.getElementById("btnOrgao")?.click();
  });
  nav.querySelector("#navAuthMobile")?.addEventListener("click", () => {
    fecharMais();
    fecharMenuMobile();
    document.getElementById("btnAuth")?.click();
  });
}

/** Atualiza só o estado ativo (usado em `rota:changed`). */
export function marcarAtivo() {
  const ativo = rotaCanonica();
  document.querySelectorAll("#navPrincipal [data-rota], #appSidebar [data-rota]").forEach((a) => {
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












