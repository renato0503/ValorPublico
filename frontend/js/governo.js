/**
 * Telas do Governo de Mato Grosso (V12) e do Governador (V13) — ValorPublico.
 *
 * Dados (agregados, nunca os brutos):
 *   metricas_por_casa/governo-mt          -> o Governo do Estado como um todo
 *   metricas_por_secretaria/<slug>       -> uma pasta por secretaria/autarquia
 *   metricas_por_agente/governador-...    -> o governador
 *   metricas_por_agente/interino-...      -> o governador interino
 *
 * As telas seguem o padrão do plano 17: pergunta no topo, cartao de KPI com ⓘ,
 * grafico com leitura e tabela com linha de explicacao.
 */

import { cartaoKpi, cartaoGrafico, escapar } from "./componentes.js";
import { explicacao, registrarExplicacoes } from "./explicacoes.js";
import { barrasHorizontais, linhasSentimento } from "./graficos.js";

const estado = {
  db: null,
  casa: null,
  secretarias: [],
  governador: null,
  interino: null,
  pastaSelecionada: "",
  ativo: false,
};

const graficos = new Map();

const ROTULO_PASTA = {
  "casa-civil": "Casa Civil",
  "controladoria-geral": "Controladoria-Geral do Estado",
  "escritorio-representacao-brasilia": "Escritório de Representação em Brasília",
  "procuradoria-geral": "Procuradoria-Geral do Estado",
  "agricultura-familiar": "Agricultura Familiar",
  "cultura-esporte-lazer": "Cultura, Esporte e Lazer",
  "ciencia-tecnologia-inovacao": "Ciência, Tecnologia e Inovação",
  "comunicacao": "Comunicação",
  "desenvolvimento-economico": "Desenvolvimento Econômico",
  "educacao": "Educação",
  "fazenda": "Fazenda",
  "justica": "Justiça",
  "meio-ambiente": "Meio Ambiente",
  "planejamento-gestao": "Planejamento e Gestão",
  "saude": "Saúde",
  "seguranca-publica": "Segurança Pública",
  "assistencia-social-cidadania": "Assistência Social e Cidadania",
  "infraestrutura-logistica": "Infraestrutura e Logística",
  detran: "Detran",
  der: "DER",
  intermat: "Intermat",
  ermat: "ERMAT",
  "mt-gas": "MT Gás",
};

