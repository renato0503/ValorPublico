import * as charts from "./charts.js";
import { montarGrafo } from "./grafo.js";
import { iniciarRouter } from "./router.js";
import { iniciarMotion } from "./motion.js";
import {
  abrirLogin,
  agentesPermitidos,
  alternarAuth,
  estadoAuth,
  fecharLogin,
  iniciarAuth,
  lerModoAcesso,
  registrarBotaoAuth,
} from "./auth.js";

import {
  abrirNewsletter,
  carregarCamadaDsm,
  chaveEscopoDsm,
  copiarNewsletter,
  definirJanelaDsm,
  renderizarCamadaDsm,
} from "./dsm.js";

const $ = (id) => document.getElementById(id);

const estado = {
  db: null,
  agentes: [],
  cidade: "",
  parlamentar: "",
  periodo: "",
  tipoTop: "",
  ultimosDados: null,
  lexical: null,
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

/* ---------- captura global de erros (banner visível) ---------- */

let ultimoErro = "";

const historicoErros = [];
window.__erros = historicoErros;

function capturarErro(mensagem, fonte = "erro") {
  const msg = String(mensagem || "Erro desconhecido");
  const semPermissao = /permission|insufficient/i.test(msg);
  const detalhe = semPermissao
    ? "Sem permissão para este escopo. Confira o perfil do usuário em usuarios/{uid}."
    : msg;
  if (detalhe === ultimoErro) return; // evita repetição infinita no mesmo erro
  ultimoErro = detalhe;
  historicoErros.push({ quando: new Date().toISOString(), fonte, mensagem: detalhe });
  if (historicoErros.length > 30) historicoErros.shift();
  const aviso = $("aviso");
  aviso.textContent = `⚠ ${fonte === "rede" ? "Falha de rede/banco" : "Falha no sistema"}: ${detalhe}`;
  aviso.className = "aviso erro";
  aviso.classList.remove("oculto");
  console.error(`[ValorPúblico] ${fonte}:`, mensagem, { escopo: estado.cidade, agente: estado.parlamentar });
}

if (typeof window !== "undefined") {
  window.addEventListener("error", (e) => {
    capturarErro(e.message || "Erro de execução", "erro");
  });
  window.addEventListener("unhandledrejection", (e) => {
    capturarErro(e.reason?.message || e.reason || "Promessa rejeitada", "erro");
  });
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

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* ---------- tema claro/escuro ---------- */

function aplicarTemaInicial() {
  const salvo = localStorage.getItem("vp_tema");
  const tema = salvo === "escuro" ? "escuro" : "claro";
  document.documentElement.dataset.tema = tema;
  atualizarBotaoTema(tema);
}

function atualizarBotaoTema(tema) {
  const el = $("btnTema");
  if (!el) return;
  const icone = el.querySelector(".btn-tema-icone");
  icone.textContent = tema === "claro" ? "☾" : "☀";
  el.title = tema === "claro" ? "Mudar para o tema escuro" : "Mudar para o tema claro";
}

function alternarTema() {
  const atual = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
  document.documentElement.dataset.tema = atual;
  localStorage.setItem("vp_tema", atual);
  atualizarBotaoTema(atual);
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
  renderizarLexical();
}


/* ---------- debug do Firestore (?debug=1) ---------- */

async function ativarDebugFirestore() {
  if (!new URLSearchParams(window.location.search).has("debug")) return;
  try {
    const temImportmap = !!document.querySelector('script[type="importmap"]');
    const modulo = temImportmap
      ? await import("firebase/firestore")
      : await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
    modulo.setLogLevel("debug");
    console.info("[App] Firestore em modo debug (remova ?debug=1 para desligar).");
  } catch (e) {
    console.warn("[App] nao foi possivel ativar o debug do Firestore:", e?.message || e);
  }
}

/* ---------- inicializacao ---------- */

async function inicializar() {
  aplicarTemaInicial();
  await ativarDebugFirestore();
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

/* ---------- análise lexical (IRAMUTEQ) ---------- */

function chaveLexical() {
  if (estado.parlamentar) return `agente-${estado.parlamentar}`;
  if (estado.cidade) return `cidade-${slugCidade(estado.cidade)}`;
  if (estado.periodo) return `periodo-${estado.periodo}`;
  return "geral";
}

function rotuloEscopoLexical() {
  const partes = [];
  if (estado.parlamentar) {
    const ag = estado.agentes.find((a) => a.id === estado.parlamentar);
    partes.push(ag ? ag.nome_urna : "Parlamentar");
  } else if (estado.cidade) {
    partes.push(estado.cidade);
  } else {
    partes.push("Todos");
  }
  const periodos = { hoje: "Hoje", "7d": "Últimos 7 dias", "30d": "Últimos 30 dias" };
  if (estado.periodo && !estado.parlamentar && !estado.cidade) {
    partes.push(periodos[estado.periodo]);
  }
  return `Escopo: ${partes.join(" · ")}`;
}

async function carregarLexical() {
  try {
    const { doc, getDoc } = await import("firebase/firestore");
    const chave = chaveLexical();
    const snap = await getDoc(doc(estado.db, "analise_lexical", chave));
    estado.lexical = snap.exists() ? snap.data() : null;
  } catch (erro) {
    console.warn("[Lexical] falha ao carregar analise:", erro?.code || erro?.message || erro);
    estado.lexical = null;
  }
  renderizarLexical();
}

let limparGrafo = null;

function renderizarLexical() {
  const conteudo = $("lexicalConteudo");
  if (!conteudo) return;
  const rotulo = $("lexicalEscopo");
  if (rotulo) rotulo.textContent = rotuloEscopoLexical();
  if (limparGrafo) {
    limparGrafo();
    limparGrafo = null;
  }
  const aba = document.querySelector(".lex-tab.ativo")?.dataset.lex || "afc";
  if (aba === "chd") return renderizarChd();
  if (aba === "dendrograma") return renderizarDendrograma();
  if (aba === "grafo") return renderizarGrafo();
  renderizarAfc();
}

function renderizarAfc() {
  const conteudo = $("lexicalConteudo");
  const dados = estado.lexical?.afc;
  if (!dados || !dados.palavras?.length) {
    const aviso = dados?.aviso ? ` (${dados.aviso})` : "";
    conteudo.innerHTML =
      `<p class="lex-vazio">AFC sem dados para este escopo${aviso}. Rode <code>analise_lexical_escopos.py</code> no backend.</p>`;
    return;
  }
  conteudo.innerHTML =
    `<div class="lex-afc-box"><canvas id="canvasAfc" aria-label="Mapa fatorial de correspondências"></canvas></div>` +
    `<p class="lex-dica">Palavras (amarelo) e períodos/meses (azul) projetados nos dois primeiros eixos fatoriais.</p>`;
  charts.criarGraficoDispersao("canvasAfc", dados);
}

function renderizarChd() {
  const conteudo = $("lexicalConteudo");
  const dados = estado.lexical?.chd;
  if (!dados || !dados.classes?.length) {
    const aviso = dados?.aviso ? ` (${dados.aviso})` : "";
    conteudo.innerHTML =
      `<p class="lex-vazio">CHD sem classes para este escopo${aviso}. Rode <code>analise_lexical_escopos.py</code> no backend.</p>`;
    return;
  }
  const cores = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#f97316", "#14b8a6"];
  const classes = [...dados.classes].sort((a, b) => (b.pct_segmentos || 0) - (a.pct_segmentos || 0));
  conteudo.innerHTML =
    `<div class="lex-chd">` +
    classes
      .map((cls, i) => {
        const cor = cores[i % cores.length];
        const palavras = cls.palavras || [];
        const maxChi = Math.max(1, ...palavras.map((p) => p.chi2 || 0));
        const chips = palavras
          .slice(0, 14)
          .map((p) => {
            const t = (p.chi2 || 0) / maxChi;
            const fs = (11 + t * 8).toFixed(1);
            const op = 0.55 + t * 0.45;
            return `<span class="lex-chip" style="font-size:${fs}px;color:${cor};opacity:${op}" title="χ² ${p.chi2} · freq ${p.frequencia}">${p.palavra}</span>`;
          })
          .join("");
        return `
          <div class="lex-classe" style="--lex-cor:${cor}">
            <div class="lex-classe-cab">
              <span class="lex-classe-num">Classe ${cls.classe}</span>
              <span class="lex-classe-pct">${cls.pct_segmentos}% dos segmentos</span>
            </div>
            <div class="lex-classe-palavras">${chips || '<span class="lex-vazio">Sem palavras características.</span>'}</div>
          </div>`;
      })
      .join("") +
    `</div>` +
    `<p class="lex-dica">Classes temáticas obtidas por Ward (CHD). O tamanho e a opacidade das palavras refletem o χ² (associação à classe).</p>`;
}

function renderizarDendrograma() {
  const conteudo = $("lexicalConteudo");
  const dados = estado.lexical?.dendrograma;
  if (!dados || !dados.polilinhas?.length) {
    const aviso = dados?.aviso ? ` (${dados.aviso})` : "";
    conteudo.innerHTML =
      `<p class="lex-vazio">Dendrograma sem dados para este escopo${aviso}. Rode <code>analise_lexical_escopos.py</code> no backend.</p>`;
    return;
  }
  const pol = dados.polilinhas;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of pol) {
    for (const v of p.x) { if (v < minX) minX = v; if (v > maxX) maxX = v; }
    for (const v of p.y) { if (v < minY) minY = v; if (v > maxY) maxY = v; }
  }
  if (!isFinite(minX) || !isFinite(minY)) {
    conteudo.innerHTML = '<p class="lex-vazio">Sem dados do dendrograma.</p>';
    return;
  }
  const pad = 10;
  const w = maxX - minX;
  const h = maxY - minY;
  const palette = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#f97316", "#14b8a6"];
  const corMapa = {};
  let k = 0;
  for (const p of pol) {
    if (!corMapa[p.cor]) corMapa[p.cor] = palette[k++ % palette.length];
  }
  const paths = pol
    .map((p) => {
      const pts = p.x.map(
        (v, i) =>
          `${(v - minX + pad).toFixed(1)},${(h - (p.y[i] - minY) + pad).toFixed(1)}`
      );
      return `<path d="M${pts.join(" L ")}" stroke="${corMapa[p.cor]}" fill="none" stroke-width="1.4" stroke-linecap="round"/>`;
    })
    .join("");
  const vbW = (w + pad * 2).toFixed(1);
  const vbH = (h + pad * 2).toFixed(1);
  conteudo.innerHTML =
    `<div class="lex-dendro-box">` +
    `<svg viewBox="0 0 ${vbW} ${vbH}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Dendrograma da CHD">${paths}</svg>` +
    `</div>` +
    `<p class="lex-dica">Dendrograma da CHD (Ward) truncado aos níveis superiores · ${formatarNumero(dados.n_segmentos)} segmentos (UCE). Cores = classes temáticas.</p>`;
}

function renderizarGrafo() {
  const conteudo = $("lexicalConteudo");
  const dados = estado.lexical?.grafo;
  if (!dados || !dados.nos?.length) {
    conteudo.innerHTML =
      '<p class="lex-vazio">Grafo de similaridade sem dados para este escopo. Rode <code>analise_lexical_escopos.py</code> no backend.</p>';
    return;
  }
  conteudo.innerHTML =
    `<div class="lex-grafo-box"><canvas id="canvasGrafo" aria-label="Grafo de similaridade lexical"></canvas></div>` +
    `<p class="lex-dica">Nós = palavras (maior = mais frequente); arestas = co-ocorrência. Passe o mouse sobre um nó para ver a palavra.</p>`;
  limparGrafo = montarGrafo($("canvasGrafo"), dados);
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
  await carregarLexical();

  const { doc, onSnapshot } = await import("firebase/firestore");
  await carregarCamadaDsm(estado.db, chaveEscopoDsm(estado), { doc, onSnapshot });

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
        capturarErro(erro?.message || "Falha ao carregar dados em tempo real.", "rede");
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
    view.distribuicao_categorias || {},
    undefined,
    true
  );
  charts.criarGraficoBarras(
    "graficoValoracao",
    view.valoracao_por_plataforma || {},
    formatarValor,
    true,
    true
  );
  renderizarSentimentoLista(view.distribuicao_sentimento || {});
  renderizarTop(view.top_veiculos || []);
  renderizarTemas(view);
  renderizarAnalise(view);
  renderizarNuvem(view);
  renderizarNoticias(view.noticias_recentes || []);
  renderizarHistorico(dados.historico_ingestao || []);
  $("atualizadoEm").textContent = formatarData(dados.atualizado_em);
  renderizarUltimaExecucao(dados.ultima_execucao);
  renderizarKpisDsm(view);
  renderizarShareOfVoice(view, dados);
}


/* ---------- Camada DSM: KPIs e share of voice ---------- */

function renderizarKpisDsm(view) {
  const mencoes = view.distribuicao_mencoes || {};
  const total = Object.values(mencoes).reduce((a, b) => a + (b || 0), 0);
  const diretas = mencoes.direta || 0;
  const pctDiretas = total ? Math.round((100 * diretas) / total) : 0;

  const elDiretas = $("kpiMencoesDiretas");
  if (elDiretas) {
    elDiretas.textContent = total ? `${pctDiretas}%` : "–";
    const nota = $("kpiMencoesDiretasNota");
    if (nota) {
      nota.textContent = total
        ? `${diretas} diretas · ${mencoes.indireta || 0} indiretas · ${mencoes.indeterminada || 0} indeterminadas`
        : "direta / indireta / indeterminada";
    }
  }

  const alertas = view.alertas || {};
  const niveisAlerta = alertas.niveis || {};
  const elAlertas = $("kpiAlertasCriticos");
  if (elAlertas) {
    elAlertas.textContent = Number(niveisAlerta.critico || 0).toLocaleString("pt-BR");
    const nota = $("kpiAlertasNota");
    if (nota) {
      const totalAlertas = alertas.total || 0;
      nota.textContent = totalAlertas
        ? `${totalAlertas} no total (${niveisAlerta.alto || 0} altos, ${niveisAlerta.atencao || 0} atenção)`
        : "exigem ação imediata";
    }
  }

  const cobertura = view.cobertura || {};
  const elSla = $("kpiSlaMedio");
  if (elSla) {
    const medio = cobertura.sla_min_medio || 0;
    elSla.textContent = medio ? `${Math.round(medio)} min` : "–";
    const nota = $("kpiSlaNota");
    if (nota) {
      nota.textContent = cobertura.sla_min_p95
        ? `p95 ${Math.round(cobertura.sla_min_p95)} min · cobertura ${cobertura.pct_cobertura || 0}%`
        : "publicação → disponibilidade";
    }
  }

  const elAvpe = $("kpiAvpe");
  if (elAvpe) {
    elAvpe.textContent = formatarValor(view.valor_avpe_total || 0);
    const nota = $("kpiAvpeNota");
    if (nota) {
      const avpe = view.valor_avpe_total || 0;
      const mercado = view.valoracao_total || 0;
      nota.textContent = avpe && mercado
        ? `${Math.round((100 * avpe) / mercado)}% do valor de mercado`
        : "centimetragem estimada";
    }
  }
}

function renderizarShareOfVoice(view, dados) {
  const canvas = $("graficoShareVoice");
  const corpo = $("corpoShareVoice");
  const share = (dados && dados.share_of_voice) || [];
  if (!share.length) {
    if (corpo) {
      corpo.innerHTML = '<tr><td colspan="6" class="vazio">Sem dados de share of voice neste escopo.</td></tr>';
    }
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    return;
  }
  const top = share.slice(0, 12);
  if (canvas) {
    charts.criarGraficoBarras(
      "graficoShareVoice",
      Object.fromEntries(top.map((s) => [s.nome || s.agente_id, s.pct_share || 0])),
      (v) => `${v}%`,
      true,
      true
    );
  }
  if (corpo) {
    corpo.innerHTML = top
      .map(
        (s) => `<tr>
          <td class="col-pos">${s.posicao}</td>
          <td>${esc(s.nome || s.agente_id)}</td>
          <td class="num">${formatarNumero(s.clippings)}</td>
          <td class="num">${s.pct_share ?? 0}%</td>
          <td class="num">${s.pct_positivo ?? 0}%</td>
          <td class="num">${s.pct_negativo ?? 0}%</td>
        </tr>`
      )
      .join("");
  }
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
  const saude = $("saudeIngestao");
  if (!exec || !exec.executado_em) {
    el.textContent = "–";
    if (saude) {
      saude.textContent = "● Sem histórico";
      saude.className = "saude saude-aviso";
    }
    return;
  }
  const quando = formatarData(exec.executado_em);
  el.textContent = `${quando} · ${formatarNumero(exec.total_gravados || 0)} clippings`;

  // Indicador de saúde
  if (!saude) return;
  const dataExec = exec.executado_em?.toDate ? exec.executado_em.toDate() : new Date(exec.executado_em);
  const horasDesde = (Date.now() - dataExec.getTime()) / 3600000;

  if (exec.sucesso === false) {
    saude.textContent = "● Última ingestão com erro";
    saude.className = "saude saude-erro";
  } else if (horasDesde > 48) {
    saude.textContent = "● Desatualizado (há mais de 2 dias)";
    saude.className = "saude saude-aviso";
  } else if (horasDesde > 26) {
    saude.textContent = "● Ingestão atrasada";
    saude.className = "saude saude-aviso";
  } else {
    saude.textContent = "● OK";
    saude.className = "saude saude-ok";
  }
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
  if ($("saudeIngestao")) {
    $("saudeIngestao").textContent = "● OK";
    $("saudeIngestao").className = "saude saude-ok";
  }
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

const NOMES_TEMAS = {
  Saude: "Saúde",
  Educacao: "Educação",
  Seguranca: "Segurança",
  "Urbanismo/Obras": "Urbanismo/Obras",
  Transporte: "Transporte",
  "Meio Ambiente": "Meio Ambiente",
  Economia: "Economia",
  Agricultura: "Agricultura",
  "Cultura/Esporte": "Cultura/Esporte",
  "Politica/Camara": "Política/Câmara",
  Eleicoes: "Eleições",
  CPI: "CPI",
  Justica: "Justiça",
  "Social/Assistencia": "Social/Assistência",
  Tecnologia: "Tecnologia",
  "Governo/Administracao": "Governo/Administração",
};

const TEMAS_ORDEM = Object.keys(NOMES_TEMAS);

// Preenche os 16 temas conhecidos (com zero onde nao houver mencoes) para o
// grafico exibir SEMPRE todas as categorias, ordenadas da maior para a menor.
function temasCompletos(distribuicao) {
  const base = distribuicao || {};
  const obj = {};
  TEMAS_ORDEM.forEach((chave) => {
    obj[NOMES_TEMAS[chave]] = base[chave] || 0;
  });
  return obj;
}

function renderizarTemas(view) {
  const canvas = $("graficoTemas");
  if (!canvas) return;
  const temas = temasCompletos(view.distribuicao_temas);
  charts.criarGraficoBarras("graficoTemas", temas, formatarNumero, true, true);
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

/* ---------- últimas notícias + histórico de ingestão ---------- */

function renderizarNoticias(lista) {
  const cont = $("noticiasLista");
  if (!cont) return;
  if (!lista?.length) {
    cont.innerHTML = '<p class="lex-vazio">Sem notícias recentes.</p>';
    return;
  }
  cont.innerHTML = "";
  lista.forEach((n) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "noticia";
    row.title = "Ver detalhes da notícia";
    const cor = CORES_SENTIMENTO[n.sentimento] || "#94a3b8";
    const titulo = (n.texto_limpo || "").slice(0, 110);
    const meta = [n.veiculo, n.agente, n.cidade].filter(Boolean).join(" · ");
    row.innerHTML = `
      <span class="noticia-sent" style="background:${cor}" aria-hidden="true"></span>
      <span class="noticia-txt">
        <span class="noticia-titulo">${esc(titulo)}</span>
        <span class="noticia-meta">${esc(meta)} · ${formatarData(n.data_publicacao)}</span>
      </span>
      <span class="noticia-valor">${formatarValor(n.valor_estimado)}</span>`;
    row.addEventListener("click", () => abrirDetalhe(n));
    cont.appendChild(row);
  });
}

function renderizarHistorico(historico) {
  const cont = $("historicoIngestao");
  if (!cont) return;
  if (!historico?.length) {
    cont.innerHTML =
      '<p class="lex-vazio">Sem histórico de execuções ainda. Rode a ingestão para registrar.</p>';
    return;
  }
  cont.innerHTML = historico
    .map((h) => {
      const ok = h.sucesso !== false;
      const qtd = formatarNumero(h.total_gravados || 0);
      return `
        <div class="hist-row">
          <span class="hist-dot ${ok ? "ok" : "erro"}" aria-hidden="true"></span>
          <span class="hist-info">
            <span class="hist-data">${formatarData(h.executado_em)}</span>
            <span class="hist-status ${ok ? "ok" : "erro"}">${ok ? "sucesso" : "erro"}</span>
          </span>
          <span class="hist-qtd">${qtd} clippings</span>
        </div>`;
    })
    .join("");
}

/* ---------- modal de detalhe (Sprint 24) ---------- */

let clipCache = [];

function abrirDetalhe(clip) {
  if (!clip) return;
  $("modalTitulo").textContent = clip.texto_limpo ? clip.texto_limpo.slice(0, 140) : clip.id_clipping;
  const veiculo = clip.metadados?.veiculo || clip.veiculo || clip.autor || "—";
  const data = formatarData(clip.data_publicacao);
  const sent = clip.sentimento || "neutro";
  const agente = clip.agente ? ` · ${clip.agente}${clip.cidade ? ` (${clip.cidade})` : ""}` : "";
  $("modalMeta").textContent =
    `${veiculo}${agente} · ${data} · ${sent.charAt(0).toUpperCase() + sent.slice(1)}`;

  const valor = clip.valor_estimado ?? 0;
  const alcance = clip.alcance ?? 0;
  $("modalValoracao").innerHTML =
    `<div class="modal-valor"><span class="rotulo">Valor (R$)</span><span class="valor">${formatarValor(valor)}</span></div>` +
    `<div class="modal-valor"><span class="rotulo">Alcance</span><span class="valor">${formatarNumero(alcance)}</span></div>` +
    `<div class="modal-valor"><span class="rotulo">Plataforma</span><span class="valor">${esc(clip.plataforma || "Web")}</span></div>`;

  const temas = clip.categorias || [];
  $("modalCategorias").innerHTML = temas.length
    ? `<strong>Categorias:</strong> ${temas.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}`
    : "";

  const palavras = extrairPalavrasChave(clip.texto_limpo);
  $("modalPalavras").innerHTML = palavras.length
    ? `<strong>Palavras-chave:</strong> ${palavras.map((p) => `<span class="chip">${esc(p)}</span>`).join("")}`
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

// PDF nativo do relatório: imprime apenas o modal (via CSS @media print).
function exportarPdf() {
  document.body.classList.add("print-relatorio");
  window.print();
  setTimeout(() => document.body.classList.remove("print-relatorio"), 300);
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

  // Somatório de espaço real (caracteres / minutos / cm²) por tipo de mídia
  const espaco = base.espaco_total || {};
  const caracSoma = espaco.caracteres || 0;
  const minSoma = Math.round((espaco.duracao_seg || 0) / 60);
  const cm2Soma = espaco.cm2 || 0;

  const cardsEspaco = [
    `<div class="soma-card">Caracteres (site)<span class="valor">${formatarNumero(caracSoma)}</span></div>`,
    `<div class="soma-card">Tempo (TV/Rádio)<span class="valor">${formatarNumero(minSoma)} min</span></div>`,
    `<div class="soma-card">Espaço (impresso)<span class="valor">${formatarNumero(cm2Soma)} cm²</span></div>`,
  ];

  $("relSoma").innerHTML =
    `<div class="soma-card">Menções<span class="valor">${formatarNumero(totalSoma)}</span></div>` +
    `<div class="soma-card">Valor (R$)<span class="valor">${formatarValor(valorSoma)}</span></div>` +
    cardsEspaco.join("");

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
  // Fecha qualquer outro modal antes de abrir um novo
  ["modalDetalhe", "modalRelatorio"].forEach((outroId) => {
    if (outroId !== id) {
      const outro = $(outroId);
      if (outro) fecharModal(outroId);
    }
  });
  const el = $(id);
  el.classList.remove("oculto");
  el.setAttribute("aria-hidden", "false");
}

function fecharModal(id) {
  const el = $(id);
  el.classList.add("oculto");
  el.setAttribute("aria-hidden", "true");
}


/* ---------- Escopo do usuário autenticado ---------- */

function aplicarEscopoUsuario() {
  const permitidos = agentesPermitidos();
  const select = $("filtroParlamentar");
  if (!select) return;
  if (!permitidos.length) return;
  const opcoes = Array.from(select.options).filter((o) => o.value && !permitidos.includes(o.value));
  opcoes.forEach((o) => o.remove());
  if (select.value && !permitidos.includes(select.value)) {
    select.value = permitidos[0] || "";
    estado.parlamentar = select.value;
  }
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
  carregarLexical();
  definirJanelaDsm(estado.periodo || "30d");
});

window.addEventListener("auth:changed", async () => {
  atualizarConta();
  if (estadoAuth.autenticado && !appIniciado) {
    fecharLogin();
    await iniciarApp();
    return;
  }
  if (!estado.db) return;
  if (!estadoAuth.autenticado && !modoPublico) {
    abrirLogin();
    return;
  }
  aplicarEscopoUsuario();
  aplicarFiltros();
});

$("filtroTipoTop").addEventListener("change", (e) => {
  estado.tipoTop = e.target.value;
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
});

$("btnTema")?.addEventListener("click", alternarTema);

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

/* Abas de análise lexical (IRAMUTEQ) */
document.querySelectorAll(".lex-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".lex-tab").forEach((t) => t.classList.remove("ativo"));
    tab.classList.add("ativo");
    renderizarLexical();
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


/* Camada DSM: newsletter consolidada (e-mail/WhatsApp) */
$("btnNewsletterDsm").addEventListener("click", () => {
  abrirNewsletter();
});
$("btnCopiarNewsletter").addEventListener("click", async () => {
  const ok = await copiarNewsletter();
  if (ok) {
    mostrarAviso("Texto da newsletter copiado — cole no WhatsApp/e-mail.");
  } else {
    mostrarAviso("Não foi possível copiar o texto da newsletter.", "erro");
  }
});
/* Fechar modais com a tecla Esc */
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    fecharModal("modalDetalhe");
    fecharModal("modalRelatorio");
  }
});

