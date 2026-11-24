/**
 * Gráficos da análise lexical (plano 10 §3/§4.2) — ECharts, interativos.
 *
 * Substitui os canvas/SVG antigos, que ficavam ilegíveis:
 *   G-21 Mapa de proximidade (AFC)  — scatter com zoom/pan e rótulos sem sobreposição
 *   G-20 Grupos de assuntos (CHD)   — cards + barras de participação legíveis
 *   Dendrograma da CHD              — linhas com zoom, legenda por classe e tooltip
 *   G-22 Rede de palavras (grafo)   — grafo de forças com zoom/arrastar, destaque de
 *                                     vizinhos e rótulos só nos nós relevantes
 *   G-23 Nuvem / G-24 Zipf          — mantidos no módulo antigo
 *
 * Regras aplicadas (plano 10 §4.2): título-conclusão fica no cartão; fonte ≥ 12 px;
 * rótulos sem sobreposição; sem 3D; sem eixo duplo; cores por classe iguais em
 * todos os gráficos; "ver dados" e texto de leitura no cartão.
 *
 * Todas as funções devolvem a instância do ECharts (para resize) e não quebram
 * quando o dado está vazio (mostram uma mensagem clara).
 */

const PALETA = [
  "#2563eb", "#16a34a", "#d97706", "#7c3aed", "#dc2626",
  "#0891b2", "#db2777", "#65a30d",
];

let instancias = [];

function cor(variavel, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
    return v || fallback;
  } catch {
    return fallback;
  }
}

function textoBase(opcoes = {}) {
  const t = cor("--texto", "#e2e8f0");
  const tm = cor("--texto-mutado", "#94a3b8");
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: t, fontSize: 12 },
    tooltip: {
      backgroundColor: cor("--card", "#111827"),
      borderColor: cor("--border", "#334155"),
      textStyle: { color: t, fontSize: 12 },
      confine: true,
      ...(opcoes.tooltip || {}),
    },
    ...opcoes,
  };
}

function vazio(elemento, mensagem) {
  if (!elemento) return null;
  elemento.innerHTML =
    `<p class="lex-vazio">${mensagem}</p>`;
  return null;
}

function instanciar(elemento, opcoes) {
  if (!elemento || typeof echarts === "undefined") return null;
  const existente = echarts.getInstanceByDom(elemento);
  if (existente) existente.dispose();
  const grafico = echarts.init(elemento, null, { renderer: "canvas" });
  grafico.setOption(opcoes);
  instancias.push(grafico);
  return grafico;
}

/** Redimensiona todos os gráficos lexicais (troca de tema / janela). */
export function redimensionarLexicais() {
  instancias = instancias.filter((g) => {
    try {
      if (g.isDisposed && g.isDisposed()) return false;
      g.resize();
      return true;
    } catch {
      return false;
    }
  });
}

/** Esvazia o registro (ao trocar de escopo). */
export function limparLexicais() {
  instancias.forEach((g) => {
    try {
      g.dispose();
    } catch {
      /* já descartado */
    }
  });
  instancias = [];
}

