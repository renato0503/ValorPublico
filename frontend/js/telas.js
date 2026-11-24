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
  linhaComPrevisao,
  linhasSentimento,
  quadrante,
  treemap,
} from "./graficos.js";

const estado = { db: null, dados: null, demandas: [], orgao: null };
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

export async function carregar(db) {
  estado.db = db;
  const escopo = escopoAtual();
  if (escopo.tipo === "nenhum") {
    estado.dados = null;
    estado.demandas = [];
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
  renderizar();
}

export function renderizar() {
  const dados = estado.dados || {};
  renderizarEdicao(dados);
  renderizarImagem(dados);
  renderizarOuvidoria(dados);
  renderizarSemana(dados);
  renderizarRedes(dados);
  renderizarConformidade(dados);
  renderizarTendencias(dados);
  registrarExplicacoes();
}

/* ---- V1 / Edição do dia ---- */
function renderizarEdicao(dados) {
  cartaoKpi("kpiEdicaoMatarias", {
    codigo: "K-01",
    valor: new Intl.NumberFormat("pt-BR").format(Number(dados.total_clippings ?? 0)),
  });
  cartaoKpi("kpiEdicaoSentimento", {
    codigo: "K-03",
    valor: Number(dados.saldo_opiniao ?? 0).toFixed(0),
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

/* ---- V3 / Imagem da Casa ---- */
function renderizarImagem(dados) {
  cartaoKpi("kpiImagemSaldo", {
    codigo: "K-03",
    valor: Number(dados.saldo_opiniao ?? 0).toFixed(0),
  });
  cartaoKpi("kpiImagemInstitucional", {
    codigo: "K-42",
    valor: Number(dados.imagem_institucional ?? 0).toFixed(0),
  });
  cartaoKpi("kpiImagemTier1", {
    codigo: "K-06",
    valor: `${Number(dados.pct_tier1 ?? 0).toFixed(0)}%`,
  });
  cartaoKpi("kpiImagemProjecao", {
    codigo: "K-33",
    valor: dados.previsao?.mencoes?.previsao?.length
      ? String(dados.previsao.mencoes.previsao.length)
      : "–",
    sufixo: "dias projetados (com margem)",
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
  const semanal = dados.relatorio_semanal || {};
  cartaoKpi("kpiSemanaVariedade", {
    codigo: "K-40",
    valor: Number(semanal.estatisticas?.variedade ?? 0).toFixed(2),
  });
  cartaoKpi("kpiSemanaSintonia", {
    codigo: "K-41",
    valor: Number(semanal.alinhamento ?? 0).toFixed(2),
  });
  cartaoKpi("kpiSemanaImagens", {
    codigo: "K-70",
    valor: String(dados.imagens?.kpis?.k70_postos_com_imagem ?? 0),
  });
  cartaoKpi("kpiSemanaEquidade", {
    codigo: "K-43",
    valor: Number(dados.equidade_visibilidade ?? 0).toFixed(2),
  });

  const canvas = document.getElementById("graficoSemanaClasses");
  if (canvas) {
    const mais = semanal.especificidades?.semana_vs_base?.mais || [];
    const menos = semanal.especificidades?.semana_vs_base?.menos || [];
    guardar("graficoSemanaClasses", barrasDivergentes(canvas, mais, menos));
  }
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

export default { carregar, renderizar, redimensionar };
