/* ==========================================================================
   Orgãos (frentes) — separação total de dados entre instituições.

   Cada órgão tem sua própria cidade/casa e seus próprios agregados:
     metricas_por_cidade/<cidadeDoc>  ·  metricas_por_casa/<casaDoc>
     radares|alertas|cobertura|newsletters/cidade-<cidadeDoc>
     analise_lexical/cidade-<cidadeDoc>
     metricas_por_agente/<id>  (com o campo `orgao`)
     metricas_por_secretaria/* (somente Governo de MT)

   O usuário logado pertence a UM só órgão (`usuarios/{uid}.orgao`), exceto
   o administrador, que escolhe qual órgão quer ver depois do login.
   ========================================================================== */

export const ORGAOS = [
  {
    slug: "cuiaba",
    rotulo: "Câmara Municipal de Cuiabá",
    curto: "Câmara de Cuiabá",
    cidade: "Cuiaba",
    cidadeDoc: "cuiaba",
    casa: "Camara Cuiaba",
    casaDoc: "camara-cuiaba",
    cor: "#1d3557",
  },
  {
    slug: "varzea-grande",
    rotulo: "Câmara Municipal de Várzea Grande",
    curto: "Câmara de Várzea Grande",
    cidade: "Varzea Grande",
    cidadeDoc: "varzea-grande",
    casa: "Camara VG",
    casaDoc: "camara-vg",
    cor: "#7a541a",
  },
  {
    slug: "almt",
    rotulo: "Assembleia Legislativa de Mato Grosso (ALMT)",
    curto: "Assembleia (ALMT)",
    cidade: "Mato Grosso",
    cidadeDoc: "mato-grosso",
    casa: "ALMT",
    casaDoc: "almt",
    cor: "#8a2f25",
  },
  {
    slug: "governo-mt",
    rotulo: "Governo de Mato Grosso",
    curto: "Governo de MT",
    cidade: "Governo de Mato Grosso",
    cidadeDoc: "governo-de-mato-grosso",
    casa: "Governo MT",
    casaDoc: "governo-mt",
    cor: "#166534",
  },
];

export function orgaoPorSlug(slug) {
  return ORGAOS.find((o) => o.slug === slug) || null;
}

export function ehAdmin(perfil) {
  return !!perfil && (perfil.papel === "admin" || perfil.papel === "owner");
}

/** Órgão de um agente do roster (usa `casa`; cai em `cidade`). */
export function orgaoDoAgente(agente) {
  if (!agente) return "";
  const porCasa = ORGAOS.find((o) => o.casa === agente.casa);
  if (porCasa) return porCasa.slug;
  const porCidade = ORGAOS.find((o) => o.cidade === agente.cidade);
  return porCidade ? porCidade.slug : "";
}

function chave(uid) {
  return "vp_orgao:" + (uid || "anon");
}

/** Escolha já feita por este usuário neste navegador (null = ainda não). */
export function orgaoSalvo(uid) {
  try {
    return localStorage.getItem(chave(uid));
  } catch {
    return null;
  }
}

/**
 * Órgão ativo no momento.
 * - Não-administrador: o órgão do perfil (fixo) ou a escolha salva.
 * - Administrador: só a escolha salva (após o seletor do login).
 * Retorna null quando ainda não há órgão (abre o seletor).
 */
export function orgaoAtual(perfil, uid) {
  if (!perfil) return null;
  const salvo = orgaoSalvo(uid);
  if (!ehAdmin(perfil)) {
    const doPerfil = perfil.orgao || "";
    if (doPerfil) return doPerfil;
    return salvo && orgaoPorSlug(salvo) ? salvo : null;
  }
  return salvo && orgaoPorSlug(salvo) ? salvo : null;
}

/**
 * Órgãos que este usuário pode ver.
 * - Admin: todos.
 * - Outro: apenas o seu (ou nenhum, se o administrador ainda não definiu).
 */
export function orgaosDisponiveis(perfil) {
  if (!perfil) return [];
  if (ehAdmin(perfil)) return ORGAOS;
  const o = perfil.orgao || "";
  return o ? ORGAOS.filter((x) => x.slug === o) : [];
}

/** Persiste a escolha e avisa o app para recarregar. */
export function definirOrgao(uid, slug, notificar = true) {
  if (!ORGAOS.some((o) => o.slug === slug)) return;
  try {
    localStorage.setItem(chave(uid), slug);
  } catch {
    /* navegador sem storage: a seleção vale só para a sessão */
  }
  if (notificar) window.dispatchEvent(new CustomEvent("orgao:changed"));
}

export function limparOrgao(uid) {
  try {
    localStorage.removeItem(chave(uid));
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent("orgao:changed"));
}