/* ================================================================== */
/* G-21 — Mapa de proximidade (AFC)                                    */
/* ================================================================== */
export function desenharAfc(elemento, afc) {
  if (!afc || !(afc.palavras || []).length) {
    return vazio(
      elemento,
      "Mapa de proximidade sem dados neste escopo. Rode <code>analise_lexical_escopos.py</code> no backend."
    );
  }
  const LIMITE_ROTULOS = 30;
  const distancia = (p) => Math.hypot(p.eixo1 || 0, p.eixo2 || 0);
  const palavras = [...(afc.palavras || [])].sort((a, b) => distancia(b) - distancia(a));
  const comRotulo = new Set(palavras.slice(0, LIMITE_ROTULOS).map((p) => p.rotulo));

  const azul = cor("--azul", PALETA[0]);
  const ambar = cor("--ambar", PALETA[2]);
  const muted = cor("--texto-mutado", "#94a3b8");

  const series = [
    {
      name: "Palavras",
      type: "scatter",
      data: palavras.map((p) => [p.eixo1, p.eixo2, p.rotulo, distancia(p)]),
      symbolSize: (v) => 6 + Math.min(12, Math.abs(Number(v[3] || 0))),
      itemStyle: { color: ambar, opacity: 0.9 },
      label: {
        show: true,
        formatter: (p) => (comRotulo.has(p.data[2]) ? p.data[2] : ""),
        position: "right",
        fontSize: 12,
        color: cor("--texto-suave", "#cbd5e1"),
      },
      labelLayout: { hideOverlap: true, moveOverlap: "shiftY" },
      emphasis: {
        scale: 1.8,
        label: { show: true, fontSize: 13, fontWeight: "bold" },
        itemStyle: { borderColor: "#fff", borderWidth: 1 },
      },
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { color: muted, opacity: 0.45, type: "dashed" },
        data: [{ xAxis: 0 }, { yAxis: 0 }],
      },
    },
  ];
  if ((afc.periodos || []).length) {
    series.push({
      name: "Períodos",
      type: "scatter",
      data: afc.periodos.map((p) => [p.eixo1, p.eixo2, p.rotulo]),
      symbolSize: 15,
      symbol: "diamond",
      itemStyle: { color: azul, borderColor: "#fff", borderWidth: 1 },
      label: {
        show: true,
        formatter: (p) => p.data[2],
        position: "top",
        fontSize: 12,
        color: cor("--texto-suave", "#cbd5e1"),
      },
      labelLayout: { hideOverlap: true },
      emphasis: { scale: 1.6, label: { fontWeight: "bold" } },
    });
  }

  const instancia = instanciar(
    elemento,
    textoBase({
      grid: { left: 18, right: 26, top: 30, bottom: 54, containLabel: true },
      legend: {
        top: 0,
        textStyle: { color: muted, fontSize: 12 },
      },
      tooltip: {
        trigger: "item",
        formatter: (p) => {
          if (p.seriesName === "Períodos") {
            return `<b>${p.data[2]}</b><br/>eixo 1: ${Number(p.data[0]).toFixed(2)}<br/>eixo 2: ${Number(p.data[1]).toFixed(2)}`;
          }
          return (
            `<b>${p.data[2]}</b><br/>eixo 1: ${Number(p.data[0]).toFixed(2)}` +
            `<br/>eixo 2: ${Number(p.data[1]).toFixed(2)}` +
            `<br/>distância da origem: ${Number(p.data[3]).toFixed(2)}`
          );
        },
      },
      xAxis: {
        type: "value",
        name: "eixo 1 (horizontal)",
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        splitLine: { lineStyle: { color: cor("--border", "#334155"), opacity: 0.3 } },
      },
      yAxis: {
        type: "value",
        name: "eixo 2 (vertical)",
        nameLocation: "middle",
        nameGap: 34,
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        splitLine: { lineStyle: { color: cor("--border", "#334155"), opacity: 0.3 } },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0, yAxisIndex: 0, filterMode: "none" },
        {
          type: "slider",
          xAxisIndex: 0,
          height: 16,
          bottom: 12,
          borderColor: cor("--border", "#334155"),
          fillerColor: "rgba(37, 99, 235, 0.18)",
          textStyle: { color: muted, fontSize: 10 },
        },
      ],
      series,
    })
  );
  return instancia;
}

