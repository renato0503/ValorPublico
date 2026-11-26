/* Testes das Firestore Rules (Emulator Suite).

Uso (na pasta backend/tests):
    npm install
    npm test            # sobe o emulador e roda este arquivo

Valida:
  - Modo publico (config_acesso/publico = true): leitura das colecoes do
    dashboard, incluindo as da Camada DSM.
  - Clippings (subcolecao) NUNCA expostos ao cliente.
  - Escritas bloqueadas (o backend escreve via Admin SDK).
  - Modo restrito (publico = false): usuario so le o proprio agente;
    anonimo nao le nada de agente; 'geral' fica para quem tem perfil.
  - Usuarios: apenas o proprio documento.
*/

const { initializeTestEnvironment, assertFails, assertSucceeds } =
  require("@firebase/rules-unit-testing");
const fs = require("fs");
const path = require("path");

const PROJECT_ID = process.env.PROJECT_ID || "assessorpublico";
const FS = "firestore.rules";

let testEnv;

async function setup() {
  const rules = fs.readFileSync(
    path.resolve(__dirname, "../../firestore.rules"),
    "utf8"
  ).replace(/\r\n/g, "\n");
  testEnv = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: { rules },
  });
}

async function limpar() {
  if (testEnv) await testEnv.cleanup();
}

function anon() {
  return testEnv.unauthenticatedContext();
}

function usuario(uid) {
  return testEnv.authenticatedContext(uid);
}

async function devePermitir(desc, fn) {
  await assertSucceeds(fn());
  console.log("  PASS  (permitido)  " + desc);
}

async function deveBloquear(desc, fn) {
  await assertFails(fn());
  console.log("  PASS  (bloqueado)  " + desc);
}

async function semear() {
  await testEnv.withSecurityRulesDisabled(async (context) => {
  const db = context.firestore();
  await db.doc("config_acesso/publico").set({ publico: true, modo: "publico" });
  await db.doc("usuarios/uid-1").set({
    email: "agente1@exemplo.com",
    papel: "agente",
    agente_id: "agente-a",
    agente_ids: ["agente-a"],
    chaves: ["agente-agente-a"],
    orgao: "cuiaba",
  });
  await db.doc("usuarios/uid-2").set({
    email: "agente2@exemplo.com",
    papel: "agente",
    agente_id: "agente-b",
    agente_ids: ["agente-b"],
    chaves: ["agente-agente-b"],
    orgao: "varzea-grande",
  });
  await db.doc("usuarios/uid-adm").set({
    email: "admin@exemplo.com",
    papel: "owner",
    agente_id: "",
    agente_ids: [],
    chaves: ["geral"],
    orgao: "",
  });
  await db.doc("metricas_por_agente/agente-a").set({ total_clippings: 10, orgao: "cuiaba" });
  await db.doc("metricas_por_agente/agente-b").set({ total_clippings: 20, orgao: "varzea-grande" });
  await db.doc("agentes_publicos/agente-a").set({ nome_urna: "A", orgao: "cuiaba", cidade: "Cuiaba" });
  await db.doc("agentes_publicos/agente-b").set({ nome_urna: "B", orgao: "varzea-grande", cidade: "Varzea Grande" });
  await db.doc("metricas_por_cidade/cuiaba").set({ total_clippings: 10, orgao: "cuiaba" });
  await db.doc("metricas_por_cidade/varzea-grande").set({ total_clippings: 20, orgao: "varzea-grande" });
  await db.doc("metricas_por_cidade/mato-grosso").set({ total_clippings: 30, orgao: "almt" });
  await db.doc("metricas_por_cidade/governo-de-mato-grosso").set({ total_clippings: 40, orgao: "governo-mt" });
  await db.doc("metricas_por_casa/camara-cuiaba").set({ total_clippings: 10, orgao: "cuiaba" });
  await db.doc("metricas_por_casa/camara-vg").set({ total_clippings: 20, orgao: "varzea-grande" });
  await db.doc("metricas_por_casa/almt").set({ total_clippings: 30, orgao: "almt" });
  await db.doc("metricas_por_casa/governo-mt").set({ total_clippings: 40, orgao: "governo-mt" });
  await db.doc("metricas_por_secretaria/saude").set({ total_clippings: 5, orgao: "governo-mt" });
  await db.doc("clipping_governo/2026-11-1").set({ mes: "2026-11", noticias: [], orgao: "governo-mt" });
  await db.doc("imagens_governo/instagram").set({ miniaturas: {}, orgao: "governo-mt" });
  await db.doc("usuarios/uid-gov").set({
    email: "secom@exemplo.com",
    papel: "secom",
    agente_id: "",
    agente_ids: [],
    chaves: [],
    orgao: "governo-mt",
  });
  await db.doc("alertas/agente-agente-a").set({ escopo: { chave: "agente-agente-a" }, orgao: "cuiaba" });
  await db.doc("alertas/agente-agente-b").set({ escopo: { chave: "agente-agente-b" }, orgao: "varzea-grande" });
  await db.doc("alertas/geral").set({ escopo: { chave: "geral" }, orgao: "" });
  await db.doc("alertas/cidade-cuiaba").set({ escopo: { chave: "cidade-cuiaba" }, orgao: "cuiaba" });
  await db.doc("alertas/cidade-mato-grosso").set({ escopo: { chave: "cidade-mato-grosso" }, orgao: "almt" });
  await db.doc("alertas/cidade-governo-de-mato-grosso").set({ escopo: { chave: "cidade-governo-de-mato-grosso" }, orgao: "governo-mt" });
  await db.doc("analise_lexical/cidade-cuiaba").set({ escopo: { tipo: "cidade" }, orgao: "cuiaba" });
  await db.doc("analise_lexical/cidade-mato-grosso").set({ escopo: { tipo: "cidade" }, orgao: "almt" });
  });
}

