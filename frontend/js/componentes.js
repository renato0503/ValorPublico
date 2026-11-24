/**
 * Componentes padrão do front (plano 17 §4).
 *
 *   4.1 Cartão de KPI    — nome amigável + ⓘ + valor + variação (cor+seta+texto)
 *                           + minigráfico (G-01)
 *   4.2 Cartão de gráfico — título-conclusão + ⓘ + subtítulo (escopo/período/n)
 *                           + gráfico + leitura do momento + "ver dados" / PNG
 *   4.3 Tabela           — linha de explicação + ⓘ nas colunas + ordenação + busca
 *
 * Todos usam `explicacoes.js` (plano 17 §5): nada entra no ar sem explicação.
 */

import { explicacao, nomeAmigavel, registrarExplicacoes } from "./explicacoes.js";
import { minigrafico, redimensionar } from "./graficos.js";

const graficosAtivos = new Set();

/* ------------------------------------------------------------------ */
/* 4.1 — Cartão de KPI                                                  */
/* ------------------------------------------------------------------ */

/**
 * Monta (ou atualiza) um cartão de KPI.
 *
 * @param {string} idElemento  id do <article> que vira o cartão
 * @param {object} opcoes
 *   - codigo: "K-01" (obrigatório: sem explicação não entra no ar)
 *   - valor: texto já formatado
 *   - variacao: { valor: number, rotulo: string, periodo: string }
 *   - serie: number[] para o minigráfico
 *   - sufixo: texto pequeno abaixo do valor
 */
export function cartaoKpi(idElemento, opcoes = {}) {
  const elemento = document.getElementById(idElemento);
  if (!elemento) return null;
  const codigo = opcoes.codigo || "";
  const item = explicacao(codigo);
  const nome = opcoes.nome || nomeAmigavel(codigo);

  const variacao = opcoes.variacao;
  let classeVariacao = "";
  let setaVariacao = "";
  let textoVariacao = "";
  if (variacao && typeof variacao.valor === "number" && Number.isFinite(variacao.valor)) {
    const subiu = variacao.valor > 0;
    const igual = variacao.valor === 0;
    classeVariacao = igual ? "kpi-variacao-igual" : subiu ? "kpi-variacao-alta" : "kpi-variacao-baixa";
    setaVariacao = igual ? "→" : subiu ? "▲" : "▼";
    const numero = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
      Math.abs(variacao.valor)
    );
    textoVariacao = `${setaVariacao} ${numero}${
      variacao.periodo ? ` vs. ${variacao.periodo}` : ""
    }`;
  }

  elemento.className = `card kpi ${opcoes.classe || ""}`.trim();
  elemento.innerHTML = `
    <div class="kpi-cabecalho">
      <span class="kpi-rotulo">${escapar(nome)}</span>
      <button class="btn-info" type="button" data-explicacao="${escapar(codigo)}" aria-label="O que é ${escapar(nome)}?">ⓘ</button>
    </div>
    <span class="kpi-valor">${escapar(String(opcoes.valor ?? "–"))}</span>
    ${
      textoVariacao
        ? `<span class="kpi-variacao ${classeVariacao}">${escapar(textoVariacao)}</span>`
        : ""
    }
    ${opcoes.sufixo ? `<span class="kpi-sufixo">${escapar(opcoes.sufixo)}</span>` : ""}
    <div class="kpi-spark" id="spark-${idElemento}"></div>
  `;
  registrarExplicacoes(elemento);

  if (Array.isArray(opcoes.serie) && opcoes.serie.length) {
    const spark = document.getElementById(`spark-${idElemento}`);
    if (spark) {
      const instancia = minigrafico(spark, opcoes.serie);
      if (instancia) graficosAtivos.add(instancia);
    }
  }
  return elemento;
}

/* ------------------------------------------------------------------ */
/* 4.2 — Cartão de gráfico                                              */
/* ------------------------------------------------------------------ */

/**
 * Cria a estrutura de um cartão de gráfico (título-conclusão, leitura, ações).
 * Devolve o elemento do canvas para o desenho.
 */
export function cartaoGrafico(elementoPai, opcoes = {}) {
  const codigo = opcoes.codigo || "";
  const item = explicacao(codigo);
  const titulo = opcoes.titulo || nomeAmigavel(codigo);
  const idCanvas = opcoes.idCanvas || `gfx-${Math.random().toString(36).slice(2, 9)}`;

  elementoPai.innerHTML = `
    <div class="grafico-cabecalho">
      <div>
        <h3 class="grafico-titulo">${escapar(titulo)}</h3>
        <p class="grafico-subtitulo">${escapar(opcoes.subtitulo || "")}</p>
      </div>
      <button class="btn-info" type="button" data-explicacao="${escapar(codigo)}" aria-label="O que é ${escapar(titulo)}?">ⓘ</button>
    </div>
    <div class="grafico-area" id="${idCanvas}"></div>
    ${
      opcoes.leitura
        ? `<div class="grafico-leitura"><span class="grafico-leitura-rotulo">Leitura do momento</span>${escapar(opcoes.leitura)}</div>`
        : ""
    }
    <div class="grafico-acoes">
      ${opcoes.aoClicarDados ? '<button class="btn-texto" type="button" data-acao="ver-dados">Ver dados</button>' : ""}
      <button class="btn-texto" type="button" data-acao="baixar-imagem">Baixar imagem</button>
      <button class="btn-texto" type="button" data-acao="como-calculamos">Como calculamos</button>
    </div>
  `;
  registrarExplicacoes(elementoPai);

  const canvas = document.getElementById(idCanvas);
  if (canvas) {
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `${titulo}. ${item ? item.oQueE : ""}`);
  }
  return canvas;
}

/* ------------------------------------------------------------------ */
/* 4.3 — Tabela                                                         */
/* ------------------------------------------------------------------ */

/**
 * Monta a linha de explicação de uma tabela (plano 17 §4.3) e devolve o texto.
 */
export function explicacaoTabela(codigo) {
  const item = explicacao(codigo);
  return item ? `${item.oQueE} ${item.comoLer}` : "";
}

/* ------------------------------------------------------------------ */
/* Utilidades                                                           */
/* ------------------------------------------------------------------ */

export function escapar(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Redimensiona todos os gráficos ativos (troca de tema / redimensiona janela). */
export function redimensionarGraficos() {
  graficosAtivos.forEach((instancia) => {
    try {
      instancia.resize();
    } catch {
      /* instâncias descartadas */
    }
  });
  redimensionar();
}

/** Esvazia o registro de gráficos (ao trocar de tela). */
export function limparGraficos() {
  graficosAtivos.clear();
}