/* ================================================================== */
/* G-20 — Grupos de assuntos (CHD): cards + barras de participação      */
/* ================================================================== */
export function desenharChd(elementoCards, elementoBarras, chd) {
  if (!chd || !(chd.classes || []).length) {
    return vazio(
      elementoCards,
      "Grupos de assuntos sem dados neste escopo. Rode <code>analise_lexical_escopos.py</code> no backend."
    );
  }
  const classes = [...chd.classes].sort((a, b) => (b.pct_segmentos || 0) - (a.pct_segmentos || 0));

  // Cards com as palavras características (tamanho ∝ χ²).
  if (elementoCards) {
    elementoCards.innerHTML = `<div class="lex-chd">${classes
      .map((cl, i) => {
        const corClasse = PALETA[i % PALETA.length];
        const palavras = cl.palavras || [];
        const maxChi = Math.max(1, ...palavras.map((p) => p.chi2 || 0));
        const chips = palavras
          .slice(0, 12)
          .map((p) => {
            const t = (p.chi2 || 0) / maxChi;
            const fs = (12 + t * 8).toFixed(1);
            return `<span class="lex-chip" style="font-size:${fs}px;color:${corClasse}" title="χ² ${p.chi2} · ${p.frequencia} ocorrências">${escapar(p.palavra)}</span>`;
          })
          .join("");
        return `<div class="lex-classe" data-classe="${cl.classe}" tabindex="0" role="button" style="--lex-cor:${corClasse}">
          <div class="lex-classe-cab">
            <span class="lex-classe-num">Grupo ${cl.classe}</span>
            <span class="lex-classe-pct">${cl.pct_segmentos}% · ${cl.n_segmentos || 0} segmentos</span>
          </div>
          <div class="lex-classe-palavras">${chips || '<span class="lex-vazio">Sem palavras características.</span>'}</div>
        </div>`;
      })
      .join("")}</div>`;
  }

  // Barras horizontais: participação de cada grupo (leitura imediata).
  if (!elementoBarras) return null;
  const dados = [...classes].reverse().map((cl, i) => ({
    value: cl.pct_segmentos,
    itemStyle: { color: PALETA[(classes.length - 1 - i) % PALETA.length], borderRadius: 4 },
  }));
  return instanciar(
    elementoBarras,
    textoBase({
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      tooltip: { trigger: "item", formatter: (p) => `${p.name}: ${p.value}% dos segmentos` },
      xAxis: { type: "value", show: false, max: (v) => Math.min(100, v.max * 1.2) },
      yAxis: {
        type: "category",
        data: [...classes].reverse().map((cl) => {
          const top = (cl.palavras || [])[0]?.palavra || `Grupo ${cl.classe}`;
          return `Grupo ${cl.classe} · ${top}`;
        }),
        axisLabel: { color: cor("--texto-suave", "#cbd5e1"), fontSize: 12 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          data: dados,
          barMaxWidth: 22,
          label: {
            show: true,
            position: "right",
            fontSize: 12,
            color: cor("--texto-suave", "#cbd5e1"),
            formatter: "{c}%",
          },
        },
      ],
    })
  );
}

