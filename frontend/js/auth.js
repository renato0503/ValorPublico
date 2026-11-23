/* ==========================================================================
   Autenticação e escopo do usuário (Firebase Auth + RBAC por agente).

   O painel continua funcionando em modo público (demo). Quando o operador
   habilita o Firebase Auth e desliga o modo público (documento
   `config_acesso/publico`), cada usuário autenticado passa a ver apenas os
   dados do próprio agente — o escopo é aplicado no cliente (filtros) E
   garantido no servidor (firestore.rules).
   ========================================================================== */

const $ = (id) => document.getElementById(id);

export const estadoAuth = {
  auth: null,
  usuario: null,
  perfil: null, // {uid, email, papel, agente_id, agente_ids}
  autenticado: false,
  desinscrever: null,
  carregando: true,
};

const CHAVE_SESSAO = "cerra_sessao";

/* ---------- carregamento do modulo Auth do SDK ---------- */

function urlAuth() {
  // Usa o mesmo SDK do app: AssessorPublico carrega o SDK por URL (9.22.0),
  // ValorPublico usa importmap (bare specifier).
  const temImportmap = !!document.querySelector('script[type="importmap"]');
  if (temImportmap) return import("firebase/auth");
  return import("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js");
}

/* ---------- sessao ---------- */

export async function iniciarAuth() {
  try {
    const { app } = await import("./firebase-init.js");
    const modulo = await urlAuth();
    estadoAuth.auth = modulo.getAuth(app);
    estadoAuth.desinscrever = modulo.onAuthStateChanged(estadoAuth.auth, async (usuario) => {
      estadoAuth.usuario = usuario;
      estadoAuth.autenticado = !!usuario;
      estadoAuth.perfil = usuario ? await carregarPerfil(usuario.uid) : null;
      estadoAuth.carregando = false;
      atualizarBotao();
      await notificarTroca();
    });
  } catch (e) {
    // Auth nao habilitado no projeto: segue em modo publico.
    console.warn("Auth indisponivel, seguindo em modo publico:", e?.message || e);
    estadoAuth.carregando = false;
    atualizarBotao();
  }
}

async function carregarPerfil(uid) {
  const { db } = await import("./firebase-init.js");
  try {
    const { doc, getDoc } = await import("firebase/firestore");
    const snap = await getDoc(doc(db, "usuarios", uid));
    return snap.exists() ? snap.data() : null;
  } catch (e) {
    console.warn("Perfil do usuario indisponivel:", e?.message || e);
    return null;
  }
}

async function notificarTroca() {
  const evento = new CustomEvent("auth:changed", { detail: estadoAuth });
  window.dispatchEvent(evento);
}

/* ---------- acoes ---------- */

export async function entrar(email, senha) {
  if (!estadoAuth.auth) throw new Error("Autenticação indisponível neste projeto.");
  const modulo = await urlAuth();
  await modulo.signInWithEmailAndPassword(estadoAuth.auth, email, senha);
}

export async function sair() {
  if (!estadoAuth.auth) return;
  const modulo = await urlAuth();
  await modulo.signOut(estadoAuth.auth);
}

/* ---------- escopo ---------- */

/** Ids de agentes que o usuario logado pode ver (vazio = sem restricao). */
export function agentesPermitidos() {
  const perfil = estadoAuth.perfil;
  if (!perfil) return [];
  if (Array.isArray(perfil.agente_ids) && perfil.agente_ids.length) return perfil.agente_ids;
  if (perfil.agente_id) return [perfil.agente_id];
  return [];
}

/** Verdadeiro quando o acesso esta restrito (usuario logado com escopo). */
export function acessoRestrito() {
  return estadoAuth.autenticado && agentesPermitidos().length > 0;
}

/* ---------- interface ---------- */

function atualizarBotao() {
  const botao = $("btnAuth");
  if (!botao) return;
  if (estadoAuth.carregando) {
    botao.textContent = "…";
    botao.title = "Verificando sessão";
    return;
  }
  if (estadoAuth.autenticado) {
    const perfil = estadoAuth.perfil;
    botao.textContent = "Sair";
    botao.title = perfil?.email || estadoAuth.usuario?.email || "Sair da conta";
    botao.classList.add("btn-atualizar");
  } else {
    botao.textContent = "Entrar";
    botao.title = "Entrar com e-mail e senha";
    botao.classList.remove("btn-atualizar");
  }
}

export function abrirLogin() {
  const modal = $("modalLogin");
  if (!modal) return;
  modal.classList.remove("oculto");
  $("loginErro")?.classList.add("oculto");
  $("loginEmail")?.focus();
}

export function fecharLogin() {
  $("modalLogin")?.classList.add("oculto");
}

export async function submeterLogin(evento) {
  evento?.preventDefault();
  const email = ($("loginEmail")?.value || "").trim();
  const senha = $("loginSenha")?.value || "";
  const erro = $("loginErro");
  if (!email || !senha) {
    if (erro) {
      erro.textContent = "Informe e-mail e senha.";
      erro.classList.remove("oculto");
    }
    return;
  }
  const botao = $("btnEntrar");
  if (botao) {
    botao.disabled = true;
    botao.textContent = "Entrando…";
  }
  try {
    await entrar(email, senha);
    fecharLogin();
  } catch (e) {
    const codigo = String(e?.code || "");
    const mensagens = {
      "auth/invalid-credential": "E-mail ou senha inválidos.",
      "auth/user-not-found": "E-mail ou senha inválidos.",
      "auth/wrong-password": "E-mail ou senha inválidos.",
      "auth/too-many-requests": "Muitas tentativas. Tente novamente em alguns minutos.",
      "auth/network-request-failed": "Falha de rede ao autenticar.",
    };
    if (erro) {
      erro.textContent = mensagens[codigo] || e?.message || "Não foi possível entrar.";
      erro.classList.remove("oculto");
    }
  } finally {
    if (botao) {
      botao.disabled = false;
      botao.textContent = "Entrar";
    }
  }
}

export async function alternarAuth() {
  if (estadoAuth.autenticado) {
    await sair();
    return;
  }
  abrirLogin();
}

export function registrarBotaoAuth() {
  $("btnAuth")?.addEventListener("click", alternarAuth);
  $("btnFecharLogin")?.addEventListener("click", fecharLogin);
  $("formLogin")?.addEventListener("submit", submeterLogin);
  $("modalLogin")?.addEventListener("click", (e) => {
    if (e.target === $("modalLogin")) fecharLogin();
  });
}
