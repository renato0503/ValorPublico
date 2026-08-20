import * as charts from "./charts.js";

const $ = (id) => document.getElementById(id);

const estado = {
  db: null,
  agentes: [],
  cidade: "",
  parlamentar: "",
  periodo: "",
  tipoTop: "",
  ultimosDados: null,
  desinscrever: [],
};

const REDES = new Set(["Twitter", "Instagram", "Facebook"]);

const estadoNuvem = {
  geral: {},
  porMes: {},
  meses: [],
  mes: "",
};

/* ---------- utilitarios ---------- */

function mostrarAviso(mensagem, tipo = "") {
  const aviso = $("aviso");
  aviso.textContent = mensagem;
  aviso.className = `aviso ${tipo}`.trim();
}

function formatarNumero(n) {
  return new Intl.NumberFormat("pt-BR").format(Math.round(n || 0));
}

function formatarValor(n) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(n || 0);
}

function formatarData(v) {
  if (!v) return "–";
  const d = v.toDate ? v.toDate() : new Date(v);
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(d);
}

function normalizarData(v) {
  if (!v) return null;
  if (v.toDate) return v.toDate();
  return new Date(v);
}

function chaveDia(v) {
  const d = normalizarData(v);
  if (!d || isNaN(d)) return new Date().toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function slugCidade(cidade) {
  return cidade
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-");
}

function categoria(plataforma) {
  if (REDES.has(plataforma)) return "Redes Sociais";
  if (plataforma === "Web") return "Web";
  return plataforma;
}

/* ---------- inicializacao ---------- */

async function inicializar() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(console.warn);
  }

  let modulo;
  try {
    modulo = await import("./firebase-init.js");
  } catch {
    mostrarAviso(
      "Configuração do Firebase ausente: crie o arquivo frontend/firebase-config.js a partir do firebase-config.example.js.",
      "erro"
    );
    return;
  }
  estado.db = modulo.db;
  await carregarAgentes();
  aplicarFiltros();
}

async function carregarAgentes() {
  const { collection, getDocs } = await import("firebase/firestore");
  const snap = await getDocs(collection(estado.db, "agentes_publicos"));
  estado.agentes = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
  estado.agentes.sort((a, b) =>
    (a.cidade + a.nome_urna).localeCompare(b.cidade + b.nome_urna)
  );
  popularFiltros();
}

function popularFiltros() {
  const selCidade = $("filtroCidade");
  const cidades = [...new Set(estado.agentes.map((a) => a.cidade))].sort();
  cidades.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    selCidade.appendChild(opt);
  });
}

function atualizarParlamentares() {
  const sel = $("filtroParlamentar");
  const valorAtual = sel.value;
  sel.innerHTML = '<option value="">Todos os parlamentares</option>';
  const agentes = estado.cidade
    ? estado.agentes.filter((a) => a.cidade === estado.cidade)
    : estado.agentes;
  agentes.forEach((a) => {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.nome_urna;
    sel.appendChild(opt);
  });
  sel.value = estado.agentes.some((a) => a.id === valorAtual) ? valorAtual : "";
}

/* ---------- assinaturas em tempo real ---------- */

function desinscreverTudo() {
  estado.desinscrever.forEach((fn) => fn());
  estado.desinscrever = [];
}

async function aplicarFiltros() {
  desinscreverTudo();
  atualizarParlamentares();
  mostrarAviso("", "");

  const { doc, onSnapshot } = await import("firebase/firestore");

  let ref;
  if (estado.parlamentar) {
    ref = doc(estado.db, "metricas_por_agente", estado.parlamentar);
  } else if (estado.cidade) {
    ref = doc(estado.db, "metricas_por_cidade", slugCidade(estado.cidade));
  } else {
    ref = doc(estado.db, "metricas", "geral");
  }

  estado.desinscrever.push(
    onSnapshot(
      ref,
      (snap) => {
        if (snap.exists()) {
          renderizar(snap.data());
        } else {
          renderizarVazio();
        }
      },
      (erro) => {
        console.error(erro);
        mostrarAviso("Falha ao carregar dados em tempo real.", "erro");
      }
    )
  );
}

/* ---------- renderizacao ---------- */

const CORES_SENTIMENTO = {
  positivo: "#22c55e",
  neutro: "#3b82f6",
  negativo: "#ef4444",
};