/* ================================================================== */
/* Dendrograma da CHD                                                  */
/* ================================================================== */
export function desenharDendrograma(elemento, dendrograma, chd) {
  const pol = dendrograma?.polilinhas || [];
  if (!pol.length) {
    return vazio(
      elemento,
      "Dendrograma sem dados neste escopo. Rode <code>analise_lexical_escopos.py</code> no backend."
    );
  }

  // Mapa cor -> nome do grupo (usa a ordem das classes da CHD).
  const classes = (chd?.classes || []).map((c) => c.classe);
  const nomePorCor = {};
  const coresUnicas = [...new Set(pol.map((p) => p.cor))];
  coresUnicas.forEach((c, i) => {
    const indice = Number(String(c).replace(/\D/g, "")) || i + 1;
    nomePorCor[c] = `Grupo ${indice}`;
  });

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const p of pol) {
    for (const v of p.x) {
      if (v < minX) minX = v;
      if (v > maxX) maxX = v;
    }
    for (const v of p.y) {
      if (v < minY) minY = v;
      if (v > maxY) maxY = v;
    }
  }
  if (!Number.isFinite(minX)) return vazio(elemento, "Sem dados do dendrograma.");

  const largura = maxX - minX || 1;
  const altura = maxY - minY || 1;
  // Mantém a proporção: a altura do container acompanha os dados.
  const proporcao = Math.max(0.35, Math.min(1.6, altura / largura));
  if (elemento.parentElement) {
    elemento.style.height = `${Math.round(260 * proporcao + 120)}px`;
  }

  const series = pol.map((p, i) => ({
    name: nomePorCor[p.cor] || `Ramo ${i + 1}`,
    type: "line",
    showSymbol: false,
    smooth: false,
    data: p.x.map((xv, k) => [xv, p.y[k]]),
    lineStyle: {
      width: 1.6,
      opacity: 0.85,
      color: PALETA[coresUnicas.indexOf(p.cor) % PALETA.length],
    },
    emphasis: { lineStyle: { width: 4 } },
  }));

  // Rótulos dos grupos nas folhas (ponto mais à esquerda de cada cor).
  const rotulos = coresUnicas.map((c, i) => {
    const pontos = [];
    pol
      .filter((p) => p.cor === c)
      .forEach((p) => p.x.forEach((xv, k) => pontos.push({ x: xv, y: p.y[k] })));
    const min = pontos.reduce((a, b) => (b.x < a.x ? b : a), pontos[0] || { x: minX, y: minY });
    return {
      value: [min.x, min.y],
      name: nomePorCor[c] || `Grupo ${i + 1}`,
      itemStyle: { color: PALETA[i % PALETA.length] },
    };
  });
  if (rotulos.length) {
    series.push({
      name: "Grupos",
      type: "scatter",
      data: rotulos,
      symbolSize: 7,
      itemStyle: { color: cor("--texto-suave", "#cbd5e1") },
      label: {
        show: true,
        formatter: (p) => p.data.name,
        position: "left",
        fontSize: 12,
        color: cor("--texto-suave", "#cbd5e1"),
      },
      labelLayout: { hideOverlap: true, moveOverlap: "shiftY" },
      silent: true,
    });
  }

  // Agrupa a legenda por cor (uma entrada por grupo).
  const porGrupo = {};
  series.forEach((s) => {
    if (s.name !== "Grupos") porGrupo[s.name] = true;
  });

  return instanciar(
    elemento,
    textoBase({
      grid: { left: 46, right: 24, top: 30, bottom: 48, containLabel: true },
      legend: {
        top: 0,
        data: Object.keys(porGrupo),
        textStyle: { color: cor("--texto-mutado", "#94a3b8"), fontSize: 12 },
        itemWidth: 14,
        itemHeight: 10,
      },
      tooltip: {
        trigger: "item",
        formatter: (p) => {
          if (p.seriesName === "Grupos") return p.data.name;
          return `${p.seriesName}<br/>fusão em ${Number(p.value?.[0] || 0).toFixed(1)}`;
        },
      },
      xAxis: {
        type: "value",
        name: "distância de fusão",
        nameLocation: "middle",
        nameGap: 26,
        nameTextStyle: { color: cor("--texto-mutado", "#94a3b8"), fontSize: 11 },
        axisLabel: { color: cor("--texto-mutado", "#94a3b8"), fontSize: 11 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        show: false,
        min: minY - altura * 0.05,
        max: maxY + altura * 0.05,
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0, filterMode: "none" },
        { type: "inside", yAxisIndex: 0, filterMode: "none" },
        {
          type: "slider",
          xAxisIndex: 0,
          height: 14,
          bottom: 8,
          borderColor: cor("--border", "#334155"),
          fillerColor: "rgba(37, 99, 235, 0.16)",
          textStyle: { color: cor("--texto-mutado", "#94a3b8"), fontSize: 10 },
        },
      ],
      series,
    })
  );
}

/* ================================================================== */
/* G-22 — Rede de palavras (grafo de similitude)                        */
/* ================================================================== */
function comunidades(nos, arestas) {
  /** Detecção simples por propagação de rótulo (suficiente para ≤ 60 nós). */
  const vizinhos = new Map(nos.map((n) => [n.id, []]));
  arestas.forEach((a) => {
    vizinhos.get(a.a)?.push(a.b);
    vizinhos.get(a.b)?.push(a.a);
  });
  const rotulo = new Map(nos.map((n) => [n.id, n.id]));
  for (let iter = 0; iter < 12; iter++) {
    let mudou = false;
    for (const n of nos) {
      const contagem = new Map();
      for (const viz of vizinhos.get(n.id) || []) {
        const r = rotulo.get(viz);
        contagem.set(r, (contagem.get(r) || 0) + 1);
      }
      if (!contagem.size) continue;
      const melhor = [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];
      if (melhor !== rotulo.get(n.id)) {
        rotulo.set(n.id, melhor);
        mudou = true;
      }
    }
    if (!mudou) break;
  }
  const grupos = [...new Set(rotulo.values())];
  return { rotulo, grupos };
}

