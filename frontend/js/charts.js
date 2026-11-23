let charts = {};

/* ------------------------------------------------------------------
   Paleta: vem dos tokens do tema (cada app tem a sua identidade).
   ------------------------------------------------------------------ */
function corTema(variavel, fallback = "#64748b") {
  const v = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
  return v || fallback;
}

function hexParaRgba(hex, alfa = 1) {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alfa})`;
}

function paleta() {
  const base = [
    corTema("--verde"),
    corTema("--azul"),
    corTema("--ambar"),
    corTema("--roxo"),
    corTema("--vermelho"),
  ];
  return [
    ...base,
    hexParaRgba(base[1], 0.72),
    hexParaRgba(base[0], 0.72),
    hexParaRgba(base[2], 0.72),
    hexParaRgba(base[3], 0.72),
    hexParaRgba(base[4], 0.72),
    hexParaRgba(base[0], 0.46),
    hexParaRgba(base[1], 0.46),
    hexParaRgba(base[2], 0.46),
    hexParaRgba(base[3], 0.46),
  ];
}

function coresSentimento() {
  return {
    positivo: corTema("--verde"),
    neutro: corTema("--azul"),
    negativo: corTema("--vermelho"),
  };
}

function corContraste(cor) {
  const rgba = String(cor).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  let r, g, b;
  if (rgba) {
    [, r, g, b] = rgba.map(Number);
  } else {
    const h = String(cor).replace("#", "");
    const full = h.length === 3 ? h.split("").map((x) => x + x).join("") : h;
    const n = parseInt(full, 16);
    r = (n >> 16) & 255;
    g = (n >> 8) & 255;
    b = n & 255;
  }
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.62 ? "#121820" : "#ffffff";
}

function fonteGrafico(peso = 600, tamanho = 10) {
  return `${peso} ${tamanho}px Inter, "Segoe UI", system-ui, sans-serif`;
}

function destruir(canvasId) {
  if (charts[canvasId]) {
    charts[canvasId].destroy();
    delete charts[canvasId];
  }
}

function contexto(canvasId) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  destruir(canvasId);
  return el;
}

/* ------------------------------------------------------------------
   Plugin: valores nos pontos / barras / fatias
   ------------------------------------------------------------------ */
function pluginValores({ horizontal = true, formatador = null, maxRotulos = 20 } = {}) {
  return {
    id: "valoresGrafico",
    afterDatasetsDraw(chart) {
      const tipo = chart.config.type;
      const c = chart.ctx;
      const fmt = formatador || ((v) => (typeof v === "number" ? v.toLocaleString("pt-BR") : v));
      c.save();
      c.font = fonteGrafico(600, 10);
      c.textBaseline = "middle";

      if (tipo === "line") {
        const total = chart.data.labels.length;
        const multi = chart.data.datasets.length > 1;
        const passo = total > maxRotulos ? Math.ceil(total / maxRotulos) : 1;
        chart.data.datasets.forEach((ds, di) => {
          const meta = chart.getDatasetMeta(di);
          if (!meta || meta.hidden || !meta.data) return;
          const cor = ds.borderColor || corTema("--texto-suave");
          c.fillStyle = cor;
          const valores = ds.data || [];
          const maximo = Math.max(...valores.map((v) => (typeof v === "number" ? v : 0)));
          let ultimaX = -Infinity;
          meta.data.forEach((pt, i) => {
            const v = valores[i];
            if (v === undefined || v === null) return;
            const ehUltimo = i === valores.length - 1;
            const ehMaximo = v === maximo && v > 0;
            const mostra = multi
              ? ehUltimo || ehMaximo
              : total <= maxRotulos || ehUltimo || ehMaximo || i % passo === 0;
            if (!mostra) return;
            if (pt.x - ultimaX < 26) return;
            ultimaX = pt.x;
            const txt = fmt(v);
            c.textAlign = "center";
            c.fillText(txt, pt.x, pt.y - 9);
          });
        });
      }

      if (tipo === "bar") {
        const meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data) return;
        c.fillStyle = corTema("--texto-suave");
        let ultimo = -Infinity;
        meta.data.forEach((bar, i) => {
          const v = chart.data.datasets[0].data[i];
          if (v === undefined || v === null) return;
          const txt = fmt(v);
          if (horizontal) {
            if (Math.abs(bar.y - ultimo) < 13) return;
            ultimo = bar.y;
            c.textAlign = "left";
            c.fillText(txt, bar.x + 7, bar.y);
          } else {
            if (Math.abs(bar.x - ultimo) < 30) return;
            ultimo = bar.x;
            c.textAlign = "center";
            c.fillText(txt, bar.x, bar.y - 7);
          }
        });
      }

      if (tipo === "doughnut") {
        const meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data) return;
        const dados = chart.data.datasets[0].data || [];
        const total = dados.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        c.textAlign = "center";
        c.textBaseline = "middle";
        meta.data.forEach((arco, i) => {
          const v = Number(dados[i]) || 0;
          const pct = (v / total) * 100;
          if (pct < 5) return;
          const p = arco.tooltipPosition();
          const corFatia = chart.data.datasets[0].backgroundColor[i] || "#64748b";
          c.font = fonteGrafico(700, 11);
          c.fillStyle = corContraste(corFatia);
          c.fillText(`${pct.toFixed(0)}%`, p.x, p.y);
        });
      }
      c.restore();
    },
  };
}

/** Texto no centro da rosca (total). */
function pluginCentro(formatador) {
  return {
    id: "centroRosca",
    afterDraw(chart) {
      if (chart.config.type !== "doughnut") return;
      const dados = chart.data.datasets[0]?.data || [];
      const total = dados.reduce((a, b) => a + (Number(b) || 0), 0);
      if (!total) return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      const x = (chartArea.left + chartArea.right) / 2;
      const y = (chartArea.top + chartArea.bottom) / 2;
      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = corTema("--texto");
      ctx.font = fonteGrafico(700, 20);
      ctx.fillText(formatador ? formatador(total) : total.toLocaleString("pt-BR"), x, y + 2);
      ctx.fillStyle = corTema("--texto-mutado");
      ctx.font = fonteGrafico(500, 9);
      ctx.fillText("total", x, y + 20);
      ctx.restore();
    },
  };
}

/* ------------------------------------------------------------------
   Gráficos
   ------------------------------------------------------------------ */
export function criarGraficoTemporal(canvasId, dados) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  const serieSentimento = dados.serie_sentimento || {};
  const rotulos = Object.keys(serieSentimento);
  if (!rotulos.length) rotulos.push(...Object.keys(dados.dias || {}).sort());

  const cores = coresSentimento();
  const temSerie = Object.values(serieSentimento).some(
    (v) => typeof v === "object" && v !== null
  );

  const datasets = [];
  if (temSerie) {
    for (const [sent, cor] of Object.entries(cores)) {
      datasets.push({
        label: sent[0].toUpperCase() + sent.slice(1),
        data: rotulos.map((dia) => (serieSentimento[dia] && serieSentimento[dia][sent]) || 0),
        borderColor: cor,
        backgroundColor: hexParaRgba(cor, 0.16),
        fill: false,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: cor,
        borderWidth: 2,
      });
    }
  } else {
    const cor = corTema("--verde");
    const totais = rotulos.map((dia) =>
      Object.values(dados.dias[dia] || {}).reduce((a, b) => a + b, 0)
    );
    datasets.push({
      label: "Menções por dia",
      data: totais,
      borderColor: cor,
      backgroundColor: hexParaRgba(cor, 0.14),
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 6,
      pointBackgroundColor: cor,
      borderWidth: 2,
    });
  }

  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: rotulos, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18, right: 8 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: temSerie,
          position: "bottom",
          labels: { color: corTema("--texto-suave"), boxWidth: 12, padding: 14 },
        },
        tooltip: {
          callbacks: {
            label: (c) => ` ${c.dataset.label}: ${Number(c.parsed.y).toLocaleString("pt-BR")}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: corTema("--texto-suave"), maxTicksLimit: 10 },
          grid: { color: corTema("--border") },
        },
        y: {
          beginAtZero: true,
          grace: "10%",
          ticks: { color: corTema("--texto-suave"), precision: 0 },
          grid: { color: corTema("--border") },
        },
      },
    },
    plugins: [pluginValores({ formatador: (v) => Number(v).toLocaleString("pt-BR") })],
  });
  return charts[canvasId];
}

