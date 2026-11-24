/* ==========================================================================
   Camada DSM — radar de propaganda pública, alertas acionáveis, menções/
   porta-vozes e cobertura/SLA.

   Consome as coleções publicadas pelo backend:
     radares/<escopo>    → radar de propaganda pública/institucional
     alertas/<escopo>    → alertas acionáveis (negativa direta, compliance…)
     cobertura/<escopo>  → SLA, cobertura por veículo/tier e fontes ausentes
     newsletters/<escopo>→ newsletter consolidada (HTML + texto WhatsApp)
   ========================================================================== */

import * as charts from "./charts.js";

const $ = (id) => document.getElementById(id);

export const estadoDsm = {
  radar: null,
  alertas: null,
  cobertura: null,
  newsletter: null,
  desinscrever: [],
  janela: "30d",
};

const JANELAS = ["hoje", "7d", "15d", "30d"];

const CORES_MENCAO = {
  direta: "#f59e0b",
  indireta: "#3b82f6",
  indeterminada: "#64748b",
};

const CORES_NIVEL = {
  critico: "#ef4444",
  alto: "#f59e0b",
  atencao: "#0ea5e9",
  info: "#64748b",
};

/* ---------- utilidades ---------- */

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function fmtNumero(n) {
  return new Intl.NumberFormat("pt-BR").format(Math.round(n || 0));
}

function fmtValor(n) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

function fmtData(v) {
  if (!v) return "–";
  const d = v.toDate ? v.toDate() : new Date(v);
  if (isNaN(d)) return "–";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(d);
}

/** Chave do escopo selecionado no painel (agente > cidade do órgão). */
export function chaveEscopoDsm(estado) {
  if (estado.parlamentar) return `agente-${estado.parlamentar}`;
  if (estado.orgaoInfo) return `cidade-${estado.orgaoInfo.cidadeDoc}`;
  return "";
}

/* ---------- carga dos dados ---------- */

export async function carregarCamadaDsm(db, chave, firestore) {
  estadoDsm.desinscrever.forEach((fn) => fn());
  estadoDsm.desinscrever = [];
  estadoDsm.radar = null;
  estadoDsm.alertas = null;
  estadoDsm.cobertura = null;
  estadoDsm.newsletter = null;
  if (!chave) {
    renderizarCamadaDsm();
    return;
  }

  // O módulo do Firestore é injetado pelo app (cada projeto usa uma versão
  // do SDK diferente): evita carregar duas instâncias do Firebase.
  let modulo = firestore;
  if (!modulo) {
    modulo = await import(
      "https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js"
    );
  }
  const { doc, onSnapshot } = modulo;

  const pares = [
    ["radares", (snap) => (estadoDsm.radar = snap.exists() ? snap.data() : null)],
    ["alertas", (snap) => (estadoDsm.alertas = snap.exists() ? snap.data() : null)],
    ["cobertura", (snap) => (estadoDsm.cobertura = snap.exists() ? snap.data() : null)],
    ["newsletters", (snap) => (estadoDsm.newsletter = snap.exists() ? snap.data() : null)],
  ];

  pares.forEach(([colecao, aoReceber]) => {
    estadoDsm.desinscrever.push(
      onSnapshot(
        doc(db, colecao, chave),
        (snap) => {
          aoReceber(snap);
          renderizarCamadaDsm();
        },
        (erro) => {
          // Ajuda a diagnosticar permissao no console do navegador.
          console.warn(
            `[DSM] sem acesso a ${colecao}/${chave}:`,
            erro?.code || erro?.message || erro
          );
        }
      )
    );
  });
}

/* ---------- render ---------- */

function janelaAtiva() {
  const periodo = estadoDsm.janela;
  return `periodo-${periodo}`;
}

function bloco(doc, chave) {
  if (!doc) return null;
  // Degrada para janelas mais largas quando a selecionada está vazia
  const ordem = [chave, "periodo-30d", "periodo-15d", "periodo-7d", "periodo-hoje", "periodo-todas"];
  const temConteudo = (b) =>
    !!b &&
    ((b.radar?.itens || []).length > 0 ||
      (b.alertas?.itens || []).length > 0 ||
      (b.cobertura?.total || 0) > 0 ||
      (b.mencoes?.total || 0) > 0);
  for (const chaveAlternativa of ordem) {
    const candidato = doc[chaveAlternativa];
    if (candidato && temConteudo(candidato)) return candidato;
  }
  return doc[chave] || doc[ordem[ordem.length - 1]] || null;
}