export function desenharGrafo(elemento, grafo) {
  const todosNos = grafo?.nos || [];
  const todasArestas = grafo?.arestas || [];
  if (!todosNos.length) {
    return vazio(
      elemento,
      "Rede de palavras sem dados neste escopo. Rode <code>analise_lexical_escopos.py</code> no backend."
    );
  }
  if (elemento.parentElement) elemento.style.height = "500px";

  // Limita a rede para manter legibilidade (top 40 nós por peso; top 80 arestas).
  const nos = [...todosNos]
    .sort((a, b) => Number(b.peso || b.frequencia || 0) - Number(a.peso || a.frequencia || 0))
    .slice(0, 40);
  const ids = new Set(nos.map((n) => n.id));
  const arestas = todasArestas
    .filter((a) => ids.has(a.a) && ids.has(a.b))
    .sort((a, b) => Number(b.peso || 1) - Number(a.peso || 1))
    .slice(0, 80);

  const grau = new Map(nos.map((n) => [n.id, 0]));
  arestas.forEach((a) => {
    grau.set(a.a, (grau.get(a.a) || 0) + 1);
    grau.set(a.b, (grau.get(a.b) || 0) + 1);
  });
  const topGrau = new Set(
    [...nos]
      .sort((a, b) => (grau.get(b.id) || 0) - (grau.get(a.id) || 0))
      .slice(0, 20)
      .map((n) => n.id)
  );
  const maxPeso = Math.max(1, ...nos.map((n) => n.peso || n.frequencia || 1));
  const maxAresta = Math.max(1, ...arestas.map((a) => a.peso || 1));

  const { rotulo, grupos } = comunidades(nos, arestas);
  const indiceGrupo = new Map(grupos.map((g, i) => [g, i]));
  const categorias = grupos.map((g, i) => ({
    name: `Grupo ${i + 1}`,
    itemStyle: { color: PALETA[i % PALETA.length] },
  }));

  return instanciar(
    elemento,
    textoBase({
      legend: {
        top: 0,
        data: categorias.map((c) => c.name),
        textStyle: { color: cor("--texto-mutado", "#94a3b8"), fontSize: 12 },
        itemWidth: 12,
        itemHeight: 10,
      },
      tooltip: {
        trigger: "item",
        formatter: (p) => {
          if (p.dataType === "edge") {
            return `co-ocorrência: <b>${p.data.source}</b> ↔ <b>${p.data.target}</b> (${p.data.value})`;
          }
          return `<b>${p.data.name}</b><br/>${p.data.value} ocorrências<br/>${p.data.grau} conexões`;
        },
      },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: true,
          draggable: true,
          categories: categorias,
          force: {
            repulsion: 300,
            edgeLength: [50, 150],
            gravity: 0.05,
            friction: 0.25,
            layoutAnimation: true,
          },
          emphasis: { focus: "adjacency", lineStyle: { width: 4 } },
          label: {
            show: true,
            fontSize: 12,
            color: cor("--texto-suave", "#cbd5e1"),
            position: "right",
          },
          labelLayout: { hideOverlap: true },
          lineStyle: { color: "source", curveness: 0.06, opacity: 0.45 },
          edgeSymbol: ["none", "none"],
          data: nos.map((n) => ({
            name: n.id,
            value: n.peso || n.frequencia || 1,
            grau: grau.get(n.id) || 0,
            label: { show: topGrau.has(n.id) },
            symbolSize: 14 + 26 * ((n.peso || n.frequencia || 1) / maxPeso),
            category: indiceGrupo.get(rotulo.get(n.id)) ?? 0,
          })),
          links: arestas.map((a) => ({
            source: a.a,
            target: a.b,
            value: a.peso || 1,
            lineStyle: { width: 1 + 3 * ((a.peso || 1) / maxAresta) },
          })),
        },
      ],
    })
  );
}

/* ================================================================== */
/* "Ver dados" — tabela acessível de cada gráfico                       */
/* ================================================================== */
/* ================================================================== */
/* Leitura automática dos resultados + CSV + reset de zoom             */
/* ================================================================== */

function _topPalavras(classe, n = 4) {
  return (classe?.palavras || [])
    .slice(0, n)
    .map((p) => escapar(p.palavra))
    .join(", ");
}