export function criarGraficoDonut(canvasId, distribuicao, cores = paleta(), ordenar = false, formatador = null) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  let entradas = Object.entries(distribuicao || {});
  if (ordenar) entradas.sort((a, b) => b[1] - a[1]);
  const rotulos = entradas.map(([k]) => k);
  const valores = entradas.map(([, v]) => v);
  const total = valores.reduce((a, b) => a + (Number(b) || 0), 0);

  const fmt = formatador || ((v) => Number(v).toLocaleString("pt-BR"));

  charts[canvasId] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rotulos,
      datasets: [
        {
          data: valores,
          backgroundColor: rotulos.map((_, i) => cores[i % cores.length]),
          borderWidth: 2,
          borderColor: corTema("--card"),
          hoverOffset: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: corTema("--texto-suave"),
            boxWidth: 12,
            padding: 14,
            generateLabels: (chart) => {
              const ds = chart.data.datasets[0];
              return chart.data.labels.map((rotulo, i) => {
                const valor = ds.data[i];
                const pct = total ? ((Number(valor) / total) * 100).toFixed(0) : "0";
                return {
                  text: `${rotulo} · ${fmt(valor)} (${pct}%)`,
                  fillStyle: ds.backgroundColor[i],
                  strokeStyle: ds.backgroundColor[i],
                  lineWidth: 1,
                  hidden: false,
                  index: i,
                };
              });
            },
          },
        },
        tooltip: {
          callbacks: {
            label: (c) => {
              const valor = Number(c.parsed) || 0;
              const pct = total ? ((valor / total) * 100).toFixed(1) : "0";
              return ` ${c.label}: ${fmt(valor)} (${pct}%)`;
            },
          },
        },
      },
    },
    plugins: [pluginValores(), pluginCentro(fmt)],
  });
  return charts[canvasId];
}

