/**
 * Recepção do discurso pelas personas (MiroFish / painel sintético).
 *
 * Lê `simulacao_semanal/{casa-<slug>}__{semana}` (últimas 4 semanas) e mostra:
 * adesão ± IC 90%, rejeição, emoção, comentário e frases de risco por persona.
 * Nunca lê dados de outra frente e nunca apresenta como pesquisa.
 */

import { cartaoKpi, escapar } from "./componentes.js";

const estado = {
  db: null,
  orgao: null,
  semana: "",
  dados: null,
};

function semanaISO(data = new Date()) {
  const d = new Date(Date.UTC(data.getFullYear(), data.getMonth(), data.getDate()));
  const dia = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dia);
  const inicio = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const semana = Math.ceil(((d - inicio) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(semana).padStart(2, "0")}`;
}

function semanasRecentes(n = 4) {
  const saida = [];
  const base = new Date();
  for (let i = 0; i < n; i++) {
    const d = new Date(base);
    d.setDate(d.getDate() - i * 7);
    saida.push(semanaISO(d));
  }
  return saida;
}

async function sdk() {
  try {
    return await import("firebase/firestore");
  } catch {
    return await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
  }
}

async function lerDoc(db, id) {
  try {
    const { doc, getDoc } = await sdk();
    const snap = await getDoc(doc(db, "simulacao_semanal", id));
    return snap.exists() ? snap.data() : null;
  } catch {
    return null;
  }
}

/** Carrega a simulação mais recente da Casa do órgão. */
export async function carregar(db, orgao) {
  estado.db = db;
  estado.orgao = orgao || null;
  estado.dados = null;
  estado.semana = "";
  if (!orgao || orgao.slug !== "governo-mt") {
    renderizar();
    return;
  }
  const escopo = `casa-${orgao.slug}`;
  for (const semana of semanasRecentes(4)) {
    const dados = await lerDoc(db, `${escopo}__${semana}`);
    if (dados) {
      estado.dados = dados;
      estado.semana = dados.semana || semana;
      break;
    }
  }
  renderizar();
}

function _media(personas, campo) {
  if (!personas.length) return 0;
  return personas.reduce((acc, p) => acc + Number(p[campo] || 0), 0) / personas.length;
}

function _numero(n, casas = 1) {
  return Number(n || 0).toFixed(casas);
}

export function renderizar() {
  const dados = estado.dados;
  const personas = Array.isArray(dados?.personas) ? dados.personas : [];

  cartaoKpi("simKpiPersonas", {
    codigo: "K-25",
    nome: "Personas na simulação",
    valor: dados ? String(personas.length || 12) : "—",
    sufixo: "personas sintéticas",
  });
  cartaoKpi("simKpiAdesao", {
    codigo: "K-03",
    nome: "Adesão média",
    valor: dados ? _numero(_media(personas, "adesao")) : "—",
    sufixo: "nota de 1 a 7",
  });
  cartaoKpi("simKpiRejeicao", {
    codigo: "K-20",
    nome: "Rejeição média",
    valor: dados ? `${Math.round(_media(personas, "rejeicao") * 100)}%` : "—",
    sufixo: "reações negativas",
  });
  cartaoKpi("simKpiPolarizacao", {
    codigo: "K-28",
    nome: "Polarização",
    valor: dados ? _numero(dados.polarizacao, 2) : "—",
    sufixo: "diferença entre personas",
  });

  const semana = document.getElementById("simSemana");
  if (semana) {
    semana.textContent = dados
      ? `Semana ${estado.semana} · método ${dados.metodo || "painel_n2"}`
      : "Simulação do Governo de MT";
  }

  const seletor = document.getElementById("simVariante");
  if (seletor) {
    const variantes = Array.isArray(dados?.variantes) ? dados.variantes : [];
    seletor.innerHTML = variantes.length
      ? variantes
          .map(
            (v) =>
              `<option value="${escapar(v.id || "")}">Variante ${escapar(
                v.id || ""
              )} · adesão ${_numero(v.adesao)}</option>`
          )
          .join("")
      : '<option value="">Sem variantes</option>';
    seletor.disabled = !variantes.length;
  }

  const grade = document.getElementById("simPersonas");
  if (!grade) return;
  if (!dados || !personas.length) {
    grade.innerHTML =
      '<p class="grafico-leitura">A simulação desta semana ainda não foi gerada. ' +
      "Ela roda no domingo, depois do discurso, com as 12 personas do Governo.</p>";
  } else {
    grade.innerHTML = personas
      .map((p) => {
        const ic = Array.isArray(p.adesao_ic90)
          ? `IC 90% ${_numero(p.adesao_ic90[0])}–${_numero(p.adesao_ic90[1])}`
          : "";
        return `<article class="persona-card">
          <span class="persona-status">${escapar(p.id || "persona")}</span>
          <h3>${escapar(p.rotulo || p.id || "Persona")}</h3>
          <span class="persona-tom">${escapar(p.emocao || "reação")}</span>
          <span class="persona-adesao">${_numero(p.adesao)}</span>
          <span class="persona-num">${escapar(ic)}</span>
          <span class="persona-rejeicao">rejeição ${Math.round(Number(p.rejeicao || 0) * 100)}%</span>
          ${p.comentario ? `<span class="persona-comentario">“${escapar(p.comentario)}”</span>` : ""}
          ${
            (p.frases_risco || []).length
              ? `<span class="persona-num">Risco: ${escapar((p.frases_risco || [])[0])}</span>`
              : ""
          }
        </article>`;
      })
      .join("");
  }

  const risco = document.getElementById("simFrasesRisco");
  if (risco) {
    const frases = Array.isArray(dados?.frases_risco) ? dados.frases_risco : [];
    risco.innerHTML = frases.length
      ? `<strong>Frases de risco</strong><ul>${frases
          .slice(0, 8)
          .map((f) => `<li>${escapar(f)}</li>`)
          .join("")}</ul>`
      : "";
  }
}

/** Injeção para testes. */
export function definirDados(dados) {
  estado.dados = dados || null;
  estado.semana = dados?.semana || "";
  renderizar();
}

export function redimensionar() {
  /* sem gráficos próprios nesta tela */
}

export default { carregar, renderizar, redimensionar, definirDados };
