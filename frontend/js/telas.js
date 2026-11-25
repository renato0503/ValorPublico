/**
 * Telas do ValorPúblico / "Newsroom" (plano 13 §4, plano 12 §4).
 *
 * Diferenças em relacao ao Assessor (plano 12 §2):
 *  - unidade de analise = **a Casa** (e nao o agente);
 *  - visao de visibilidade e **equidade** (K-43), sem ranking;
 *  - dados institucionais (K-42 imagem, K-44 encaminhadas, K-45 promocao pessoal);
 *  - **sem** discurso por membro e **sem** simulacao (D8: desligada).
 *
 * Todas as telas leem **agregados** e usam `explicacoes.js` (o texto muda
 * automaticamente para "a Casa" — ver a variante `valor` no registro).
 */

import { cartaoKpi, cartaoGrafico, escapar } from "./componentes.js";
import { explicacao, registrarExplicacoes } from "./explicacoes.js";
import {
  barrasDivergentes,
  barrasEmpilhadas,
  barrasHorizontais,
  linhaComPrevisao,
  linhasSentimento,
  quadrante,
  treemap,
} from "./graficos.js";

const estado = {
  db: null,
  dados: null,
  demandas: [],
  orgao: null,
  relatorio: null,
  discurso: null,
  simulacao: null,
  semana: "",
  semanaFixa: "",
  periodo: "",
  varianteAtiva: 0,
  discursoGovernador: null,
  semanaGovernador: "",
  simulacaoGovernador: null,
  discursoInterino: null,
  semanaInterino: "",
  varianteInterino: 0,
  varianteGovernador: 0,
};
const graficos = new Map();
let paginaClipping = 1;
const CLIPPING_POR_PAGINA = 25;

/** Define o órgão ativo (a Casa). Sem ele nenhuma tela lê dados. */
export function definirOrgao(info) {
  estado.orgao = info || null;
}

/** Aplica o recorte de período global às telas institucionais. */
export function definirPeriodo(periodo) {
  estado.periodo = periodo || "";
  if (estado.dados) renderizar();
}

function rotuloSemana(semana) {
  const m = /^(\d{4})-W(\d{2})$/.exec(semana || "");
  if (!m) return semana || "Semana";
  const ano = Number(m[1]);
  const numero = Number(m[2]);
  const jan4 = new Date(Date.UTC(ano, 0, 4));
  const dia = jan4.getUTCDay() || 7;
  const segunda = new Date(jan4);
  segunda.setUTCDate(jan4.getUTCDate() - dia + 1 + (numero - 1) * 7);
  const domingo = new Date(segunda);
  domingo.setUTCDate(segunda.getUTCDate() + 6);
  const fmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });
  return `Semana ${numero} · ${fmt.format(segunda)}–${fmt.format(domingo)}`;
}

function preencherSelectsSemana() {
  const semanas = semanasRecentes(12);
  const selecionada = estado.semanaFixa || estado.semana || semanas[0];
  document.querySelectorAll("select[data-semana]").forEach((select) => {
    select.innerHTML = semanas
      .map((s) => `<option value="${s}">${escapar(rotuloSemana(s))}</option>`)
      .join("");
    select.value = semanas.includes(selecionada) ? selecionada : semanas[0];
  });
}

/** Troca a semana exibida em Semana/Governador (relatório, discurso e simulação). */
export function iniciarSemanas() {
  preencherSelectsSemana();
}

export function definirSemana(semana) {
  estado.semanaFixa = semana || "";
  if (estado.db) carregar(estado.db);
}

/** Injeção para testes de UI (sem Firestore). */
export function definirDados(dados) {
  estado.dados = dados || null;
  renderizar();
}

function dadosDaJanela(dados) {
  if (!estado.periodo) return dados;
  const recorte = dados?.por_periodo?.[estado.periodo];
  if (!recorte) return {};
  // As notícias ficam fora do recorte para caber no limite de 1 MiB do doc.
  return {
    ...dados,
    ...recorte,
    noticias_recentes: recorte.noticias_recentes || dados?.noticias_recentes || [],
  };
}

function guardar(id, instancia) {
  if (instancia) graficos.set(id, instancia);
}

export function redimensionar() {
  graficos.forEach((instancia) => {
    try {
      instancia.resize();
    } catch {
      /* descartado */
    }
  });
}

async function sdkFirestore() {
  try {
    return await import("firebase/firestore");
  } catch {
    return await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
  }
}

async function lerDoc(db, caminho, id) {
  const { doc, getDoc } = await sdkFirestore();
  const snap = await getDoc(doc(db, caminho, id));
  return snap.exists() ? snap.data() : null;
}

async function lerDocSeguro(db, caminho, id) {
  try {
    return await lerDoc(db, caminho, id);
  } catch {
    return null;
  }
}

