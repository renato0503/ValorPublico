import * as charts from "./charts.js";
import { montarGrafo } from "./grafo.js";
import { iniciarRouter } from "./router.js";
import * as lexical from "./lexical.js";
import * as lexico from "./lexico.js";
import { iniciarMotion } from "./motion.js";
import { registrarExplicacoes } from "./explicacoes.js";
import { ligarBarraGlobal, aoMudarFiltros } from "./filtros.js";
import * as telas from "./telas.js";
import * as governo from "./governo.js";
import * as simulacao from "./simulacao.js";
import * as personas from "./personas.js";
import { renderMenu, marcarAtivo } from "./menu.js";
import { redimensionarGraficos } from "./componentes.js";
import {
  abrirLogin,
  agentesPermitidos,
  alternarAuth,
  estadoAuth,
  fecharLogin,
  iniciarAuth,
  lerModoAcesso,
  registrarBotaoAuth,
  sair,
} from "./auth.js";

import {
  orgaoAtual,
  orgaoSalvo,
  orgaosDisponiveis,
  definirOrgao,
  limparOrgao,
  orgaoPorSlug,
} from "./orgaos.js";

import {
  abrirNewsletter,
  carregarCamadaDsm,
  chaveEscopoDsm,
  copiarNewsletter,
  definirJanelaDsm,
  renderizarCamadaDsm,
} from "./dsm.js";

const $ = (id) => document.getElementById(id);
const UX_NAV2 = new URLSearchParams(window.location.search).get("ux") !== "nav1";
if (UX_NAV2) document.documentElement.dataset.ux = "nav2";
const CHAVE_SIDEBAR = "vp_sidebar_colapsada";

const estado = {
  db: null,
  agentes: [],
  agentesTodos: [],
  cidade: "",
  parlamentar: "",
  periodo: "",
  tipoTop: "",
  orgao: "",
  orgaoInfo: null,
  uid: "",
  ultimosDados: null,
  lexical: null,
  desinscrever: [],
};

const REDES = new Set(["Twitter", "Instagram", "Facebook", "TikTok", "Threads", "Kwai"]);

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

/* ---------- casa / escopo (Câmara Cuiabá, Câmara VG, ALMT) ---------- */

const ROTULO_CASA = {
  "Camara Cuiaba": "Câmara de Cuiabá",
  "Camara VG": "Câmara de Várzea Grande",
  ALMT: "Assembleia (ALMT)",
  "Governo MT": "Governo de Mato Grosso",
};

function casaDoAgente(a) {
  if (a.casa) return a.casa;
  if (a.esfera === "estadual" || a.cidade === "Mato Grosso") return "ALMT";
  if (a.cidade === "Varzea Grande") return "Camara VG";
  if (a.cidade === "Governo de Mato Grosso") return "Governo MT";
  return "Camara Cuiaba";
}

function rotuloCasa(casa) {
  return ROTULO_CASA[casa] || casa;
}

