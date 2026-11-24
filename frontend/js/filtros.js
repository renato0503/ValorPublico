/**
 * Barra global de filtros (plano 13 §2) — vale para todas as telas.
 *
 * Filtros: Período · Comparar com · Escopo/Casa · Canal · Tema
 * (Assessor: Escopo = Eu / um rival / Eu × rivais; Valor: Escopo = a Casa).
 *
 * O estado vive na **URL** (`#/midia?periodo=30d&canal=instagram&tema=saude`):
 * link compartilhável, botão "voltar" funciona e a tela recarrega no mesmo
 * estado. Um evento `filtros:mudou` é disparado para cada tela.
 *
 * Chips de filtro ativo com "limpar tudo" (plano 13 §1.6).
 */

const CHAVES = ["periodo", "comparar", "escopo", "canal", "tema", "parlamentar"];

export const PERIODOS = [
  { valor: "", rotulo: "Todo o período" },
  { valor: "hoje", rotulo: "Hoje" },
  { valor: "7d", rotulo: "Últimos 7 dias" },
  { valor: "15d", rotulo: "Últimos 15 dias" },
  { valor: "30d", rotulo: "Últimos 30 dias" },
  { valor: "90d", rotulo: "Últimos 90 dias" },
  { valor: "12m", rotulo: "Últimos 12 meses" },
];

export const CANAIS = [
  { valor: "", rotulo: "Todos os canais" },
  { valor: "imprensa", rotulo: "Imprensa (portal/jornal)" },
  { valor: "tvradio", rotulo: "TV e rádio" },
  { valor: "redes", rotulo: "Redes sociais" },
  { valor: "oficial", rotulo: "Oficial (diário e sites públicos)" },
];

const estado = {
  periodo: "",
  comparar: "anterior",
  escopo: "",
  canal: "",
  tema: "",
  parlamentar: "",
};

const ouvintes = new Set();

/** Estado atual dos filtros (cópia). */
export function filtros() {
  return { ...estado };
}

/** Assina mudanças de filtro. */
export function aoMudarFiltros(funcao) {
  ouvintes.add(funcao);
  return () => ouvintes.delete(funcao);
}

/** Lê o estado da URL (sem '#'). */
export function lerDaUrl() {
  const bruto = window.location.hash.split("?")[1] || "";
  const params = new URLSearchParams(bruto);
  CHAVES.forEach((chave) => {
    const valor = params.get(chave);
    if (valor !== null) estado[chave] = valor;
  });
  return { ...estado };
}

/** Escreve o estado na URL, preservando a rota. */
export function escreverNaUrl(novoEstado = {}) {
  Object.assign(estado, novoEstado);
  const base = window.location.hash.split("?")[0] || "#/";
  const params = new URLSearchParams();
  CHAVES.forEach((chave) => {
    if (estado[chave]) params.set(chave, estado[chave]);
  });
  const consulta = params.toString();
  const novaHash = consulta ? `${base}?${consulta}` : base;
  if (novaHash !== window.location.hash) {
    history.replaceState(null, "", novaHash);
  }
  return { ...estado };
}

/** Aplica um conjunto de filtros e avisa as telas. */
export function aplicarFiltros(novoEstado = {}) {
  Object.assign(estado, novoEstado);
  escreverNaUrl();
  atualizarChips();
  ouvintes.forEach((funcao) => {
    try {
      funcao(filtros());
    } catch (erro) {
      console.warn("[Filtros] ouvinte falhou:", erro);
    }
  });
  document.dispatchEvent(new CustomEvent("filtros:mudou", { detail: filtros() }));
}

/** Limpa todos os filtros. */
export function limparFiltros() {
  aplicarFiltros({ periodo: "", comparar: "anterior", escopo: "", canal: "", tema: "", parlamentar: "" });
}

/* ------------------------------------------------------------------ */
/* Chips de filtro ativo (plano 13 §1.6)                                 */
/* ------------------------------------------------------------------ */