export function criarGraficoBarras(canvasId, distribuicao, formatador, horizontal = true, ordenar = false) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  let entradas = Object.entries(distribuicao || {});
  if (ordenar) entradas.sort((a, b) => b[1] - a[1]);
  const rotulos = entradas.map(([k]) => k);
  const valores = entradas.map(([, v]) => v);
  const cores = paleta();

  charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rotulos,
      datasets: [
        {
          data: valores,
          backgroundColor: rotulos.map((_, i) => cores[i % cores.length]),
          borderRadius: 6,
          borderSkipped: false,
          maxBarThickness: horizontal ? 22 : 46,
        },
      ],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: horizontal ? 6 : 20, right: horizontal ? 54 : 8 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) =>
              ` ${formatador ? formatador(c.parsed[horizontal ? "x" : "y"]) : c.parsed[horizontal ? "x" : "y"]}`,
          },
        },
      },
      scales: horizontal
        ? {
            x: {
              grace: "14%",
              ticks: {
                color: corTema("--texto-suave"),
                callback: (v) => (formatador ? formatador(v) : v),
              },
              grid: { color: corTema("--border") },
            },
            y: { ticks: { color: corTema("--texto-suave"), autoSkip: false }, grid: { display: false } },
          }
        : {
            x: { ticks: { color: corTema("--texto-suave") }, grid: { display: false } },
            y: {
              grace: "14%",
              ticks: {
                color: corTema("--texto-suave"),
                callback: (v) => (formatador ? formatador(v) : v),
              },
              grid: { color: corTema("--border") },
            },
          },
    },
    plugins: [pluginValores({ horizontal, formatador })],
  });
  return charts[canvasId];
}

