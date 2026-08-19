import * as charts from "./charts.js";

const $ = (id) => document.getElementById(id);

const estado = {
  db: null,
  agentes: [],
  cidade: "",
  parlamentar: "",
  desinscrever: [],
};

const REDES = new Set(["Twitter", "Instagram", "Facebook"]);

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
  $("kpiVeiculos").textContent = formatarNumero(dados.total_veiculos);
  $("kpiAudiencia").textContent = formatarNumero(dados.audiencia_total);
  $("kpiValoracao").textContent = formatarValor(dados.valoracao_total);
  $("kpiClippings").textContent = formatarNumero(dados.total_clippings);

  renderizarTendencias(dados);

  charts.criarGraficoTemporal("graficoTemporal", dados);
  charts.criarGraficoDonut(
    "graficoSentimento",
    dados.distribuicao_sentimento || {},
    ["#22c55e", "#3b82f6", "#ef4444"]
  );
  charts.criarGraficoDonut(
    "graficoShare",
    dados.distribuicao_categorias || {}
  );
  charts.criarGraficoBarras(
    "graficoValoracao",
    dados.valoracao_por_plataforma || {},
    formatarValor,
    true
  );
  renderizarSentimentoLista(dados.distribuicao_sentimento || {});
  renderizarTop(dados.top_veiculos || []);
  $("atualizadoEm").textContent = formatarData(dados.atualizado_em);
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
  $("sentimentoLista").innerHTML = "";
  $("corpoTop").innerHTML = "";
  $("atualizadoEm").textContent = "–";
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
  if (!lista.length) {
    corpo.innerHTML =
      '<tr><td colspan="5" class="vazio">Sem fontes registradas.</td></tr>';
    return;
  }
  lista.forEach((v, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${v.nome}</td>
      <td class="num">${formatarNumero(v.clippings)}</td>
      <td class="num">${formatarNumero(v.audiencia)}</td>
      <td class="num">${formatarValor(v.valor_estimado)}</td>`;
    corpo.appendChild(tr);
  });
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

inicializar();