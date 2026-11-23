/* Testes das Firestore Rules do ValorPúblico (Emulator Suite).

Uso (na pasta backend/tests):
    npm install
    npm test            # sobe o emulador e roda este arquivo

Valida as regras de RBAC:
  - Leitura pública das coleções do dashboard (metricas, agentes_publicos,
    tabela_midia, analise_lexical, metricas_por_cidade, metricas_por_agente).
  - Clippings (subcoleção) NÃO são expostos ao cliente.
  - Usuário lê/edita apenas o próprio documento em `usuarios`.
  - Execucoes_ingestao bloqueada ao cliente.
*/

const { initializeTestEnvironment, assertFails, assertSucceeds } =
  require("@firebase/rules-unit-testing");
const fs = require("fs");
const path = require("path");

const PROJECT_ID = "valorpublico-b1e6d";
const FS = "firestore.rules";

let testEnv;

async function setup() {
  // Lê as rules como UTF-8 e passa o conteúdo direto (evita problemas de encoding)
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
  console.log("  PASS  (leitura permitida)  " + desc);
}

async function deveBloquear(desc, fn) {
  await assertFails(fn());
  console.log("  PASS  (bloqueado)          " + desc);
}

async function run() {
  await setup();
  console.log(`Rodando testes de regras no projeto ${PROJECT_ID}...`);

  const db = anon().firestore();

  // --- Leitura pública do dashboard ---
  await devePermitir("ler metricas/geral", () =>
    db.collection("metricas").doc("geral").get());
  await devePermitir("ler metricas_por_cidade", () =>
    db.collection("metricas_por_cidade").doc("cuiaba").get());
  await devePermitir("ler metricas_por_agente", () =>
    db.collection("metricas_por_agente").doc("algum").get());
  await devePermitir("ler tabela_midia/geral", () =>
    db.collection("tabela_midia").doc("geral").get());
  await devePermitir("ler analise_lexical/geral", () =>
    db.collection("analise_lexical").doc("geral").get());
  await devePermitir("listar agentes_publicos", () =>
    db.collection("agentes_publicos").get());

  // --- Clippings bloqueados ao cliente ---
  await deveBloquear("ler clippings (subcoleção)", () =>
    db.collection("agentes_publicos").doc("x").collection("clippings").get());

  // --- Escrita bloqueada (backend usa Admin SDK, cliente não escreve) ---
  await deveBloquear("escrever em metricas/geral", () =>
    db.collection("metricas").doc("geral").set({ x: 1 }));
  await deveBloquear("escrever em analise_lexical/geral", () =>
    db.collection("analise_lexical").doc("geral").set({ x: 1 }));

  // --- Usuários: apenas o próprio documento ---
  const dbU1 = usuario("uid-1").firestore();
  await devePermitir("usuário lê o próprio doc", () =>
    dbU1.collection("usuarios").doc("uid-1").get());
  await deveBloquear("usuário lê doc de outro", () =>
    dbU1.collection("usuarios").doc("uid-2").get());
  await deveBloquear("anônimo lê usuários", () =>
    db.collection("usuarios").doc("uid-1").get());

  // --- execucoes_ingestao bloqueada ao cliente ---
  await deveBloquear("ler execucoes_ingestao", () =>
    db.collection("execucoes_ingestao").get());

  console.log("\nTodos os testes de regras passaram.");
}

run()
  .then(limpar)
  .then(() => process.exit(0))
  .catch((e) => {
    console.error("FALHA NOS TESTES:", e);
    return limpar().then(() => process.exit(1));
  });