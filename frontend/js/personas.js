/**
 * Personas do Governo de MT.
 *
 * - Mostra as 12 personas sintéticas (prévia do plano enquanto o treino local
 *   não publica os perfis no Firestore).
 * - Quando `personas` existir para o órgão, usa o perfil publicado.
 * - Chat online: usa `window.__PERSONAS_API_URL` (Cloud Run + DeepSeek + RAG).
 *   Sem a API publicada, mostra um estado honesto de "aguardando publicação".
 */

import { escapar } from "./componentes.js";
import { estadoAuth } from "./auth.js";

const PERSONAS_PREVIA = [
  { id: "servidor-estadual", rotulo: "Servidor público estadual", stakeholder: "servidor publico", tom: "cético e técnico" },
  { id: "professor-rede", rotulo: "Professor(a) da rede estadual", stakeholder: "educação", tom: "reivindicativo" },
  { id: "profissional-saude", rotulo: "Profissional de saúde (SES)", stakeholder: "saúde", tom: "exausto e pragmático" },
  { id: "produtor-rural", rotulo: "Produtor rural / agro", stakeholder: "agro", tom: "desconfiado" },
  { id: "empresario-industria", rotulo: "Empresário / indústria", stakeholder: "indústria", tom: "pragmático" },
  { id: "comerciante-mei", rotulo: "Comerciante / MEI", stakeholder: "comércio", tom: "cobrador" },
  { id: "trabalhador-informal", rotulo: "Trabalhador informal/autônomo", stakeholder: "trabalho informal", tom: "crítico" },
  { id: "jovem-estudante", rotulo: "Jovem / estudante", stakeholder: "juventude", tom: "esperançoso" },
  { id: "mae-beneficiaria", rotulo: "Mãe / beneficiária de programas", stakeholder: "assistência social", tom: "emocional" },
  { id: "seguranca-publica", rotulo: "Agente de segurança pública", stakeholder: "segurança", tom: "firme" },
  { id: "lideranca-comunitaria", rotulo: "Liderança comunitária / periferia", stakeholder: "comunidade", tom: "engajado" },
  { id: "formador-opiniao", rotulo: "Formador de opinião / imprensa", stakeholder: "imprensa", tom: "analítico" },
];

const estado = {
  db: null,
  orgao: null,
  personas: [],
  publicadas: new Set(),
};

function apiUrl() {
  return (
    window.__PERSONAS_API_URL ||
    document.querySelector('meta[name="personas-api"]')?.content ||
    ""
  );
}

async function sdk() {
  try {
    return await import("firebase/firestore");
  } catch {
    return await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
  }
}

/** Carrega perfis publicados (se existirem) e mantém a prévia das 12. */
export async function carregar(db, orgao) {
  estado.db = db;
  estado.orgao = orgao || null;
  estado.publicadas = new Set();
  if (!orgao || orgao.slug !== "governo-mt") {
    estado.personas = [];
    renderizar();
    return;
  }
  try {
    const { collection, getDocs, query, where } = await sdk();
    const snap = await getDocs(
      query(collection(db, "personas"), where("orgao", "==", orgao.slug))
    );
    const publicadas = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
    estado.publicadas = new Set(publicadas.map((p) => p.id));
    estado.personas = PERSONAS_PREVIA.map((base) => {
      const doc = publicadas.find((p) => p.id === base.id);
      return doc ? { ...base, ...doc, status: "treinada" } : base;
    });
  } catch {
    estado.personas = PERSONAS_PREVIA.slice();
  }
  renderizar();
}

function renderizar() {
  const grade = document.getElementById("personasGrade");
  if (!grade) return;
  const personas = estado.personas.length ? estado.personas : PERSONAS_PREVIA;
  const treinadas = estado.publicadas.size;
  const status = document.getElementById("personasStatus");
  if (status) {
    status.textContent = `${personas.length} personas sintéticas · ${treinadas} com perfil publicado`;
  }
  grade.innerHTML = personas
    .map(
      (p) => `<article class="persona-card">
        <span class="persona-status">${escapar(p.id)}</span>
        <h3>${escapar(p.rotulo)}</h3>
        <span class="persona-tom">${escapar(p.stakeholder || "stakeholder")}</span>
        <span class="persona-num">tom: ${escapar(p.tom || p.tom_base || "—")}</span>
        <span class="persona-num">${
          estado.publicadas.has(p.id)
            ? p.versao_rag || p.rag_version
              ? "base RAG publicada"
              : "perfil publicado (RAG pendente)"
            : "aguardando treino local"
        }</span>
      </article>`
    )
    .join("");

  const seletor = document.getElementById("chatPersona");
  if (seletor) {
    seletor.innerHTML = personas
      .map((p) => `<option value="${escapar(p.id)}">${escapar(p.rotulo)}</option>`)
      .join("");
  }
  const aviso = document.getElementById("chatAviso");
  if (aviso) {
    aviso.textContent = apiUrl()
      ? "Resposta sintética de uma persona. Não é pesquisa nem opinião de pessoa real."
      : "O chat será habilitado quando a base RAG das personas for publicada na nuvem.";
  }
  const botao = document.getElementById("btnPerguntar");
  if (botao) botao.disabled = !apiUrl();
}

function adicionarMensagem(texto, tipo = "eu", citacoes = []) {
  const caixa = document.getElementById("chatMensagens");
  if (!caixa) return;
  const div = document.createElement("div");
  div.className = `chat-msg ${tipo}`;
  div.innerHTML =
    escapar(texto).replace(/\n/g, "<br>") +
    (citacoes.length
      ? `<span class="chat-fonte">${citacoes
          .slice(0, 3)
          .map(
            (c) =>
              `${escapar(c.titulo || "fonte")}${
                c.url ? ` · <a href="${escapar(c.url)}" target="_blank" rel="noopener">abrir</a>` : ""
              }`
          )
          .join(" · ")}</span>`
      : "");
  caixa.appendChild(div);
  caixa.scrollTop = caixa.scrollHeight;
}

async function perguntar() {
  const campo = document.getElementById("chatPergunta");
  const seletor = document.getElementById("chatPersona");
  const pergunta = (campo?.value || "").trim();
  if (!pergunta) return;
  adicionarMensagem(pergunta, "eu");
  if (campo) campo.value = "";
  const url = apiUrl();
  if (!url) {
    adicionarMensagem(
      "O chat das personas entra depois que a base RAG for publicada na nuvem.",
      "persona"
    );
    return;
  }
  try {
    const token = await estadoAuth.usuario?.getIdToken?.();
    const resposta = await fetch(
      `${url.replace(/\/$/, "")}/v1/personas/${encodeURIComponent(
        seletor?.value || ""
      )}/perguntar`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ pergunta }),
      }
    );
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    const dados = await resposta.json();
    adicionarMensagem(dados.resposta || "Sem resposta.", "persona", dados.citacoes || []);
  } catch (erro) {
    adicionarMensagem(
      "Não foi possível falar com a persona agora. Tente novamente em instantes.",
      "persona"
    );
    console.warn("[Personas] falha no chat:", erro?.message || erro);
  }
}

if (typeof document !== "undefined") {
  document.getElementById("chatForm")?.addEventListener("submit", (evento) => {
    evento.preventDefault();
    perguntar();
  });
}

/** Injeção para testes. */
export function definirDados(personas, publicadas = []) {
  estado.personas = personas || [];
  estado.publicadas = new Set((publicadas || []).map((p) => p.id || p));
  renderizar();
}

export default { carregar, definirDados };
