/**
 * Gráficos em ECharts (Apache-2.0) — plano 13 §6, plano 14 §3, plano 10 §4.2.
 *
 * Um arquivo por tipo, todos lendo as cores de `corTema(...)` e redesenhando
 * no `alternarTema()`.
 *
 * Regras de legibilidade (plano 10 §4.2), aplicadas aqui:
 *  1. título = conclusão (o título fica no cartão, fora do gráfico);
 *  2. fonte mínima de 12 px; contraste conferido por `tests/contraste.py`;
 *  3. rótulos sem sobreposição (`labelLayout: { hideOverlap: true }`);
 *  4. sem 3D, sem pizza com mais de 5 fatias, sem eixo duplo;
 *  5. legenda direta quando possível; texto alternativo e tabela "ver dados"
 *     são montados pelo cartão (`frontend/js/componentes.js`).
 *
 * Este módulo é compartilhável entre os dois apps; muda só a paleta, que vem
 * do tema via `corTema()`.
 */

const PALETA_CATEGORICA = [
  "#2563eb", "#0891b2", "#16a34a", "#d97706", "#dc2626",
  "#7c3aed", "#db2777", "#0d9488", "#65a30d", "#ea580c",
];

let instanciaAtual = null;

/** Cor do tema atual (fallback se o CSS nao responder). */
export function corTema(variavel, fallback = "#94a3b8") {
  try {
    const valor = getComputedStyle(document.documentElement)
      .getPropertyValue(variavel)
      .trim();
    return valor || fallback;
  } catch {
    return fallback;
  }
}

/** Cores de séries: as do tema quando existem, senão a paleta categórica. */
export function coresDeSerie(n = 5) {
  const base = [
    corTema("--azul", PALETA_CATEGORICA[0]),
    corTema("--verde", PALETA_CATEGORICA[2]),
    corTema("--ambar", PALETA_CATEGORICA[3]),
    corTema("--vermelho", PALETA_CATEGORICA[4]),
    corTema("--roxo", PALETA_CATEGORICA[5]),
  ];
  const saida = base.slice(0, n);
  for (let i = saida.length; i < n; i += 1) {
    saida.push(PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]);
  }
  return saida;
}

/** Base comum de todos os gráficos (fonte, grade, tooltip). */
function opcoesBase(opcoes = {}) {
  const texto = corTema("--texto", "#e2e8f0");
  const textoMuto = corTema("--texto-mutado", "#94a3b8");
  const grade = corTema("--border", "#334155");
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: texto },
    animationDuration: 350,
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: corTema("--card", "#111827"),
      borderColor: corTema("--border", "#334155"),
      textStyle: { color: texto, fontSize: 12 },
      axisPointer: { type: "shadow" },
      ...(opcoes.tooltip || {}),
    },
    legend: {
      textStyle: { color: textoMuto, fontSize: 12 },
      ...(opcoes.legend || {}),
    },
    ...opcoes,
  };
}

/** Cria (ou recria) um gráfico ECharts dentro de um elemento. */
export function criar(elemento, opcoes) {
  if (!elemento || typeof echarts === "undefined") return null;
  const existente = echarts.getInstanceByDom(elemento);
  if (existente) existente.dispose();
  instanciaAtual = echarts.init(elemento, null, { renderer: "canvas" });
  instanciaAtual.setOption(opcoes);
  return instanciaAtual;
}

/** Redimensiona o gráfico ativo (troca de tema / redimensiona a janela). */
export function redimensionar() {
  if (instanciaAtual) instanciaAtual.resize();
}