function renderizar(dados) {
  if (!dados || !dados.total_clippings) {
    renderizarVazio();
    return;
  }
  estado.ultimosDados = dados;
  const view = dadosDePeriodo(dados);
  $("kpiVeiculos").textContent = formatarNumero(view.total_veiculos);
  $("kpiAudiencia").textContent = formatarNumero(view.audiencia_total);
  $("kpiValoracao").textContent = formatarValor(view.valoracao_total);
  $("kpiClippings").textContent = formatarNumero(view.total_clippings);

  renderizarTendencias(view);
  renderizarInsights(view);

  charts.criarGraficoTemporal("graficoTemporal", view);
  const distribuicaoSentimento = view.distribuicao_sentimento || {};
  charts.criarGraficoDonut(
    "graficoSentimento",
    distribuicaoSentimento,
    Object.keys(distribuicaoSentimento).map(
      (rotulo) => CORES_SENTIMENTO[rotulo] || "#f59e0b"
    )
  );
  charts.criarGraficoDonut(
    "graficoShare",
    view.distribuicao_categorias || {}
  );
  charts.criarGraficoBarras(
    "graficoValoracao",
    view.valoracao_por_plataforma || {},
    formatarValor,
    true
  );
  renderizarSentimentoLista(view.distribuicao_sentimento || {});
  renderizarTop(view.top_veiculos || []);
  renderizarTemas(view);
  renderizarAnalise(view);
  renderizarNuvem(view);
  $("atualizadoEm").textContent = formatarData(dados.atualizado_em);
  renderizarUltimaExecucao(dados.ultima_execucao);
}

/* Retorna o subconjunto de dados correspondente ao período selecionado. */
function dadosDePeriodo(dados) {
  if (!estado.periodo) return dados;
  const sub = (dados.por_periodo || {})[estado.periodo];
  if (!sub || !sub.total_clippings) return dados;
  return sub;
}

function renderizarInsights(view) {
  const ins = view.insights || {};
  const elMaior = $("insightMaior");
  const elVeiculo = $("insightVeiculo");
  const elTendencia = $("insightTendencia");
  if (!elMaior) return;
  elMaior.textContent =
    `${ins.maior_cobertura?.categoria || "—"} · ${formatarNumero(ins.maior_cobertura?.mencoes || 0)}`;
  elVeiculo.textContent = ins.veiculo_destaque || "—";
  const tendencia = ins.tendencia_positiva;
  elTendencia.textContent =
    tendencia === null || tendencia === undefined
      ? "—"
      : `${tendencia >= 0 ? "+" : ""}${tendencia}%`;
  elTendencia.className = `insight-valor ${
    tendencia >= 0 ? "trend-alta" : tendencia < 0 ? "trend-baixa" : ""
  }`.trim();
}

function renderizarUltimaExecucao(exec) {
  const el = $("ultimaExecucao");
  if (!exec || !exec.executado_em) {
    el.textContent = "–";
    return;
  }
  const quando = formatarData(exec.executado_em);
  el.textContent = `${quando} · ${formatarNumero(exec.total_gravados || 0)} clippings`;
}

/* Calcula tendência comparando os últimos 7 dias com os 7 anteriores da série. */
function calcularTendencia(dias) {
  const chaves = Object.keys(dias || {}).sort();
  if (chaves.length < 14) return null;

  const soma7 = (arr) =>
    arr.reduce((acc, k) => acc + Object.values(dias[k] || {}).reduce((a, b) => a + b, 0), 0);

  const anterior = soma7(chaves.slice(0, chaves.length - 7));
  const recente = soma7(chaves.slice(chaves.length - 7));

  if (anterior === 0) return recente === 0 ? null : 100;
  return Math.round(((recente - anterior) / anterior) * 100);
}

function aplicarTendencia(elementoId, valor, formatador) {
  const el = $(elementoId);
  if (valor === null) {
    el.textContent = "—";
    el.className = "kpi-tendencia";
    return;
  }
  const sinal = valor >= 0 ? "+" : "";
  el.textContent = `${sinal}${valor}% esta semana`;
  el.className = `kpi-tendencia ${valor >= 0 ? "trend-alta" : "trend-baixa"}`;
}

