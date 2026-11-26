// Teste da lógica do clipping do Governo (filtros, contagens, título), sem navegador.
// Uso: node frontend/tests/teste_clipping_governo.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

globalThis.window = { location: { hash: "#/clipping?secretaria=SEDUC&municipio=Cuiab%C3%A1" } };
globalThis.history = { replaceState: (_a, _b, h) => (globalThis.window.location.hash = h) };
globalThis.document = {
  getElementById: () => null,
  querySelector: () => null,
  dispatchEvent: () => {},
  body: { dataset: { orgao: "governo-mt" } },
};
globalThis.CustomEvent = class {};

const aqui = dirname(fileURLToPath(import.meta.url));
const mod = await import(pathToFileURL(join(aqui, "..", "js", "clipping-governo.js")).href);
const { estado, aplicarFiltros, tituloLimpo } = mod._teste;

let falhas = 0;
const checar = (nome, ok) => {
  console.log(`${ok ? "  PASS  " : "  FALHOU  "}${nome}`);
  if (!ok) falhas += 1;
};

// base: notícias reais do arquivo de 5 meses, no formato das partes
const jsonl = readFileSync(
  join(aqui, "..", "..", "backend", "data", "governo_mt", "5m-2026-11-25", "noticias-2026-11-25.jsonl"),
  "utf-8"
);
const noticias = jsonl
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l))
  .map((r, i) => ({
    id: String(i),
    titulo: r.titulo,
    veiculo: r.veiculo,
    data: r.data,
    siglas: r.siglas || [],
    municipios: /Cuiab/.test(r.titulo) ? ["Cuiabá"] : [],
    alvos: (r.alvos || []).filter((a) => a === "governador" || a === "interino"),
    escopo: r.escopo,
    sentimento: r.sentimento,
  }));
estado.indice = { partes: [{ id: "tudo", mes: "2026-11", total: noticias.length }], secretarias: {} };
estado.partes.set("tudo", noticias);

checar("lê filtros da URL", mod.lerFiltrosDaUrl() && estado.filtros.secretaria === "SEDUC" && estado.filtros.municipio === "Cuiabá");
const seducCuiaba = aplicarFiltros(noticias);
checar(
  "filtro secretaria + município",
  seducCuiaba.length > 0 && seducCuiaba.every((n) => n.siglas.includes("SEDUC") && n.municipios.includes("Cuiabá"))
);
Object.keys(estado.filtros).forEach((k) => (estado.filtros[k] = ""));
checar("sem filtro devolve tudo", aplicarFiltros(noticias).length === noticias.length);
estado.filtros.pessoa = "governador";
const gov = aplicarFiltros(noticias);
checar("filtro governador", gov.length > 0 && gov.every((n) => n.alvos.includes("governador")));
estado.filtros.pessoa = "";
estado.filtros.tom = "negativo";
checar("filtro tom", aplicarFiltros(noticias).every((n) => n.sentimento === "negativo"));
estado.filtros.tom = "";
estado.filtros.busca = "seduc";
checar("busca sem diferenciar maiúsculas", aplicarFiltros(noticias).every((n) => `${n.titulo} ${n.veiculo}`.toLowerCase().includes("seduc")));
estado.filtros.busca = "";

checar("título sem o veículo no fim", tituloLimpo({ titulo: "Obra nova - Fatos de MT", veiculo: "Fatos de MT" }) === "Obra nova");
checar("título intacto sem sufixo", tituloLimpo({ titulo: "Obra nova", veiculo: "G1" }) === "Obra nova");

const porMun = mod.contagemPorMunicipio("");
checar("contagem por município", porMun && porMun.get("Cuiabá")?.total === noticias.filter((n) => n.municipios.length).length);
const porMunSeduc = mod.contagemPorMunicipio("SEDUC");
checar("contagem por município da pasta", porMunSeduc.get("Cuiabá")?.total === seducCuiaba.length);
const tot = mod.totaisDoPeriodo("");
checar("totais do período", tot.total === noticias.length && tot.comMunicipio === porMun.get("Cuiabá").total);

console.log(`\nRESULTADO: ${falhas} falha(s)`);
process.exit(falhas ? 1 : 0);