export function definirJanelaDsm(periodo) {
  if (periodo && JANELAS.includes(periodo)) {
    estadoDsm.janela = periodo;
    renderizarCamadaDsm();
  }
}

export function renderizarCamadaDsm() {
  renderizarRadar();
  renderizarAlertas();
  renderizarMencoes();
  renderizarCobertura();
  renderizarBotaoNewsletter();
}

function renderizarRadar() {
  const corpo = $("dsmRadarCorpo");
  const resumo = $("dsmRadarResumo");
  if (!corpo || !resumo) return;

  const blocoRadar = bloco(estadoDsm.radar, janelaAtiva());
  const itens = (blocoRadar?.radar?.itens || []).filter((i) =>
    i.classe === "propaganda_publica" || i.classe === "publicacao_oficial");
  const info = blocoRadar?.radar?.resumo || {};

  if (!itens.length) {
    resumo.innerHTML = "";
    corpo.innerHTML =
      '<tr><td colspan="5" class="vazio">Nenhuma propaganda pública detectada no período.</td></tr>';
    return;
  }

  resumo.innerHTML = [
    ["Publicações", fmtNumero(info.total_propaganda || itens.length)],
    ["% do clipping", `${info.pct_propaganda ?? 0}%`],
    ["Valor estimado", fmtValor(info.valor_estimado)],
    ["Com símbolos", fmtNumero(info.com_simbolos_publicos || 0)],
  ]
    .map(([rotulo, valor]) => `<div class="dsm-kpi"><span>${rotulo}</span><strong>${valor}</strong></div>`)
    .join("");

  corpo.innerHTML = itens
    .slice(0, 40)
    .map(
      (item) => `
      <tr>
        <td>${esc((item.titulo || "").slice(0, 140))}</td>
        <td>${esc(item.orgao || "n/i")}</td>
        <td>${esc(item.tipo || "n/i")}</td>
        <td class="num">${fmtValor(item.valor_avpe || item.valor_estimado)}</td>
        <td>${
          item.simbolos_publicos
            ? '<span class="dsm-chip dsm-chip-alerta">Símbolo público</span>'
            : '<span class="dsm-chip">ok</span>'
        }</td>
        <td>${item.url ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">abrir</a>` : ""}</td>
      </tr>`
    )
    .join("");
}

function renderizarAlertas() {
  const lista = $("dsmAlertasLista");
  if (!lista) return;

  const blocoAlertas = bloco(estadoDsm.alertas, janelaAtiva());
  const alertas = blocoAlertas?.alertas?.itens || [];

  if (!alertas.length) {
    lista.innerHTML = '<p class="dsm-vazio">Nenhum alerta crítico no período.</p>';
    return;
  }

  lista.innerHTML = alertas
    .slice(0, 25)
    .map(
      (alerta) => `
      <div class="dsm-alerta dsm-alerta-${esc(alerta.nivel || "info")}">
        <div class="dsm-alerta-topo">
          <span class="dsm-chip" style="border-color:${CORES_NIVEL[alerta.nivel] || "#64748b"}">
            ${esc(alerta.nivel || "info")}
          </span>
          <strong>${esc(alerta.titulo || "")}</strong>
        </div>
        <div class="dsm-alerta-detalhe">${esc((alerta.detalhe || "").slice(0, 220))}</div>
        <div class="dsm-alerta-rodape">
          ${esc(alerta.veiculo || "fonte n/i")} · ${fmtData(alerta.data_publicacao)} ·
          ${fmtValor(alerta.valor_estimado)}
          ${
            alerta.url
              ? ` · <a href="${esc(alerta.url)}" target="_blank" rel="noopener">abrir</a>`
              : ""
          }
        </div>
        ${
          alerta.acao_sugerida
            ? `<div class="dsm-alerta-acao">→ ${esc(alerta.acao_sugerida)}</div>`
            : ""
        }
      </div>`
    )
    .join("");
}

function renderizarMencoes() {
  const canvas = $("graficoMencoes");
  const portas = $("dsmPortaVozes");
  const blocoMencoes = bloco(estadoDsm.radar, janelaAtiva());
  const resumo = blocoMencoes?.mencoes || {};

  if (canvas) {
    const dados = {
      direta: resumo.direta || 0,
      indireta: resumo.indireta || 0,
      indeterminada: resumo.indeterminada || 0,
    };
    charts.criarGraficoDonut(
      "graficoMencoes",
      dados,
      Object.keys(dados).map((k) => CORES_MENCAO[k]),
      false
    );
  }

  if (!portas) return;
  const itens = (blocoMencoes?.radar?.itens || []).slice(0, 60);
  const encontrados = new Map();
  itens.forEach((item) => {
    (item.porta_vozes || []).forEach((pv) => {
      if (!encontrados.has(pv)) encontrados.set(pv, 0);
      encontrados.set(pv, encontrados.get(pv) + 1);
    });
  });
  if (!encontrados.size) {
    portas.innerHTML = '<p class="dsm-vazio">Nenhum porta-voz identificado.</p>';
    return;
  }
  const top = [...encontrados.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  portas.innerHTML = top
    .map(
      ([nome, qtd]) =>
        `<span class="dsm-chip dsm-chip-porta-voz">${esc(nome)} <strong>${qtd}</strong></span>`
    )
    .join("");
}

function renderizarCobertura() {
  const resumo = $("dsmCoberturaResumo");
  const faltantes = $("dsmCoberturaFaltantes");
  if (!resumo) return;

  const blocoCobertura = bloco(estadoDsm.cobertura, janelaAtiva());
  const cob = blocoCobertura?.cobertura || {};

  resumo.innerHTML = [
    ["SLA médio", `${fmtNumero(cob.sla_min_medio)} min`],
    ["SLA p95", `${fmtNumero(cob.sla_min_p95)} min`],
    ["Cobertura", `${cob.pct_cobertura ?? 0}%`],
    ["Veículos", fmtNumero(cob.com_veiculo || 0)],
    ["Sem data", fmtNumero(cob.sem_data_publicacao || 0)],
  ]
    .map(([rotulo, valor]) => `<div class="dsm-kpi"><span>${rotulo}</span><strong>${valor}</strong></div>`)
    .join("");

  if (!faltantes) return;
  const ausentes = cob.veiculos_ausentes || [];
  if (!ausentes.length) {
    faltantes.innerHTML = '<span class="dsm-chip dsm-chip-ok">Todos os veículos esperados foram coletados</span>';
    return;
  }
  faltantes.innerHTML =
    '<span class="dsm-chip dsm-chip-alerta">Veículos sem coleta: </span>' +
    ausentes.map((v) => `<span class="dsm-chip">${esc(v)}</span>`).join("");
}

function renderizarBotaoNewsletter() {
  const botao = $("btnNewsletterDsm");
  if (!botao) return;
  const blocoNl = bloco(estadoDsm.newsletter, janelaAtiva());
  const total = blocoNl?.total || 0;
  botao.textContent = total ? `Newsletter (${total})` : "Newsletter";
  botao.disabled = !total;
}

/** Abre a newsletter gerada (HTML) em nova aba. Devolve "ok", "vazio" ou "bloqueado". */
export function abrirNewsletter() {
  const blocoNl = bloco(estadoDsm.newsletter, janelaAtiva());
  if (!blocoNl?.html) return "vazio";
  const janela = window.open("", "_blank");
  if (!janela) return "bloqueado";
  janela.document.open();
  janela.document.write(blocoNl.html);
  janela.document.close();
  return "ok";
}

/** Copia o texto da newsletter (canal WhatsApp/Telegram). */
export async function copiarNewsletter() {
  const blocoNl = bloco(estadoDsm.newsletter, janelaAtiva());
  if (!blocoNl?.texto) return false;
  try {
    await navigator.clipboard.writeText(blocoNl.texto);
    return true;
  } catch (e) {
    console.error("Falha ao copiar newsletter", e);
    return false;
  }
}
