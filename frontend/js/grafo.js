// Grafo de similaridade lexical (IRAMUTEQ) — layout de forças em canvas puro.
// Exporta `montarGrafo(canvas, grafo)` que desenha o grafo e reage ao hover.

function formatarNumero(n) {
  return new Intl.NumberFormat("pt-BR").format(Math.round(n || 0));
}

function corTema(variavel) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
  return v || "#94a3b8";
}

export function montarGrafo(canvas, grafo) {
  const nos = grafo.nos || [];
  const arestas = grafo.arestas || [];
  if (!nos.length || !canvas) return;

  const mapa = new Map(nos.map((n) => [n.id, { ...n, x: Math.random(), y: Math.random() }]));
  const ligacoes = arestas
    .map((a) => ({ a: mapa.get(a.a), b: mapa.get(a.b), peso: a.peso || 0 }))
    .filter((e) => e.a && e.b);
  const maxPeso = Math.max(1, ...nos.map((n) => n.peso || 1));
  const maxAresta = Math.max(1, ...arestas.map((a) => a.peso || 1));

  // --- simulação de forças (Fruchterman-Reingold simplificado) ---
  const k = 0.55;
  let temperatura = 0.35;
  for (let it = 0; it < 260; it++) {
    const forcas = new Map();
    nos.forEach((n) => forcas.set(n.id, { fx: 0, fy: 0 }));

    // repulsão entre todos os pares
    for (let i = 0; i < nos.length; i++) {
      for (let j = i + 1; j < nos.length; j++) {
        const a = mapa.get(nos[i].id);
        const b = mapa.get(nos[j].id);
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let d = Math.hypot(dx, dy) || 1e-6;
        const f = (k * k) / (d * d);
        dx /= d;
        dy /= d;
        forcas.get(a.id).fx += dx * f;
        forcas.get(a.id).fy += dy * f;
        forcas.get(b.id).fx -= dx * f;
        forcas.get(b.id).fy -= dy * f;
      }
    }
    // atração nas arestas
    for (const e of ligacoes) {
      let dx = e.b.x - e.a.x;
      let dy = e.b.y - e.a.y;
      let d = Math.hypot(dx, dy) || 1e-6;
      const f = ((d * d) / k) * 0.6;
      dx /= d;
      dy /= d;
      forcas.get(e.a.id).fx += dx * f;
      forcas.get(e.a.id).fy += dy * f;
      forcas.get(e.b.id).fx -= dx * f;
      forcas.get(e.b.id).fy -= dy * f;
    }
    // aplica com leve atração central + resfriamento
    for (const n of nos) {
      const f = forcas.get(n.id);
      const dx = 0.5 - n.x;
      const dy = 0.5 - n.y;
      n.x += (f.fx + dx * 0.06) * temperatura;
      n.y += (f.fy + dy * 0.06) * temperatura;
      n.x = Math.max(0.02, Math.min(0.98, n.x));
      n.y = Math.max(0.02, Math.min(0.98, n.y));
    }
    temperatura *= 0.984;
  }

  const ctx = canvas.getContext("2d");

  function redimensionar() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === 0 || h === 0) return null;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    return { w, h, dpr };
  }

  function desenhar(destaque = null) {
    const dim = redimensionar();
    if (!dim) return;
    const { w, h, dpr } = dim;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    for (const e of ligacoes) {
      ctx.beginPath();
      ctx.moveTo(e.a.x * w, e.a.y * h);
      ctx.lineTo(e.b.x * w, e.b.y * h);
      ctx.strokeStyle = `rgba(148,163,184,${0.12 + 0.45 * (e.peso / maxAresta)})`;
      ctx.lineWidth = 0.6 + 1.6 * (e.peso / maxAresta);
      ctx.stroke();
    }

    for (const n of nos) {
      const r = 5 + 15 * (n.peso / maxPeso);
      const ativo = destaque === n.id;
      ctx.beginPath();
      ctx.arc(n.x * w, n.y * h, ativo ? r + 2 : r, 0, Math.PI * 2);
      ctx.fillStyle = ativo ? "rgba(245,158,11,0.95)" : "rgba(59,130,246,0.8)";
      ctx.fill();
      ctx.strokeStyle = "rgba(148,163,184,0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    const topo = [...nos].sort((a, b) => (b.peso || 0) - (a.peso || 0)).slice(0, 14);
    ctx.font = "600 11px Inter, sans-serif";
    ctx.fillStyle = corTema("--texto-suave");
    for (const n of topo) {
      const r = 5 + 15 * (n.peso / maxPeso);
      ctx.fillText(n.id, n.x * w + r + 3, n.y * h + 3);
    }

    if (destaque) {
      const n = mapa.get(destaque);
      if (n) {
        ctx.font = "600 12px Inter, sans-serif";
        ctx.fillStyle = "#f59e0b";
        ctx.fillText(`${n.id} (${formatarNumero(n.peso)})`, n.x * w + 14, n.y * h - 10);
      }
    }
  }

  function noEm(x, y) {
    const dim = redimensionar();
    if (!dim) return null;
    const { w, h } = dim;
    let melhor = null;
    let menorDist = 18;
    for (const n of nos) {
      const r = 5 + 15 * (n.peso / maxPeso);
      const px = n.x * w;
      const py = n.y * h;
      const d = Math.hypot(x - px, y - py);
      if (d <= r + 8 && d < menorDist) {
        menorDist = d;
        melhor = n.id;
      }
    }
    return melhor;
  }

  function aoMover(e) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    desenhar(noEm(x, y));
  }

  desenhar();
  canvas.addEventListener("mousemove", aoMover);
  canvas.addEventListener("mouseleave", () => desenhar());
  window.addEventListener("resize", () => desenhar());

  return () => {
    canvas.removeEventListener("mousemove", aoMover);
    canvas.removeEventListener("mouseleave", () => desenhar());
    window.removeEventListener("resize", () => desenhar());
  };
}