export function leituraLexical(tipo, dados, chd) {
  if (tipo === "afc") {
    const palavras = dados?.palavras || [];
    if (!palavras.length) return "";
    const eixo1 = [...palavras].sort((a, b) => (b.eixo1 || 0) - (a.eixo1 || 0));
    const eixo2 = [...palavras].sort((a, b) => (b.eixo2 || 0) - (a.eixo2 || 0));
    const direita = eixo1.slice(0, 3).map((p) => escapar(p.rotulo)).join(", ");
    const esquerda = eixo1.slice(-3).reverse().map((p) => escapar(p.rotulo)).join(", ");
    const cima = eixo2.slice(0, 3).map((p) => escapar(p.rotulo)).join(", ");
    const baixo = eixo2.slice(-3).reverse().map((p) => escapar(p.rotulo)).join(", ");
    return `<div class="lex-leitura" id="lexLeitura">
      <strong>O que este mapa mostra</strong>
      <p>Cada ponto é uma palavra ou período. Quanto mais perto dois pontos estão, mais eles aparecem nos mesmos textos. Os pontos mais afastados da origem são os mais característicos deste escopo.</p>
      <p><b>À direita:</b> ${direita || "—"}. <b>À esquerda:</b> ${esquerda || "—"}. <b>Acima:</b> ${cima || "—"}. <b>Abaixo:</b> ${baixo || "—"}.</p>
      <p class="lex-como-ler">Como ler: eixo 1 (horizontal) e eixo 2 (vertical) são eixos de oposição; não são “notas”. Passe o mouse para ver as coordenadas, use a roda para zoom e arraste para navegar. Clique em “Ver dados” para a tabela completa.</p>
    </div>`;
  }
  if (tipo === "chd") {
    const classes = [...(dados?.classes || [])].sort(
      (a, b) => (b.pct_segmentos || 0) - (a.pct_segmentos || 0)
    );
    if (!classes.length) return "";
    const maior = classes[0];
    const menor = classes[classes.length - 1];
    return `<div class="lex-leitura" id="lexLeitura">
      <strong>O que os grupos mostram</strong>
      <p>O corpus foi dividido em <b>${classes.length} grupos</b> de textos que usam as mesmas palavras. O maior é o <b>Grupo ${maior.classe}</b> (${maior.pct_segmentos}% dos segmentos), com destaque para <b>${_topPalavras(maior)}</b>. O menor é o <b>Grupo ${menor.classe}</b> (${menor.pct_segmentos}%), com <b>${_topPalavras(menor)}</b>.</p>
      <p class="lex-como-ler">Como ler: o tamanho da palavra no cartão indica o χ² (quanto mais típica do grupo). Clique em um cartão para ver os detalhes; a barra mostra a participação de cada grupo.</p>
    </div>`;
  }
  if (tipo === "dendrograma") {
    const pol = dados?.polilinhas || [];
    if (!pol.length) return "";
    let maxX = -Infinity;
    pol.forEach((p) => (p.x || []).forEach((x) => (maxX = Math.max(maxX, x))));
    const classes = chd?.classes || [];
    const top = classes
      .slice(0, 3)
      .map((c) => `Grupo ${c.classe} (${c.pct_segmentos}%)`)
      .join(", ");
    return `<div class="lex-leitura" id="lexLeitura">
      <strong>O que o dendrograma mostra</strong>
      <p>Cada linha é um ramo da árvore. Quanto mais à direita acontece a fusão (máximo ${Number(maxX).toFixed(1)}), mais diferentes são os grupos que se juntam. ${top ? `Os grupos principais são ${top}.` : ""}</p>
      <p class="lex-como-ler">Como ler: comece pelas folhas (grupos) e siga as linhas até a fusão. Use a roda para zoom, arraste para navegar e o controle inferior para percorrer a distância.</p>
    </div>`;
  }
  if (tipo === "grafo") {
    const nos = dados?.nos || [];
    const arestas = dados?.arestas || [];
    if (!nos.length) return "";
    const grau = new Map();
    arestas.forEach((a) => {
      grau.set(a.a, (grau.get(a.a) || 0) + 1);
      grau.set(a.b, (grau.get(a.b) || 0) + 1);
    });
    const centrais = [...nos]
      .sort((a, b) => (grau.get(b.id) || 0) - (grau.get(a.id) || 0))
      .slice(0, 5)
      .map((n) => `${escapar(n.id)} (${grau.get(n.id) || 0})`)
      .join(", ");
    return `<div class="lex-leitura" id="lexLeitura">
      <strong>O que a rede mostra</strong>
      <p>Cada nó é uma palavra; as linhas ligam palavras que aparecem juntas. As mais centrais são <b>${centrais}</b>. A rede exibe as ${nos.length} palavras e ${arestas.length} conexões mais fortes.</p>
      <p class="lex-como-ler">Como ler: quanto maior o nó, mais frequente; quanto mais conexões, mais central. Arraste os nós, use a roda para zoom e passe o mouse para destacar as vizinhas.</p>
    </div>`;
  }
  return "";
}

