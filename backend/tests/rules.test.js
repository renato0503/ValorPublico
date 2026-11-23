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
  });
  await db.doc("usuarios/uid-2").set({
    email: "agente2@exemplo.com",
    papel: "agente",
    agente_id: "agente-b",
    agente_ids: ["agente-b"],
    chaves: ["agente-agente-b"],
  });
  await db.doc("metricas_por_agente/agente-a").set({ total_clippings: 10 });
  await db.doc("metricas_por_agente/agente-b").set({ total_clippings: 20 });
  await db.doc("alertas/agente-agente-a").set({ escopo: { chave: "agente-agente-a" } });
  await db.doc("alertas/agente-agente-b").set({ escopo: { chave: "agente-agente-b" } });
  await db.doc("alertas/geral").set({ escopo: { chave: "geral" } });
  });
}

async function testarModoPublico() {
  console.log("\n[1] Modo publico (publico = true)");
  const db = anon().firestore();

  await devePermitir("ler metricas/geral", () =>
    db.collection("metricas").doc("geral").get());
  await devePermitir("ler metricas_por_cidade", () =>
    db.collection("metricas_por_cidade").doc("cuiaba").get());
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
  await devePermitir("agente logado lê o escopo geral", () =>
    dbU1.collection("alertas").doc("geral").get());
  await deveBloquear("usuario sem perfil lê metrica de agente", () =>
    usuario("uid-sem-perfil").firestore()
      .collection("metricas_por_agente").doc("agente-a").get());
}

async function run() {
  await setup();
  console.log(`Rodando testes de regras no projeto ${PROJECT_ID}...`);
  await semear();
  await testarModoPublico();
  await testarUsuarios();
  await testarModoRestrito();
  console.log("\nTodos os testes de regras passaram.");
}

run()
  .then(limpar)
  .then(() => process.exit(0))
  .catch((e) => {
    console.error("FALHA NOS TESTES:", e);
    return limpar().then(() => process.exit(1));
  });
