/* Testes das Firestore Rules — colecoes novas (planos 09/10/12/13/14/18/19).

Este arquivo e carregado por `rules.test.js` (que compartilha o contexto do
emulador e os helpers `devePermitir`/`deveBloquear`). Ele exporta apenas as
funcoes; nao roda sozinho.

Casos novos:
  - `imagens/*` (plano 18): **privada** — nem anonimo nem o proprio agente leem;
  - `relatorio_semanal/*` e `discurso_semanal/*` (09/10): leitura por escopo;
  - `demandas/*` (13): privada por escopo; papel Ouvidoria/Secom veem;
  - `auditoria/*` (12): so Controle/Transparencia/SeCom leem;
  - `metricas_por_casa/*` (14): leitura no modo restrito;
  - `execucoes_navegador/*` (19): so admin leem.

Cada colecao tem caso POSITIVO e caso NEGATIVO.
*/

const COLECOES_NOVAS = [
  { nome: "imagens", doc: "abc123phash" },
  { nome: "relatorio_semanal", doc: "agente-agente-a__2026-W48", orgao: "cuiaba" },
  { nome: "discurso_semanal", doc: "agente-agente-a__2026-W48", orgao: "cuiaba" },
  { nome: "simulacao_semanal", doc: "casa-governo-mt__2026-W48", orgao: "governo-mt" },
  { nome: "personas", doc: "servidor-estadual", orgao: "governo-mt" },
  { nome: "demandas", doc: "agente-agente-a", orgao: "cuiaba" },
  { nome: "auditoria", doc: "2026-11-24T10:00:00" },
  { nome: "metricas_por_casa", doc: "camara-cuiaba", orgao: "cuiaba" },
  { nome: "execucoes_navegador", doc: "run-0001" },
];

async function semearNovas(ctx) {
  await ctx.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await db.doc("usuarios/uid-ouvidoria").set({
      email: "ouvidoria@exemplo.com",
      papel: "ouvidoria",
      agente_id: "",
      agente_ids: [],
      chaves: [],
    });
    await db.doc("usuarios/uid-controle").set({
      email: "controle@exemplo.com",
      papel: "controle",
      agente_id: "",
      agente_ids: [],
      chaves: [],
    });
    await db.doc("usuarios/uid-agente").set({
      email: "agente@exemplo.com",
      papel: "agente",
      agente_id: "agente-a",
      agente_ids: ["agente-a"],
      chaves: ["agente-agente-a"],
      orgao: "cuiaba",
    });
    await db.doc("usuarios/uid-governo").set({
      email: "governo@exemplo.com",
      papel: "assessor",
      agente_id: "",
      agente_ids: [],
      chaves: [],
      orgao: "governo-mt",
    });
    await db.doc("usuarios/uid-admin").set({
      email: "admin@exemplo.com",
      papel: "admin",
      agente_id: "",
      agente_ids: [],
      chaves: ["geral"],
      orgao: "",
    });
    await db.collection("metricas_por_secretaria").doc("saude").set({ teste: true });
    for (const item of COLECOES_NOVAS) {
      await db.collection(item.nome).doc(item.doc).set({
        teste: true,
        orgao: item.orgao || "",
        // O escopo vem no proprio documento (o id da semana tem sufixo).
        escopo: item.nome === "relatorio_semanal" || item.nome === "discurso_semanal"
          ? "agente-agente-a"
          : "",
      });
    }
  });
}