function renderizarTendencias(dados) {
  const t = calcularTendencia(dados.dias);
  aplicarTendencia("tendenciaVeiculos", t, formatarNumero);
  aplicarTendencia("tendenciaAudiencia", t, formatarNumero);
  aplicarTendencia("tendenciaValoracao", t, formatarValor);
  aplicarTendencia("tendenciaClippings", t, formatarNumero);
}

function renderizarVazio() {
  $("kpiVeiculos").textContent = "–";
  $("kpiAudiencia").textContent = "–";
  $("kpiValoracao").textContent = "–";
  $("kpiClippings").textContent = "–";
  ["tendenciaVeiculos", "tendenciaAudiencia", "tendenciaValoracao", "tendenciaClippings"].forEach(
    (id) => {
      $(id).textContent = "—";
      $(id).className = "kpi-tendencia";
    }
  );
  charts.criarGraficoTemporal("graficoTemporal", { dias: {} });
  charts.criarGraficoDonut("graficoSentimento", {});
  charts.criarGraficoDonut("graficoShare", {});
  charts.criarGraficoBarras("graficoValoracao", {}, formatarValor, true);
  if ($("graficoTemas")) charts.criarGraficoBarras("graficoTemas", {}, formatarNumero, true);
  if ($("analiseConteudo")) $("analiseConteudo").innerHTML = "<p>Sem dados para análise.</p>";
  $("sentimentoLista").innerHTML = "";
  $("corpoTop").innerHTML = "";
  const selMes = $("filtroMes");
  selMes.innerHTML = '<option value="">Todos os meses</option>';
  estadoNuvem.mes = "";
  $("nuvemPalavras").innerHTML = "";
  ["insightMaior", "insightVeiculo", "insightTendencia"].forEach((id) => {
    const el = $(id);
    if (el) {
      el.textContent = "—";
      el.className = "insight-valor";
    }
  });
  $("atualizadoEm").textContent = "–";
  $("ultimaExecucao").textContent = "–";
  mostrarAviso(
    "Sem dados ainda. Rode o motor de ingestão e o backend/scripts/atualizar_metricas.py para popular o dashboard.",
    ""
  );
}

function renderizarSentimentoLista(distribuicao) {
  const total = Object.values(distribuicao).reduce((a, b) => a + b, 0) || 1;
  const container = $("sentimentoLista");
  container.innerHTML = "";
  for (const [chave, cor] of Object.entries(CORES_SENTIMENTO)) {
    const qtd = distribuicao[chave] || 0;
    const pct = Math.round((qtd / total) * 100);
    const linha = document.createElement("div");
    linha.className = "barra-sentimento";
    linha.innerHTML = `
      <span class="rotulo">${chave}</span>
      <span class="trilho"><span class="preenchimento" style="width:${pct}%;background:${cor}"></span></span>
      <span class="valor">${formatarNumero(qtd)} (${pct}%)</span>`;
    container.appendChild(linha);
  }
}

