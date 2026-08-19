let charts = {};

export function criarGraficoTemporal(canvasId, dados) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  destruir(canvasId);

  const rotulos = Object.keys(dados.dias).sort();
  const totais = rotulos.map((dia) =>
    Object.values(dados.dias[dia]).reduce((a, b) => a + b, 0)
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
          backgroundColor: "rgba(34,197,94,0.15)",
          fill: true,
          tension: 0.35,
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#94a3b8", maxTicksLimit: 15 }, grid: { color: "#1e293b" } },
        y: { beginAtZero: true, ticks: { color: "#94a3b8", precision: 0 }, grid: { color: "#1e293b" } },
      },
    },
  });
  return charts[canvasId];
}

export function criarGraficoRosca(canvasId, distribuicao) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  destruir(canvasId);

  const cores = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
  const rotulos = Object.keys(distribuicao);
  const valores = Object.values(distribuicao);

  charts[canvasId] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rotulos,
      datasets: [
        {
          data: valores,
          backgroundColor: rotulos.map((_, i) => cores[i % cores.length]),
          borderWidth: 2,
          borderColor: "#0f172a",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0", boxWidth: 12 } },
      },
    },
  });
  return charts[canvasId];
}

export function destruir(canvasId) {
  if (charts[canvasId]) {
    charts[canvasId].destroy();
    delete charts[canvasId];
  }
}