let appIniciado = false;
let modoPublico = true;

function atualizarConta() {
  const perfil = estadoAuth.perfil;
  const email = $("contaEmail");
  if (email) email.textContent = perfil?.email || estadoAuth.usuario?.email || "—";
  const papel = $("contaPapel");
  if (papel) papel.textContent = perfil?.papel || (estadoAuth.autenticado ? "usuario" : "visitante");
  const escopo = $("contaEscopo");
  if (escopo) {
    const ids = perfil?.agente_ids || [];
    escopo.textContent = ids.length ? ids.join(", ") : (estadoAuth.autenticado ? "geral" : "—");
  }
  const sair = $("btnSairConta");
  if (sair) sair.textContent = estadoAuth.autenticado ? "Sair" : "Entrar";
}

function atualizarEdicao() {
  const agora = new Date();
  const data = $("edicaoData");
  const hora = $("edicaoHora");
  if (data) data.textContent = agora.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
  if (hora) hora.textContent = "atualizado " + agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

async function iniciarApp() {
  if (appIniciado) return;
  appIniciado = true;
  await inicializar();
  atualizarConta();
  atualizarEdicao();
}

async function bootstrap() {
  aplicarTemaInicial();
  iniciarRouter();
  registrarBotaoAuth();
  iniciarMotion();
  $("btnAbrirRelatorio")?.addEventListener("click", () => abrirModal("modalRelatorio"));
  $("btnAbrirNewsletter")?.addEventListener("click", abrirNewsletter);
  $("btnSairConta")?.addEventListener("click", alternarAuth);
  $("btnTemaConta")?.addEventListener("click", alternarTema);
  await iniciarAuth();
  modoPublico = await lerModoAcesso();
  if (!modoPublico && !estadoAuth.autenticado) {
    abrirLogin();
    return;
  }
  await iniciarApp();
}

bootstrap();

// Gancho de depuracao (usado pelo smoke test do painel e pelo console do browser)
window.__app_test = {
  estado,
  renderizar,
  renderizarKpisDsm,
  renderizarShareOfVoice,
  irPara: (rota) => window.__router?.irPara(rota),
};


