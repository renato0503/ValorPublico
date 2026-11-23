let charts = {};

const CORES = [
  "#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4",
  "#ec4899", "#f97316", "#14b8a6", "#84cc16", "#a855f7", "#0ea5e9",
  "#eab308", "#6366f1",
];

// Lê uma cor do tema CSS vigente (claro/escuro) para os gráficos acompanharem.
function corTema(variavel) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
  return v || corTema("--texto-suave");
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

export function criarGraficoTemporal(canvasId, dados) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  const serieSentimento = dados.serie_sentimento || {};
  const rotulos = Object.keys(serieSentimento);
  if (!rotulos.length) rotulos.push(...Object.keys(dados.dias || {}).sort());

  const CORES_SENTIMENTO = {
    positivo: "#22c55e",
    neutro: "#3b82f6",
    negativo: "#ef4444",
  };
  const temSerie = Object.values(serieSentimento).some(
    (v) => typeof v === "object" && v !== null
  );

  const datasets = [];
  if (temSerie) {
    for (const [sent, cor] of Object.entries(CORES_SENTIMENTO)) {
      datasets.push({
        label: sent[0].toUpperCase() + sent.slice(1),
        data: rotulos.map(
          (dia) => (serieSentimento[dia] && serieSentimento[dia][sent]) || 0
        ),
        borderColor: cor,
        backgroundColor: cor + "26",
        fill: false,
        tension: 0.35,
        pointRadius: 2,
        pointBackgroundColor: cor,
        borderWidth: 2,
      });
    }
  } else {
    const totais = rotulos.map((dia) =>
      Object.values(dados.dias[dia] || {}).reduce((a, b) => a + b, 0)
    );
    datasets.push({
      label: "Menções por dia",
      data: totais,
      borderColor: "#22c55e",
      backgroundColor: "rgba(34,197,94,0.12)",
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointBackgroundColor: "#22c55e",
      borderWidth: 2,
    });
  }

  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: rotulos, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: temSerie,
          position: "bottom",
          labels: { color: corTema("--texto-suave"), boxWidth: 12, padding: 14 },
        },
      },
      scales: {
        x: {
          ticks: { color: corTema("--texto-suave"), maxTicksLimit: 12 },
          grid: { color: corTema("--border") },
        },
        y: {
          beginAtZero: true,
          ticks: { color: corTema("--texto-suave"), precision: 0 },
          grid: { color: corTema("--border") },
        },
      },
    },
  });
  return charts[canvasId];
}

export function criarGraficoDonut(canvasId, distribuicao, cores = CORES, ordenar = false) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  let entradas = Object.entries(distribuicao || {});
  if (ordenar) entradas.sort((a, b) => b[1] - a[1]);
  const rotulos = entradas.map(([k]) => k);
  const valores = entradas.map(([, v]) => v);

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
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", labels: { color: corTema("--texto-suave"), boxWidth: 12, padding: 14 } },
      },
    },
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

  const pluginValores = {
    id: "valoresBarras",
    afterDatasetsDraw(chart) {
      const c = chart.ctx;
      const meta = chart.getDatasetMeta(0);
      if (!meta.data || !meta.data.length) return;
      c.save();
      c.font = "600 10px Inter, sans-serif";
      c.textBaseline = "middle";
      c.fillStyle = corTema("--texto-suave");
      meta.data.forEach((bar, i) => {
        const valor = chart.data.datasets[0].data[i];
        if (valor === undefined || valor === null) return;
        const txt = formatador ? formatador(valor) : valor;
        const x = horizontal ? bar.x + 4 : bar.x + bar.width + 4;
        const y = horizontal ? bar.y : bar.y + bar.height / 2;
        c.textAlign = "left";
        c.fillText(txt, x, y);
      });
      c.restore();
    },
  };

  charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rotulos,
      datasets: [
        {
          data: valores,
          backgroundColor: rotulos.map((_, i) => CORES[i % CORES.length]),
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) => (formatador ? formatador(c.parsed[horizontal ? "x" : "y"]) : c.parsed[horizontal ? "x" : "y"]),
          },
        },
      },
      scales: horizontal
        ? {
            x: { grace: "8%", ticks: { color: corTema("--texto-suave"), callback: (v) => (formatador ? formatador(v) : v) }, grid: { color: corTema("--border") } },
            y: { ticks: { color: corTema("--texto-suave") }, grid: { display: false } },
          }
        : {
            x: { ticks: { color: corTema("--texto-suave") }, grid: { display: false } },
            y: { grace: "8%", ticks: { color: corTema("--texto-suave"), callback: (v) => (formatador ? formatador(v) : v) }, grid: { color: corTema("--border") } },
          },
    },
    plugins: [pluginValores],
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

  const pluginRotulos = {
    id: "rotulosPeriodos",
    afterDatasetsDraw(chart) {
      const c = chart.ctx;
      const meta = chart.getDatasetMeta(1);
      if (!meta || !meta.data) return;
      c.save();
      c.font = "10px Inter, sans-serif";
      c.fillStyle = corTema("--azul");
      c.textAlign = "left";
      meta.data.forEach((pt, i) => {
        if (i % 4 !== 0) return;
        const r = periodosVisiveis[i];
        if (!r) return;
        c.fillText(r.rotulo, pt.x + 5, pt.y - 5);
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
          backgroundColor: "rgba(245,158,11,0.75)",
          borderColor: "#f59e0b",
          borderWidth: 1,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: "Períodos (mês)",
          data: periodosVisiveis,
          backgroundColor: "rgba(59,130,246,0.9)",
          borderColor: "#3b82f6",
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

export { destruir };