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
import { barrasEmpilhadas, barrasHorizontais, corTema, linhasSentimento } from "./graficos.js";
import * as clippingGoverno from "./clipping-governo.js";

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
  renderizarMunicipios(casa);
}

/* ------------------------------------------------------------------ */
/* Notícias por município (plano 22)                                   */
/* ------------------------------------------------------------------ */

let mapaRegistrado = null; // Promise do GeoJSON de MT (IBGE)

function _registrarMapa() {
  if (!mapaRegistrado) {
    mapaRegistrado = fetch("assets/geo/mt-municipios.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((geo) => {
        if (typeof echarts !== "undefined") echarts.registerMap("mt-municipios", geo);
        return true;
      })
      .catch((erro) => {
        console.warn("[Governo] mapa de MT indisponivel:", erro?.message || erro);
        mapaRegistrado = null;
        return false;
      });
  }
  return mapaRegistrado;
}

function _siglaSelecionada() {
  if (!estado.pastaSelecionada) return "";
  const pasta = estado.secretarias.find((p) => p.id === estado.pastaSelecionada);
  return pasta?.pasta?.sigla || "";
}

function _linkClipping(municipio) {
  const params = new URLSearchParams({ municipio });
  const sigla = _siglaSelecionada();
  if (sigla) params.set("secretaria", sigla);
  return `#/clipping?${params}`;
}

function _contagemMunicipios(casa) {
  const sigla = _siglaSelecionada();
  const doClipping = clippingGoverno.contagemPorMunicipio(sigla);
  if (doClipping) return doClipping;
  // reserva: total do agregado (Governo inteiro ou a pasta escolhida)
  const origem = sigla
    ? (estado.secretarias.find((p) => p.id === estado.pastaSelecionada) || {}).por_municipio
    : casa?.por_municipio;
  return new Map(Object.entries(origem || {}));
}