/** Semana ISO (YYYY-Www), igual ao `%G-W%V` usado no backend. */
function semanaISO(data = new Date()) {
  const d = new Date(Date.UTC(data.getFullYear(), data.getMonth(), data.getDate()));
  const dia = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dia);
  const inicioAno = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const semana = Math.ceil(((d - inicioAno) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(semana).padStart(2, "0")}`;
}

function semanasRecentes(quantidade = 4) {
  const saida = [];
  const base = new Date();
  for (let i = 0; i < quantidade; i++) {
    const d = new Date(base);
    d.setDate(d.getDate() - i * 7);
    saida.push(semanaISO(d));
  }
  return saida;
}

/**
 * Carrega relatório, discurso e simulação da semana para a Casa atual.
 * Procura nas últimas 4 semanas (a geração pode ter falhado em uma delas).
 */
async function lerSemana(db, orgao, semanaFixa = "") {
  if (!orgao) return { relatorio: null, discurso: null, simulacao: null, semana: "" };
  const escopo = `casa-${orgao.slug}`;
  for (const semana of (semanaFixa ? [semanaFixa] : semanasRecentes(4))) {
    const [relatorio, discurso, simulacao] = await Promise.all([
      lerDocSeguro(db, "relatorio_semanal", `${escopo}__${semana}`),
      lerDocSeguro(db, "discurso_semanal", `${escopo}__${semana}`),
      lerDocSeguro(db, "simulacao_semanal", `${escopo}__${semana}`),
    ]);
    if (relatorio || discurso || simulacao) {
      return { relatorio, discurso, simulacao, semana };
    }
  }
  return {
    relatorio: null,
    discurso: null,
    simulacao: null,
    semana: semanaFixa || semanasRecentes(1)[0],
  };
}

async function lerDemandas(db, orgao) {
  if (!orgao) return [];
  try {
    const { collection, getDocs, query, where } = await sdkFirestore();
    const snap = await getDocs(
      query(collection(db, "demandas"), where("orgao", "==", orgao))
    );
    return snap.docs.slice(0, 80).map((d) => ({ id: d.id, ...d.data() }));
  } catch {
    return [];
  }
}

/** Escopo: sempre a Casa do órgão selecionado (nunca a URL nem o "geral"). */
export function escopoAtual() {
  if (estado.orgao) return { tipo: "casa", id: estado.orgao.casaDoc };
  return { tipo: "nenhum", id: "" };
}

async function lerDiscursoAgente(db, escopoBase, semanaFixa = "") {
  for (const semana of (semanaFixa ? [semanaFixa] : semanasRecentes(4))) {
    const doc = await lerDocSeguro(
      db,
      "discurso_semanal",
      `${escopoBase}__${semana}`
    );
    if (doc) return { doc, semana };
  }
  return { doc: null, semana: semanaFixa || semanasRecentes(1)[0] };
}

async function lerSimulacaoAgente(db, escopoBase, semanaFixa = "") {
  for (const semana of (semanaFixa ? [semanaFixa] : semanasRecentes(4))) {
    const doc = await lerDocSeguro(
      db,
      "simulacao_semanal",
      `${escopoBase}__${semana}`
    );
    if (doc) return { doc, semana };
  }
  return { doc: null, semana: semanaFixa || semanasRecentes(1)[0] };
}

export async function carregar(db) {
  estado.db = db;
  const escopo = escopoAtual();
  if (escopo.tipo === "nenhum") {
    estado.dados = null;
    estado.demandas = [];
    estado.relatorio = null;
    estado.discurso = null;
    estado.simulacao = null;
    renderizar();
    return;
  }
  try {
    estado.dados = await lerDoc(db, "metricas_por_casa", escopo.id);
  } catch (erro) {
    console.warn("[Telas Valor] falha ao carregar metricas:", erro?.code || erro?.message || erro);
    estado.dados = null;
  }
  estado.demandas = await lerDemandas(db, estado.orgao?.slug);
  const semana = await lerSemana(db, estado.orgao, estado.semanaFixa);
  estado.relatorio = semana.relatorio;
  estado.discurso = semana.discurso;
  estado.simulacao = semana.simulacao;
  estado.semana = semana.semana;
  if (estado.orgao?.slug === "governo-mt") {
    const gov = await lerDiscursoAgente(
      db,
      "agente-governador-otaviano-pivetta",
      estado.semanaFixa
    );
    estado.discursoGovernador = gov.doc;
    estado.semanaGovernador = gov.semana;
    const simGov = await lerSimulacaoAgente(
      db,
      "agente-governador-otaviano-pivetta",
      estado.semanaFixa
    );
    estado.simulacaoGovernador = simGov.doc;
    const interino = await lerDiscursoAgente(
      db,
      "agente-interino-max-russi",
      estado.semanaFixa
    );
    estado.discursoInterino = interino.doc;
    estado.semanaInterino = interino.semana;
  } else {
    estado.discursoGovernador = null;
    estado.semanaGovernador = "";
    estado.simulacaoGovernador = null;
    estado.discursoInterino = null;
    estado.semanaInterino = "";
  }
  renderizar();
}

export function renderizar() {
  const dados = dadosDaJanela(estado.dados || {});
  renderizarEdicao(dados);
  renderizarClipping(dados);
  renderizarImagem(dados);
  renderizarOuvidoria(dados);
  renderizarSemana(dados);
  renderizarGovernadorDiscurso();
  renderizarRecepcaoGovernador();
  renderizarInterinoDiscurso();
  renderizarRedes(dados);
  renderizarConformidade(dados);
  renderizarTendencias(dados);
  preencherSelectsSemana();
  registrarExplicacoes();
}

function saldoDeOpiniao(dados) {
  if (dados?.saldo_opiniao !== undefined && dados?.saldo_opiniao !== null) {
    return Number(dados.saldo_opiniao);
  }
  const d = dados?.distribuicao_sentimento || {};
  const positivo = Number(d.positivo || 0);
  const negativo = Number(d.negativo || 0);
  const total = positivo + negativo + Number(d.neutro || 0);
  return total ? Math.round(((positivo - negativo) / total) * 100) : 0;
}

/* ---- V1 / Edição do dia ---- */
function renderizarEdicao(dados) {
  const tem = (v) => v !== undefined && v !== null;
  cartaoKpi("kpiEdicaoMatarias", {
    codigo: "K-01",
    valor: tem(dados.total_clippings)
      ? new Intl.NumberFormat("pt-BR").format(Number(dados.total_clippings))
      : "—",
    ...(tem(dados.total_clippings) ? {} : { semBase: true, motivo: "sem clippings no período" }),
  });
  cartaoKpi("kpiEdicaoSentimento", {
    codigo: "K-03",
    valor: tem(dados.distribuicao_sentimento) ? Number(saldoDeOpiniao(dados)).toFixed(0) : "—",
    ...(tem(dados.distribuicao_sentimento) ? {} : { semBase: true, motivo: "sem sentimento classificado" }),
  });
  cartaoKpi("kpiEdicaoAlcance", {
    codigo: "K-05",
    valor: tem(dados.audiencia_total)
      ? new Intl.NumberFormat("pt-BR").format(Number(dados.audiencia_total))
      : "—",
    ...(tem(dados.audiencia_total) ? {} : { semBase: true, motivo: "sem audiência calculada" }),
  });
  cartaoKpi("kpiEdicaoValor", {
    codigo: "K-08",
    valor: tem(dados.valor_avpe_total) || tem(dados.valoracao_total)
      ? new Intl.NumberFormat("pt-BR", {
          style: "currency",
          currency: "BRL",
          maximumFractionDigits: 0,
        }).format(Number(dados.valor_avpe_total ?? dados.valoracao_total))
      : "—",
    valorMidia: true,
    ...(tem(dados.valor_avpe_total) || tem(dados.valoracao_total)
      ? {}
      : { semBase: true, motivo: "valor de mídia não calculado" }),
  });
  cartaoKpi("kpiEdicaoAlertas", {
    codigo: "K-20",
    valor: tem(dados.alertas?.total) ? String(Number(dados.alertas.total)) : "—",
    ...(tem(dados.alertas?.total) ? {} : { semBase: true, motivo: "sem alertas calculados" }),
  });
  cartaoKpi("kpiEdicaoSla", {
    codigo: "K-60",
    valor: tem(dados.cobertura?.sla_min_medio)
      ? `${Math.round(Number(dados.cobertura.sla_min_medio))} min`
      : "—",
    ...(tem(dados.cobertura?.sla_min_medio) ? {} : { semBase: true, motivo: "sem SLA calculado" }),
  });

  const canvas = document.getElementById("graficoEdicaoSentimento");
  if (canvas) {
    guardar("graficoEdicaoSentimento", linhasSentimento(canvas, serieSentimento(dados), {}));
  }
}

/* ---- V2 / Clipping (últimas notícias do agregado) ---- */
function _dataCurta(valor) {
  if (!valor) return "—";
  if (valor.toDate) return valor.toDate().toLocaleDateString("pt-BR");
  const d = new Date(valor);
  if (!isNaN(d)) return d.toLocaleDateString("pt-BR");
  return String(valor).slice(0, 10);
}

function renderizarClipping(dados) {
  const corpo = document.getElementById("corpoClipping");
  if (!corpo) return;
  const itens = Array.isArray(dados?.noticias_recentes) ? dados.noticias_recentes : [];
  const selVeiculo = document.getElementById("filtroClipVeiculo");
  const selTier = document.getElementById("filtroClipTier");
  const selTipo = document.getElementById("filtroClipTipo");
  const busca = document.getElementById("filtroClipBusca");

  if (selVeiculo) {
    const atual = selVeiculo.value;
    const veiculos = [...new Set(itens.map((n) => n.veiculo).filter(Boolean))].sort();
    selVeiculo.innerHTML =
      '<option value="">Todos os veículos</option>' +
      veiculos.map((v) => `<option value="${escapar(v)}">${escapar(v)}</option>`).join("");
    selVeiculo.value = veiculos.includes(atual) ? atual : "";
  }
  if (selTier) {
    const temTier = itens.some((n) => n.tier);
    selTier.disabled = !temTier;
    selTier.title = temTier ? "" : "O tier não está disponível neste agregado.";
    if (!temTier) selTier.value = "";
  }
  if (selTipo) {
    const temTipo = itens.some((n) => n.tipo_mencao || n.tipo);
    selTipo.disabled = !temTipo;
    selTipo.title = temTipo ? "" : "O tipo de menção não está disponível neste agregado.";
    if (!temTipo) selTipo.value = "";
  }

  const veiculo = selVeiculo?.value || "";
  const tier = selTier?.value || "";
  const tipo = selTipo?.value || "";
  const termo = (busca?.value || "").trim().toLowerCase();
  const filtrados = itens.filter((n) => {
    if (veiculo && n.veiculo !== veiculo) return false;
    if (tier && n.tier !== tier) return false;
    const tipoItem = n.tipo_mencao || n.tipo || "";
    if (tipo && tipoItem !== tipo) return false;
    if (termo) {
      const alvo = `${n.titulo || ""} ${n.texto_limpo || ""} ${n.veiculo || ""}`.toLowerCase();
      if (!alvo.includes(termo)) return false;
    }
    return true;
  });

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / CLIPPING_POR_PAGINA));
  paginaClipping = Math.min(Math.max(1, paginaClipping), totalPaginas);
  const inicio = (paginaClipping - 1) * CLIPPING_POR_PAGINA;
  const visiveis = filtrados.slice(inicio, inicio + CLIPPING_POR_PAGINA);

  corpo.innerHTML = visiveis.length
    ? visiveis
        .map(
          (n) => `<tr>
            <td data-label="Matéria">${n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">${escapar(n.titulo || n.texto_limpo || "notícia")}</a>` : escapar(n.titulo || n.texto_limpo || "notícia")}</td>
            <td data-label="Veículo">${escapar(n.veiculo || n.autor || "—")}</td>
            <td data-label="Data">${escapar(_dataCurta(n.data_publicacao || n.data))}</td>
            <td data-label="Tipo">${escapar(n.tipo_mencao || n.tipo || "—")}</td>
            <td data-label="Tom">${escapar(n.sentimento || "—")}</td>
          </tr>`
        )
        .join("")
    : `<tr><td colspan="5">Nenhuma notícia atende aos filtros selecionados.</td></tr>`;

  renderizarPaginacaoClipping(filtrados.length, totalPaginas);

  const nota = document.getElementById("clippingNota");
  if (nota) {
    if (!itens.length) {
      nota.textContent = "Ainda não há notícias neste agregado. A coleta diária preenche esta lista.";
    } else if (!filtrados.length) {
      nota.textContent = `Nenhuma das ${itens.length} notícias do agregado atende aos filtros.`;
    } else {
      nota.textContent = `Mostrando ${inicio + 1}–${inicio + visiveis.length} de ${filtrados.length} notícias filtradas (${itens.length} no agregado).`;
    }
  }
}

function renderizarPaginacaoClipping(total, totalPaginas) {
  const alvo = document.getElementById("paginacaoClipping");
  if (!alvo) return;
  if (!total || totalPaginas <= 1) {
    alvo.innerHTML = "";
    return;
  }
  const paginas = [];
  const inicial = Math.max(1, paginaClipping - 2);
  const final = Math.min(totalPaginas, inicial + 4);
  for (let p = inicial; p <= final; p++) paginas.push(p);

  alvo.innerHTML = `
    <span class="pagina-info">página ${paginaClipping} de ${totalPaginas}</span>
    <button type="button" data-pagina="${paginaClipping - 1}" ${paginaClipping === 1 ? "disabled" : ""} aria-label="Página anterior">‹</button>
    ${paginas
      .map(
        (p) =>
          `<button type="button" data-pagina="${p}" ${p === paginaClipping ? 'aria-current="page"' : ""}>${p}</button>`
      )
      .join("")}
    <button type="button" data-pagina="${paginaClipping + 1}" ${paginaClipping === totalPaginas ? "disabled" : ""} aria-label="Próxima página">›</button>`;
  alvo.querySelectorAll("[data-pagina]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const destino = Number(botao.dataset.pagina);
      if (!Number.isFinite(destino) || destino < 1 || destino > totalPaginas) return;
      paginaClipping = destino;
      renderizarClipping(dadosDaJanela(estado.dados || {}));
    });
  });
}
/* ---- V3 / Imagem da Casa ---- */
function renderizarImagem(dados) {
  cartaoKpi("kpiImagemSaldo", {
    codigo: "K-03",
    valor: Number(saldoDeOpiniao(dados)).toFixed(0),
  });
  cartaoKpi("kpiImagemInstitucional", {
    codigo: "K-42",
    valor:
      dados.imagem_institucional !== undefined && dados.imagem_institucional !== null
        ? Number(dados.imagem_institucional).toFixed(0)
        : "—",
    sufixo:
      dados.imagem_institucional === undefined
        ? "não calculada nesta base"
        : "",
  });
  cartaoKpi("kpiImagemTier1", {
    codigo: "K-06",
    valor:
      dados.pct_tier1 !== undefined && dados.pct_tier1 !== null
        ? `${Number(dados.pct_tier1).toFixed(0)}%`
        : "—",
    sufixo: dados.pct_tier1 === undefined ? "sem tier na base" : "",
  });
  cartaoKpi("kpiImagemProjecao", {
    codigo: "K-33",
    valor: dados.previsao?.mencoes?.previsao?.length
      ? String(dados.previsao.mencoes.previsao.length)
      : "—",
    sufixo: dados.previsao?.mencoes?.previsao?.length
      ? "dias projetados (com margem)"
      : "sem projeção nesta semana",
  });

  const previsao = dados.previsao?.mencoes || {};
  const canvas = document.getElementById("graficoImagemPrevisao");
  const temPrevisao = (previsao.historico || []).length > 0 || (previsao.previsao || []).length > 0;
  const cardPrevisao = canvas?.closest(".card");
  if (cardPrevisao) cardPrevisao.classList.toggle("oculto", !temPrevisao);
  if (canvas && temPrevisao) {
    guardar(
      "graficoImagemPrevisao",
      linhaComPrevisao(
        canvas,
        {
          datas: (previsao.historico || []).map((h) => h.data),
          valores: (previsao.historico || []).map((h) => h.valor),
        },
        {
          datas: (previsao.previsao || []).map((p) => p.data),
          valores: (previsao.previsao || []).map((p) => p.valor),
          superiores: (previsao.previsao || []).map((p) => p.superior),
        }
      )
    );
  }

  const canvas2 = document.getElementById("graficoImagemCanais");
  if (canvas2) {
    guardar("graficoImagemCanais", barrasEmpilhadas(canvas2, seriePorCanal(dados)));
  }

  const canvas3 = document.getElementById("graficoImagemMudou");
  if (canvas3) {
    const mais = dados.especificidades?.semana_vs_base?.mais || [];
    const menos = dados.especificidades?.semana_vs_base?.menos || [];
    guardar("graficoImagemMudou", barrasDivergentes(canvas3, mais, menos));
  }

  const canvas4 = document.getElementById("graficoImagemCrise");
  if (canvas4) {
    guardar(
      "graficoImagemCrise",
      linhasSentimento(canvas4, serieSentimento(dados), {})
    );
  }
}

/* ---- V5 / Ouvidoria ---- */
function renderizarOuvidoria(dados) {
  const demandas = estado.demandas || [];
  const total = demandas.length;
  const abertas = demandas.filter((d) => String(d.status || "nova") !== "respondida").length;
  const encaminhadas = demandas.filter((d) => String(d.status) === "encaminhada").length;

  cartaoKpi("kpiOuvNovas", { codigo: "K-24", valor: String(total) });
  cartaoKpi("kpiOuvAbertas", { codigo: "K-25", valor: String(abertas) });
  cartaoKpi("kpiOuvTempo", {
    codigo: "K-26",
    valor: "–",
    sufixo: "preenchido quando houver respostas com data",
  });
  cartaoKpi("kpiOuvEncaminhadas", {
    codigo: "K-44",
    valor: `${total ? Math.round((encaminhadas / total) * 100) : 0}%`,
  });

  const corpo = document.getElementById("corpoOuvidoria");
  if (corpo) {
    const item = explicacao("T-05");
    corpo.innerHTML = demandas.length
      ? demandas
          .slice(0, 40)
          .map(
            (d) => `<tr>
              <td>${escapar((d.resumo || d.texto || "").slice(0, 120))}</td>
              <td>${escapar(d.tema || "outros")}</td>
              <td>${escapar(d.bairro || "—")}</td>
              <td>${escapar(d.urgencia || "baixa")}</td>
              <td>${escapar(d.origem || "comentário")}</td>
              <td>${escapar(d.status || "nova")}</td>
            </tr>`
          )
          .join("")
      : `<tr><td colspan="6">${item ? escapar(item.oQueE) : ""}</td></tr>`;
  }

  const canvas = document.getElementById("graficoOuvTemas");
  if (canvas) {
    guardar("graficoOuvTemas", treemap(canvas, contagemPor(demandas, "tema")));
  }
  const canvas2 = document.getElementById("graficoOuvBairros");
  if (canvas2) {
    guardar("graficoOuvBairros", treemap(canvas2, contagemPor(demandas, "bairro")));
  }
}

/* ---- V6 / Semana da Casa ---- */
function _rotuloClasse(classe) {
  const genericas = new Set([
    "de", "da", "do", "das", "dos", "e", "em", "a", "o", "as", "os", "para",
    "por", "com", "nbsp", "mt", "mato", "grosso", "no", "na", "nos", "nas",
  ]);
  const formas = (classe?.formas || [])
    .map((f) => String(f.f || "").trim().toLowerCase())
    .filter((f) => f && !genericas.has(f))
    .slice(0, 2);
  if (formas.length) return formas.join(" · ");
  return `Classe ${classe?.id ?? "?"}`;
}

function renderizarSemana(dados) {
  const rel = estado.relatorio || dados.relatorio_semanal || {};
  const disc = estado.discurso || {};
  const sim = estado.simulacao || {};

  const classes = rel.chd?.classes || [];
  const variedade = classes.length
    ? 1 -
      classes.reduce(
        (acc, c) => acc + Math.pow(Number(c.pct || 0) / 100, 2),
        0
      )
    : null;
  cartaoKpi("kpiSemanaVariedade", {
    codigo: "K-40",
    valor: variedade !== null ? variedade.toFixed(2) : "—",
    sufixo: variedade !== null
      ? `diversidade dos assuntos (0 a 1) · ${variedade < 0.35 ? "baixa" : variedade < 0.6 ? "média" : "alta"}`
      : "não calculada nesta semana",
  });
  const temSintonia = rel.alinhamento !== undefined && rel.alinhamento !== null;
  document.getElementById("kpiSemanaSintonia")?.classList.toggle("oculto", !temSintonia);
  if (temSintonia) {
    cartaoKpi("kpiSemanaSintonia", {
      codigo: "K-41",
      valor: Number(rel.alinhamento).toFixed(2),
    });
  }
  const imagens = dados.imagens?.kpis;
  const temImagens = imagens && imagens.k70_postos_com_imagem !== undefined;
  document.getElementById("kpiSemanaImagens")?.classList.toggle("oculto", !temImagens);
  if (temImagens) {
    cartaoKpi("kpiSemanaImagens", {
      codigo: "K-70",
      valor: String(Number(imagens.k70_postos_com_imagem)),
    });
  }
  const temEquidade =
    dados.equidade_visibilidade !== undefined &&
    dados.equidade_visibilidade !== null;
  document.getElementById("kpiSemanaEquidade")?.classList.toggle("oculto", !temEquidade);
  if (temEquidade) {
    cartaoKpi("kpiSemanaEquidade", {
      codigo: "K-43",
      valor: Number(dados.equidade_visibilidade).toFixed(2),
    });
  }

  const canvas = document.getElementById("graficoSemanaClasses");
  if (canvas) {
    const classesChd = rel.chd?.classes || [];
    if (classesChd.length) {
      const itens = classesChd.slice(0, 8).map((c) => ({
        rotulo: _rotuloClasse(c),
        valor: Math.round(Number(c.pct ?? 0) * (Number(c.pct ?? 0) <= 1 ? 100 : 1)),
      }));
      guardar("graficoSemanaClasses", barrasHorizontais(canvas, itens));
    } else {
      const mais = rel.especificidades?.semana_vs_base?.mais || [];
      const menos = rel.especificidades?.semana_vs_base?.menos || [];
      guardar("graficoSemanaClasses", barrasDivergentes(canvas, mais, menos));
    }
  }

  const leitura = document.getElementById("semanaLeitura");
  if (leitura) {
    const maior = [...classes].sort(
      (a, b) => Number(b.pct || 0) - Number(a.pct || 0)
    )[0];
    const nItens =
      rel.estatisticas?.textos ??
      rel.estatisticas?.n_textos ??
      rel.estatisticas?.n_itens ??
      rel.estatisticas?.n ??
      0;
    const texto = rel.semana
      ? `Semana ${rel.semana}: ${nItens} textos analisados, ${classes.length} classes temáticas` +
        (maior ? `. O maior grupo reúne ${maior.pct}% dos segmentos.` : ".") +
        " Veja o PDF e a aba Análise para a leitura completa."
      : "O relatório da semana é gerado aos domingos, na máquina da Secom.";
    leitura.innerHTML =
      `<span class="grafico-leitura-rotulo">Leitura do momento</span>${escapar(texto)}`;
  }

  renderizarDiscurso(disc, sim);
}

let textoDiscursoAtual = "";

function renderizarDiscurso(disc, sim) {
  const alvo = document.getElementById("discursoTexto");
  const btnCopiar = document.getElementById("btnCopiarDiscurso");
  if (!alvo) return;
  const variantes = Array.isArray(disc?.variantes) ? disc.variantes : [];
  if (!variantes.length) {
    textoDiscursoAtual = "";
    alvo.innerHTML =
      '<p class="grafico-leitura">O discurso desta semana ainda não foi gerado. ' +
      "Ele aparece aqui no domingo, depois da análise lexical e do relatório semanal.</p>";
    if (btnCopiar) btnCopiar.disabled = true;
    return;
  }
  const idx = Math.min(estado.varianteAtiva, variantes.length - 1);
  estado.varianteAtiva = idx;
  const abas = variantes
    .map(
      (v, i) =>
        `<button class="disc-aba${i === idx ? " ativo" : ""}" type="button" ` +
        `data-disc-variante="${i}">${escapar(
          v.angulo || v.id || `Variante ${i + 1}`
        )}</button>`
    )
    .join("");
  const atual = variantes[idx] || {};
  const texto = atual.tribuna || atual.texto || atual.institucional || "";
  textoDiscursoAtual = texto;
  const fontes = (atual.fontes || [])
    .slice(0, 8)
    .map(
      (f) =>
        `<li>${escapar(f.veiculo || f.fonte || "Fonte")}${
          f.data ? " · " + escapar(String(f.data).slice(0, 10)) : ""
        }${f.url ? ` · <a href="${escapar(f.url)}" target="_blank" rel="noopener">abrir</a>` : ""}</li>`
    )
    .join("");
  const video = atual.video
    ? `<details class="disc-extra"><summary>Versão para vídeo (60s)</summary><p>${escapar(atual.video)}</p></details>`
    : "";
  const post = atual.post
    ? `<details class="disc-extra"><summary>Versão para post</summary><p>${escapar(atual.post)}</p></details>`
    : "";
  const vencedora = disc.vencedora && disc.vencedora === atual.id
    ? '<span class="disc-selo">variante vencedora na simulação</span>'
    : "";
  const simResumo = sim?.personas?.length
    ? `<p class="disc-sim-resumo">Recepção simulada: ${sim.personas.length} personas · ` +
      `adesão média ${Number(sim.personas.reduce((a, p) => a + Number(p.adesao || 0), 0) / sim.personas.length).toFixed(1)} · ` +
      `<a href="#/simulacao">ver relatório completo</a></p>`
    : "";
  alvo.innerHTML =
    `<div class="disc-tabs" role="tablist">${abas}</div>` +
    `<article class="disc-texto-ativo">` +
    `<div class="disc-meta"><span>${escapar(disc.semana || estado.semana || "")}</span>${vencedora}</div>` +
    `<p>${escapar(texto).replace(/\n/g, "</p><p>")}</p>` +
    video +
    post +
    (fontes ? `<div class="disc-fontes"><strong>Fontes</strong><ul>${fontes}</ul></div>` : "") +
    simResumo +
    `<p class="disc-aviso">Rascunho gerado por IA — confira as fontes antes de usar.</p>` +
    `</article>`;
  if (btnCopiar) btnCopiar.disabled = false;

  alvo.querySelectorAll("[data-disc-variante]").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.varianteAtiva = Number(botao.dataset.discVariante);
      renderizarDiscurso(disc, sim);
    });
  });
}

function renderizarRecepcaoGovernador() {
  const alvo = document.getElementById("recepcaoGovernador");
  if (!alvo) return;
  const sim = estado.simulacaoGovernador;
  const personas = Array.isArray(sim?.personas) ? sim.personas : [];
  if (!sim || !personas.length) {
    alvo.innerHTML =
      '<p class="grafico-leitura">A recepção do discurso do governador ainda não foi simulada nesta semana.</p>';
    return;
  }
  const media = (campo) =>
    personas.reduce((acc, p) => acc + Number(p[campo] || 0), 0) / personas.length;
  const variantes = (sim.variantes || [])
    .map(
      (v) =>
        `Variante ${escapar(v.id)}: ${Number(v.adesao || 0).toFixed(1)}` +
        ` (rejeição ${Math.round(Number(v.rejeicao || 0) * 100)}%)`
    )
    .join(" · ");
  const cards = personas
    .map(
      (p) => `<article class="persona-card">
        <span class="persona-status">${escapar(p.id)}</span>
        <h3>${escapar(p.rotulo || p.id)}</h3>
        <span class="persona-tom">${escapar(p.emocao || "reação")}</span>
        <span class="persona-adesao">${Number(p.adesao || 0).toFixed(1)}</span>
        <span class="persona-num">IC 90% ${(p.adesao_ic90 || []).map((n) => Number(n).toFixed(1)).join("–")}</span>
        <span class="persona-rejeicao">rejeição ${Math.round(Number(p.rejeicao || 0) * 100)}%</span>
        ${p.comentario ? `<span class="persona-comentario">“${escapar(p.comentario)}”</span>` : ""}
      </article>`
    )
    .join("");
  alvo.innerHTML =
    `<p class="grafico-leitura">Semana ${escapar(sim.semana || "")} · variante vencedora ` +
    `<b>${escapar(sim.vencedora || "—")}</b> · adesão média ${media("adesao").toFixed(1)} · ` +
    `rejeição ${Math.round(media("rejeicao") * 100)}%. ${escapar(variantes)}</p>` +
    `<div class="personas-grade">${cards}</div>` +
    `<p class="selo-simulacao">${escapar(sim.aviso || "Simulação (hipótese) — não é pesquisa.")}</p>`;
}

let textoGovernadorAtual = "";

function renderizarGovernadorDiscurso() {
  const alvo = document.getElementById("discursoGovernador");
  if (!alvo) return;
  const disc = estado.discursoGovernador;
  const btnCopiar = document.getElementById("btnCopiarDiscursoGovernador");
  const variantes = Array.isArray(disc?.variantes) ? disc.variantes : [];
  if (!variantes.length) {
    textoGovernadorAtual = "";
    alvo.innerHTML =
      '<p class="grafico-leitura">O discurso do governador desta semana ainda não foi gerado. ' +
      "Ele entra aqui após a análise das notícias e a validação do formato.</p>";
    if (btnCopiar) btnCopiar.disabled = true;
    return;
  }
  const idx = Math.min(estado.varianteGovernador, variantes.length - 1);
  estado.varianteGovernador = idx;
  const atual = variantes[idx] || {};
  const texto = atual.tribuna || atual.texto || "";
  textoGovernadorAtual = texto;
  const abas = variantes
    .map(
      (v, i) =>
        `<button class="disc-aba${i === idx ? " ativo" : ""}" type="button" ` +
        `data-disc-gov="${i}">${escapar(v.angulo || v.id || `Variante ${i + 1}`)}</button>`
    )
    .join("");
  const fontes = (atual.fontes || [])
    .slice(0, 10)
    .map(
      (f) =>
        `<li>${escapar(f.veiculo || f.fonte || "Fonte")}${
          f.data ? " · " + escapar(String(f.data).slice(0, 10)) : ""
        }${f.url ? ` · <a href="${escapar(f.url)}" target="_blank" rel="noopener">abrir</a>` : ""}</li>`
    )
    .join("");
  alvo.innerHTML =
    `<div class="disc-tabs" role="tablist">${abas}</div>` +
    `<article class="disc-texto-ativo">` +
    `<div class="disc-meta"><span>${escapar(disc.semana || estado.semanaGovernador || "")}</span>` +
    `<span>${escapar(disc.modelo || "IA")}</span></div>` +
    `<p>${escapar(texto).replace(/\n/g, "</p><p>")}</p>` +
    (atual.video
      ? `<details class="disc-extra"><summary>Versão para vídeo (60s)</summary><p>${escapar(atual.video)}</p></details>`
      : "") +
    (atual.post
      ? `<details class="disc-extra"><summary>Versão para post</summary><p>${escapar(atual.post)}</p></details>`
      : "") +
    (fontes
      ? `<div class="disc-fontes"><strong>Fontes</strong><ul>${fontes}</ul></div>`
      : "") +
    `<p class="disc-aviso">Rascunho gerado por IA — confira as fontes antes de usar.</p>` +
    `</article>`;
  if (btnCopiar) btnCopiar.disabled = false;

  alvo.querySelectorAll("[data-disc-gov]").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.varianteGovernador = Number(botao.dataset.discGov);
      renderizarGovernadorDiscurso();
    });
  });
}

async function copiarDiscursoSemana() {
  if (!textoDiscursoAtual) return;
  try {
    await navigator.clipboard.writeText(textoDiscursoAtual);
    textoDiscursoAtual && (document.getElementById("discursoTexto").dataset.copiado = "1");
  } catch {
    /* sem clipboard */
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("#btnCopiarDiscurso")) {
      copiarDiscursoSemana();
    }
    if (evento.target.closest("#btnBaixarPdfSemanal")) {
      document.body.classList.add("print-semana");
      window.print();
      setTimeout(() => document.body.classList.remove("print-semana"), 300);
    }
    if (evento.target.closest("#btnCopiarDiscursoInterino")) {
      if (textoInterinoAtual) {
        navigator.clipboard?.writeText(textoInterinoAtual).catch(() => {});
      }
    }
    if (evento.target.closest("#btnCopiarDiscursoGovernador")) {
      if (textoGovernadorAtual) {
        navigator.clipboard?.writeText(textoGovernadorAtual).catch(() => {});
      }
    }
    if (evento.target.closest("#btnBaixarPdfGovernador")) {
      document.body.classList.add("print-governador");
      window.print();
      setTimeout(() => document.body.classList.remove("print-governador"), 300);
    }
  });
}

/* ---- V7 / Redes da Casa ---- */
function renderizarRedes(dados) {
  const proprias = dados.redes_proprias || {};
  const temContas = Array.isArray(proprias.conectadas) && proprias.conectadas.length > 0;
  const socialBase = dados.redes_sociais || {};
  const social = { ...socialBase, posts: socialBase.posts || estado.dados?.redes_sociais?.posts || [] };
  const imagens = dados.imagens?.kpis || {};
  const postsSociais = Array.isArray(social.posts) ? social.posts : [];
  const totalRedes = Number(social.total || 0);
  const comentarios = Number(social.comentarios_total || 0);
  const ultimoPost = postsSociais[0]?.data || social.recentes?.[0]?.data;

  if (temContas) {
    cartaoKpi("kpiRedesSeguidores", {
      codigo: "K-10",
      nome: "Seguidores",
      valor: new Intl.NumberFormat("pt-BR").format(Number(proprias.seguidores || 0)),
      sufixo: "contas oficiais conectadas",
    });
    cartaoKpi("kpiRedesEngajamento", {
      codigo: "K-11",
      nome: "Engajamento",
      valor: `${Number(proprias.engajamento_7d || 0).toFixed(2)}%`,
    });
    cartaoKpi("kpiRedesComentarios", {
      codigo: "K-12",
      nome: "Comentários",
      valor: String(Number(proprias.comentarios?.total || 0)),
    });
    cartaoKpi("kpiRedesResposta", {
      codigo: "K-27",
      nome: "Taxa de resposta",
      valor: `${Math.round(Number(proprias.taxa_resposta || 0))}%`,
    });
  } else {
    cartaoKpi("kpiRedesSeguidores", {
      codigo: "K-10",
      nome: "Publicações monitoradas",
      valor: totalRedes ? String(totalRedes) : "—",
      sufixo: totalRedes ? "Instagram e redes captadas" : "",
      ...(totalRedes ? {} : { semBase: true, motivo: "nenhuma publicação captada" }),
    });
    cartaoKpi("kpiRedesEngajamento", {
      codigo: "K-11",
      nome: "Comentários captados",
      valor: comentarios ? String(comentarios) : "—",
      sufixo: comentarios ? "comentários públicos estruturados" : "",
      ...(comentarios ? {} : { semBase: true, motivo: "nenhum comentário captado" }),
    });
    cartaoKpi("kpiRedesComentarios", {
      codigo: "K-12",
      nome: "Posts com imagem",
      valor: imagens.k70_postos_com_imagem !== undefined ? String(Number(imagens.k70_postos_com_imagem)) : "—",
      sufixo: imagens.k70_postos_com_imagem !== undefined ? "com capa analisada" : "",
      ...(imagens.k70_postos_com_imagem !== undefined ? {} : { semBase: true, motivo: "análise de imagem pendente" }),
    });
    cartaoKpi("kpiRedesResposta", {
      codigo: "K-27",
      nome: "Última coleta",
      valor: ultimoPost ? _dataCurta(ultimoPost) : "—",
      sufixo: ultimoPost ? "Instagram monitorado" : "sem coleta recente",
      ...(ultimoPost ? {} : { semBase: true, motivo: "sem data de coleta" }),
    });
  }

    const container = document.getElementById("redesContas");
  if (container) {
    const conectadas = proprias.conectadas || [];
    if (conectadas.length) {
      container.innerHTML = conectadas
        .map(
          (rede) => `<div class="card kpi">
            <div class="kpi-cabecalho"><span class="kpi-rotulo">${escapar(rede)}</span></div>
            <span class="kpi-valor">${new Intl.NumberFormat("pt-BR").format(
              Number(proprias[rede]?.seguidores ?? 0)
            )}</span>
            <span class="kpi-sufixo">seguidores · ${Number(
              proprias[rede]?.alcance_7d ?? 0
            ).toLocaleString("pt-BR")} de alcance</span>
          </div>`
        )
        .join("");
    } else {
      const porRede = Object.entries(social.por_rede || {});
      container.innerHTML =
        `<div class="redes-cta">
          <p><strong>Contas oficiais ainda não conectadas.</strong> Abaixo, o que foi captado publicamente no período.</p>
          <a class="btn-texto" href="#/sistema">Conectar em Sistema</a>
        </div>` +
        (porRede.length
          ? porRede
              .map(
                ([rede, total]) => `<div class="card kpi">
                  <div class="kpi-cabecalho"><span class="kpi-rotulo">${escapar(rede)}</span></div>
                  <span class="kpi-valor">${new Intl.NumberFormat("pt-BR").format(Number(total || 0))}</span>
                  <span class="kpi-sufixo">publicações monitoradas</span>
                </div>`
              )
              .join("")
          : `<p class="grafico-leitura">Nenhuma publicação de rede captada ainda.</p>`);
    }
  }

  const corpo = document.getElementById("corpoRedes");
  if (corpo) {
    const posts = Array.isArray(social.recentes) ? social.recentes : [];
    corpo.innerHTML = posts.length
      ? posts
          .map(
            (p) => `<tr>
              <td>${escapar(_dataCurta(p.data))}</td>
              <td>${escapar(p.rede || "—")}</td>
              <td>${p.url ? `<a href="${escapar(p.url)}" target="_blank" rel="noopener">${escapar((p.titulo || p.snippet || "publicação").slice(0, 120))}</a>` : escapar((p.titulo || p.snippet || "publicação").slice(0, 120))}</td>
              <td>${escapar(p.sentimento || "—")}</td>
              <td>${escapar(p.agente || "")}</td>
            </tr>`
          )
          .join("")
      : `<tr><td colspan="5">Nenhuma publicação de rede captada no período.</td></tr>`;
  }

  renderizarRedesPosts(social, dados);
  renderizarImagensValor(dados);
}

let postsRedes = [];
let todosPostsRedes = [];
let postIndice = 0;
let imagensPosts = new Map();

function _postImagem(post) {
  const imagem = imagensPosts.get(String(post.post_shortcode || post.id_externo || ""));
  return imagem?.thumb
    ? `<img src="data:image/webp;base64,${escapar(imagem.thumb)}" alt="${escapar(post.titulo || "Post do Instagram")}" loading="lazy" />`
    : `<div class="post-imagem-vazia">Sem imagem analisada</div>`;
}

function _topTermos(textos, limite = 6) {
  const paradas = new Set(["para", "com", "uma", "dos", "das", "por", "que", "não", "nao", "mais", "como", "aqui", "muito", "bem", "vai", "está", "esta", "sobre", "também", "tambem", "esse", "essa", "isso", "pelo", "pela", "nos", "nas", "seu", "sua", "meu", "minha", "todo", "toda", "tem", "foi", "ser", "são", "sao"]);
  const contagem = {};
  (textos || []).forEach((texto) => {
    (String(texto || "").toLowerCase().match(/[a-záàâãéêíóôõúç0-9]{4,}/g) || []).forEach((p) => {
      if (!paradas.has(p)) contagem[p] = (contagem[p] || 0) + 1;
    });
  });
  return Object.entries(contagem)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limite)
    .map(([termo]) => termo);
}

function _renderCardsRedes(posts) {
  const alvo = document.getElementById("redesPosts");
  if (!alvo) return;
  alvo.innerHTML = posts.length
    ? posts
        .map(
          (p, indice) => `<button type="button" class="rede-post-card" data-post-index="${indice}">
            <span class="rede-post-midia">${_postImagem(p)}</span>
            <span class="rede-post-corpo">
              <span class="rede-post-rede">${escapar(p.rede || "Instagram")} · ${escapar(_dataCurta(p.data))}</span>
              <strong>${escapar((p.titulo || p.texto || "Post").slice(0, 110))}</strong>
              <span class="rede-post-metricas">${Number(p.curtidas || 0).toLocaleString("pt-BR")} curtidas · ${Number(p.comentarios_coletados || 0).toLocaleString("pt-BR")} comentários</span>
              <span class="rede-post-tom">${escapar(p.sentimento || "neutro")}</span>
            </span>
          </button>`
        )
        .join("")
    : '<p class="grafico-leitura">Nenhum post atende aos filtros selecionados.</p>';
  alvo.querySelectorAll("[data-post-index]").forEach((card) => {
    card.addEventListener("click", () => abrirPost(Number(card.dataset.postIndex)));
  });
}

function _postsFiltradosRedes() {
  const agente = document.getElementById("filtroRedesAgente")?.value || "";
  const tom = document.getElementById("filtroRedesTom")?.value || "";
  const busca = (document.getElementById("filtroRedesBusca")?.value || "").trim().toLowerCase();
  return todosPostsRedes.filter((p) => {
    if (agente && p.agente !== agente) return false;
    if (tom && (p.sentimento || "neutro") !== tom) return false;
    if (busca) {
      const texto = `${p.titulo || ""} ${p.texto || ""} ${(p.comentarios || []).map((c) => `${c.autor || ""} ${c.texto || ""}`).join(" ")}`.toLowerCase();
      if (!texto.includes(busca)) return false;
    }
    return true;
  });
}

function preencherFiltrosRedes(posts) {
  const seletor = document.getElementById("filtroRedesAgente");
  if (!seletor) return;
  const atual = seletor.value;
  const agentes = [...new Set(posts.map((p) => p.agente).filter(Boolean))].sort();
  seletor.innerHTML = '<option value="">Todos os agentes</option>' + agentes.map((a) => `<option value="${escapar(a)}">${escapar(a)}</option>`).join("");
  seletor.value = agentes.includes(atual) ? atual : "";
}

function aplicarFiltrosRedes() {
  postsRedes = _postsFiltradosRedes();
  _renderCardsRedes(postsRedes);
  const resumo = document.getElementById("redesPostsResumo");
  if (resumo) {
    resumo.textContent = `${postsRedes.length} posts exibidos de ${todosPostsRedes.length} captados · clique para ver imagem, comentários e análise`;
  }
}

function renderizarRedesPosts(social, dados) {
  const alvo = document.getElementById("redesPosts");
  if (!alvo) return;
  const posts = Array.isArray(social?.posts) ? social.posts : [];
  const galeria = dados?.imagens?.galeria || [];
  imagensPosts = new Map(
    galeria.map((g) => [String(g.post_shortcode || g.id_externo || ""), g])
  );
  todosPostsRedes = posts;
  preencherFiltrosRedes(posts);
  aplicarFiltrosRedes();
  if (!posts.length) {
    alvo.innerHTML = '<p class="grafico-leitura">Os posts aparecem aqui quando a coleta do Instagram estiver disponível.</p>';
  }
}


function fecharPost() {
  const modal = document.getElementById("modalPost");
  if (!modal) return;
  modal.classList.add("oculto");
  modal.setAttribute("aria-hidden", "true");
}

function atualizarPost() {
  if (!postsRedes.length) return;
  const post = postsRedes[postIndice];
  const imagem = document.getElementById("postImagem");
  const titulo = document.getElementById("postTitulo");
  const texto = document.getElementById("postTexto");
  const conta = document.getElementById("postConta");
  const metricas = document.getElementById("postMetricas");
  const resumo = document.getElementById("postResumo");
  const comentariosEl = document.getElementById("postComentarios");
  if (imagem) imagem.innerHTML = _postImagem(post);
  if (titulo) titulo.textContent = post.titulo || "Post do Instagram";
  if (texto) texto.textContent = post.texto || "";
  if (conta) conta.innerHTML = `${escapar(post.rede || "Instagram")} · ${escapar(post.agente || "")}${post.url ? ` · <a href="${escapar(post.url)}" target="_blank" rel="noopener">abrir no Instagram</a>` : ""}`;
  if (metricas) {
    metricas.innerHTML = `
      <span><strong>${Number(post.curtidas || 0).toLocaleString("pt-BR")}</strong> curtidas</span>
      <span><strong>${Number(post.comentarios_coletados || 0).toLocaleString("pt-BR")}</strong> de ${Number(post.comentarios_total || 0).toLocaleString("pt-BR")} comentários</span>
      <span>Tom: <strong>${escapar(post.sentimento || "neutro")}</strong></span>`;
  }
  const comentarios = Array.isArray(post.comentarios) ? post.comentarios : [];
  if (resumo) {
    const sent = { positivo: 0, neutro: 0, negativo: 0 };
    comentarios.forEach((c) => {
      const chave = c.sentimento || "neutro";
      if (sent[chave] !== undefined) sent[chave] += 1;
    });
    const total = comentarios.length || 1;
    const termos = _topTermos(comentarios.map((c) => c.texto));
    resumo.innerHTML = `
      <p><strong>O que importa:</strong> ${comentarios.length} comentários coletados; leitura de tom ${Math.round(sent.positivo * 100 / total)}% positivo, ${Math.round(sent.neutro * 100 / total)}% neutro e ${Math.round(sent.negativo * 100 / total)}% negativo.</p>
      ${termos.length ? `<p><strong>Termos recorrentes:</strong> ${termos.map((t) => escapar(t)).join(" · ")}</p>` : ""}`;
  }
  if (comentariosEl) {
    comentariosEl.innerHTML = comentarios.length
      ? comentarios
          .map(
            (c) => `<article class="post-comentario">
              <header><strong>@${escapar(c.autor || "anônimo")}</strong><span>${escapar(c.sentimento || "neutro")}</span></header>
              <p>${escapar(c.texto || "")}</p>
            </article>`
          )
          .join("")
      : '<p class="grafico-leitura">Nenhum comentário estruturado para este post.</p>';
  }
  const posicao = document.getElementById("postPosicao");
  if (posicao) posicao.textContent = `${postIndice + 1} de ${postsRedes.length}`;
  const anterior = document.getElementById("postAnterior");
  const proximo = document.getElementById("postProximo");
  if (anterior) anterior.disabled = postIndice === 0;
  if (proximo) proximo.disabled = postIndice >= postsRedes.length - 1;
}

function abrirPost(indice) {
  postIndice = Math.max(0, Math.min(indice, postsRedes.length - 1));
  document.querySelectorAll(".modal-overlay").forEach((m) => {
    m.classList.add("oculto");
    m.setAttribute("aria-hidden", "true");
  });
  const modal = document.getElementById("modalPost");
  if (!modal) return;
  modal.classList.remove("oculto");
  modal.setAttribute("aria-hidden", "false");
  atualizarPost();
}

if (typeof document !== "undefined") {
  ["filtroRedesAgente", "filtroRedesTom"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", aplicarFiltrosRedes);
  });
  document.getElementById("filtroRedesBusca")?.addEventListener("input", () => {
    clearTimeout(window.__timerRedes);
    window.__timerRedes = setTimeout(aplicarFiltrosRedes, 150);
  });
  document.getElementById("fecharPost")?.addEventListener("click", fecharPost);
  document.getElementById("postAnterior")?.addEventListener("click", () => {
    if (postIndice > 0) { postIndice -= 1; atualizarPost(); }
  });
  document.getElementById("postProximo")?.addEventListener("click", () => {
    if (postIndice < postsRedes.length - 1) { postIndice += 1; atualizarPost(); }
  });
  document.addEventListener("keydown", (evento) => {
    if (document.getElementById("modalPost")?.classList.contains("oculto")) return;
    if (evento.key === "Escape") fecharPost();
    if (evento.key === "ArrowLeft" && postIndice > 0) { postIndice -= 1; atualizarPost(); }
    if (evento.key === "ArrowRight" && postIndice < postsRedes.length - 1) { postIndice += 1; atualizarPost(); }
  });
}

/* ---- Imagens (também no Valor) ---- */
function renderizarImagensValor(dados) {
  const imagens = dados.imagens || {};
  const kpis = imagens.kpis || {};
  const temBase = !!dados.imagens && Object.keys(kpis).length > 0;
  const numero = (valor, formatar = (v) => String(v)) =>
    temBase && valor !== undefined && valor !== null ? formatar(Number(valor)) : "—";
  const classe = temBase ? "card kpi" : "card kpi kpi-sem-base";
  const sufixo = temBase ? "" : '<span class="kpi-sufixo">aguardando análise de imagem</span>';
  const container = document.getElementById("imagensKpis");
  if (container) {
    container.innerHTML = `
      <div class="${classe}"><div class="kpi-cabecalho"><span class="kpi-rotulo">Posts com imagem analisada</span></div><span class="kpi-valor">${numero(kpis.k70_postos_com_imagem)}</span>${sufixo}</div>
      <div class="${classe}"><div class="kpi-cabecalho"><span class="kpi-rotulo">Cards com texto</span></div><span class="kpi-valor">${numero(kpis.k72_cards_com_texto, (v) => `${Math.round(v * 100)}%`)}</span>${sufixo}</div>
      <div class="${classe}"><div class="kpi-cabecalho"><span class="kpi-rotulo">Peças com promoção pessoal</span></div><span class="kpi-valor">${numero(kpis.k75_alertas_vindos_de_imagem)}</span>${sufixo}</div>
      <div class="${classe}"><div class="kpi-cabecalho"><span class="kpi-rotulo">Imagens recicladas</span></div><span class="kpi-valor">${numero(kpis.k74_imagens_recicladas)}</span>${sufixo}</div>
    `;
  }

  const galeriaEl = document.getElementById("galeriaImagens");
  if (galeriaEl) {
    const galeria = imagens.galeria || [];
    galeriaEl.innerHTML = galeria.length
      ? galeria
          .slice(0, 24)
          .map(
            (g) => `<figure class="galeria-item" tabindex="0">
              ${g.thumb ? `<img class="galeria-thumb" src="data:image/webp;base64,${escapar(g.thumb)}" alt="${escapar(g.resumo || "Imagem analisada")}" loading="lazy" />` : '<div class="galeria-thumb"></div>'}
              <figcaption class="galeria-info">
                <p class="galeria-tipo">${escapar(g.tipo_rotulo || g.tipo || "Imagem")}</p>
                <p class="galeria-meta">${escapar(g.rede || "")} · ${escapar(g.data || "")}</p>
                <div class="galeria-chips">
                  ${g.texto_imagem ? '<span class="galeria-chip">Texto na imagem</span>' : ""}
                  ${g.reciclada ? '<span class="galeria-chip">Reciclada</span>' : ""}
                  ${g.c2pa?.gerado_ia ? '<span class="galeria-chip galeria-chip-alerta">Gerado por IA</span>' : ""}
                </div>
              </figcaption>
            </figure>`
          )
          .join("")
      : `<p class="grafico-leitura">Ainda não há imagens analisadas neste escopo. As miniaturas entram quando a coleta de peças com imagem roda.</p>`;
  }
}

/* ---- V8 / Conformidade ---- */
function renderizarConformidade(dados) {
  const tem = (v) => v !== undefined && v !== null;
  const semCompliance = !tem(dados.compliance?.total);
  const semImagens = !tem(dados.imagens?.kpis?.k75_alertas_vindos_de_imagem);
  const semAnuncios = !tem(dados.anuncios_politicos?.anuncios_ativos);
  cartaoKpi("kpiConfRiscos", {
    codigo: "K-21",
    valor: tem(dados.compliance?.total) ? String(Number(dados.compliance.total)) : "—",
    ...(semCompliance ? { semBase: true, motivo: "análise de conformidade não iniciada" } : {}),
  });
  cartaoKpi("kpiConfPromocao", {
    codigo: "K-45",
    valor: tem(dados.imagens?.kpis?.k75_alertas_vindos_de_imagem)
      ? String(Number(dados.imagens.kpis.k75_alertas_vindos_de_imagem))
      : "—",
    ...(semImagens ? { semBase: true, motivo: "sem análise de imagem" } : {}),
  });
  cartaoKpi("kpiConfAnuncios", {
    codigo: "K-22",
    valor: tem(dados.anuncios_politicos?.anuncios_ativos)
      ? String(Number(dados.anuncios_politicos.anuncios_ativos))
      : "—",
    ...(semAnuncios ? { semBase: true, motivo: "Ad Library não coletada" } : {}),
  });
  cartaoKpi("kpiConfVedacoes", {
    codigo: "K-46",
    valor: tem(dados.dias_ate_vedacoes) ? String(dados.dias_ate_vedacoes) : "—",
    ...(tem(dados.dias_ate_vedacoes) ? {} : { semBase: true, motivo: "calendário eleitoral não configurado" }),
  });
}

/* ---- V9 / Tendências ---- */
function renderizarTendencias(dados) {
  const tend = dados.tendencias || {};
  const tem = (v) => v !== undefined && v !== null;
  const fonte = document.getElementById("tendenciasFonte");
  if (fonte) {
    const quando = tend.atualizado_em ? new Date(tend.atualizado_em) : null;
    const data = quando && !isNaN(quando) ? quando.toLocaleString("pt-BR") : "";
    fonte.textContent = data
      ? `Fonte: Google Trends · atualizado em ${data}`
      : "Fonte: Google Trends";
  }
  const termosEmAlta = (tend.em_alta_mt || []).length + (tend.em_alta_br || []).length;
  cartaoKpi("kpiTendInteresse", {
    codigo: "K-30",
    nome: tem(tend.interesse_busca?.media) ? undefined : "Termos em alta",
    valor: tem(tend.interesse_busca?.media)
      ? String(Number(tend.interesse_busca.media).toFixed(0))
      : (termosEmAlta ? String(termosEmAlta) : "—"),
    sufixo: tem(tend.interesse_busca?.media)
      ? "índice de interesse"
      : (termosEmAlta ? "termos MT + BR no Google Trends" : "sem série de buscas"),
    ...(tem(tend.interesse_busca?.media) || termosEmAlta ? {} : { semBase: true, motivo: "sem série de buscas" }),
  });
  const temPico = tem(tend.pico);
  document.getElementById("kpiTendPico")?.classList.toggle("oculto", !temPico);
  if (temPico) {
    cartaoKpi("kpiTendPico", {
      codigo: "K-32",
      valor: tend.pico.ativo ? "Sim" : "Não",
      sufixo: tem(tend.pico?.fator) ? `${Number(tend.pico.fator).toFixed(1)}× a média` : "",
    });
  }
  cartaoKpi("kpiTendProjecao", {
    codigo: "K-33",
    valor: dados.previsao?.mencoes?.previsao?.length
      ? String(dados.previsao.mencoes.previsao.length)
      : "—",
    ...(dados.previsao?.mencoes?.previsao?.length ? {} : { semBase: true, motivo: "sem projeção nesta semana" }),
  });
  cartaoKpi("kpiTendCrise", {
    codigo: "K-28",
    valor: tem(dados.crise) ? (dados.crise.ativo ? "Alerta" : "Normal") : "—",
    sufixo: dados.crise?.mensagem || "",
    ...(tem(dados.crise) ? {} : { semBase: true, motivo: "índice de crise não calculado" }),
  });

  const lista = document.getElementById("listaTendencias");
  if (lista) {
    const itens = [...(tend.em_alta_mt || []), ...(tend.em_alta_br || [])].slice(0, 20);
    lista.innerHTML = itens.length
      ? itens
          .map(
            (i) => `<li>
              <span class="tend-termino">${escapar(i.termo || "")}</span>
              <span class="tend-volume">${escapar(i.volume || "")}</span>
              ${
                i.noticias && i.noticias[0]
                  ? `<a class="tend-noticia" href="${escapar(i.noticias[0].url)}" target="_blank" rel="noopener">${escapar(
                      (i.noticias[0].titulo || "").slice(0, 80)
                    )}</a>`
                  : ""
              }
            </li>`
          )
          .join("")
      : `<li><span class="tend-noticia">Nenhum assunto em alta carregado ainda. A busca do Google Trends roda uma vez por dia.</span></li>`;
  }

  const previsao = dados.previsao?.mencoes || {};
  const canvas = document.getElementById("graficoPrevisao");
  const temPrevisao = (previsao.historico || []).length > 0 || (previsao.previsao || []).length > 0;
  const cardPrevisao = canvas?.closest(".card");
  if (cardPrevisao) cardPrevisao.classList.toggle("oculto", !temPrevisao);
  if (canvas && temPrevisao) {
    guardar(
      "graficoPrevisao",
      linhaComPrevisao(
        canvas,
        {
          datas: (previsao.historico || []).map((h) => h.data),
          valores: (previsao.historico || []).map((h) => h.valor),
        },
        {
          datas: (previsao.previsao || []).map((p) => p.data),
          valores: (previsao.previsao || []).map((p) => p.valor),
          superiores: (previsao.previsao || []).map((p) => p.superior),
        }
      )
    );
  }
}

/* ---- auxiliares ---- */
function serieSentimento(dados) {
  const fonte =
    dados.serie_sentimento || dados.por_dia || dados.dias || {};
  const dias = Object.keys(fonte).sort();
  const item = (dia) =>
    fonte[dia] && typeof fonte[dia] === "object" ? fonte[dia] : {};
  return [
    {
      datas: dias,
      positivos: dias.map((d) => Number(item(d).positivo ?? 0)),
    },
    {
      datas: dias,
      neutros: dias.map((d) => Number(item(d).neutro ?? 0)),
    },
    {
      datas: dias,
      negativos: dias.map((d) => Number(item(d).negativo ?? 0)),
    },
  ];
}

function seriePorCanal(dados) {
  const canais = dados.por_canal || dados.distribuicao_categorias || {};
  if (Array.isArray(canais)) {
    return canais.map((c) => ({
      rotulo: c.categoria || c.nome || "",
      positivo: Number(c.positivo ?? 0),
      neutro: Number(c.neutro ?? 0),
      negativo: Number(c.negativo ?? 0),
    }));
  }
  return Object.entries(canais).map(([canal, item]) => ({
    rotulo: canal,
    positivo: Number(item?.positivo ?? 0),
    neutro: Number(item?.neutro ?? 0),
    negativo: Number(item?.negativo ?? 0),
  }));
}

function contagemPor(lista, campo) {
  const contagem = {};
  (lista || []).forEach((item) => {
    const chave = item[campo] || "outros";
    contagem[chave] = (contagem[chave] || 0) + 1;
  });
  return Object.entries(contagem)
    .map(([rotulo, valor]) => ({ rotulo, valor }))
    .sort((a, b) => b.valor - a.valor);
}

if (typeof document !== "undefined") {
  ["filtroClipVeiculo", "filtroClipTier", "filtroClipTipo"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      paginaClipping = 1;
      renderizarClipping(dadosDaJanela(estado.dados || {}));
    });
  });
  let buscaClippingTimer = null;
  document.getElementById("filtroClipBusca")?.addEventListener("input", () => {
    clearTimeout(buscaClippingTimer);
    buscaClippingTimer = setTimeout(() => {
      paginaClipping = 1;
      renderizarClipping(dadosDaJanela(estado.dados || {}));
    }, 180);
  });
  document.querySelectorAll("select[data-semana]").forEach((select) => {
    select.addEventListener("change", () => definirSemana(select.value));
  });
}

export default { carregar, renderizar, redimensionar };

let textoInterinoAtual = "";

function renderizarInterinoDiscurso() {
  const alvo = document.getElementById("discursoInterino");
  if (!alvo) return;
  const disc = estado.discursoInterino;
  const btn = document.getElementById("btnCopiarDiscursoInterino");
  const variantes = Array.isArray(disc?.variantes) ? disc.variantes : [];
  if (!variantes.length) {
    textoInterinoAtual = "";
    alvo.innerHTML =
      '<p class="grafico-leitura">O discurso do governador interino desta semana ainda não foi gerado.</p>';
    if (btn) btn.disabled = true;
    return;
  }
  const idx = Math.min(estado.varianteInterino, variantes.length - 1);
  estado.varianteInterino = idx;
  const atual = variantes[idx] || {};
  const texto = atual.tribuna || atual.texto || "";
  textoInterinoAtual = texto;
  const abas = variantes
    .map(
      (v, i) =>
        `<button class="disc-aba${i === idx ? " ativo" : ""}" type="button" data-disc-interino="${i}">${escapar(v.angulo || v.id || `Variante ${i + 1}`)}</button>`
    )
    .join("");
  const fontes = (atual.fontes || [])
    .slice(0, 10)
    .map(
      (f) =>
        `<li>${escapar(f.veiculo || f.fonte || "Fonte")}${f.data ? " · " + escapar(String(f.data).slice(0, 10)) : ""}${f.url ? ` · <a href="${escapar(f.url)}" target="_blank" rel="noopener">abrir</a>` : ""}</li>`
    )
    .join("");
  alvo.innerHTML =
    `<div class="disc-tabs" role="tablist">${abas}</div>` +
    `<article class="disc-texto-ativo">` +
    `<div class="disc-meta"><span>${escapar(disc.semana || estado.semanaInterino || "")}</span><span>${escapar(disc.modelo || "IA")}</span></div>` +
    `<p>${escapar(texto).replace(/\n/g, "</p><p>")}</p>` +
    (atual.video ? `<details class="disc-extra"><summary>Versão para vídeo (60s)</summary><p>${escapar(atual.video)}</p></details>` : "") +
    (atual.post ? `<details class="disc-extra"><summary>Versão para post</summary><p>${escapar(atual.post)}</p></details>` : "") +
    (fontes ? `<div class="disc-fontes"><strong>Fontes</strong><ul>${fontes}</ul></div>` : "") +
    `<p class="disc-aviso">Rascunho gerado por IA — confira as fontes antes de usar.</p>` +
    `</article>`;
  if (btn) btn.disabled = false;
  alvo.querySelectorAll("[data-disc-interino]").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.varianteInterino = Number(botao.dataset.discInterino);
      renderizarInterinoDiscurso();
    });
  });
}
