function renderizarTop(lista) {
  const corpo = $("corpoTop");
  corpo.innerHTML = "";
  const filtrada =
    estado.tipoTop && estado.tipoTop !== "Geral"
      ? lista.filter((v) => v.categoria_midia === estado.tipoTop)
      : lista;
  if (!filtrada.length) {
    corpo.innerHTML =
      '<tr><td colspan="5" class="vazio">Sem fontes registradas.</td></tr>';
    return;
  }
  filtrada.forEach((v, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${v.nome} <span class="top-cat">${v.categoria_midia || ""}</span></td>
      <td class="num">${formatarNumero(v.clippings)}</td>
      <td class="num">${formatarNumero(v.audiencia)}</td>
      <td class="num">${formatarValor(v.valor_estimado)}</td>`;
    corpo.appendChild(tr);
  });
}

/* ---------- nuvem de palavras ---------- */

const NOMES_MESES = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

function renderizarNuvem(dados) {
  estadoNuvem.geral = dados.nuvem_geral || {};
  estadoNuvem.porMes = dados.nuvem_por_mes || {};
  estadoNuvem.meses = Object.keys(estadoNuvem.porMes).sort().reverse();

  const sel = $("filtroMes");
  const atual = sel.value;
  sel.innerHTML = '<option value="">Todos os meses</option>';
  estadoNuvem.meses.forEach((m) => {
    const [ano, mes] = m.split("-");
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = `${NOMES_MESES[Number(mes) - 1] || mes}/${ano}`;
    sel.appendChild(opt);
  });
  sel.value = estadoNuvem.meses.includes(atual) ? atual : "";
  estadoNuvem.mes = sel.value;
  desenharNuvem();
}

function desenharNuvem() {
  const container = $("nuvemPalavras");
  const freq = estadoNuvem.mes
    ? estadoNuvem.porMes[estadoNuvem.mes] || {}
    : estadoNuvem.geral;
  container.innerHTML = "";

  const entradas = Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 120);
  if (!entradas.length) {
    container.innerHTML =
      '<span class="nuvem-vazio">Sem palavras para o período.</span>';
    return;
  }

  const max = entradas[0][1];
  const min = entradas[entradas.length - 1][1];
  entradas.forEach(([palavra, qtd], i) => {
    const span = document.createElement("span");
    const t = max === min ? 0.5 : (qtd - min) / (max - min);
    span.className = "nuvem-palavra";
    span.style.fontSize = `${(14 + t * 28).toFixed(1)}px`;
    span.style.fontWeight = t > 0.75 ? 700 : t > 0.45 ? 600 : 500;
    span.style.color = i < 8 ? "#f59e0b" : t > 0.5 ? "#38bdf8" : "#94a3b8";
    span.textContent = palavra;
    span.title = `${palavra}: ${formatarNumero(qtd)} menções`;
    container.appendChild(span);
  });
}

/* ---------- temas (Sprint 23) ---------- */

function renderizarTemas(view) {
  const canvas = $("graficoTemas");
  if (!canvas) return;
  const temas = view.distribuicao_temas || {};
  charts.criarGraficoBarras("graficoTemas", temas, formatarNumero, true);
}

/* ---------- análise de mídia (Sprint 26) ---------- */

function renderizarAnalise(view) {
  const conteudo = $("analiseConteudo");
  if (!conteudo) return;
  const aba = document.querySelector(".analise-tab.ativo")?.dataset.aba || "estatistica";
  if (aba === "qualitativa") {
    renderizarAnaliseQualitativa(view);
    return;
  }
  if (aba === "negativa") {
    renderizarAnaliseNegativa(view);
    return;
  }
  renderizarAnaliseEstatistica(view);
}

function renderizarAnaliseEstatistica(view) {
  const conteudo = $("analiseConteudo");
  const temas = view.distribuicao_temas || {};
  const sent = view.distribuicao_sentimento || {};
  const total = view.total_clippings || 1;
  const linhas = [
    ["Menções", formatarNumero(view.total_clippings)],
    ["Veículos", formatarNumero(view.total_veiculos)],
    ["Valoração", formatarValor(view.valoracao_total)],
    ["Positivas", `${formatarNumero(sent.positivo || 0)} (${Math.round(100 * (sent.positivo || 0) / total)}%)`],
    ["Neutras", `${formatarNumero(sent.neutro || 0)} (${Math.round(100 * (sent.neutro || 0) / total)}%)`],
    ["Negativas", `${formatarNumero(sent.negativo || 0)} (${Math.round(100 * (sent.negativo || 0) / total)}%)`],
    ["Principal tema", Object.entries(temas).sort((a, b) => b[1] - a[1])[0]?.[0] || "—"],
  ];
  conteudo.innerHTML =
    "<ul>" + linhas.map(([r, v]) => `<li><span>${r}</span><span class='num'>${v}</span></li>`).join("") + "</ul>";
}

function renderizarAnaliseQualitativa(view) {
  const conteudo = $("analiseConteudo");
  const temas = view.distribuicao_temas || {};
  const top = Object.entries(temas).sort((a, b) => b[1] - a[1]).slice(0, 8);
  if (!top.length) {
    conteudo.innerHTML = "<p>Nuvem de temas vazia para o período.</p>";
    return;
  }
  conteudo.innerHTML =
    "<p>Principais temas (assuntos) no período — base para análise qualitativa:</p><ul>" +
    top.map(([t, n]) => `<li><span>${t}</span><span class='num'>${formatarNumero(n)}</span></li>`).join("") +
    "</ul>";
}

function renderizarAnaliseNegativa(view) {
  const conteudo = $("analiseConteudo");
  const sent = view.distribuicao_sentimento || {};
  const neg = sent.negativo || 0;
  conteudo.innerHTML =
    `<p><strong>${formatarNumero(neg)}</strong> menções negativas no período (${Math.round(100 * neg / (view.total_clippings || 1))}%).</p>` +
    `<p>Consulte a aba "Relatório" e filtre por <em>Negativo</em> para revisar cada ocorrência e planejar respostas.</p>`;
}

/* ---------- modal de detalhe (Sprint 24) ---------- */

let clipCache = [];

function abrirDetalhe(clip) {
  if (!clip) return;
  $("modalTitulo").textContent = clip.texto_limpo ? clip.texto_limpo.slice(0, 140) : clip.id_clipping;
  const veiculo = clip.metadados?.veiculo || clip.autor || "—";
  const data = formatarData(clip.data_publicacao);
  const sent = clip.sentimento || "neutro";
  $("modalMeta").textContent = `${veiculo} · ${data} · ${sent.charAt(0).toUpperCase() + sent.slice(1)}`;

  const valor = clip.valor_estimado ?? 0;
  const alcance = clip.alcance ?? 0;
  $("modalValoracao").innerHTML =
    `<div class="modal-valor"><span class="rotulo">Valor (R$)</span><span class="valor">${formatarValor(valor)}</span></div>` +
    `<div class="modal-valor"><span class="rotulo">Alcance</span><span class="valor">${formatarNumero(alcance)}</span></div>` +
    `<div class="modal-valor"><span class="rotulo">Plataforma</span><span class="valor">${clip.plataforma || "Web"}</span></div>`;

  const temas = clip.categorias || [];
  $("modalCategorias").innerHTML = temas.length
    ? `<strong>Categorias:</strong> ${temas.map((t) => `<span class="chip">${t}</span>`).join("")}`
    : "";

  const palavras = extrairPalavrasChave(clip.texto_limpo);
  $("modalPalavras").innerHTML = palavras.length
    ? `<strong>Palavras-chave:</strong> ${palavras.map((p) => `<span class="chip">${p}</span>`).join("")}`
    : "";

  $("modalConteudo").textContent = clip.texto_limpo || "";
  $("modalLink").href = clip.url || "#";
  $("modalLink").style.display = clip.url ? "" : "none";
  abrirModal("modalDetalhe");
}

function extrairPalavrasChave(texto) {
  if (!texto) return [];
  const paradas = new Set(["a", "o", "de", "da", "do", "em", "e", "que", "para", "com",
    "os", "as", "um", "uma", "na", "no", "por", "se", "mais", "foi", "dos", "das", "nos"]);
  const palavras = texto.toLowerCase().match(/[a-zá-ú0-9]{4,}/g) || [];
  const cont = {};
  palavras.forEach((p) => {
    if (!paradas.has(p)) cont[p] = (cont[p] || 0) + 1;
  });
  return Object.entries(cont).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([p]) => p);
}

/* ---------- modal de relatório (Sprint 25) ---------- */

function abrirRelatorio() {
  abrirModal("modalRelatorio");
  gerarRelatorio();
}

function gerarRelatorio() {
  const periodo = $("relPeriodo").value;
  const tipo = $("relTipo").value;
  const sentimento = $("relSentimento").value;
  const dados = estado.ultimosDados || {};
  const base = periodo ? (dados.por_periodo || {})[periodo] || {} : dados;

  // Como os clippings individuais nao estao nas metricas, buscamos do Firestore
  // apenas o resumo por filtro via métricas agregadas por categoria/sentimento.
  let lista = [];
  const sentMap = base.distribuicao_sentimento || {};
  const catMap = base.distribuicao_categorias || {};
  const temaMap = base.distribuicao_temas || {};

  // Monta somatórios a partir das agregações
  const filtroSent = sentimento ? { [sentimento]: sentMap[sentimento] || 0 } : sentMap;
  const filtroCat = tipo ? { [tipo]: catMap[tipo] || 0 } : catMap;

  const totalSoma = Object.values(filtroSent).reduce((a, b) => a + b, 0);
  const valorSoma = base.valoracao_total || 0;
  const caracSoma = base.total_clippings ? Math.round(base.total_clippings * 1400) : 0;

  $("relSoma").innerHTML =
    `<div class="soma-card">Menções<span class="valor">${formatarNumero(totalSoma)}</span></div>` +
    `<div class="soma-card">Valor (R$)<span class="valor">${formatarValor(valorSoma)}</span></div>` +
    `<div class="soma-card">Espaço (site)<span class="valor">${formatarNumero(caracSoma)} carac.</span></div>`;

  // Lista amostral: representa as menções do período (distribuídas por sentimento/categoria)
  const resumo = [
    ["Portal", catMap.Portal || 0],
    ["Jornal Impresso", catMap["Jornal Impresso"] || 0],
    ["YouTube", catMap.YouTube || 0],
    ["Governo", catMap.Governo || 0],
    ["TV", catMap.TV || 0],
    ["Radio", catMap.Radio || 0],
  ];
  const linhas = resumo
    .filter(([, n]) => (!tipo || n > 0))
    .map(
      ([cat, n]) =>
        `<tr><td>${cat}</td><td class="num">${formatarNumero(n)}</td><td class="num">${formatarValor(valorSoma * (n / (base.total_clippings || 1)))}</td></tr>`
    )
    .join("");
  $("relLista").innerHTML =
    `<table class="tabela"><thead><tr><th>Categoria</th><th class="num">Menções</th><th class="num">Valor est. (R$)</th></tr></thead><tbody>${linhas}</tbody></table>`;
  lista = linhas;
}

/* ---------- utilitários de modal ---------- */

function abrirModal(id) {
  const el = $(id);
  el.classList.remove("oculto");
  el.setAttribute("aria-hidden", "false");
}

function fecharModal(id) {
  const el = $(id);
  el.classList.add("oculto");
  el.setAttribute("aria-hidden", "true");
}

function exportarPdf() {
  window.print();
}

/* ---------- eventos ---------- */

$("filtroCidade").addEventListener("change", (e) => {
  estado.cidade = e.target.value;
  estado.parlamentar = "";
  aplicarFiltros();
});

$("filtroParlamentar").addEventListener("change", (e) => {
  estado.parlamentar = e.target.value;
  aplicarFiltros();
});

$("filtroMes").addEventListener("change", (e) => {
  estadoNuvem.mes = e.target.value;
  desenharNuvem();
});

$("filtroPeriodo").addEventListener("change", (e) => {
  estado.periodo = e.target.value;
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
});

$("filtroTipoTop").addEventListener("change", (e) => {
  estado.tipoTop = e.target.value;
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
});

$("btnAtualizar").addEventListener("click", async () => {
  const btn = $("btnAtualizar");
  const texto = btn.querySelector(".btn-atualizar-texto");
  btn.disabled = true;
  texto.textContent = "Atualizando...";
  try {
    if (window.caches) {
      const chaves = await caches.keys();
      await Promise.all(chaves.map((c) => caches.delete(c)));
    }
    if (navigator.serviceWorker) {
      const registros = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registros.map((r) => r.unregister()));
    }
  } catch (err) {
    console.warn("Falha ao limpar cache:", err);
  }
  location.reload();
});

/* Abas de análise de mídia */
document.querySelectorAll(".analise-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".analise-tab").forEach((t) => t.classList.remove("ativo"));
    tab.classList.add("ativo");
    if (estado.ultimosDados) renderizarAnalise(dadosDePeriodo(estado.ultimosDados));
  });
});

/* Modal de detalhe */
$("fecharDetalhe").addEventListener("click", () => fecharModal("modalDetalhe"));
$("modalDetalhe").addEventListener("click", (e) => {
  if (e.target === $("modalDetalhe")) fecharModal("modalDetalhe");
});

/* Modal de relatório */
$("btnRelatorio").addEventListener("click", abrirRelatorio);
$("fecharRelatorio").addEventListener("click", () => fecharModal("modalRelatorio"));
$("modalRelatorio").addEventListener("click", (e) => {
  if (e.target === $("modalRelatorio")) fecharModal("modalRelatorio");
});
$("btnGerarRelatorio").addEventListener("click", gerarRelatorio);
$("btnExportarPdf").addEventListener("click", exportarPdf);

inicializar();