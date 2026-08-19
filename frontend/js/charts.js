let charts = {};

const CORES = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

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

  const rotulos = Object.keys(dados.dias || {}).sort();
  const totais = rotulos.map((dia) =>
    Object.values(dados.dias[dia] || {}).reduce((a, b) => a + b, 0)
  );

  charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels: rotulos,
      datasets: [
        {
          label: "Menções por dia",
          data: totais,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: "#22c55e",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: "#94a3b8", maxTicksLimit: 12 },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#94a3b8", precision: 0 },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
  return charts[canvasId];
}

export function criarGraficoDonut(canvasId, distribuicao, cores = CORES) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  const rotulos = Object.keys(distribuicao || {});
  const valores = Object.values(distribuicao || {});

  charts[canvasId] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rotulos,
      datasets: [
        {
          data: valores,
          backgroundColor: rotulos.map((_, i) => cores[i % cores.length]),
          borderWidth: 2,
          borderColor: "#1e293b",
          hoverOffset: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8", boxWidth: 12, padding: 14 } },
      },
    },
  });
  return charts[canvasId];
}

export function criarGraficoBarras(canvasId, distribuicao, formatador, horizontal = true) {
  const ctx = contexto(canvasId);
  if (!ctx) return null;

  const rotulos = Object.keys(distribuicao || {});
  const valores = Object.values(distribuicao || {});

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
            x: { ticks: { color: "#94a3b8", callback: (v) => (formatador ? formatador(v) : v) }, grid: { color: "rgba(255,255,255,0.05)" } },
            y: { ticks: { color: "#e2e8f0" }, grid: { display: false } },
          }
        : {
            x: { ticks: { color: "#94a3b8" }, grid: { display: false } },
            y: { ticks: { color: "#94a3b8", callback: (v) => (formatador ? formatador(v) : v) }, grid: { color: "rgba(255,255,255,0.05)" } },
          },
    },
  });
  return charts[canvasId];
}

export { destruir };