async function testarColecoesNovas(ctx, helpers) {
  const { devePermitir, deveBloquear, usuario, anon } = helpers;
  console.log("\n[4] Colecoes novas (positivo e negativo por colecao)");

  // --- imagens: sempre negada ao cliente (so o backend, via Admin SDK) ---
  await deveBloquear("anonimo le imagens", () =>
    anon().firestore().collection("imagens").doc("abc123phash").get());
  await deveBloquear("agente le imagens (privada)", () =>
    usuario("uid-agente").firestore().collection("imagens").doc("abc123phash").get());
  await deveBloquear("admin le imagens", () =>
    usuario("uid-1").firestore().collection("imagens").doc("abc123phash").get());

  // --- relatorio_semanal / discurso_semanal: por escopo ---
  await devePermitir("agente le o proprio relatorio_semanal", () =>
    usuario("uid-agente").firestore().collection("relatorio_semanal").doc("agente-agente-a__2026-W48").get());
  await deveBloquear("agente le relatorio_semanal de outro", () =>
    usuario("uid-agente").firestore().collection("relatorio_semanal").doc("agente-agente-b__2026-W48").get());
  await devePermitir("agente le o proprio discurso_semanal", () =>
    usuario("uid-agente").firestore().collection("discurso_semanal").doc("agente-agente-a__2026-W48").get());
  await deveBloquear("agente le discurso_semanal de outro", () =>
    usuario("uid-agente").firestore().collection("discurso_semanal").doc("agente-agente-b__2026-W48").get());
  await deveBloquear("escrita em relatorio_semanal", () =>
    usuario("uid-agente").firestore().collection("relatorio_semanal").doc("x").set({ a: 1 }));
  await deveBloquear("escrita em discurso_semanal", () =>
    usuario("uid-agente").firestore().collection("discurso_semanal").doc("x").set({ a: 1 }));

  // --- demandas: por escopo + papeis do orgao ---
  await devePermitir("agente le as demandas do proprio escopo", () =>
    usuario("uid-agente").firestore().collection("demandas").doc("agente-agente-a").get());
  await deveBloquear("agente le demandas de outro escopo", () =>
    usuario("uid-agente").firestore().collection("demandas").doc("agente-agente-b").get());
  await devePermitir("papel Ouvidoria le demandas", () =>
    usuario("uid-ouvidoria").firestore().collection("demandas").doc("agente-agente-a").get());
  await deveBloquear("escrita em demandas", () =>
    usuario("uid-ouvidoria").firestore().collection("demandas").doc("agente-agente-a").set({ a: 1 }));

  // --- auditoria: so Controle/Transparencia/SeCom ---
  await devePermitir("papel Controle le auditoria", () =>
    usuario("uid-controle").firestore().collection("auditoria").doc("2026-11-24T10:00:00").get());
  await deveBloquear("papel Ouvidoria nao le auditoria", () =>
    usuario("uid-ouvidoria").firestore().collection("auditoria").doc("2026-11-24T10:00:00").get());
  await deveBloquear("escrita em auditoria", () =>
    usuario("uid-controle").firestore().collection("auditoria").doc("x").set({ a: 1 }));

  // --- metricas_por_casa: leitura restrita ao orgao do usuario ---
  await devePermitir("usuario de Cuiaba le metricas_por_casa/camara-cuiaba", () =>
    usuario("uid-agente").firestore().collection("metricas_por_casa").doc("camara-cuiaba").get());
  await deveBloquear("usuario de Cuiaba NAO le metricas_por_casa/almt", () =>
    usuario("uid-agente").firestore().collection("metricas_por_casa").doc("almt").get());
  await deveBloquear("escrita em metricas_por_casa", () =>
    usuario("uid-agente").firestore().collection("metricas_por_casa").doc("camara-cuiaba").set({ a: 1 }));

  // --- metricas_por_secretaria (Governo de MT): so Governo ou admin ---
  await devePermitir("Governo de MT le metricas_por_secretaria", () =>
    usuario("uid-governo").firestore().collection("metricas_por_secretaria").doc("saude").get());
  await deveBloquear("Camara NAO le metricas_por_secretaria", () =>
    usuario("uid-agente").firestore().collection("metricas_por_secretaria").doc("saude").get());
  await devePermitir("admin le metricas_por_secretaria", () =>
    usuario("uid-admin").firestore().collection("metricas_por_secretaria").doc("saude").get());
  await deveBloquear("escrita em metricas_por_secretaria", () =>
    usuario("uid-governo").firestore().collection("metricas_por_secretaria").doc("saude").set({ a: 1 }));

  // --- simulação e personas: só Governo/admin ---
  await devePermitir("Governo le simulacao_semanal", () =>
    usuario("uid-governo").firestore().collection("simulacao_semanal").doc("casa-governo-mt__2026-W48").get());
  await deveBloquear("Camara NAO le simulacao_semanal do Governo", () =>
    usuario("uid-agente").firestore().collection("simulacao_semanal").doc("casa-governo-mt__2026-W48").get());
  await devePermitir("admin le simulacao_semanal", () =>
    usuario("uid-admin").firestore().collection("simulacao_semanal").doc("casa-governo-mt__2026-W48").get());
  await devePermitir("Governo le persona do proprio orgao", () =>
    usuario("uid-governo").firestore().collection("personas").doc("servidor-estadual").get());
  await deveBloquear("Camara NAO le persona do Governo", () =>
    usuario("uid-agente").firestore().collection("personas").doc("servidor-estadual").get());
  await deveBloquear("escrita em simulacao_semanal", () =>
    usuario("uid-governo").firestore().collection("simulacao_semanal").doc("x").set({ a: 1 }));
  await deveBloquear("escrita em personas", () =>
    usuario("uid-governo").firestore().collection("personas").doc("x").set({ a: 1 }));

  // --- execucoes_navegador: so admin ---
  await devePermitir("admin le execucoes_navegador", () =>
    usuario("uid-admin").firestore().collection("execucoes_navegador").doc("run-0001").get());
  await deveBloquear("agente le execucoes_navegador", () =>
    usuario("uid-agente").firestore().collection("execucoes_navegador").doc("run-0001").get());
}

module.exports = { testarColecoesNovas, semearNovas, COLECOES_NOVAS };
