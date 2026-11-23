/* ==========================================================================
   Autenticação e escopo do usuário (Firebase Auth + RBAC por agente).

   Modo restrito (`config_acesso/publico = false`): o app só inicializa depois
   do login — a tela de login cobre tudo e nenhum dado é buscado antes.
   Modo público (demo): o painel abre direto; "Entrar" é opcional.
   ========================================================================== */

const $ = (id) => document.getElementById(id);

export const estadoAuth = {
  auth: null,
  usuario: null,
  perfil: null, // {uid, email, papel, agente_id, agente_ids, chaves}
  autenticado: false,
  desinscrever: null,
  carregando: true,
};

const CHAVE_SESSAO = "cerra_sessao";

/* ---------- carregamento dos módulos do SDK ---------- */

function temImportmap() {
  return !!document.querySelector('script[type="importmap"]');
}

function urlAuth() {
  if (temImportmap()) return import("firebase/auth");
  return import("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js");
}

function sdkFirestore(versao = "9.22.0") {
  if (temImportmap()) return import("firebase/firestore");
  return import(`https://www.gstatic.com/firebasejs/${versao}/firebase-firestore.js`);
}

/* ---------- sessão ---------- */

export async function iniciarAuth() {
  try {
    const { app } = await import("./firebase-init.js");
    const modulo = await urlAuth();
    estadoAuth.auth = modulo.getAuth(app);
    try {
      estadoAuth.auth.languageCode = "pt-BR";
    } catch {
      /* SDK antigo sem languageCode: segue em ingles */
    }
    await new Promise((resolve) => {
      let primeira = true;
      estadoAuth.desinscrever = modulo.onAuthStateChanged(estadoAuth.auth, async (usuario) => {
        estadoAuth.usuario = usuario;
        estadoAuth.autenticado = !!usuario;
        estadoAuth.perfil = usuario ? await carregarPerfil(usuario.uid) : null;
        estadoAuth.carregando = false;
        atualizarBotao();
        await notificarTroca();
        if (primeira) {
          primeira = false;
          resolve();
        }
      });
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
    const { doc, getDoc } = await sdkFirestore();
    const snap = await getDoc(doc(db, "usuarios", uid));
    return snap.exists() ? snap.data() : null;
  } catch (e) {
    console.warn("Perfil do usuario indisponivel:", e?.message || e);
    return null;
  }
}

/** Lê `config_acesso/publico`. Sem documento = público (modo demo). */
export async function lerModoAcesso() {
  try {
    const { db } = await import("./firebase-init.js");
    const { doc, getDoc } = await sdkFirestore();
    const snap = await getDoc(doc(db, "config_acesso", "publico"));
    if (!snap.exists()) return true;
    return snap.data().publico !== false;
  } catch {
    return true;
  }
}

async function notificarTroca() {
  window.dispatchEvent(new CustomEvent("auth:changed", { detail: estadoAuth }));
}

/* ---------- ações ---------- */

export async function entrar(email, senha) {
  if (!estadoAuth.auth) throw new Error("Autenticação indisponível neste projeto.");
  const modulo = await urlAuth();
  await modulo.signInWithEmailAndPassword(estadoAuth.auth, email, senha);
}

/** Envia o e-mail de redefinição de senha (template personalizado no Firebase). */
export async function recuperarSenha(email) {
  if (!estadoAuth.auth) throw new Error("Autenticação indisponível neste projeto.");
  const modulo = await urlAuth();
  await modulo.sendPasswordResetEmail(estadoAuth.auth, email);
}

export async function sair() {
  if (!estadoAuth.auth) return;
  const modulo = await urlAuth();
  await modulo.signOut(estadoAuth.auth);
}

/* ---------- escopo ---------- */

/** Ids de agentes que o usuário logado pode ver (vazio = sem restrição). */
export function agentesPermitidos() {
  const perfil = estadoAuth.perfil;
  if (!perfil) return [];
  if (Array.isArray(perfil.agente_ids) && perfil.agente_ids.length) return perfil.agente_ids;
  if (perfil.agente_id) return [perfil.agente_id];
  return [];
}

/** Verdadeiro quando o acesso está restrito (usuário logado com escopo). */
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
    botao.textContent = "Sair";
    botao.title = estadoAuth.perfil?.email || estadoAuth.usuario?.email || "Sair da conta";
  } else {
    botao.textContent = "Entrar";
    botao.title = "Entrar com e-mail e senha";
  }
}

export function abrirLogin() {
  const tela = $("telaLogin");
  if (!tela) return;
  tela.classList.add("ativo");
  tela.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  $("loginErro")?.classList.add("oculto");
  $("loginEmail")?.focus();
}

export function fecharLogin() {
  const tela = $("telaLogin");
  if (!tela) return;
  tela.classList.remove("ativo");
  tela.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
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
      "auth/invalid-login-credentials": "E-mail ou senha inválidos.",
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
  $("formLogin")?.addEventListener("submit", submeterLogin);
  $("btnEsqueci")?.addEventListener("click", solicitarReset);
}

async function solicitarReset() {
  const email = ($("loginEmail")?.value || "").trim();
  const msg = $("loginErro");
  if (!email) {
    if (msg) {
      msg.className = "login-erro";
      msg.textContent = "Informe seu e-mail para receber o link.";
      msg.classList.remove("oculto");
    }
    $("loginEmail")?.focus();
    return;
  }
  if (msg) {
    msg.className = "login-erro";
    msg.textContent = "Enviando o link…";
    msg.classList.remove("oculto");
  }
  try {
    await recuperarSenha(email);
    if (msg) {
      msg.className = "login-erro ok";
      msg.textContent = "Link enviado para " + email + ". Confira a caixa de entrada e o spam.";
    }
  } catch (e) {
    const codigo = String(e?.code || "");
    const aviso = codigo === "auth/too-many-requests"
      ? "Muitos pedidos. Tente novamente em alguns minutos."
      : "Não foi possível enviar o link agora. Tente novamente.";
    if (msg) {
      msg.className = "login-erro";
      msg.textContent = aviso;
      msg.classList.remove("oculto");
    }
  }
}