export function criarGraficoDispersao(canvasId, dados) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  const palavras = (dados.palavras || []).map((p) => ({
    x: Number(p.eixo1),
    y: Number(p.eixo2),
    rotulo: p.rotulo,
  }));
  const periodos = (dados.periodos || []).map((p) => ({
    x: Number(p.eixo1),
    y: Number(p.eixo2),
    rotulo: p.rotulo,
  }));

  // Remove outliers extremos (artefatos do SVD) para o mapa ficar legível
  const absolutos = [...palavras, ...periodos]
    .map((p) => [Math.abs(p.x), Math.abs(p.y)])
    .flat()
    .sort((a, b) => a - b);
  const limite = absolutos.length
    ? Math.max(absolutos[Math.floor(absolutos.length * 0.98)] || 100, 1)
    : 100;
  const palavrasVisiveis = palavras.filter(
    (p) => Math.abs(p.x) <= limite && Math.abs(p.y) <= limite
  );
  const periodosVisiveis = periodos.filter(
    (p) => Math.abs(p.x) <= limite && Math.abs(p.y) <= limite
  );
  const ocultos =
    palavras.length - palavrasVisiveis.length + periodos.length - periodosVisiveis.length;

  const corPalavra = corTema("--ambar");
  const corPeriodo = corTema("--azul");

  const pluginRotulos = {
    id: "rotulosPeriodos",
    afterDatasetsDraw(chart) {
      const c = chart.ctx;
      const meta = chart.getDatasetMeta(1);
      if (!meta || !meta.data) return;
      c.save();
      c.font = fonteGrafico(600, 10);
      c.fillStyle = corPeriodo;
      c.textAlign = "left";
      c.textBaseline = "middle";
      meta.data.forEach((pt, i) => {
        if (i % 4 !== 0) return;
        const r = periodosVisiveis[i];
        if (!r) return;
        c.fillText(r.rotulo, pt.x + 6, pt.y - 6);
      });
      c.restore();
    },
  };

  charts[canvasId] = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Palavras",
          data: palavrasVisiveis,
          backgroundColor: hexParaRgba(corPalavra, 0.78),
          borderColor: corPalavra,
          borderWidth: 1,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: "Períodos (mês)",
          data: periodosVisiveis,
          backgroundColor: hexParaRgba(corPeriodo, 0.92),
          borderColor: corPeriodo,
          pointStyle: "rectRot",
          pointRadius: 4,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: corTema("--texto-suave"), boxWidth: 12, padding: 14 },
        },
        tooltip: {
          callbacks: {
            label: (c) =>
              c.raw && c.raw.rotulo
                ? `${c.raw.rotulo} (${c.raw.x.toFixed(2)}, ${c.raw.y.toFixed(2)})`
                : c.dataset.label,
          },
        },
        title: {
          display: ocultos > 0,
          text: `${ocultos} pontos com coordenadas extremas ocultos`,
          color: corTema("--texto-mutado"),
          font: { size: 11 },
          padding: { bottom: 4 },
        },
      },
      scales: {
        x: {
          ticks: { color: corTema("--texto-suave") },
          grid: { color: corTema("--border") },
          title: { display: true, text: "Eixo 1", color: corTema("--texto-mutado") },
        },
        y: {
          ticks: { color: corTema("--texto-suave") },
          grid: { color: corTema("--border") },
          title: { display: true, text: "Eixo 2", color: corTema("--texto-mutado") },
        },
      },
    },
    plugins: [pluginRotulos],
  });
  return charts[canvasId];
}

export { destruir, paleta as coresTema };