async function renderizarMunicipios(casa) {
  const lista = document.getElementById("govMunicipiosLista");
  const area = document.getElementById("graficoGovMunicipios");
  const leitura = document.getElementById("govMunicipiosLeitura");
  if (!lista || !area) return;

  const mapa = _contagemMunicipios(casa);
  const itens = [...mapa.entries()]
    .map(([nome, v]) => ({ nome, ...v }))
    .sort((a, b) => b.total - a.total || a.nome.localeCompare(b.nome));
  const sigla = _siglaSelecionada();

  if (!itens.length) {
    lista.innerHTML = "";
    const existente = typeof echarts !== "undefined" ? echarts.getInstanceByDom(area) : null;
    if (existente) existente.dispose();
    area.innerHTML = '<p class="gov-vazio">Nenhum município citado no período escolhido.</p>';
    if (leitura) leitura.textContent = "";
    return;
  }

  const maior = itens[0].total;
  lista.innerHTML = itens
    .slice(0, 12)
    .map((m) => {
      const pct = (v) => (m.total ? Math.round((v / m.total) * 100) : 0);
      return `<li>
        <a href="${_linkClipping(m.nome)}" class="gov-mun-item" title="Abrir o clipping de ${escapar(m.nome)}">
          <span class="gov-mun-nome">${escapar(m.nome)}</span>
          <span class="gov-mun-num">${_numero(m.total)}</span>
          <span class="gov-mun-barra" style="width:${Math.max(6, Math.round((m.total / maior) * 100))}%">
            <i class="pos" style="width:${pct(m.positivo)}%"></i><i class="neu" style="width:${pct(m.neutro)}%"></i><i class="neg" style="width:${pct(m.negativo)}%"></i>
          </span>
        </a>
      </li>`;
    })
    .join("");

  const totais = clippingGoverno.totaisDoPeriodo(sigla);
  if (leitura) {
    const topo = itens.slice(0, 3).map((m) => `${m.nome} (${_numero(m.total)})`).join(", ");
    leitura.textContent =
      `${_numero(itens.length)} municípios citados${sigla ? ` nas notícias da ${sigla}` : ""}. ` +
      `Os mais citados: ${topo}.` +
      (totais
        ? ` ${_numero(totais.comMunicipio)} de ${_numero(totais.total)} notícias do período citam algum município; as demais falam do Estado como um todo.`
        : "");
  }

  if (!(await _registrarMapa()) || typeof echarts === "undefined") {
    area.innerHTML = '<p class="gov-vazio">Mapa indisponível; veja a lista ao lado.</p>';
    return;
  }
  const existente = echarts.getInstanceByDom(area);
  if (existente) existente.dispose();
  area.innerHTML = "";
  const grafico = echarts.init(area, null, { renderer: "canvas" });
  const texto = corTema("--texto", "#1a2432");
  const borda = corTema("--border", "#e2dac9");
  const vazio = corTema("--bg-deep", "#ece5d6");
  // do menos ao mais citado; no tema escuro a rampa clareia (mais = mais claro)
  const escuro = document.documentElement.dataset.tema === "escuro";
  const rampa = escuro
    ? ["#1f3a5f", "#2c5689", "#3f74b0", "#6b98cf", "#a3c2e8", "#e3eefb"]
    : ["#c9d8ec", "#9db9dd", "#6f97c9", "#4677b3", "#24578f", "#0b2a52"];
  grafico.setOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: corTema("--card", "#fff"),
      borderColor: borda,
      textStyle: { color: texto, fontSize: 12 },
      formatter: (p) => {
        const m = mapa.get(p.name);
        if (!m) return `<b>${escapar(p.name)}</b><br>sem notícias no período`;
        return (
          `<b>${escapar(p.name)}</b><br>${_numero(m.total)} notícias<br>` +
          `positivas ${_numero(m.positivo)} · neutras ${_numero(m.neutro)} · negativas ${_numero(m.negativo)}`
        );
      },
    },
    // faixas: a capital concentra o noticiário e esconderia o interior numa escala linear
    visualMap: {
      type: "piecewise",
      left: 0,
      bottom: 0,
      itemWidth: 14,
      itemHeight: 10,
      textStyle: { color: texto, fontSize: 11 },
      pieces: [
        { min: 100, label: "100 ou mais", color: rampa[5] },
        { min: 25, max: 99, label: "25 a 99", color: rampa[4] },
        { min: 10, max: 24, label: "10 a 24", color: rampa[3] },
        { min: 5, max: 9, label: "5 a 9", color: rampa[2] },
        { min: 2, max: 4, label: "2 a 4", color: rampa[1] },
        { min: 1, max: 1, label: "1", color: rampa[0] },
      ],
      outOfRange: { color: vazio },
    },
    series: [
      {
        type: "map",
        map: "mt-municipios",
        roam: false,
        selectedMode: false,
        itemStyle: { areaColor: vazio, borderColor: borda, borderWidth: 0.5 },
        emphasis: {
          label: { show: true, color: texto, fontSize: 11 },
          itemStyle: { areaColor: corTema("--ambar", "#7a5314") },
        },
        label: { show: false },
        data: itens.map((m) => ({ name: m.nome, value: m.total })),
      },
    ],
  });
  grafico.on("click", (p) => {
    if (mapa.get(p.name)) window.location.hash = _linkClipping(p.name);
  });
  graficos.set("graficoGovMunicipios", grafico);
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
        ${total ? `<a class="btn-texto gov-sec-todas" href="#/clipping?secretaria=${encodeURIComponent(sigla)}">Ver todas as ${_numero(total)} notícias da ${escapar(sigla)} no clipping ›</a>` : ""}
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

/** O que os documentos em PDF precisam do Governo (recorte de período ativo). */
export function contextoDocumentos() {
  return {
    casa: _janela(estado.casa) || estado.casa,
    secretarias: (estado.secretarias || []).map((p) => ({ ...p, ...(_janela(p) || {}) })),
    governador: _janela(estado.governador) || estado.governador,
    interino: _janela(estado.interino) || estado.interino,
    pastaSelecionada: estado.pastaSelecionada,
  };
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
  document.getElementById("btnExportarSecretarias")?.addEventListener("click", exportarSecretarias);
  document.getElementById("btnExportarGovernador")?.addEventListener("click", exportarGovernador);
}







if (typeof document !== "undefined") {
  document.getElementById("filtroGovSecretaria")?.addEventListener("change", (evento) => {
    filtrarPasta(evento.target.value);
  });
  // o clipping completo chegou: o mapa passa a respeitar período e pasta
  document.addEventListener("clipping-governo:carregado", () => {
    if (estado.casa) renderizarMunicipios(_janela(estado.casa) || estado.casa);
  });
}
