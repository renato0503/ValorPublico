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
  varianteAtiva: 0,
  discursoGovernador: null,
  semanaGovernador: "",
  varianteGovernador: 0,
};
const graficos = new Map();

/** Define o órgão ativo (a Casa). Sem ele nenhuma tela lê dados. */
export function definirOrgao(info) {
  estado.orgao = info || null;
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
async function lerSemana(db, orgao) {
  if (!orgao) return { relatorio: null, discurso: null, simulacao: null, semana: "" };
  const escopo = `casa-${orgao.slug}`;
  for (const semana of semanasRecentes(4)) {
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
    semana: semanasRecentes(1)[0],
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

async function lerDiscursoAgente(db, escopoBase) {
  for (const semana of semanasRecentes(4)) {
    const doc = await lerDocSeguro(
      db,
      "discurso_semanal",
      `${escopoBase}__${semana}`
    );
    if (doc) return { doc, semana };
  }
  return { doc: null, semana: semanasRecentes(1)[0] };
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
  const semana = await lerSemana(db, estado.orgao);
  estado.relatorio = semana.relatorio;
  estado.discurso = semana.discurso;
  estado.simulacao = semana.simulacao;
  estado.semana = semana.semana;
  if (estado.orgao?.slug === "governo-mt") {
    const gov = await lerDiscursoAgente(
      db,
      "agente-governador-otaviano-pivetta"
    );
    estado.discursoGovernador = gov.doc;
    estado.semanaGovernador = gov.semana;
  } else {
    estado.discursoGovernador = null;
    estado.semanaGovernador = "";
  }
  renderizar();
}

export function renderizar() {
  const dados = estado.dados || {};
  renderizarEdicao(dados);
  renderizarClipping(dados);
  renderizarImagem(dados);
  renderizarOuvidoria(dados);
  renderizarSemana(dados);
  renderizarGovernadorDiscurso();
  renderizarRedes(dados);
  renderizarConformidade(dados);
  renderizarTendencias(dados);
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
  cartaoKpi("kpiEdicaoMatarias", {
    codigo: "K-01",
    valor: new Intl.NumberFormat("pt-BR").format(Number(dados.total_clippings ?? 0)),
  });
  cartaoKpi("kpiEdicaoSentimento", {
    codigo: "K-03",
    valor: Number(saldoDeOpiniao(dados)).toFixed(0),
  });
  cartaoKpi("kpiEdicaoAlcance", {
    codigo: "K-05",
    valor: new Intl.NumberFormat("pt-BR").format(Number(dados.audiencia_total ?? 0)),
  });
  cartaoKpi("kpiEdicaoValor", {
    codigo: "K-08",
    valor: new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 0,
    }).format(Number(dados.valor_avpe_total ?? dados.valoracao_total ?? 0)),
    valorMidia: true,
  });
  cartaoKpi("kpiEdicaoAlertas", {
    codigo: "K-20",
    valor: String(Number(dados.alertas?.total ?? 0)),
  });
  cartaoKpi("kpiEdicaoSla", {
    codigo: "K-60",
    valor: `${Math.round(Number(dados.cobertura?.sla_min_medio ?? 0))} min`,
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

  const veiculo = selVeiculo?.value || "";
  const tier = selTier?.value || "";
  const tipo = selTipo?.value || "";
  const filtrados = itens.filter((n) => {
    if (veiculo && n.veiculo !== veiculo) return false;
    if (tier && n.tier !== tier) return false;
    const tipoItem = n.tipo_mencao || n.tipo || "";
    if (tipo && tipoItem !== tipo) return false;
    return true;
  });

  corpo.innerHTML = filtrados.length
    ? filtrados
        .slice(0, 100)
        .map(
          (n) => `<tr>
            <td>${n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">${escapar(n.titulo || "notícia")}</a>` : escapar(n.titulo || "notícia")}</td>
            <td>${escapar(n.veiculo || n.autor || "—")}</td>
            <td>${escapar(_dataCurta(n.data_publicacao || n.data))}</td>
            <td>${escapar(n.tipo_mencao || n.tipo || "—")}</td>
            <td>${escapar(n.sentimento || "—")}</td>
          </tr>`
        )
        .join("")
    : `<tr><td colspan="5">Nenhuma das últimas notícias atende aos filtros selecionados.</td></tr>`;

  const nota = document.getElementById("clippingNota");
  if (nota) {
    nota.textContent = itens.length
      ? `Mostrando ${filtrados.length} de ${itens.length} notícias recentes do agregado do Governo. A lista completa será carregada pela API de clipping.`
      : "Ainda não há notícias recentes neste agregado. A coleta diária preenche esta lista.";
  }
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
  if (canvas) {
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
    sufixo: variedade !== null ? "diversidade dos assuntos" : "não calculada nesta semana",
  });
  cartaoKpi("kpiSemanaSintonia", {
    codigo: "K-41",
    valor:
      rel.alinhamento !== undefined && rel.alinhamento !== null
        ? Number(rel.alinhamento).toFixed(2)
        : "—",
    sufixo:
      rel.alinhamento === undefined || rel.alinhamento === null
        ? "sem base na semana"
        : "",
  });
  const imagens = dados.imagens?.kpis;
  cartaoKpi("kpiSemanaImagens", {
    codigo: "K-70",
    valor: imagens ? String(imagens.k70_postos_com_imagem ?? 0) : "—",
    sufixo: imagens ? "" : "sem análise de imagem",
  });
  cartaoKpi("kpiSemanaEquidade", {
    codigo: "K-43",
    valor:
      dados.equidade_visibilidade !== undefined &&
      dados.equidade_visibilidade !== null
        ? Number(dados.equidade_visibilidade).toFixed(2)
        : "—",
    sufixo:
      dados.equidade_visibilidade === undefined
        ? "não calculado nesta semana"
        : "",
  });

  const canvas = document.getElementById("graficoSemanaClasses");
  if (canvas) {
    const classesChd = rel.chd?.classes || [];
    if (classesChd.length) {
      const itens = classesChd.slice(0, 8).map((c) => ({
        rotulo: c.rotulo || c.forma || `Classe ${c.id}`,
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
  cartaoKpi("kpiRedesSeguidores", {
    codigo: "K-10",
    valor: new Intl.NumberFormat("pt-BR").format(Number(proprias.seguidores ?? 0)),
  });
  cartaoKpi("kpiRedesEngajamento", {
    codigo: "K-11",
    valor: `${Number(proprias.engajamento_7d ?? 0).toFixed(2)}%`,
  });
  cartaoKpi("kpiRedesComentarios", {
    codigo: "K-12",
    valor: String(Number(proprias.comentarios?.total ?? 0)),
  });
  cartaoKpi("kpiRedesResposta", {
    codigo: "K-27",
    valor: `${Math.round(Number(proprias.taxa_resposta ?? 0))}%`,
  });

  const container = document.getElementById("redesContas");
  if (container) {
    const conectadas = proprias.conectadas || [];
    container.innerHTML = conectadas.length
      ? conectadas
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
          .join("")
      : `<p class="grafico-leitura">Nenhuma conta institucional conectada ainda. A Secom pode conectar a Página e o Instagram da Casa na tela de Sistema.</p>`;
  }

  renderizarImagensValor(dados);
}

/* ---- Imagens (também no Valor) ---- */
function renderizarImagensValor(dados) {
  const imagens = dados.imagens || {};
  const kpis = imagens.kpis || {};
  const container = document.getElementById("imagensKpis");
  if (container) {
    container.innerHTML = `
      <div class="card kpi"><div class="kpi-cabecalho"><span class="kpi-rotulo">Posts com imagem analisada</span></div><span class="kpi-valor">${Number(kpis.k70_postos_com_imagem ?? 0)}</span></div>
      <div class="card kpi"><div class="kpi-cabecalho"><span class="kpi-rotulo">Cards com texto</span></div><span class="kpi-valor">${Math.round(Number(kpis.k72_cards_com_texto ?? 0) * 100)}%</span></div>
      <div class="card kpi"><div class="kpi-cabecalho"><span class="kpi-rotulo">Peças com promoção pessoal</span></div><span class="kpi-valor">${Number(kpis.k75_alertas_vindos_de_imagem ?? 0)}</span></div>
      <div class="card kpi"><div class="kpi-cabecalho"><span class="kpi-rotulo">Imagens recicladas</span></div><span class="kpi-valor">${Number(kpis.k74_imagens_recicladas ?? 0)}</span></div>
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
  cartaoKpi("kpiConfRiscos", {
    codigo: "K-21",
    valor: String(Number(dados.compliance?.total ?? 0)),
  });
  cartaoKpi("kpiConfPromocao", {
    codigo: "K-45",
    valor: String(Number(dados.imagens?.kpis?.k75_alertas_vindos_de_imagem ?? 0)),
  });
  cartaoKpi("kpiConfAnuncios", {
    codigo: "K-22",
    valor: String(Number(dados.anuncios_politicos?.anuncios_ativos ?? 0)),
  });
  cartaoKpi("kpiConfVedacoes", {
    codigo: "K-46",
    valor: dados.dias_ate_vedacoes !== undefined ? String(dados.dias_ate_vedacoes) : "–",
  });
}

/* ---- V9 / Tendências ---- */
function renderizarTendencias(dados) {
  const tend = dados.tendencias || {};
  cartaoKpi("kpiTendInteresse", {
    codigo: "K-30",
    valor: String(Number(tend.interesse_busca?.media ?? 0).toFixed(0)),
  });
  cartaoKpi("kpiTendPico", {
    codigo: "K-32",
    valor: tend.pico?.ativo ? "Sim" : "Não",
    sufixo: tend.pico?.fator ? `${Number(tend.pico.fator).toFixed(1)}× a média` : "",
  });
  cartaoKpi("kpiTendProjecao", {
    codigo: "K-33",
    valor: dados.previsao?.mencoes?.previsao?.length
      ? String(dados.previsao.mencoes.previsao.length)
      : "–",
  });
  cartaoKpi("kpiTendCrise", {
    codigo: "K-28",
    valor: dados.crise?.ativo ? "Alerta" : "Normal",
    sufixo: dados.crise?.mensagem || "",
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
  if (canvas) {
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
  const porDia = dados.por_dia || dados.dias || {};
  const dias = Object.keys(porDia);
  return [
    { datas: dias, positivos: dias.map((d) => Number(porDia[d]?.positivo ?? 0)) },
    { datas: dias, neutros: dias.map((d) => Number(porDia[d]?.neutro ?? 0)) },
    { datas: dias, negativos: dias.map((d) => Number(porDia[d]?.negativo ?? 0)) },
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
      renderizarClipping(estado.dados);
    });
  });
}

export default { carregar, renderizar, redimensionar };
