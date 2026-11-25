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
import { barrasEmpilhadas, barrasHorizontais, linhasSentimento } from "./graficos.js";

const estado = {
  db: null,
  casa: null,
  secretarias: [],
  governador: null,
  interino: null,
  pastaSelecionada: "",
  ativo: false,
  periodo: "",
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

/** Aplica o recorte de período global aos agregados do Governo. */
export function definirPeriodo(periodo) {
  estado.periodo = periodo || "";
  if (estado.casa) renderizar();
}

function _janela(dados) {
  if (!dados || !estado.periodo) return dados;
  const recorte = dados.por_periodo?.[estado.periodo];
  return recorte ? { ...dados, ...recorte } : null;
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
  const casa = _janela(estado.casa);
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

  // Cobertura por secretaria e tom (G-33)
  const canvas2 = document.getElementById("graficoGovPastas");
  if (canvas2) {
    const itens = estado.secretarias
      .filter((p) => !estado.pastaSelecionada || p.id === estado.pastaSelecionada)
      .map((p) => {
        const dados = _janela(p) || {};
        const dist = dados.distribuicao_sentimento || p.distribuicao_sentimento || {};
        const positivo = Number(dist.positivo || 0);
        const neutro = Number(dist.neutro || 0);
        const negativo = Number(dist.negativo || 0);
        const total = positivo + neutro + negativo;
        return {
          rotulo: p.pasta?.sigla || p.id,
          positivo: total ? Math.round((positivo / total) * 100) : 0,
          neutro: total ? Math.round((neutro / total) * 100) : 0,
          negativo: total ? Math.round((negativo / total) * 100) : 0,
          total,
        };
      })
      .filter((item) => item.total > 0)
      .sort((a, b) => b.total - a.total)
      .slice(0, 14);
    const grafico2 = barrasEmpilhadas(canvas2, itens);
    if (grafico2) graficos.set("graficoGovPastas", grafico2);
  }

  // Menu de secretarias
  const seletorSecretaria = document.getElementById("filtroGovSecretaria");
  if (seletorSecretaria) {
    const atual = estado.pastaSelecionada;
    seletorSecretaria.innerHTML = '<option value="">Todas as secretarias</option>' +
      estado.secretarias
        .map((p) => {
          const nome = p.pasta?.nome || ROTULO_PASTA[p.id] || p.id;
          return `<option value="${escapar(p.id)}">${escapar(nome)}</option>`;
        })
        .join("");
    seletorSecretaria.value = atual;
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

  renderizarNoticiasPorSecretaria(casa);
}

function _dataNoticia(valor) {
  if (!valor) return "—";
  if (valor.toDate) return valor.toDate().toLocaleDateString("pt-BR");
  const d = new Date(valor);
  return isNaN(d) ? String(valor).slice(0, 10) : d.toLocaleDateString("pt-BR");
}

function renderizarNoticiasPorSecretaria(casa) {
  const alvo = document.getElementById("govNoticiasSecretarias");
  if (!alvo) return;
  const selecionada = estado.pastaSelecionada;
  const pastas = (estado.secretarias || []).filter(
    (p) => !selecionada || p.id === selecionada
  );
  const blocos = [];
  pastas.forEach((p, indice) => {
    const item = _janela(p) || {};
    const noticias = (item.noticias_recentes || []).slice(0, 8);
    const total = Number(item.total_clippings ?? p.total_clippings ?? 0);
    if (!noticias.length && !selecionada) return;
    const sigla = p.pasta?.sigla || p.id;
    const nome = p.pasta?.nome || ROTULO_PASTA[p.id] || sigla;
    blocos.push(
      `<details class="gov-sec-news"${indice === 0 || selecionada ? " open" : ""}>
        <summary>
          <span class="gov-sec-sigla">${escapar(sigla)}</span>
          <span class="gov-sec-nome">${escapar(nome)}</span>
          <span class="gov-sec-total">${_numero(total)} notícias</span>
        </summary>
        ${
          noticias.length
            ? `<ul>${noticias
                .map(
                  (n) => `<li>
                    <span class="gov-data">${escapar(_dataNoticia(n.data_publicacao || n.data))}</span>
                    ${n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">${escapar(n.titulo || "notícia")}</a>` : escapar(n.titulo || "notícia")}
                    <span class="gov-sec-veiculo">${escapar(n.veiculo || n.autor || "—")}</span>
                  </li>`
                )
                .join("")}</ul>`
            : '<p class="gov-vazio">Sem notícias nesta secretaria para o período.</p>'
        }
      </details>`
    );
  });
  if (blocos.length) {
    alvo.innerHTML = blocos.join("");
    return;
  }
  const recentes = (casa.noticias_recentes || []).slice(0, 10);
  alvo.innerHTML = recentes.length
    ? `<p class="grafico-leitura">Ainda sem notícias vinculadas a uma secretaria. Últimas do Governo:</p><ul class="gov-sec-lista">${recentes
        .map(
          (n) => `<li><span class="gov-data">${escapar(_dataNoticia(n.data_publicacao || n.data))}</span> ${
            n.url ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">${escapar(n.titulo || "notícia")}</a>` : escapar(n.titulo || "notícia")
          }</li>`
        )
        .join("")}</ul>`
    : '<p class="gov-vazio">Sem notícias por secretaria neste período.</p>';
}

function _serieSentimento(dados) {
  const serie = dados.serie_sentimento || dados.serie || {};
  const dias = Object.keys(serie).sort();
  return [
    {
      datas: dias,
      positivos: dias.map((d) => Number(serie[d]?.positivo ?? 0)),
    },
    {
      datas: dias,
      neutros: dias.map((d) => Number(serie[d]?.neutro ?? 0)),
    },
    {
      datas: dias,
      negativos: dias.map((d) => Number(serie[d]?.negativo ?? 0)),
    },
  ];
}

/* ------------------------------------------------------------------ */
/* V13 — Governador                                                    */
/* ------------------------------------------------------------------ */
function renderizarGovernador() {
  const alvo = document.getElementById("tela-governador");
  if (!alvo || !estado.governador) return;
  const g = _janela(estado.governador);
  if (!g) {
    cartaoKpi("kpiGovMencoesGovernador", { codigo: "K-01", semBase: true, motivo: "sem dados nesta janela" });
    cartaoKpi("kpiGovSaldoGovernador", { codigo: "K-03", semBase: true, motivo: "sem dados nesta janela" });
    cartaoKpi("kpiGovValorGovernador", { codigo: "K-08", semBase: true, motivo: "sem dados nesta janela" });
    cartaoKpi("kpiGovCrise", { codigo: "K-28", semBase: true, motivo: "sem dados nesta janela" });
    const corpo = document.getElementById("govTabelaGovernador");
    if (corpo) corpo.innerHTML = '<tr><td colspan="4">Sem notícias do governador nesta janela.</td></tr>';
    const interino = document.getElementById("govInterino");
    if (interino) interino.innerHTML = '<p class="gov-vazio">Sem dados nesta janela.</p>';
    return;
  }

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
    const i = _janela(estado.interino);
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

/* ------------------------------------------------------------------ */
/* Exportações CSV (Governo, secretarias e governador)                */
/* ------------------------------------------------------------------ */

function _csv(valor) {
  const texto = String(valor ?? "");
  return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

function _dataCsv(valor) {
  if (!valor) return "";
  if (valor.toDate) return valor.toDate().toISOString().slice(0, 10);
  const d = new Date(valor);
  return isNaN(d) ? String(valor).slice(0, 10) : d.toISOString().slice(0, 10);
}

function _baixarCsv(nome, linhas) {
  const csv = linhas.map((linha) => linha.map(_csv).join(";")).join("\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function _sufixoPeriodo() {
  return estado.periodo ? `-${estado.periodo}` : "";
}

function exportarGoverno() {
  const casa = _janela(estado.casa);
  if (!casa) return;
  const linhas = [
    ["indicador", "valor"],
    ["total_clippings", casa.total_clippings ?? 0],
    ["total_veiculos", casa.total_veiculos ?? 0],
    ["saldo_opiniao", _saldo(casa)],
    ["valoracao_total", casa.valoracao_total ?? 0],
    ["alertas_total", casa.alertas?.total ?? 0],
    [],
    ["data", "titulo", "veiculo", "sentimento", "url"],
  ];
  (casa.noticias_recentes || []).forEach((n) => {
    linhas.push([_dataCsv(n.data_publicacao), n.titulo || "", n.veiculo || "", n.sentimento || "", n.url || ""]);
  });
  _baixarCsv(`valorpublico-governo${_sufixoPeriodo()}.csv`, linhas);
}

function exportarSecretarias() {
  const linhas = [
    ["secretaria", "total_clippings", "saldo_opiniao", "valoracao_total", "veiculos"],
  ];
  (estado.secretarias || []).forEach((s) => {
    const item = _janela(s) || {};
    linhas.push([
      s.id,
      item.total_clippings ?? 0,
      _saldo(item),
      item.valoracao_total ?? 0,
      item.total_veiculos ?? 0,
    ]);
  });
  _baixarCsv(`valorpublico-secretarias${_sufixoPeriodo()}.csv`, linhas);
}

function exportarGovernador() {
  const g = _janela(estado.governador);
  const i = _janela(estado.interino);
  if (!g && !i) return;
  const linhas = [
    ["cargo", "total_clippings", "saldo_opiniao", "valoracao_total", "veiculos"],
    ["governador", g?.total_clippings ?? 0, _saldo(g || {}), g?.valoracao_total ?? 0, g?.total_veiculos ?? 0],
    ["interino", i?.total_clippings ?? 0, _saldo(i || {}), i?.valoracao_total ?? 0, i?.total_veiculos ?? 0],
    [],
    ["cargo", "data", "titulo", "veiculo", "sentimento", "url"],
  ];
  [["governador", g], ["interino", i]].forEach(([cargo, dados]) => {
    (dados?.noticias_recentes || []).forEach((n) => {
      linhas.push([cargo, _dataCsv(n.data_publicacao), n.titulo || "", n.veiculo || "", n.sentimento || "", n.url || ""]);
    });
  });
  _baixarCsv(`valorpublico-governador${_sufixoPeriodo()}.csv`, linhas);
}

if (typeof document !== "undefined") {
  document.getElementById("btnExportarGoverno")?.addEventListener("click", exportarGoverno);
  document.getElementById("btnBaixarPdfGoverno")?.addEventListener("click", () => {
    document.body.classList.add("print-governo");
    window.print();
    setTimeout(() => document.body.classList.remove("print-governo"), 300);
  });
  document.getElementById("btnExportarSecretarias")?.addEventListener("click", exportarSecretarias);
  document.getElementById("btnExportarGovernador")?.addEventListener("click", exportarGovernador);
}







if (typeof document !== "undefined") {
  document.getElementById("filtroGovSecretaria")?.addEventListener("change", (evento) => {
    filtrarPasta(evento.target.value);
  });
}