function rotuloDe(chave, valor) {
  if (chave === "periodo") {
    return PERIODOS.find((p) => p.valor === valor)?.rotulo || valor;
  }
  if (chave === "canal") {
    return CANAIS.find((c) => c.valor === valor)?.rotulo || valor;
  }
  if (chave === "comparar") {
    return valor === "anterior" ? "vs. período anterior" : valor === "ano" ? "vs. ano anterior" : "sem comparação";
  }
  if (chave === "escopo") return `Escopo: ${valor}`;
  if (chave === "parlamentar") return `Parlamentar: ${valor}`;
  return `${chave}: ${valor}`;
}

/** Atualiza a faixa de chips e o resumo do botão "Filtros". */
export function atualizarChips() {
  const container = document.getElementById("filtrosAtivos");
  if (container) {
    const ativos = CHAVES.filter((chave) => estado[chave] && chave !== "comparar");
    container.innerHTML = "";
    container.classList.toggle("oculto", !ativos.length);
    ativos.forEach((chave) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip-filtro";
      chip.textContent = `${rotuloDe(chave, estado[chave])} ×`;
      chip.setAttribute("aria-label", `Remover filtro ${rotuloDe(chave, estado[chave])}`);
      chip.addEventListener("click", () => aplicarFiltros({ [chave]: "" }));
      container.appendChild(chip);
    });
    if (ativos.length > 1) {
      const limpar = document.createElement("button");
      limpar.type = "button";
      limpar.className = "chip-filtro chip-filtro-limpar";
      limpar.textContent = "Limpar tudo";
      limpar.addEventListener("click", limparFiltros);
      container.appendChild(limpar);
    }
  }

  const resumo = document.getElementById("filtrosResumo");
  if (resumo) {
    const periodo = PERIODOS.find((p) => p.valor === estado.periodo)?.rotulo || "Todo o período";
    const canal = CANAIS.find((c) => c.valor === estado.canal)?.rotulo || "Todos os canais";
    resumo.textContent = `${periodo} · ${canal}`;
  }
}

/* ------------------------------------------------------------------ */
/* Ligação com os <select> da barra global                              */
/* ------------------------------------------------------------------ */

export function ligarBarraGlobal() {
  const mapa = {
    filtroPeriodoGlobal: "periodo",
    filtroCompararGlobal: "comparar",
    filtroEscopoGlobal: "escopo",
    filtroCanalGlobal: "canal",
    filtroTemaGlobal: "tema",
  };
  Object.entries(mapa).forEach(([idElemento, chave]) => {
    const elemento = document.getElementById(idElemento);
    if (!elemento) return;
    elemento.addEventListener("change", () => {
      aplicarFiltros({ [chave]: elemento.value });
    });
  });

  // Estado inicial vindo da URL.
  lerDaUrl();
  const inicial = { ...estado };
  Object.entries(mapa).forEach(([idElemento, chave]) => {
    const elemento = document.getElementById(idElemento);
    if (elemento && inicial[chave] !== undefined) elemento.value = inicial[chave];
  });
  atualizarChips();

  // Botão "voltar" do navegador refaz a tela no mesmo estado.
  window.addEventListener("hashchange", () => {
    lerDaUrl();
    atualizarChips();
    document.dispatchEvent(new CustomEvent("filtros:mudou", { detail: filtros() }));
  });
}

/** Escreve o resumo dos filtros no topo (usado pelo botão). */
export function resumoFiltros() {
  const partes = [];
  if (estado.periodo) partes.push(PERIODOS.find((p) => p.valor === estado.periodo)?.rotulo);
  if (estado.canal) partes.push(CANAIS.find((c) => c.valor === estado.canal)?.rotulo);
  if (estado.escopo) partes.push(estado.escopo);
  return partes.length ? partes.join(" · ") : "Todos · todo o período";
}

export default { filtros, aplicarFiltros, limparFiltros, ligarBarraGlobal, aoMudarFiltros };