function renderizarParlamentaresPorCasa() {
  const alvo = $("parlamentaresPorCasa");
  if (!alvo) return;
  if (!estado.agentes.length) {
    alvo.innerHTML =
      '<p class="lex-vazio">Nenhum agente carregado. Faça login para ver as casas.</p>';
    return;
  }
  const grupos = {};
  estado.agentes.forEach((a) => {
    const casa = casaDoAgente(a);
    (grupos[casa] = grupos[casa] || []).push(a);
  });
  const ordem = ["Camara Cuiaba", "Camara VG", "ALMT"];
  const casas = ordem.filter((c) => grupos[c]).concat(
    Object.keys(grupos).filter((c) => !ordem.includes(c))
  );
  alvo.innerHTML = casas
    .map((casa) => {
      const lista = grupos[casa]
        .slice()
        .sort((x, y) => String(x.nome_urna).localeCompare(String(y.nome_urna)));
      const itens = lista
        .map(
          (a) =>
            `<li><a href="#/parlamentares" class="casa-nome">${esc(a.nome_urna)}</a>` +
            `<span class="casa-partido">${esc(a.partido || "")}${
              a.cargo ? " · " + esc(a.cargo) : ""
            }</span></li>`
        )
        .join("");
      return (
        `<div class="casa-grupo">` +
        `<h3>${esc(rotuloCasa(casa))} <span class="casa-total">${lista.length}</span></h3>` +
        `<ul class="casa-lista">${itens}</ul></div>`
      );
    })
    .join("");
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

function corToken(variavel, fallback = "#94a3b8") {
  const v = getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
  return v || fallback;
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
  el.title = tema === "claro" ? "Mudar para o tema escuro" : "Mudar para o tema claro";
}

/* ---------- valor de mídia (secundário/opcional) ---------- */

const CHAVE_VALOR_MIDIA = "vp_mostrar_valor";

function valorMidiaAtivo() {
  try {
    return localStorage.getItem(CHAVE_VALOR_MIDIA) === "1";
  } catch {
    return false;
  }
}

function aplicarPreferenciaValor() {
  const ativo = valorMidiaAtivo();
  document.body.classList.toggle("mostrar-valor", ativo);
  const chk = $("toggleValorMidia");
  if (chk) chk.checked = ativo;
  const kpi = $("kpiValoracao");
  if (kpi) kpi.closest(".card")?.classList.add("valor-midia");
}

function alternarTema() {
  const atual = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
  document.documentElement.dataset.tema = atual;
  localStorage.setItem("vp_tema", atual);
  atualizarBotaoTema(atual);
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
  renderizarLexical();
  renderizarCamadaDsm();
  governo.renderizar(); // gráficos e mapa do Governo usam as cores do tema
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
  const { collection, getDocs, query, where } = await import("firebase/firestore");
  const alvo = estado.orgaoInfo;
  if (!alvo) {
    estado.agentes = [];
    popularFiltros();
    return;
  }
  const snap = await getDocs(
    query(collection(estado.db, "agentes_publicos"), where("orgao", "==", alvo.slug))
  );
  estado.agentesTodos = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
  // Só os agentes do órgão selecionado: nunca mistura frentes.
  estado.agentes = estado.agentesTodos.filter(
    (a) =>
      a.orgao === alvo.slug ||
      a.casa === alvo.casa ||
      (!a.casa && a.cidade === alvo.cidade)
  );
  estado.agentes.sort((a, b) =>
    (a.cidade + a.nome_urna).localeCompare(b.cidade + b.nome_urna)
  );
  popularFiltros();
}

function popularFiltros() {
  const selCidade = $("filtroCidade");
  if (selCidade) {
    if (estado.orgaoInfo) {
      selCidade.innerHTML = `<option value="${esc(estado.cidade)}">${esc(
        estado.orgaoInfo.rotulo
      )}</option>`;
      selCidade.value = estado.cidade;
      selCidade.disabled = true;
    } else {
      selCidade.innerHTML = '<option value="">Selecione o órgão</option>';
      selCidade.disabled = true;
    }
  }
  renderizarParlamentaresPorCasa();
  atualizarParlamentares();
}

function atualizarParlamentares() {
  const sel = $("filtroParlamentar");
  const pretendido = estado.parlamentar || sel.value;
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
  sel.value = estado.agentes.some((a) => a.id === pretendido) ? pretendido : "";
  estado.parlamentar = sel.value;
}

/* ---------- análise lexical (IRAMUTEQ) ---------- */

function chaveLexical() {
  if (estado.parlamentar) return `agente-${estado.parlamentar}`;
  if (estado.orgaoInfo) return `cidade-${estado.orgaoInfo.cidadeDoc}`;
  return "";
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
    const chave = chaveLexical();
    if (!chave) {
      estado.lexical = null;
      renderizarLexical();
      return;
    }
    if (!estado.db) return;
    const { doc, getDoc } = await import("firebase/firestore");
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
  // vocabulário (palavras sem assunto + temas) antes do primeiro desenho
  lexico.carregar().then(() => {
    lexico.ligarControle(conteudo, () => {
      renderizarLexical();
      desenharNuvem();
    });
    _renderizarLexical(conteudo);
  });
}

function _renderizarLexical(conteudo) {
  const rotulo = $("lexicalEscopo");
  if (rotulo) rotulo.textContent = rotuloEscopoLexical();
  if (limparGrafo) {
    limparGrafo();
    limparGrafo = null;
  }
  lexical.limparLexicais();
  const aba = document.querySelector(".lex-tab.ativo")?.dataset.lex || "chd";
  if (aba === "chd") return renderizarChd();
  if (aba === "dendrograma") return renderizarDendrograma();
  if (aba === "grafo") return renderizarGrafo();
  renderizarAfc();
}

function renderizarAfc() {
  const conteudo = $("lexicalConteudo");
  const dados = lexico.filtrarAfc(estado.lexical?.afc);
  conteudo.innerHTML =
    lexico.controleHtml() +
    lexical.leituraLexical("afc", dados) +
    `<div class="lex-afc-box" id="canvasAfc" role="img" aria-label="Mapa de proximidade (AFC)"></div>` +
    `<div class="lex-controles">
       <span class="lex-dica-texto">Arraste para mover · roda para zoom · passe o mouse para detalhes</span>
       <button class="btn-texto" type="button" data-lex-dados="afc">Ver dados</button>
       <button class="btn-texto" type="button" data-lex-csv="afc">Baixar CSV</button>
       <button class="btn-texto" type="button" data-lex-reset="canvasAfc">Resetar zoom</button>
     </div>`;
  lexical.desenharAfc($("canvasAfc"), dados);
}

function renderizarChd() {
  const conteudo = $("lexicalConteudo");
  const dados = lexico.filtrarChd(estado.lexical?.chd);
  conteudo.innerHTML =
    lexico.controleHtml() +
    lexical.leituraLexical("chd", dados) +
    `<div id="chdCards"></div>` +
    `<div class="lex-afc-box" id="chdBarras" role="img" aria-label="Participação de cada grupo de assuntos"></div>` +
    `<div class="lex-controles">
       <span class="lex-dica-texto">Clique em um grupo para ver as palavras típicas · barras = participação</span>
       <button class="btn-texto" type="button" data-lex-dados="chd">Ver dados</button>
       <button class="btn-texto" type="button" data-lex-csv="chd">Baixar CSV</button>
     </div>`;
  lexical.desenharChd($("chdCards"), $("chdBarras"), dados);
}

function renderizarDendrograma() {
  const conteudo = $("lexicalConteudo");
  const dados = estado.lexical?.dendrograma;
  const chdFiltrado = lexico.filtrarChd(estado.lexical?.chd);
  conteudo.innerHTML =
    lexico.controleHtml() +
    lexical.leituraLexical("dendrograma", dados, chdFiltrado) +
    `<div class="lex-dendro-box" id="canvasDendro" role="img" aria-label="Dendrograma dos grupos de assuntos"></div>` +
    `<div class="lex-controles">
       <span class="lex-dica-texto">Roda para zoom · arraste para navegar · barra inferior para percorrer</span>
       <button class="btn-texto" type="button" data-lex-dados="dendrograma">Ver dados</button>
       <button class="btn-texto" type="button" data-lex-csv="dendrograma">Baixar CSV</button>
       <button class="btn-texto" type="button" data-lex-reset="canvasDendro">Resetar zoom</button>
     </div>`;
  lexical.desenharDendrograma($("canvasDendro"), dados, chdFiltrado);
}

function renderizarGrafo() {
  const conteudo = $("lexicalConteudo");
  const dados = lexico.filtrarGrafo(estado.lexical?.grafo);
  conteudo.innerHTML =
    lexico.controleHtml() +
    lexical.leituraLexical("grafo", dados) +
    `<div class="lex-grafo-box" id="canvasGrafo" role="img" aria-label="Rede de palavras"></div>` +
    `<div class="lex-controles">
       <span class="lex-dica-texto">Arraste os nós · roda para zoom · destaque de vizinhas</span>
       <button class="btn-texto" type="button" data-lex-dados="grafo">Ver dados</button>
       <button class="btn-texto" type="button" data-lex-csv="grafo">Baixar CSV</button>
       <button class="btn-texto" type="button" data-lex-reset="canvasGrafo">Resetar zoom</button>
     </div>`;
  limparGrafo = null;
  lexical.desenharGrafo($("canvasGrafo"), dados);
}

/* ---------- assinaturas em tempo real ---------- */

function desinscreverTudo() {
  estado.desinscrever.forEach((fn) => fn());
  estado.desinscrever = [];
}


function mostrarCarregando(ativo) {
  const barra = $("barraCarregando");
  if (barra) barra.hidden = !ativo;
  $("appShell")?.setAttribute("aria-busy", String(!!ativo));
}
async function aplicarFiltros() {
  mostrarCarregando(true);
  desinscreverTudo();
  // O parlamentar selecionado tem de ser do órgão ativo.
  if (
    estado.parlamentar &&
    !estado.agentes.some((a) => a.id === estado.parlamentar)
  ) {
    estado.parlamentar = "";
  }
  atualizarParlamentares();
  mostrarAviso("", "");
  await carregarLexical();

  const { doc, onSnapshot } = await import("firebase/firestore");
  await carregarCamadaDsm(estado.db, chaveEscopoDsm(estado), { doc, onSnapshot });

  let ref = null;
  if (estado.parlamentar) {
    ref = doc(estado.db, "metricas_por_agente", estado.parlamentar);
  } else if (estado.orgaoInfo) {
    // Sempre o agregado do órgão selecionado: nunca mistura frentes.
    ref = doc(estado.db, "metricas_por_cidade", estado.orgaoInfo.cidadeDoc);
  }

  governo.definirAtivo(estado.orgao === "governo-mt");

  if (!ref) {
    renderizarVazio();
    mostrarCarregando(false);
    return;
  }

  estado.desinscrever.push(
    onSnapshot(
      ref,
      (snap) => {
        if (snap.exists()) {
          renderizar(snap.data());
          // Telas novas (E2): leem os mesmos agregados.
          Promise.allSettled([
            telas.carregar(estado.db),
            governo.carregar(estado.db),
            simulacao.carregar(estado.db, estado.orgaoInfo),
            personas.carregar(estado.db, estado.orgaoInfo),
          ]).finally(() => mostrarCarregando(false));
        } else {
          renderizarVazio();
          mostrarCarregando(false);
        }
      },
      (erro) => {
        mostrarCarregando(false);
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
  const semRecorte = estado.periodo && Object.keys(view).length === 0;
  $("kpiVeiculos").textContent = semRecorte ? "—" : formatarNumero(view.total_veiculos);
  $("kpiAudiencia").textContent = semRecorte ? "—" : formatarNumero(view.audiencia_total);
  $("kpiValoracao").textContent = semRecorte ? "—" : formatarValor(view.valoracao_total);
  $("kpiClippings").textContent = semRecorte ? "—" : formatarNumero(view.total_clippings);

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
  renderizarRedes(view);
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
  if (!sub) return {};
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
  lexico.carregar().then(desenharNuvem);
}

function desenharNuvem() {
  const container = $("nuvemPalavras");
  const freq = lexico.filtrarFrequencias(
    estadoNuvem.mes ? estadoNuvem.porMes[estadoNuvem.mes] || {} : estadoNuvem.geral
  );
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
    span.style.color = i < 8
      ? corToken("--ambar")
      : t > 0.5
        ? corToken("--azul")
        : corToken("--texto-mutado");
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

/* ---------- redes sociais (agregado redes_sociais) ---------- */

let redesCache = {};

function renderizarRedes(view) {
  const rs =
    (view && view.redes_sociais) ||
    (estado.ultimosDados && estado.ultimosDados.redes_sociais) ||
    {};
  redesCache = rs;
  const porRede = rs.por_rede || {};
  const total = rs.total || Object.values(porRede).reduce((a, b) => a + (Number(b) || 0), 0);
  const comentarios = rs.comentarios_total || 0;
  const nRedes = Object.keys(porRede).length;

  const kpis = $("kpisRedes");
  if (kpis) {
    kpis.innerHTML = [
      ["Menções em redes", formatarNumero(total)],
      ["Comentários públicos", formatarNumero(comentarios)],
      ["Redes com atividade", formatarNumero(nRedes)],
    ]
      .map(
        ([rotulo, valor]) =>
          `<div class="rede-kpi"><span>${rotulo}</span><strong>${valor}</strong></div>`
      )
      .join("");
  }

  if ($("graficoRedes")) {
    charts.criarGraficoDonut("graficoRedes", porRede, undefined, true);
  }

  const sel = $("filtroRede");
  if (sel) {
    const atual = sel.value;
    const redes = Object.keys(porRede).sort();
    sel.innerHTML =
      '<option value="">Todas as redes</option>' +
      redes.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("");
    sel.value = redes.includes(atual) ? atual : "";
  }

  const alvo = $("redesSentimento");
  if (alvo) {
    const spr = rs.sentimento_por_rede || {};
    const linhas = Object.entries(spr).sort((a, b) => a[0].localeCompare(b[0]));
    alvo.innerHTML = linhas.length
      ? `<table class="tabela"><thead><tr><th>Rede</th>` +
        `<th class="num">Positivo</th><th class="num">Neutro</th><th class="num">Negativo</th></tr></thead><tbody>` +
        linhas
          .map(
            ([rede, d]) =>
              `<tr><td>${esc(rede)}</td>` +
              `<td class="num">${formatarNumero(d.positivo || 0)}</td>` +
              `<td class="num">${formatarNumero(d.neutro || 0)}</td>` +
              `<td class="num">${formatarNumero(d.negativo || 0)}</td></tr>`
          )
          .join("") +
        `</tbody></table>`
      : '<p class="lex-vazio">Sem dados de sentimento por rede no período.</p>';
  }

  renderizarRedesFeed();
}

function renderizarRedesFeed() {
  const feed = $("redesFeed");
  if (!feed) return;
  const rede = $("filtroRede")?.value || "";
  const tipo = $("filtroTipoRede")?.value || "";
  const itens = (redesCache.recentes || []).filter(
    (i) => (!rede || i.rede === rede) && (!tipo || i.tipo === tipo)
  );
  if (!itens.length) {
    feed.innerHTML = '<li class="redes-vazio">Sem itens de redes no período.</li>';
    return;
  }
  feed.innerHTML = itens
    .map((i) => {
      const d = i.data ? (i.data.toDate ? i.data.toDate() : new Date(i.data)) : null;
      const dataTxt = d && !isNaN(d)
        ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(d)
        : "";
      const tipoComentario = i.tipo === "Comentario";
      return (
        `<li class="rede-item">` +
        `<div class="rede-item-topo">` +
        `<span class="rede-badge">${esc(i.rede || "")}</span>` +
        `<span class="rede-tipo${tipoComentario ? " rede-tipo-comentario" : ""}">${esc(
          i.tipo || "Postagem"
        )}</span>` +
        `<span class="rede-agente">${esc(i.agente || "")}</span>` +
        `<span class="rede-data">${esc(dataTxt)}</span></div>` +
        `<p class="rede-snippet">${esc((i.snippet || i.titulo || "").slice(0, 320))}</p>` +
        `<div class="rede-item-rodape">` +
        (i.sentimento ? `<span class="sent-${esc(i.sentimento)}">${esc(i.sentimento)}</span>` : "") +
        (i.confianca ? `<span class="rede-conf">confiança ${esc(i.confianca)}</span>` : "") +
        (i.url
          ? `<a href="${esc(i.url)}" target="_blank" rel="noopener">abrir original</a>`
          : "") +
        `</div></li>`
      );
    })
    .join("");
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
  const mostrarValor = valorMidiaAtivo();

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

  const cardsSoma = [
    `<div class="soma-card">Menções<span class="valor">${formatarNumero(totalSoma)}</span></div>`,
  ];
  if (mostrarValor) {
    cardsSoma.push(
      `<div class="soma-card">Valor (R$)<span class="valor">${formatarValor(valorSoma)}</span></div>`
    );
  }
  cardsSoma.push(...cardsEspaco);
  $("relSoma").innerHTML = cardsSoma.join("");

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
    .map(([cat, n]) => {
      const valorCelula = mostrarValor
        ? `<td class="num">${formatarValor(valorSoma * (n / (base.total_clippings || 1)))}</td>`
        : "";
      return `<tr><td>${cat}</td><td class="num">${formatarNumero(n)}</td>${valorCelula}</tr>`;
    })
    .join("");
  const cabecalhoValor = mostrarValor
    ? '<th class="num">Valor est. (R$)</th>'
    : "";
  $("relLista").innerHTML =
    `<table class="tabela"><thead><tr><th>Categoria</th><th class="num">Menções</th>${cabecalhoValor}</tr></thead><tbody>${linhas}</tbody></table>`;
  lista = linhas;
}

/* ---------- utilitários de modal ---------- */

function abrirModal(id) {
  // Fecha qualquer outro modal antes de abrir um novo
  ["modalDetalhe", "modalRelatorio", "modalPost"].forEach((outroId) => {
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

/* ---------- escopo por orgao (separacao total de dados) ---------- */

function aplicarEscopoOrgao(slug) {
  const info = orgaoPorSlug(slug);
  estado.orgao = slug || "";
  estado.orgaoInfo = info || null;
  estado.parlamentar = "";
  estado.cidade = info ? info.cidade : "";
  document.body.dataset.orgao = info ? info.slug : "";
  telas.definirOrgao(info);
  governo.definirAtivo(info ? info.slug === "governo-mt" : false);
  renderMenu(info ? info.slug : "");
  aplicarSidebar();
  atualizarBotaoOrgao();
  atualizarRotulosOrgao(info);
  // Se estava numa tela do Executivo e trocou de frente, volta para a edição.
  const rotaAtual = (window.location.hash.replace(/^#\/?/, "").split("?")[0] || "");
  if (info && info.slug !== "governo-mt" && (rotaAtual === "governo" || rotaAtual === "governador")) {
    window.location.hash = "#/edicao";
  }
  // Ao entrar no Governo, a primeira tela é a Visão do Governo (não a edição genérica).
  if (info && info.slug === "governo-mt" && (!rotaAtual || rotaAtual === "edicao" || rotaAtual === "painel")) {
    window.location.hash = "#/governo";
  }
}

function atualizarRotulosOrgao(info) {
  const faixa = $("faixaOrgaos");
  if (faixa) faixa.textContent = info ? info.rotulo : "Selecione o órgão";
  const sub = $("parlamentaresSubtitulo");
  if (sub) {
    sub.textContent = info
      ? `Membros de ${info.rotulo} — cobertura individual com o mesmo tratamento`
      : "Membros da instituição selecionada";
  }
  const rodape = $("rodapeOrgao");
  if (rodape) rodape.textContent = info ? info.rotulo : "Selecione a instituição";
}

function atualizarBotaoOrgao() {
  const btn = $("btnOrgao");
  if (!btn) return;
  const info = estado.orgaoInfo;
  const perfil = estadoAuth.perfil || {};
  const disponiveis = orgaosDisponiveis(perfil);
  if (info) {
    btn.textContent = info.curto || info.rotulo;
    btn.title = "Trocar o órgão (" + info.rotulo + ")";
  } else {
    btn.textContent = "Órgão";
    btn.title = "Selecione o órgão a ser exibido";
  }
  // Quem pertence a um só órgão não troca de frente pelo cabeçalho.
  btn.style.display = disponiveis.length > 1 ? "" : "none";
}

/**
 * Abre o painel depois de garantir o escopo de dados.
 * Modo restrito: exige um órgão selecionado (abre o seletor e trava).
 * Modo público: órgão padrão, sem misturar órgãos.
 */
async function entrarApp() {
  if (modoPublico) {
    fecharLogin();
    aplicarEscopoOrgao("cuiaba");
    await iniciarApp();
    return;
  }
  const perfil = estadoAuth.perfil || {};
  const disponiveis = orgaosDisponiveis(perfil);
  if (!disponiveis.length) {
    abrirSeletorOrgao();
    return;
  }
  const uid = estadoAuth.usuario?.uid || "";
  // Usuário de um só órgão entra direto, sem a tela de escolha.
  if (disponiveis.length === 1) {
    const slug = disponiveis[0].slug;
    definirOrgao(uid, slug, false);
    fecharSeletorOrgao();
    aplicarEscopoOrgao(slug);
    await iniciarApp();
    return;
  }
  const salvo = orgaoSalvo(uid);
  const o = orgaoAtual(perfil, uid);
  if (salvo && salvo === o && disponiveis.some((x) => x.slug === o)) {
    fecharSeletorOrgao();
    aplicarEscopoOrgao(o);
    await iniciarApp();
    return;
  }
  // Primeiro acesso (ou depois de sair): escolhe a frente explicitamente.
  abrirSeletorOrgao();
}

/* ---------- seletor de orgao (UI) ---------- */

function renderOrgaoCards() {
  const grid = $("orgaoCards");
  if (!grid) return;
  const perfil = estadoAuth.perfil || {};
  const lista = orgaosDisponiveis(perfil);
  const erro = $("orgaoErro");
  if (!lista.length) {
    grid.innerHTML = "";
    if (erro) {
      if (estadoAuth.erroPerfil) {
        erro.innerHTML =
          "Não foi possível carregar seu perfil agora (rede/cota). " +
          '<button class="btn-texto" type="button" id="btnRecarregarPerfil">Tentar novamente</button>';
        document
          .getElementById("btnRecarregarPerfil")
          ?.addEventListener("click", () => location.reload());
      } else {
        erro.textContent =
          "Órgão não definido para seu usuário. Solicite ao administrador que libere o acesso.";
      }
      erro.classList.remove("oculto");
    }
    return;
  }
  if (erro) erro.classList.add("oculto");
  grid.innerHTML = lista
    .map(
      (o) =>
        `<a href="#" class="orgao-card" data-orgao="${o.slug}" role="button">` +
        `<span class="orgao-sigla">${esc(o.curto || o.slug)}</span>` +
        `<span class="orgao-rotulo">${esc(o.rotulo)}</span>` +
        `<span class="orgao-cidade">${esc(o.cidade)}</span>` +
        `</a>`
    )
    .join("");
  grid.querySelectorAll(".orgao-card").forEach((card) => {
    card.addEventListener("click", (ev) => {
      ev.preventDefault();
      card.classList.add("carregando");
      card.setAttribute("aria-busy", "true");
      definirOrgao(estadoAuth.usuario?.uid || "", card.dataset.orgao);
      fecharSeletorOrgao();
    });
  });
}

function abrirSeletorOrgao() {
  fecharLogin();
  const tela = $("telaOrgao");
  if (!tela) return;
  renderOrgaoCards();
  tela.classList.add("ativo");
  tela.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function fecharSeletorOrgao() {
  const tela = $("telaOrgao");
  if (!tela) return;
  tela.classList.remove("ativo");
  tela.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

/* ---------- eventos ---------- */

/* ---------- graficos lexicais: "ver dados" + resize ---------- */

document.addEventListener("click", (evento) => {
  const botaoDados = evento.target.closest("[data-lex-dados]");
  if (botaoDados) {
    evento.preventDefault();
    const tipo = botaoDados.dataset.lexDados;
    const dados = estado.lexical?.[tipo] || null;
    const anterior = document.getElementById("lexDadosTabela");
    if (anterior) anterior.remove();
    const caixa = document.createElement("div");
    caixa.id = "lexDadosTabela";
    caixa.className = "lex-dados";
    caixa.innerHTML = lexical.tabelaDadosLexicais(tipo, dados);
    const conteudo = document.getElementById("lexicalConteudo");
    if (conteudo) {
      conteudo.appendChild(caixa);
      caixa.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    return;
  }

  const botaoCsv = evento.target.closest("[data-lex-csv]");
  if (botaoCsv) {
    evento.preventDefault();
    const tipo = botaoCsv.dataset.lexCsv;
    const csv = lexical.csvLexical(tipo, estado.lexical?.[tipo] || null);
    if (!csv) return;
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `valorpublico-lexical-${tipo}-${(estado.orgao || "escopo")}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    return;
  }

  const botaoReset = evento.target.closest("[data-lex-reset]");
  if (botaoReset) {
    evento.preventDefault();
    lexical.resetarZoom(botaoReset.dataset.lexReset);
    return;
  }

  // o cartão já traz nome, explicação e exemplos; o clique só destaca o grupo
  const classe = evento.target.closest(".lex-classe[data-classe]");
  if (classe && !evento.target.closest("[data-lex-ocultar-palavra]")) {
    classe.parentElement
      ?.querySelectorAll(".lex-classe")
      .forEach((c) => c.classList.toggle("selecionado", c === classe));
  }
});

window.addEventListener("resize", () => {
  if (lexical && lexical.redimensionarLexicais) lexical.redimensionarLexicais();
});


$("filtroCidade").addEventListener("change", (e) => {
  estado.cidade = e.target.value;
  estado.parlamentar = "";
  aplicarFiltros();
});

$("filtroMes").addEventListener("change", (e) => {
  estadoNuvem.mes = e.target.value;
  desenharNuvem();
});

function alternarFiltrosLateral(forcar) {
  const aberto = typeof forcar === "boolean"
    ? forcar
    : !document.body.classList.contains("filtros-aberto");
  document.body.classList.toggle("filtros-aberto", aberto);
  const backdrop = $("filtrosBackdrop");
  if (backdrop) backdrop.hidden = !aberto;
  const shell = $("appShell");
  if (shell) shell.inert = aberto;
  if (aberto) {
    alternarMenuMobile(false);
    setTimeout(() => $("btnFecharFiltros")?.focus(), 40);
  } else if (document.activeElement?.closest?.("#filtrosLateral")) {
    $("btnFiltros")?.focus();
  }
  $("btnFiltros")?.setAttribute("aria-expanded", String(aberto));
}

function registrarFiltrosLateral() {
  $("btnFiltros")?.addEventListener("click", () => alternarFiltrosLateral());
  $("btnFecharFiltros")?.addEventListener("click", () => alternarFiltrosLateral(false));
  $("filtrosBackdrop")?.addEventListener("click", () => alternarFiltrosLateral(false));
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") alternarFiltrosLateral(false);
  });
}

function alternarMenuMobile(forcar) {
  const aberto =
    typeof forcar === "boolean"
      ? forcar
      : !document.body.classList.contains("menu-aberto");
  document.body.classList.toggle("menu-aberto", aberto);
  const backdrop = $("menuBackdrop");
  if (backdrop) backdrop.hidden = !aberto;
  const conteudo = $("conteudo");
  if (conteudo) conteudo.inert = aberto;
  $("btnMenu")?.setAttribute("aria-expanded", String(aberto));
  if (aberto) {
    alternarFiltrosLateral(false);
    setTimeout(() => $("navFecharMobile")?.focus(), 40);
  } else if (document.activeElement?.closest?.("#navPrincipal")) {
    $("btnMenu")?.focus();
  }
}


function atualizarAlturaHeader() {
  const header = document.querySelector(".masthead");
  const altura = header ? Math.round(header.getBoundingClientRect().height) : 72;
  document.documentElement.style.setProperty("--masthead-h", `${altura}px`);
}

function aplicarSidebar() {
  if (!UX_NAV2) return;
  let colapsada = false;
  try {
    colapsada = localStorage.getItem(CHAVE_SIDEBAR) === "1";
  } catch {
    colapsada = false;
  }
  document.body.classList.toggle("sidebar-colapsada", colapsada);
  $("btnSidebar")?.setAttribute("aria-expanded", String(!colapsada));
  $("btnSidebar")?.setAttribute("aria-label", colapsada ? "Expandir navegação" : "Recolher navegação");
  $("btnSidebarToggle")?.setAttribute("aria-expanded", String(!colapsada));
  $("btnSidebarToggle")?.setAttribute("aria-label", colapsada ? "Expandir navegação" : "Recolher navegação");
  atualizarAlturaHeader();
}

function alternarSidebar() {
  if (!UX_NAV2) return;
  const colapsada = !document.body.classList.contains("sidebar-colapsada");
  document.body.classList.toggle("sidebar-colapsada", colapsada);
  try {
    localStorage.setItem(CHAVE_SIDEBAR, colapsada ? "1" : "0");
  } catch {
    /* sem storage */
  }
  aplicarSidebar();
  redimensionarGraficos();
  telas.redimensionar();
  governo.redimensionar();
  simulacao.redimensionar();
}


function ativarAbaSemana(aba) {
  document.querySelectorAll("[data-semana-bloco]").forEach((bloco) => {
    bloco.hidden = bloco.dataset.semanaBloco !== aba;
  });
  document.querySelectorAll("[data-semana-aba]").forEach((botao) => {
    const ativo = botao.dataset.semanaAba === aba;
    botao.classList.toggle("ativo", ativo);
    botao.setAttribute("aria-selected", String(ativo));
  });
}

function registrarAbas() {
  document.addEventListener("click", (evento) => {
    const aba = evento.target.closest("[data-semana-aba]");
    if (aba) {
      evento.preventDefault();
      ativarAbaSemana(aba.dataset.semanaAba);
      return;
    }
    const secretarias = evento.target.closest("[data-gov-secretarias]");
    if (secretarias) {
      evento.preventDefault();
      if (window.location.hash !== "#/governo") window.location.hash = "#/governo";
      setTimeout(() => {
        document.getElementById("govSecretarias")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 120);
    }
  });
}
function registrarSidebar() {
  aplicarSidebar();
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("#btnSidebar") || evento.target.closest("#btnSidebarToggle")) {
      evento.preventDefault();
      alternarSidebar();
      return;
    }
    if (evento.target.closest("#sidebarFiltros")) {
      evento.preventDefault();
      alternarFiltrosLateral();
    }

  });
  window.addEventListener("resize", atualizarAlturaHeader);
  document.addEventListener("click", (evento) => {
    const link = evento.target.closest("[data-rota]");
    if (!link) return;
    window.dispatchEvent(
      new CustomEvent("nav:click", { detail: { rota: link.dataset.rota } })
    );
  });
}
function registrarMenuMobile() {
  $("btnMenu")?.addEventListener("click", (evento) => {
    evento.stopPropagation();
    alternarMenuMobile();
  });
  $("menuBackdrop")?.addEventListener("click", () => alternarMenuMobile(false));
  document.addEventListener("click", (evento) => {
    if (!document.body.classList.contains("menu-aberto")) return;
    if (evento.target.closest("#navFecharMobile")) {
      evento.preventDefault();
      alternarMenuMobile(false);
      return;
    }
    if (evento.target.closest("#navPrincipal") || evento.target.closest("#btnMenu")) return;
    alternarMenuMobile(false);
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") alternarMenuMobile(false);
  });
}

const ICONES_POR_ID = {
  btnTema: "i-tema",
  btnTemaConta: "i-tema",
  btnFiltros: "i-filtro",
  btnFecharFiltros: "i-fechar",
  btnRelatorio: "i-relatorios",
  btnAbrirRelatorio: "i-relatorios",
  btnGerarRelatorio: "i-relatorios",
  btnOrgao: "i-orgao",
  btnAtualizar: "i-atualizar",
  btnSairConta: "i-sair",
  btnAbrirNewsletter: "i-email",
  btnNewsletterDsm: "i-email",
  btnCopiarNewsletter: "i-copiar",
  btnCopiarDiscurso: "i-copiar",
  btnCopiarDiscursoGovernador: "i-copiar",
  btnCopiarDiscursoInterino: "i-copiar",
  btnBaixarPdfSemanal: "i-pdf",
  btnBaixarPdfGovernador: "i-pdf",
  btnExportarPdf: "i-pdf",
  btnBaixarPdfGoverno: "i-pdf",
  btnPerguntar: "i-perguntar",
  btnInvestigar: "i-investigar",
  btnEnviarBoletim: "i-enviar",
  btnEntrar: "i-entrar",
  btnEsqueci: "i-chave",
};

const ICONES_POR_TEXTO = [
  ["copiar", "i-copiar"],
  ["csv", "i-baixar"],
  ["pdf", "i-pdf"],
  ["baixar", "i-baixar"],
  ["ver dados", "i-tabela"],
  ["resetar", "i-zoom"],
  ["fechar", "i-fechar"],
  ["limpar", "i-fechar"],
  ["abrir", "i-relatorios"],
  ["enviar", "i-enviar"],
  ["investigar", "i-investigar"],
  ["perguntar", "i-perguntar"],
];

function svgIcone(id) {
  return `<svg class="icone-btn" aria-hidden="true" focusable="false"><use href="#${id}"></use></svg>`;
}

function decorarBotao(botao) {
  if (!botao || botao.dataset.icone === "1") return;
  const texto = (botao.textContent || "").trim().toLowerCase();
  let icone = ICONES_POR_ID[botao.id] || "";
  let somenteIcone = false;

  if (botao.classList.contains("btn-info")) {
    icone = "i-info";
    somenteIcone = true;
  } else if (botao.classList.contains("modal-fechar")) {
    icone = "i-fechar";
    somenteIcone = true;
  } else if (!icone && botao.id === "btnAuth") {
    icone = texto.includes("sair") ? "i-sair" : "i-entrar";
  } else if (!icone && botao.classList.contains("btn-texto")) {
    icone = ICONES_POR_TEXTO.find(([chave]) => texto.includes(chave))?.[1] || "";
  }

  if (!icone) return;
  botao.dataset.icone = "1";
  if (somenteIcone) {
    botao.innerHTML = svgIcone(icone);
  } else {
    botao.insertAdjacentHTML("afterbegin", svgIcone(icone));
  }
}

function decorarBotoes(raiz = document) {
  raiz.querySelectorAll("button").forEach(decorarBotao);
}

function iniciarIconesBotoes() {
  decorarBotoes();
  const observador = new MutationObserver((mutacoes) => {
    mutacoes.forEach((mutacao) => {
      mutacao.addedNodes.forEach((no) => {
        if (no.nodeType === 3 && no.parentElement?.matches?.("button")) {
          const botao = no.parentElement;
          if (!botao.querySelector(".icone-btn")) {
            botao.dataset.icone = "";
            decorarBotao(botao);
          }
          return;
        }
        if (no.nodeType !== 1) return;
        if (no.matches?.("button")) decorarBotao(no);
        no.querySelectorAll?.("button").forEach(decorarBotao);
      });
    });
  });
  observador.observe(document.body, { childList: true, subtree: true });
}
const ROTAS_SEM_FILTROS_GLOBAIS = new Set([
  "clipping",
  "semana",
  "simulacao",
  "personas",
  "relatorios",
  "sistema",
]);

function rotaAtualSimples() {
  return (window.location.hash.replace(/^#\/?/, "").split("?")[0] || "").toLowerCase();
}

function atualizarFiltrosContexto() {
  const rota = rotaAtualSimples();
  const temFiltros = !ROTAS_SEM_FILTROS_GLOBAIS.has(rota);
  const botao = $("btnFiltros");
  if (botao) botao.hidden = !temFiltros;
  if (!temFiltros) alternarFiltrosLateral(false);

  const governo = estado.orgao === "governo-mt";
  const campoParlamentar = $("filtroParlamentarCampo");
  if (campoParlamentar) {
    const usaAgente =
      !rota || rota === "edicao" || rota === "painel" || rota === "analise";
    campoParlamentar.hidden = !usaAgente;
  }
  const escopo = $("filtrosEscopo");
  if (escopo) escopo.textContent = estado.orgaoInfo?.curto || "Painel";
  const rotulo = $("rotuloFiltroAgente");
  if (rotulo) rotulo.textContent = governo ? "Agente/pasta" : "Parlamentar";
  const seletor = $("filtroParlamentar");
  if (seletor) {
    seletor.setAttribute(
      "aria-label",
      governo ? "Filtrar por agente ou pasta" : "Filtrar por parlamentar"
    );
  }
  const nota = $("filtrosNota");
  if (nota) {
    nota.textContent = governo
      ? "Período afeta o painel e os gráficos. Agente/pasta filtra a edição e a análise."
      : "Período afeta o painel e os gráficos. Parlamentar filtra a edição e a análise.";
  }
}
window.addEventListener("auth:changed", async () => {
  const uid = estadoAuth.usuario?.uid || "";
  if (uid) estado.uid = uid;
  atualizarConta();
  if (estadoAuth.autenticado && !appIniciado) {
    if (!loginExplicito) {
      abrirLogin();
      return;
    }
    fecharLogin();
    modoPublico = await lerModoAcesso();
    await entrarApp();
    return;
  }
  if (!estadoAuth.autenticado) {
    // Ao sair, a próxima entrada pede a frente de novo (e recarrega tudo).
    loginExplicito = false;
    desinscreverTudo();
    if (estado.uid) limparOrgao(estado.uid);
    estado.uid = "";
    estado.orgao = "";
    estado.orgaoInfo = null;
    estado.parlamentar = "";
    appIniciado = false;
    document.body.dataset.orgao = "";
    renderMenu("");
    if (!modoPublico) abrirLogin();
    return;
  }
  if (!estado.db) return;
  aplicarEscopoUsuario();
  aplicarFiltros();
});

window.addEventListener("orgao:changed", async () => {
  if (!estadoAuth.autenticado && !modoPublico) return;
  const perfil = estadoAuth.perfil || {};
  const uid = estadoAuth.usuario?.uid || estado.uid || "";
  const o = orgaoAtual(perfil, uid);
  if (!o) return;
  aplicarEscopoOrgao(o);
  if (appIniciado) {
    await carregarAgentes();
    aplicarEscopoUsuario();
    aplicarFiltros();
    atualizarConta();
  } else {
    await iniciarApp();
  }
});

$("filtroTipoTop").addEventListener("change", (e) => {
  estado.tipoTop = e.target.value;
  if (estado.ultimosDados) renderizar(estado.ultimosDados);
});

$("btnTema")?.addEventListener("click", alternarTema);
$("filtroRede")?.addEventListener("change", renderizarRedesFeed);
$("filtroTipoRede")?.addEventListener("change", renderizarRedesFeed);

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
  const resultado = abrirNewsletter();
  if (resultado === "bloqueado") {
    mostrarAviso("Permita pop-ups para abrir a newsletter em uma nova aba.", "");
  }
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
let loginExplicito = false;

window.addEventListener("login:submit", () => {
  loginExplicito = true;
});
let modoPublico = true;

function atualizarConta() {
  const perfil = estadoAuth.perfil;
  const email = $("contaEmail");
  if (email) email.textContent = perfil?.email || estadoAuth.usuario?.email || "—";
  const papel = $("contaPapel");
  if (papel) papel.textContent = perfil?.papel || (estadoAuth.autenticado ? "usuario" : "visitante");
  const escopo = $("contaEscopo");
  if (escopo) {
    const partes = [];
    if (estado.orgaoInfo) partes.push(estado.orgaoInfo.rotulo);
    const ids = perfil?.agente_ids || [];
    if (ids.length) partes.push("Agente: " + ids.join(", "));
    escopo.textContent = partes.length
      ? partes.join(" · ")
      : (estadoAuth.autenticado ? "—" : "—");
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
  aplicarPreferenciaValor();
  iniciarIconesBotoes();
  abrirLogin();
  renderMenu("");
  iniciarRouter();
  atualizarFiltrosContexto();
  registrarBotaoAuth();
  iniciarMotion();
  registrarExplicacoes();
  registrarFiltrosLateral();
  registrarMenuMobile();
  registrarSidebar();
  registrarAbas();
  ativarAbaSemana("relatorio");
  telas.iniciarSemanas();
  window.addEventListener("resize", () => {
    redimensionarGraficos();
    telas.redimensionar();
    governo.redimensionar();
    simulacao.redimensionar();
  });
  document.addEventListener("rota:changed", () => {
    registrarExplicacoes();
    marcarAtivo();
    atualizarFiltrosContexto();
    alternarMenuMobile(false);
    alternarFiltrosLateral(false);
    telas.redimensionar();
    governo.redimensionar();
    simulacao.redimensionar();
  });
  aoMudarFiltros(async (f) => {
    estado.periodo = f.periodo || "";
    if (f.parlamentar !== estado.parlamentar) {
      estado.parlamentar = f.parlamentar || "";
      if (estado.db) await aplicarFiltros();
    }
    if (estado.ultimosDados) renderizar(estado.ultimosDados);
    carregarLexical();
    definirJanelaDsm(estado.periodo || "todas");
    telas.definirPeriodo(estado.periodo);
    governo.definirPeriodo(estado.periodo);
  });
  ligarBarraGlobal();
  $("btnAbrirRelatorio")?.addEventListener("click", () => abrirModal("modalRelatorio"));
  $("btnAbrirNewsletter")?.addEventListener("click", () => {
    const resultado = abrirNewsletter();
    if (resultado === "bloqueado") {
      mostrarAviso(
        "Permita pop-ups para abrir a newsletter em uma nova aba.",
        ""
      );
    } else if (resultado !== "ok") {
      mostrarAviso(
        "A newsletter desta semana ainda não foi gerada. Ela entra após a coleta semanal.",
        ""
      );
    }
  });
  $("btnSairConta")?.addEventListener("click", alternarAuth);
  $("btnOrgao")?.addEventListener("click", abrirSeletorOrgao);
  $("btnTemaConta")?.addEventListener("click", alternarTema);
  $("toggleValorMidia")?.addEventListener("change", (evento) => {
    try {
      localStorage.setItem(
        CHAVE_VALOR_MIDIA,
        evento.target.checked ? "1" : "0"
      );
    } catch {
      /* sem storage: vale só na sessão */
    }
    aplicarPreferenciaValor();
  });
  await iniciarAuth();
  modoPublico = await lerModoAcesso();
  if (!modoPublico) {
    if (!loginExplicito) {
      if (estadoAuth.autenticado) await sair();
      abrirLogin();
      return;
    }
    await entrarApp();
    return;
  }
  fecharLogin();
  await entrarApp();
}

bootstrap();
const BOTOES_PDF = {
  btnBaixarPdfClipping: "print-clipping",
  btnBaixarPdfRedes: "print-redes",
  btnBaixarPdfTendencias: "print-tendencias",
  btnBaixarPdfPersonas: "print-personas",
};
Object.entries(BOTOES_PDF).forEach(([id, classe]) => {
  $("" + id)?.addEventListener("click", () => {
    document.body.classList.add(classe);
    window.print();
    setTimeout(() => document.body.classList.remove(classe), 500);
  });
});
let tituloAntesDaImpressao = "";
function prepararCabecalhoImpressao() {
  const titulo = document.getElementById("printTitulo");
  const meta = document.getElementById("printMeta");
  if (!titulo || !meta) return;
  const mapa = {
    "print-relatorio": "Relatório executivo",
    "print-semana": "Semana & Discurso",
    "print-governador": "Governador",
    "print-governo": "Governo de Mato Grosso",
    "print-redes": "Redes da Casa",
    "print-tendencias": "Tendências",
    "print-clipping": "Clipping",
    "print-personas": "Personas",
  };
  const classe = Object.keys(mapa).find((c) => document.body.classList.contains(c));
  const tituloTela = classe ? mapa[classe] : (document.querySelector(".tela.ativa h2")?.textContent || document.title);
  titulo.textContent = tituloTela.trim();
  tituloAntesDaImpressao = document.title;
  document.title = `${tituloTela.trim()} — ValorPúblico`;
  const partes = [
    estado.orgaoInfo?.rotulo || "ValorPúblico",
    estado.periodo ? `Período: ${estado.periodo}` : "Todo o período",
    new Date().toLocaleDateString("pt-BR"),
  ];
  meta.textContent = partes.join(" · ");
  document.querySelectorAll("details:not([open])").forEach((detalhe) => {
    detalhe.dataset.abertoAntesDaImpressao = "1";
    detalhe.open = true;
  });
}

window.addEventListener("beforeprint", prepararCabecalhoImpressao);
window.addEventListener("afterprint", () => {
  document.querySelectorAll("details[data-aberto-antes-da-impressao]").forEach((detalhe) => {
    detalhe.open = false;
    delete detalhe.dataset.abertoAntesDaImpressao;
  });
  if (tituloAntesDaImpressao) document.title = tituloAntesDaImpressao;
});


// Gancho de depuracao (usado pelo smoke test do painel e pelo console do browser)
window.__app_test = {
  estado,
  renderizar,
  renderizarKpisDsm,
  renderizarShareOfVoice,
  renderizarCamadaDsm,
  renderizarParlamentaresPorCasa,
  telas,
  governo,
  simulacao,
  personas,
  irPara: (rota) => window.__router?.irPara(rota),
};




/* ---------- Governo de MT: filtro por pasta ---------- */

document.addEventListener("click", (evento) => {
  const botao = evento.target.closest(".gov-pasta");
  if (!botao) return;
  const slug = botao.dataset.pasta || "";
  governo.filtrarPasta(slug === (window.__pastaSelecionada || "") ? "" : slug);
  window.__pastaSelecionada = slug === (window.__pastaSelecionada || "") ? "" : slug;
});