async function testarModoPublico() {
  console.log("\n[1] Modo publico (publico = true)");
  const db = anon().firestore();

  await devePermitir("ler metricas/geral", () =>
    db.collection("metricas").doc("geral").get());
  await devePermitir("ler metricas_por_cidade", () =>
    db.collection("metricas_por_cidade").doc("cuiaba").get());
  await devePermitir("ler metricas_por_cidade/mato-grosso (ALMT)", () =>
    db.collection("metricas_por_cidade").doc("mato-grosso").get());
  await devePermitir("ler metricas_por_agente", () =>
    db.collection("metricas_por_agente").doc("agente-a").get());
  await devePermitir("ler tabela_midia/geral", () =>
    db.collection("tabela_midia").doc("geral").get());
  await devePermitir("ler analise_lexical/geral", () =>
    db.collection("analise_lexical").doc("geral").get());
  await devePermitir("ler releases_ia/geral", () =>
    db.collection("releases_ia").doc("geral").get());
  await devePermitir("ler radares/geral", () =>
    db.collection("radares").doc("geral").get());
  await devePermitir("ler alertas/agente-agente-a (modo publico)", () =>
    db.collection("alertas").doc("agente-agente-a").get());
  await devePermitir("ler cobertura/geral", () =>
    db.collection("cobertura").doc("geral").get());
  await devePermitir("ler newsletters/geral", () =>
    db.collection("newsletters").doc("geral").get());
  await devePermitir("listar agentes_publicos", () =>
    db.collection("agentes_publicos").get());

  await deveBloquear("ler clippings (subcoleção)", () =>
    db.collection("agentes_publicos").doc("x").collection("clippings").get());
  await deveBloquear("escrever em metricas/geral", () =>
    db.collection("metricas").doc("geral").set({ x: 1 }));
  await deveBloquear("escrever em alertas/geral", () =>
    db.collection("alertas").doc("geral").set({ x: 1 }));
  await deveBloquear("escrever em config_acesso", () =>
    db.collection("config_acesso").doc("publico").set({ publico: true }));
  await deveBloquear("ler execucoes_ingestao", () =>
    db.collection("execucoes_ingestao").get());
}

async function testarUsuarios() {
  console.log("\n[2] Documentos de usuario");
  const dbU1 = usuario("uid-1").firestore();
  await devePermitir("usuario lê o proprio doc", () =>
    dbU1.collection("usuarios").doc("uid-1").get());
  await deveBloquear("usuario lê doc de outro", () =>
    dbU1.collection("usuarios").doc("uid-2").get());
  await deveBloquear("anonimo lê usuarios", () =>
    anon().firestore().collection("usuarios").doc("uid-1").get());
  await deveBloquear("usuario escreve no proprio doc", () =>
    dbU1.collection("usuarios").doc("uid-1").set({ agente_id: "outro" }));
}