export function csvLexical(tipo, dados) {
  const linhas = [];
  if (tipo === "afc") {
    linhas.push("palavra;eixo1;eixo2");
    (dados?.palavras || []).forEach((p) =>
      linhas.push(`${p.rotulo};${Number(p.eixo1).toFixed(4)};${Number(p.eixo2).toFixed(4)}`)
    );
  } else if (tipo === "chd") {
    linhas.push("grupo;percentual_segmentos;palavras_caracteristicas");
    (dados?.classes || []).forEach((c) =>
      linhas.push(
        `${c.classe};${c.pct_segmentos};${(c.palavras || []).map((p) => p.palavra).join(" | ")}`
      )
    );
  } else if (tipo === "grafo") {
    linhas.push("palavra;ocorrencias");
    (dados?.nos || []).forEach((n) => linhas.push(`${n.id};${n.peso ?? n.frequencia ?? 0}`));
  } else if (tipo === "dendrograma") {
    linhas.push("ramo;cor;x;y");
    (dados?.polilinhas || []).forEach((p, i) =>
      (p.x || []).forEach((x, k) => linhas.push(`${i + 1};${p.cor};${x};${p.y[k]}`))
    );
  }
  return linhas.join("\n");
}

export function resetarZoom(elementoId) {
  if (typeof echarts === "undefined") return;
  const el = document.getElementById(elementoId);
  const grafico = el && echarts.getInstanceByDom(el);
  if (grafico) grafico.dispatchAction({ type: "restore" });
}

export function tabelaDadosLexicais(tipo, dados) {
  if (tipo === "afc") {
    const linhas = [...(dados?.palavras || [])].slice(0, 25);
    return `<table class="tabela"><thead><tr><th>Palavra/Período</th><th class="num">Eixo 1</th><th class="num">Eixo 2</th></tr></thead><tbody>${linhas
      .map((p) => `<tr><td>${escapar(p.rotulo)}</td><td class="num">${Number(p.eixo1).toFixed(2)}</td><td class="num">${Number(p.eixo2).toFixed(2)}</td></tr>`)
      .join("")}</tbody></table>`;
  }
  if (tipo === "chd") {
    const classes = dados?.classes || [];
    return `<table class="tabela"><thead><tr><th>Grupo</th><th class="num">% dos segmentos</th><th>Palavras características</th></tr></thead><tbody>${classes
      .map((c) => `<tr><td>Grupo ${c.classe}</td><td class="num">${c.pct_segmentos}%</td><td>${(c.palavras || []).slice(0, 8).map((p) => escapar(p.palavra)).join(", ")}</td></tr>`)
      .join("")}</tbody></table>`;
  }
  if (tipo === "grafo") {
    const nos = [...(dados?.nos || [])].sort((a, b) => (b.peso || 0) - (a.peso || 0)).slice(0, 30);
    return `<table class="tabela"><thead><tr><th>Palavra</th><th class="num">Ocorrências</th></tr></thead><tbody>${nos
      .map((n) => `<tr><td>${escapar(n.id)}</td><td class="num">${n.peso ?? n.frequencia ?? 0}</td></tr>`)
      .join("")}</tbody></table>`;
  }
  if (tipo === "dendrograma") {
    const pol = dados?.polilinhas || [];
    return `<table class="tabela"><thead><tr><th>Ramo</th><th>Cor</th><th class="num">Pontos</th><th class="num">Fusão máxima</th></tr></thead><tbody>${pol
      .slice(0, 40)
      .map((p, i) => {
        const max = Math.max(...(p.x || [0]));
        return `<tr><td>${i + 1}</td><td>${escapar(p.cor)}</td><td class="num">${(p.x || []).length}</td><td class="num">${Number(max).toFixed(2)}</td></tr>`;
      })
      .join("")}</tbody></table>`;
  }
  return "";
}

function escapar(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