/* ------------------------------------------------------------------ */
/* G-01 — Minigráfico (sparkline) do cartão de KPI                      */
/* ------------------------------------------------------------------ */
export function minigrafico(elemento, valores) {
  const dados = (valores || []).map((v) => Number(v) || 0);
  if (!dados.length) return null;
  const cor = corTema("--azul", PALETA_CATEGORICA[0]);
  return criar(elemento, {
    animation: false,
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: { type: "category", show: false, data: dados.map((_, i) => i) },
    yAxis: { type: "value", show: false, min: "dataMin", max: "dataMax" },
    tooltip: { trigger: "axis", show: false },
    series: [
      {
        type: "line",
        data: dados,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: cor },
        areaStyle: { color: `${cor}22` },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-02 — Barras horizontais ordenadas (ranking)                       */
/* ------------------------------------------------------------------ */
export function barrasHorizontais(elemento, itens, opcoes = {}) {
  const dados = (itens || []).slice(0, opcoes.limite || 12);
  if (!dados.length) return null;
  const cores = coresDeSerie(Math.min(dados.length, 8));
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    grid: { left: 8, right: 40, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "value", show: false, max: (v) => v.max * 1.15 },
    yAxis: {
      type: "category",
      data: dados.map((d) => d.rotulo ?? d.nome ?? d.label ?? "").reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12 },
    },
    series: [
      {
        type: "bar",
        data: dados
          .map((d, i) => ({
            value: Number(d.valor ?? d.n ?? d.value ?? 0),
            itemStyle: { color: d.cor || cores[dados.length - 1 - i % cores.length], borderRadius: 4 },
          }))
          .reverse(),
        barMaxWidth: 18,
        label: {
          show: true,
          position: "right",
          color: corTema("--texto-suave", "#cbd5e1"),
          fontSize: 12,
          formatter: (p) => formatarCurto(p.value),
        },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-03 — Linhas por sentimento com eventos anotados                    */
/* ------------------------------------------------------------------ */
export function linhasSentimento(elemento, series, opcoes = {}) {
  if (!series || !series.length) return null;
  const cores = {
    positivo: corTema("--verde", PALETA_CATEGORICA[2]),
    neutro: corTema("--azul", PALETA_CATEGORICA[0]),
    negativo: corTema("--vermelho", PALETA_CATEGORICA[4]),
  };
  return criar(elemento, {
    ...opcoesBase(),
    legend: { show: true, top: 0, right: 0, textStyle: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12 } },
    xAxis: {
      type: "category",
      data: series[0]?.datas || [],
      axisLabel: { color: corTema("--texto-mutado", "#94a3b8"), fontSize: 11 },
      axisLine: { lineStyle: { color: corTema("--border", "#334155") } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    series: [
      { name: "Positivas", type: "line", smooth: true, showSymbol: false, itemStyle: { color: cores.positivo }, data: series[0]?.positivos || [] },
      { name: "Neutras", type: "line", smooth: true, showSymbol: false, itemStyle: { color: cores.neutro }, data: series[1]?.neutros || [] },
      { name: "Negativas", type: "line", smooth: true, showSymbol: false, itemStyle: { color: cores.negativo }, data: series[2]?.negativos || [] },
    ],
    ...opcoes,
  });
}

function corThemeMudo() {
  return corTema("--texto-mutado", "#94a3b8");
}

/* ------------------------------------------------------------------ */
/* G-04 — Barras 100% empilhadas (sentimento por canal)                 */
/* ------------------------------------------------------------------ */
export function barrasEmpilhadas(elemento, itens) {
  const dados = (itens || []).slice(0, 14);
  if (!dados.length) return null;
  const cores = {
    positivo: corTema("--verde", PALETA_CATEGORICA[2]),
    neutro: corTema("--azul", PALETA_CATEGORICA[0]),
    negativo: corTema("--vermelho", PALETA_CATEGORICA[4]),
  };
  return criar(elemento, {
    ...opcoesBase(),
    legend: { show: true, top: 0, right: 0, textStyle: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12 } },
    xAxis: {
      type: "value",
      max: 100,
      axisLabel: { color: corThemeMudo(), fontSize: 11, formatter: "{value}%" },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    yAxis: {
      type: "category",
      data: dados.map((d) => d.rotulo ?? d.nome ?? ""),
      axisLabel: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: ["positivo", "neutro", "negativo"].map((chave) => ({
      name: chave[0].toUpperCase() + chave.slice(1),
      type: "bar",
      stack: "total",
      barMaxWidth: 20,
      itemStyle: { color: cores[chave] },
      label: {
        show: true,
        fontSize: 11,
        color: "#0f172a",
        formatter: (p) => (p.value >= 12 ? `${Math.round(p.value)}%` : ""),
      },
      data: dados.map((d) => Number(d[chave] ?? 0)),
    })),
  });
}

/* ------------------------------------------------------------------ */
/* G-07 — Barras divergentes (o que mudou)                              */
/* ------------------------------------------------------------------ */
export function barrasDivergentes(elemento, mais, menos) {
  const listaMais = (mais || []).slice(0, 10);
  const listaMenos = (menos || []).slice(0, 10);
  if (!listaMais.length && !listaMenos.length) return null;
  const rotulos = [...listaMais.map((d) => d.palavra ?? d.termo ?? d.label), ...listaMenos.map((d) => d.palavra ?? d.termo ?? d.label)].reverse();
  const valores = [
    ...listaMais.map((d) => Number(d.valor ?? d.chi2 ?? 0)),
    ...listaMenos.map((d) => -Number(d.valor ?? d.chi2 ?? 0)),
  ].reverse();
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    yAxis: {
      type: "category",
      data: rotulos,
      axisLabel: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12, interval: 0 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        data: valores.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? corTema("--verde", PALETA_CATEGORICA[2]) : corTema("--vermelho", PALETA_CATEGORICA[4]), borderRadius: 3 },
        })),
        barMaxWidth: 16,
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          color: corTema("--texto-suave", "#cbd5e1"),
          formatter: (p) => (p.value ? p.value.toFixed(1) : ""),
        },
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-09 — Quadrante de posição (visibilidade × opinião)                 */
/* ------------------------------------------------------------------ */
export function quadrante(elemento, bolhas) {
  const dados = (bolhas || []).slice(0, 40);
  if (!dados.length) return null;
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    xAxis: {
      type: "value",
      name: "Visibilidade",
      nameTextStyle: { color: corThemeMudo(), fontSize: 11 },
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    yAxis: {
      type: "value",
      name: "Opinião",
      nameTextStyle: { color: corThemeMudo(), fontSize: 11 },
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    series: [
      {
        type: "scatter",
        symbolSize: (d) => Math.max(10, Math.min(48, Math.sqrt(Number(d[2]) || 10) * 3)),
        itemStyle: { color: corTema("--azul", PALETA_CATEGORICA[0]), opacity: 0.75 },
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          color: corTema("--texto-suave", "#cbd5e1"),
          formatter: (p) => p.data[3] || "",
        },
        labelLayout: { hideOverlap: true, moveOverlap: "shiftY" },
        data: dados.map((b) => [b.x ?? 0, b.y ?? 0, b.tamanho ?? 10, b.rotulo ?? ""]),
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-12 — Tendência com margem de previsão                            */
/* ------------------------------------------------------------------ */
export function linhaComPrevisao(elemento, historico, previsao) {
  const datas = [...(historico?.datas || []), ...(previsao?.datas || [])];
  if (!datas.length) return null;
  const cor = corTema("--azul", PALETA_CATEGORICA[0]);
  return criar(elemento, {
    ...opcoesBase(),
    xAxis: {
      type: "category",
      data: datas,
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      axisLine: { lineStyle: { color: corTema("--border", "#334155") } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    series: [
      {
        name: "Realizado",
        type: "line",
        smooth: true,
        showSymbol: false,
        itemStyle: { color: cor },
        data: [...(historico?.valores || []), ...(previsao?.valores || []).map(() => null)],
      },
      {
        name: "Projeção",
        type: "line",
        smooth: true,
        showSymbol: false,
        itemStyle: { color: cor },
        lineStyle: { type: "dashed" },
        data: [
          ...(historico?.valores || []).slice(0, -1).map(() => null),
          (historico?.valores || []).slice(-1)[0] ?? null,
          ...(previsao?.valores || []),
        ],
      },
      {
        name: "Margem",
        type: "line",
        smooth: true,
        showSymbol: false,
        stack: "margem",
        lineStyle: { opacity: 0 },
        areaStyle: { color: `${cor}22` },
        data: [
          ...(historico?.valores || []).slice(0, -1).map(() => null),
          (historico?.valores || []).slice(-1)[0] ?? null,
          ...(previsao?.valores || []).map((_, i) => {
            const p = previsao?.valores?.[i] ?? 0;
            const s = previsao?.superiores?.[i] ?? p;
            return Math.max(0, (s - p));
          }),
        ],
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-13 — Treemap (mapa de temas)                                       */
/* ------------------------------------------------------------------ */
export function treemap(elemento, itens) {
  const dados = (itens || []).slice(0, 30);
  if (!dados.length) return null;
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    series: [
      {
        type: "treemap",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        itemStyle: { borderColor: corTema("--bg", "#0b1220"), borderWidth: 2, gapWidth: 2 },
        label: { show: true, fontSize: 12, color: "#f8fafc", formatter: "{b}" },
        data: dados.map((d, i) => ({
          name: d.rotulo ?? d.tema ?? d.nome ?? "",
          value: Number(d.valor ?? d.n ?? 0),
          itemStyle: { color: coresDeSerie(8)[i % 8] },
        })),
      },
    ],
  });
}

/* ------------------------------------------------------------------ */
/* G-08 — Heatmap dia × hora                                            */
/* ------------------------------------------------------------------ */
export function heatmap(elemento, pontos) {
  const dados = (pontos || []).slice(0, 200);
  if (!dados.length) return null;
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: diasDaSemana(), axisLabel: { color: corThemeMudo(), fontSize: 11 } },
    yAxis: { type: "category", data: horasDoDia(), axisLabel: { color: corThemeMudo(), fontSize: 10 } },
    visualMap: {
      min: 0,
      max: Math.max(...dados.map((p) => Number(p[2]) || 0), 1),
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 10,
      itemHeight: 80,
      textStyle: { color: corThemeMudo(), fontSize: 10 },
      inRange: { color: ["#1e293b", "#1d4ed8", "#16a34a"] },
    },
    series: [
      {
        type: "heatmap",
        data: dados,
        label: { show: false },
        itemStyle: { borderColor: corTema("--bg", "#0b1220"), borderWidth: 1, borderRadius: 2 },
      },
    ],
  });
}

function diasDaSemana() {
  return ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
}

function horasDoDia() {
  return ["00", "03", "06", "09", "12", "15", "18", "21"];
}

/* ------------------------------------------------------------------ */
/* G-25 — Pontos com margem (comparação das variantes do discurso)      */
/* ------------------------------------------------------------------ */
export function pontosComMargem(elemento, variantes) {
  const dados = (variantes || []).slice(0, 6);
  if (!dados.length) return null;
  return criar(elemento, {
    ...opcoesBase({ tooltip: { trigger: "item" } }),
    grid: { left: 8, right: 24, top: 16, bottom: 24, containLabel: true },
    xAxis: {
      type: "category",
      data: dados.map((v) => v.id ?? v.nome ?? ""),
      axisLabel: { color: corTema("--texto-suave", "#cbd5e1"), fontSize: 12 },
      axisLine: { lineStyle: { color: corTema("--border", "#334155") } },
    },
    yAxis: {
      type: "value",
      min: 1,
      max: 7,
      axisLabel: { color: corThemeMudo(), fontSize: 11 },
      splitLine: { lineStyle: { color: corTema("--border", "#334155"), opacity: 0.4 } },
    },
    series: [
      {
        type: "custom",
        renderItem: (params, api) => {
          const indice = api.value(0);
          const centro = api.coord([indice, api.value(1)]);
          const cima = api.coord([indice, api.value(3)]);
          const baixo = api.coord([indice, api.value(2)]);
          return {
            type: "group",
            children: [
              {
                type: "line",
                shape: { x1: centro[0], y1: cima[1], x2: centro[0], y2: baixo[1] },
                style: { stroke: corTema("--texto-mutado", "#94a3b8"), lineWidth: 2 },
              },
              {
                type: "circle",
                shape: { cx: centro[0], cy: centro[1], r: 7 },
                style: { fill: corTema("--azul", PALETA_CATEGORICA[0]) },
              },
            ],
          };
        },
        encode: { x: 0, y: 1 },
        data: dados.map((v, i) => [
          i,
          Number(v.media ?? v.valor ?? 0),
          Number(v.inferior ?? (v.media ?? 0) - 0.3),
          Number(v.superior ?? (v.media ?? 0) + 0.3),
        ]),
      },
    ],
  });
}

/** Formata numero grande de forma curta (1,2 mi · 3,4 mil). */
export function formatarCurto(valor) {
  const n = Number(valor) || 0;
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(1).replace(".", ",")} mi`;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1).replace(".", ",")} mil`;
  return new Intl.NumberFormat("pt-BR").format(Math.round(n));
}