async function testarModoRestrito() {
  console.log("\n[3] Modo restrito (publico = false)");
  await testEnv.withSecurityRulesDisabled(async (context) => {
    await context.firestore().doc("config_acesso/publico").set({ publico: false });
  });

  const db = anon().firestore();
  await deveBloquear("anonimo lê metricas_por_agente", () =>
    db.collection("metricas_por_agente").doc("agente-a").get());
  await deveBloquear("anonimo lê alertas/agente-agente-a", () =>
    db.collection("alertas").doc("agente-agente-a").get());
  await deveBloquear("anonimo lê alertas/geral", () =>
    db.collection("alertas").doc("geral").get());
  await devePermitir("anonimo lê a config de acesso", () =>
    db.collection("config_acesso").doc("publico").get());

  const dbU1 = usuario("uid-1").firestore();
  await devePermitir("agente lê a propria metrica", () =>
    dbU1.collection("metricas_por_agente").doc("agente-a").get());
  await deveBloquear("agente lê metrica de outro", () =>
    dbU1.collection("metricas_por_agente").doc("agente-b").get());
  await devePermitir("agente lê o proprio alerta", () =>
    dbU1.collection("alertas").doc("agente-agente-a").get());
  await deveBloquear("agente lê alerta de outro", () =>
    dbU1.collection("alertas").doc("agente-agente-b").get());
  await deveBloquear("escopo 'geral' e so do administrador", () =>
    dbU1.collection("alertas").doc("geral").get());
  await deveBloquear("usuario sem perfil lê metrica de agente", () =>
    usuario("uid-sem-perfil").firestore()
      .collection("metricas_por_agente").doc("agente-a").get());

  // --- separacao por orgao (modo restrito) ---
  const dbCuiaba = usuario("uid-1").firestore(); // orgao = cuiaba
  const dbVg = usuario("uid-2").firestore(); // orgao = varzea-grande
  const dbAdm = usuario("uid-adm").firestore(); // owner

  await devePermitir("Cuiaba lê metricas_por_casa/camara-cuiaba", () =>
    dbCuiaba.collection("metricas_por_casa").doc("camara-cuiaba").get());
  await devePermitir("Cuiaba lê metricas_por_cidade/cuiaba", () =>
    dbCuiaba.collection("metricas_por_cidade").doc("cuiaba").get());
  await deveBloquear("Cuiaba NAO lê metricas_por_casa/almt", () =>
    dbCuiaba.collection("metricas_por_casa").doc("almt").get());
  await deveBloquear("Cuiaba NAO lê metricas_por_cidade/mato-grosso", () =>
    dbCuiaba.collection("metricas_por_cidade").doc("mato-grosso").get());
  await deveBloquear("Cuiaba NAO lê metricas_por_casa/governo-mt", () =>
    dbCuiaba.collection("metricas_por_casa").doc("governo-mt").get());
  await deveBloquear("Cuiaba NAO lê metricas/geral", () =>
    dbCuiaba.collection("metricas").doc("geral").get());

  await devePermitir("V.Grande lê metricas_por_casa/camara-vg", () =>
    dbVg.collection("metricas_por_casa").doc("camara-vg").get());
  await deveBloquear("V.Grande NAO lê metricas_por_casa/camara-cuiaba", () =>
    dbVg.collection("metricas_por_casa").doc("camara-cuiaba").get());

  // --- DSM / lexical tambem separados por orgao ---
  await devePermitir("Cuiaba lê alertas/cidade-cuiaba", () =>
    dbCuiaba.collection("alertas").doc("cidade-cuiaba").get());
  await deveBloquear("Cuiaba NAO lê alertas/cidade-mato-grosso", () =>
    dbCuiaba.collection("alertas").doc("cidade-mato-grosso").get());
  await deveBloquear("Cuiaba NAO lê alertas/cidade-governo-de-mato-grosso", () =>
    dbCuiaba.collection("alertas").doc("cidade-governo-de-mato-grosso").get());
  await devePermitir("Cuiaba lê analise_lexical/cidade-cuiaba", () =>
    dbCuiaba.collection("analise_lexical").doc("cidade-cuiaba").get());
  await deveBloquear("Cuiaba NAO lê analise_lexical/cidade-mato-grosso", () =>
    dbCuiaba.collection("analise_lexical").doc("cidade-mato-grosso").get());
  await devePermitir("V.Grande lê alertas/agente-agente-b (mesmo orgao)", () =>
    dbVg.collection("alertas").doc("agente-agente-b").get());

  // --- roster (agentes_publicos) separado por orgao ---
  await devePermitir("Cuiaba lista agentes do proprio orgao", () =>
    dbCuiaba.collection("agentes_publicos").where("orgao", "==", "cuiaba").get());
  await deveBloquear("Cuiaba NAO lista agentes sem filtro de orgao", () =>
    dbCuiaba.collection("agentes_publicos").get());
  await devePermitir("Cuiaba le agente do proprio orgao", () =>
    dbCuiaba.collection("agentes_publicos").doc("agente-a").get());
  await deveBloquear("Cuiaba NAO le agente de outro orgao", () =>
    dbCuiaba.collection("agentes_publicos").doc("agente-b").get());
  await devePermitir("admin lista todos os agentes", () =>
    dbAdm.collection("agentes_publicos").get());

  await deveBloquear("Camara NAO lê metricas_por_secretaria", () =>
    dbCuiaba.collection("metricas_por_secretaria").doc("saude").get());

  await devePermitir("admin lê metricas/geral (todos os orgaos)", () =>
    dbAdm.collection("metricas").doc("geral").get());
  await devePermitir("admin lê metricas_por_casa/almt", () =>
    dbAdm.collection("metricas_por_casa").doc("almt").get());
  await devePermitir("admin lê metricas_por_cidade/governo-de-mato-grosso", () =>
    dbAdm.collection("metricas_por_cidade").doc("governo-de-mato-grosso").get());
  await devePermitir("admin lê metricas_por_secretaria", () =>
    dbAdm.collection("metricas_por_secretaria").doc("saude").get());

  // Plano 22: clipping completo do Governo
  const dbGov = usuario("uid-gov").firestore();
  await devePermitir("Governo lê clipping_governo", () =>
    dbGov.collection("clipping_governo").doc("2026-11-1").get());
  await deveBloquear("Camara NAO lê clipping_governo", () =>
    dbCuiaba.collection("clipping_governo").doc("2026-11-1").get());
  await deveBloquear("anonimo NAO lê clipping_governo", () =>
    anon().firestore().collection("clipping_governo").doc("2026-11-1").get());
  await deveBloquear("Governo NAO escreve clipping_governo", () =>
    dbGov.collection("clipping_governo").doc("x").set({ a: 1 }));
  await devePermitir("admin lê clipping_governo", () =>
    dbAdm.collection("clipping_governo").doc("2026-11-1").get());
  await devePermitir("Governo lê imagens_governo", () =>
    dbGov.collection("imagens_governo").doc("instagram").get());
  await deveBloquear("Camara NAO lê imagens_governo", () =>
    dbCuiaba.collection("imagens_governo").doc("instagram").get());
  await deveBloquear("Governo NAO lê clippings brutos", () =>
    dbGov.collection("agentes_publicos").doc("governo-mt").collection("clippings").doc("x").get());
  await devePermitir("admin lê escopo geral", () =>
    dbAdm.collection("alertas").doc("geral").get());
}

async function run() {
  await setup();
  console.log(`Rodando testes de regras no projeto ${PROJECT_ID}...`);
  await semear();
  await testarModoPublico();
  await testarUsuarios();
  await testarModoRestrito();
  // Colecoes novas (roda em modo restrito, ja ativado acima).
  const novas = require("./rules_novas.test.js");
  await novas.semearNovas(testEnv);
  await novas.testarColecoesNovas(testEnv, {
    devePermitir,
    deveBloquear,
    usuario,
    anon,
  });
  console.log("\nTodos os testes de regras passaram.");
}

run()
  .then(limpar)
  .then(() => process.exit(0))
  .catch((e) => {
    console.error("FALHA NOS TESTES:", e);
    return limpar().then(() => process.exit(1));
  });