function slug(sigla) {
  return String(sigla || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Liga/desliga as telas do Governo (só a frente Governo de MT as usa). */
export function definirAtivo(ativo) {
  const novo = !!ativo;
  if (estado.ativo === novo) return;
  estado.ativo = novo;
  if (!novo) {
    estado.casa = null;
    estado.secretarias = [];
    estado.governador = null;
    estado.interino = null;
    estado.pastaSelecionada = "";
  }
  renderizar();
}

/** Carrega os agregados do Governo (somente quando a frente é governo-mt). */
export async function carregar(db) {
  estado.db = db;
  if (!estado.ativo) return;
  try {
    const { doc, getDoc, getDocs, collection } = await sdk();
    const snapCasa = await getDoc(doc(db, "metricas_por_casa", "governo-mt"));
    estado.casa = snapCasa.exists() ? snapCasa.data() : null;

    const snapGov = await getDoc(
      doc(db, "metricas_por_agente", "governador-otaviano-pivetta")
    );
    estado.governador = snapGov.exists() ? snapGov.data() : null;

    const snapInt = await getDoc(doc(db, "metricas_por_agente", "interino-max-russi"));
    estado.interino = snapInt.exists() ? snapInt.data() : null;

    const snapPastas = await getDocs(collection(db, "metricas_por_secretaria"));
    estado.secretarias = snapPastas.docs
      .map((d) => ({ id: d.id, ...d.data() }))
      .sort((a, b) => (b.total_clippings || 0) - (a.total_clippings || 0));
  } catch (erro) {
    console.warn("[Governo] falha ao carregar agregados:", erro?.message || erro);
  }
  renderizar();
}

async function sdk() {
  try {
    return await import("firebase/firestore");
  } catch {
    return await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
  }
}

/** Desenha as duas telas (a que estiver ativa). */
export function renderizar() {
  renderizarGoverno();
  renderizarGovernador();
  registrarExplicacoes();
}

function _saldo(dados) {
  const dist = dados?.distribuicao_sentimento || {};
  const total = (dist.positivo || 0) + (dist.neutro || 0) + (dist.negativo || 0);
  if (!total) return 0;
  return Math.round(((dist.positivo || 0) - (dist.negativo || 0)) / total * 100);
}

function _numero(n) {
  return new Intl.NumberFormat("pt-BR").format(Math.round(n || 0));
}

/** Preenche os cartoes com um estado vazio explicativo (plano 17 §2.7). */
function _estadoVazio(ids, mensagem) {
  ids.forEach((id) => {
    cartaoKpi(id, { codigo: "K-01", valor: "–", sufixo: "sem dados" });
  });
  const alvo = document.getElementById("govGradePastas");
  if (alvo && !alvo.innerHTML.trim()) {
    alvo.innerHTML = `<p class="gov-vazio">${escapar(mensagem)}</p>`;
  }
}

function _dinheiro(n) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

/* ------------------------------------------------------------------ */
/* V12 — Governo de MT                                                */
/* ------------------------------------------------------------------ */
function renderizarGoverno() {
  const casa = estado.casa;
  if (!casa) {
    _estadoVazio(
      [
        "kpiGovMencoes",
        "kpiGovSaldo",
        "kpiGovValor",
        "kpiGovVeiculos",
        "kpiGovAlertas",
        "kpiGovPastas",
      ],
      "Ainda não há dados do Governo do Estado neste escopo. A coleta roda uma vez por dia; "
        + "a primeira carga aparece no dia seguinte."
    );
    return;
  }

  cartaoKpi("kpiGovMencoes", {
    codigo: "K-01",
    valor: _numero(casa.total_clippings),
    sufixo: "notícias sobre o Governo do Estado",
  });
  cartaoKpi("kpiGovSaldo", {
    codigo: "K-03",
    valor: String(_saldo(casa)),
    sufixo: "de −100 (crítica) a +100 (favorável)",
  });
  cartaoKpi("kpiGovValor", {
    codigo: "K-08",
    valor: _dinheiro(casa.valoracao_total),
    sufixo: "valor estimado da mídia",
    valorMidia: true,
  });
  cartaoKpi("kpiGovVeiculos", {
    codigo: "K-61",
    valor: _numero(casa.total_veiculos),
    sufixo: "veículos que publicaram",
  });
  cartaoKpi("kpiGovAlertas", {
    codigo: "K-20",
    valor: _numero(casa.alertas?.total),
    sufixo: "alertas que pedem atenção",
  });
  cartaoKpi("kpiGovPastas", {
    codigo: "K-43",
    valor: _numero(estado.secretarias.length),
    sufixo: "secretarias e autarquias com cobertura",
  });

  // Serie de sentimento (G-03)
  const canvas = document.getElementById("graficoGovSentimento");
  if (canvas) {
    const serie = _serieSentimento(casa);
    const grafico = linhasSentimento(canvas, serie, {});
    if (grafico) graficos.set("graficoGovSentimento", grafico);
  }

  // Ranking de secretarias (G-33)
  const canvas2 = document.getElementById("graficoGovPastas");
  if (canvas2) {
    const itens = estado.secretarias
      .filter((p) => !estado.pastaSelecionada || p.id === estado.pastaSelecionada)
      .slice(0, 12)
      .map((p) => ({
        rotulo: `${p.pasta?.sigla || p.id}`,
        valor: p.total_clippings || 0,
      }));
    const grafico2 = barrasHorizontais(canvas2, itens);
    if (grafico2) graficos.set("graficoGovPastas", grafico2);
  }

  // Grade de secretarias
  const grade = document.getElementById("govGradePastas");
  if (grade) {
    grade.innerHTML = estado.secretarias
      .map((p) => {
        const sigla = p.pasta?.sigla || p.id;
        const nome = p.pasta?.nome || ROTULO_PASTA[p.id] || sigla;
        const titular = p.pasta?.titular || "";
        const saldo = _saldo(p);
        return `<button class="gov-pasta" type="button" data-pasta="${escapar(p.id)}">
            <span class="gov-pasta-sigla">${escapar(sigla)}</span>
            <span class="gov-pasta-nome">${escapar(nome)}</span>
            ${titular ? `<span class="gov-pasta-titular">${escapar(titular)}</span>` : ""}
            <span class="gov-pasta-num"><b>${_numero(p.total_clippings)}</b> notícias</span>
            <span class="gov-pasta-saldo ${saldo < 0 ? "negativo" : "positivo"}">saldo ${saldo}</span>
          </button>`;
      })
      .join("");
  }

  // Tabela de noticias recentes
  const corpo = document.getElementById("govTabelaNoticias");
  if (corpo) {
    const recentes = (casa.noticias_recentes || []).slice(0, 25);
    const explicacaoT = explicacao("T-15");
    corpo.innerHTML = recentes.length
      ? recentes
          .map(
            (n) => `<tr>
              <td>${escapar((n.data_publicacao || n.data || "").toString().slice(0, 10))}</td>
              <td>${escapar(n.titulo || "")}</td>
              <td>${escapar(n.veiculo || n.autor || "—")}</td>
              <td>${escapar(n.tema || "—")}</td>
              <td>${n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">abrir</a>` : "—"}</td>
            </tr>`
          )
          .join("")
      : `<tr><td colspan="5">${explicacaoT ? escapar(explicacaoT.oQueE) : "Sem notícias carregadas."}</td></tr>`;
  }
}

function _serieSentimento(dados) {
  const serie = dados.serie_sentimento || dados.serie || {};
  const dias = Object.keys(serie).sort();
  const acc = { positivo: [], neutro: [], negativo: [] };
  for (const dia of dias) {
    const item = serie[dia] || {};
    acc.positivo.push(Number(item.positivo || 0));
    acc.neutro.push(Number(item.neutro || 0));
    acc.negativo.push(Number(item.negativo || 0));
  }
  return [{ datas: dias, ...acc }];
}

/* ------------------------------------------------------------------ */
/* V13 — Governador                                                    */
/* ------------------------------------------------------------------ */
function renderizarGovernador() {
  const alvo = document.getElementById("tela-governador");
  if (!alvo || !estado.governador) return;
  const g = estado.governador;

  cartaoKpi("kpiGovMencoesGovernador", {
    codigo: "K-01",
    valor: _numero(g.total_clippings),
    sufixo: "notícias que citam o governador",
  });
  cartaoKpi("kpiGovSaldoGovernador", {
    codigo: "K-03",
    valor: String(_saldo(g)),
    sufixo: "saldo de opinião",
  });
  cartaoKpi("kpiGovValorGovernador", {
    codigo: "K-08",
    valor: _dinheiro(g.valoracao_total),
    sufixo: "valor estimado da mídia",
    valorMidia: true,
  });
  cartaoKpi("kpiGovCrise", {
    codigo: "K-28",
    valor: "Normal",
    sufixo: "nenhuma crise acima do normal",
  });

  const canvas = document.getElementById("graficoGovGovernador");
  if (canvas) {
    const grafico = linhasSentimento(canvas, _serieSentimento(g), {});
    if (grafico) graficos.set("graficoGovGovernador", grafico);
  }

  const corpo = document.getElementById("govTabelaGovernador");
  if (corpo) {
    const recentes = (g.noticias_recentes || []).slice(0, 25);
    corpo.innerHTML = recentes.length
      ? recentes
          .map(
            (n) => `<tr>
              <td>${escapar((n.data_publicacao || n.data || "").toString().slice(0, 10))}</td>
              <td>${escapar(n.titulo || "")}</td>
              <td>${escapar(n.veiculo || n.autor || "—")}</td>
              <td>${n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">abrir</a>` : "—"}</td>
            </tr>`
          )
          .join("")
      : '<tr><td colspan="4">Sem notícias carregadas para o governador.</td></tr>';
  }

  const interino = document.getElementById("govInterino");
  if (interino) {
    const i = estado.interino;
    interino.innerHTML = i
      ? `<div class="gov-aviso"><b>${escapar(i.total_clippings || 0)}</b> notícias citaram o governador interino
         <span class="gov-selo">cargo por ausência</span></div>
         <ul class="gov-lista">${(i.noticias_recentes || [])
           .slice(0, 8)
           .map(
             (n) =>
               `<li><span class="gov-data">${escapar(
                 (n.data_publicacao || n.data || "").toString().slice(0, 10)
               )}</span> ${escapar(n.titulo || "")}</li>`
           )
           .join("")}</ul>`
      : '<p class="gov-vazio">Sem dados do período em que assumiu interinamente.</p>';
  }
}

/** Injeta os agregados direto (teste de front e producao sem Firestore). */
export const __setDados = definirDados;

export function definirDados(dados) {
  estado.casa = dados?.casa || null;
  estado.secretarias = dados?.secretarias || [];
  estado.governador = dados?.governador || null;
  estado.interino = dados?.interino || null;
  renderizar();
}

/** Filtro por pasta (usado nos cliques da grade). */
export function filtrarPasta(slugPasta) {
  estado.pastaSelecionada = slugPasta || "";
  renderizar();
}

/** Redimensiona os graficos das telas do Governo. */
export function redimensionar() {
  graficos.forEach((g) => {
    try {
      g.resize();
    } catch {
      /* descartado */
    }
  });
}

