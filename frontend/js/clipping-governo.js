/**
 * Clipping completo do Governo de MT (plano 22).
 *
 * Lê `clipping_governo/_indice` e as partes mensais `clipping_governo/<AAAA-MM>-<n>`
 * (geradas pelo backend em `atualizar_metricas_governo.py`). Diferente do
 * clipping genérico, não depende das 200 notícias do agregado: traz todas as
 * notícias do período e filtra por secretaria, município, pessoa, escopo, tom,
 * veículo e texto. A URL guarda os filtros: `#/clipping?secretaria=SEDUC&municipio=Sinop`.
 */
import { escapar } from "./componentes.js";

const POR_PAGINA = 25;
const ROTULO_ESCOPO = {
  "governo-estado": "Sobre o Executivo",
  "geral-mt": "Interesse geral de MT",
  "instituicoes-mt": "Outras instituições",
};
const ROTULO_PESSOA = { governador: "Governador", interino: "Interino" };
const ROTULO_TOM = { positivo: "Positivo", neutro: "Neutro", negativo: "Negativo" };
const PARAMS = ["secretaria", "municipio", "pessoa", "escopo", "tom"];

const estado = {
  db: null,
  indice: null,
  partes: new Map(), // id -> noticias[]
  periodo: "",
  pagina: 1,
  carregando: false,
  erro: "",
  filtros: { secretaria: "", municipio: "", pessoa: "", escopo: "", tom: "", veiculo: "", busca: "" },
};

async function sdk() {
  try {
    return await import("firebase/firestore");
  } catch {
    return await import("https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore.js");
  }
}

function corte(periodo) {
  const agora = new Date();
  if (periodo === "hoje") return new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
  const dias = { "7d": 7, "15d": 15, "30d": 30 }[periodo];
  return dias ? new Date(agora.getTime() - dias * 86400000) : null;
}

function partesDoPeriodo() {
  const partes = estado.indice?.partes || [];
  const limite = corte(estado.periodo);
  if (!limite) return partes;
  const mesLimite = limite.toISOString().slice(0, 7);
  return partes.filter((p) => p.mes >= mesLimite || p.mes === "sem-data");
}

/** Lê o índice e as partes do período (com cache). */
export async function carregar(db, periodo = "") {
  estado.db = db;
  estado.periodo = periodo || "";
  estado.erro = "";
  estado.carregando = true;
  renderizar();
  try {
    const { doc, getDoc } = await sdk();
    if (!estado.indice) {
      const snap = await getDoc(doc(db, "clipping_governo", "_indice"));
      estado.indice = snap.exists() ? snap.data() : null;
    }
    const faltam = partesDoPeriodo().filter((p) => !estado.partes.has(p.id));
    const lidas = await Promise.all(
      faltam.map(async (p) => {
        const snap = await getDoc(doc(db, "clipping_governo", p.id));
        return [p.id, snap.exists() ? snap.data().noticias || [] : []];
      })
    );
    lidas.forEach(([id, noticias]) => estado.partes.set(id, noticias));
  } catch (erro) {
    console.warn("[Clipping Governo] falha ao carregar:", erro?.code || erro?.message || erro);
    estado.erro = "Não foi possível carregar o clipping do Governo agora.";
  }
  estado.carregando = false;
  renderizar();
  document.dispatchEvent(new CustomEvent("clipping-governo:carregado"));
}

/**
 * Notícias por município no período carregado (opcionalmente de uma pasta).
 * Devolve null enquanto o clipping não foi carregado.
 */
export function contagemPorMunicipio(sigla = "") {
  if (!estado.indice || !estado.partes.size) return null;
  const saida = new Map();
  noticiasDoPeriodo().forEach((n) => {
    if (sigla && !(n.siglas || []).includes(sigla)) return;
    (n.municipios || []).forEach((m) => {
      const linha = saida.get(m) || { total: 0, positivo: 0, neutro: 0, negativo: 0 };
      linha.total += 1;
      if (linha[n.sentimento] !== undefined) linha[n.sentimento] += 1;
      saida.set(m, linha);
    });
  });
  return saida;
}

/** Quantas notícias do período citam algum município (para a leitura do gráfico). */
export function totaisDoPeriodo(sigla = "") {
  if (!estado.indice || !estado.partes.size) return null;
  const lista = noticiasDoPeriodo().filter((n) => !sigla || (n.siglas || []).includes(sigla));
  return { total: lista.length, comMunicipio: lista.filter((n) => (n.municipios || []).length).length };
}

export function definirPeriodo(periodo) {
  if ((periodo || "") === estado.periodo) return;
  if (estado.db) carregar(estado.db, periodo);
}

/** Lê os filtros da URL (link direto vindo da tela do Governo). */
export function lerFiltrosDaUrl() {
  const params = new URLSearchParams(window.location.hash.split("?")[1] || "");
  let mudou = false;
  PARAMS.forEach((chave) => {
    const valor = params.get(chave) || "";
    if (valor !== estado.filtros[chave]) {
      estado.filtros[chave] = valor;
      mudou = true;
    }
  });
  if (mudou) estado.pagina = 1;
  return mudou;
}

function escreverFiltrosNaUrl() {
  const [base, consulta = ""] = window.location.hash.split("?");
  const params = new URLSearchParams(consulta);
  PARAMS.forEach((chave) => {
    if (estado.filtros[chave]) params.set(chave, estado.filtros[chave]);
    else params.delete(chave);
  });
  const nova = params.toString() ? `${base}?${params}` : base;
  if (nova !== window.location.hash) history.replaceState(null, "", nova);
}

function noticiasDoPeriodo() {
  const limite = corte(estado.periodo);
  const todas = [];
  partesDoPeriodo().forEach((p) => todas.push(...(estado.partes.get(p.id) || [])));
  const filtradas = limite ? todas.filter((n) => n.data && new Date(n.data) >= limite) : todas;
  return filtradas.sort((a, b) => (b.data || "").localeCompare(a.data || ""));
}

function aplicarFiltros(lista) {
  const f = estado.filtros;
  const termo = f.busca.trim().toLowerCase();
  return lista.filter((n) => {
    if (f.secretaria && !(n.siglas || []).includes(f.secretaria)) return false;
    if (f.municipio && !(n.municipios || []).includes(f.municipio)) return false;
    if (f.pessoa && !(n.alvos || []).includes(f.pessoa)) return false;
    if (f.escopo && n.escopo !== f.escopo) return false;
    if (f.tom && n.sentimento !== f.tom) return false;
    if (f.veiculo && n.veiculo !== f.veiculo) return false;
    if (termo && !`${n.titulo} ${n.veiculo}`.toLowerCase().includes(termo)) return false;
    return true;
  });
}

/** Título sem o " - Veículo" que o agregador cola no fim. */
function tituloLimpo(n) {
  const t = n.titulo || "notícia";
  const sufixo = ` - ${n.veiculo || ""}`;
  return n.veiculo && t.endsWith(sufixo) ? t.slice(0, -sufixo.length) : t;
}

function dataCurta(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? iso.slice(0, 10) : d.toLocaleDateString("pt-BR");
}

function opcoes(select, valores, rotuloTodos, rotular = (v) => v) {
  if (!select) return;
  const atual = estado.filtros[select.dataset.filtro] ?? select.value;
  select.innerHTML =
    `<option value="">${rotuloTodos}</option>` +
    valores.map((v) => `<option value="${escapar(v)}">${escapar(rotular(v))}</option>`).join("");
  select.value = valores.includes(atual) ? atual : "";
}

function contar(lista, campo) {
  const c = new Map();
  lista.forEach((n) => {
    const valores = Array.isArray(n[campo]) ? n[campo] : [n[campo]];
    valores.filter(Boolean).forEach((v) => c.set(v, (c.get(v) || 0) + 1));
  });
  return c;
}

function preencherSelects(base) {
  const porSecretaria = contar(base, "siglas");
  const porMunicipio = contar(base, "municipios");
  const porVeiculo = contar(base, "veiculo");
  const nomes = estado.indice?.secretarias || {};
  const ordenar = (m) => [...m.keys()].sort((a, b) => m.get(b) - m.get(a) || a.localeCompare(b));
  opcoes(
    document.getElementById("filtroClipSecretaria"),
    ordenar(porSecretaria),
    "Todas as secretarias",
    (s) => `${s}${nomes[s] && nomes[s] !== s ? ` · ${nomes[s]}` : ""} (${porSecretaria.get(s)})`
  );
  opcoes(
    document.getElementById("filtroClipMunicipio"),
    ordenar(porMunicipio),
    "Todos os municípios",
    (m) => `${m} (${porMunicipio.get(m)})`
  );
  opcoes(
    document.getElementById("filtroClipVeiculo"),
    [...porVeiculo.keys()].sort((a, b) => a.localeCompare(b)),
    "Todos os veículos"
  );
}

function chips(lista, classe) {
  return (lista || []).map((v) => `<span class="clip-chip ${classe}">${escapar(v)}</span>`).join(" ");
}

export function renderizar() {
  const corpo = document.getElementById("corpoClipping");
  if (!corpo) return;
  const nota = document.getElementById("clippingNota");

  if (estado.carregando && !estado.partes.size) {
    corpo.innerHTML = '<tr><td colspan="6">Carregando o clipping do Governo…</td></tr>';
    return;
  }
  if (estado.erro || !estado.indice) {
    corpo.innerHTML = `<tr><td colspan="6">${escapar(
      estado.erro || "O clipping do Governo ainda não foi publicado. Ele é gerado junto com as métricas do Governo."
    )}</td></tr>`;
    if (nota) nota.textContent = "";
    return;
  }

  const base = noticiasDoPeriodo();
  preencherSelects(base);
  const filtradas = aplicarFiltros(base);
  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / POR_PAGINA));
  estado.pagina = Math.min(Math.max(1, estado.pagina), totalPaginas);
  const inicio = (estado.pagina - 1) * POR_PAGINA;
  const visiveis = filtradas.slice(inicio, inicio + POR_PAGINA);

  corpo.innerHTML = visiveis.length
    ? visiveis
        .map(
          (n) => `<tr>
            <td data-label="Matéria">${
              n.url
                ? `<a href="${escapar(n.url)}" target="_blank" rel="noopener">${escapar(tituloLimpo(n))}</a>`
                : escapar(tituloLimpo(n))
            }${(n.alvos || []).length ? `<div class="clip-pessoas">${chips(n.alvos.map((a) => ROTULO_PESSOA[a] || a), "pessoa")}</div>` : ""}</td>
            <td data-label="Veículo">${escapar(n.veiculo || "—")}</td>
            <td data-label="Data">${escapar(dataCurta(n.data))}</td>
            <td data-label="Secretaria">${chips(n.siglas, "sec") || '<span class="clip-vazio">—</span>'}</td>
            <td data-label="Município">${chips(n.municipios, "mun") || '<span class="clip-vazio">—</span>'}</td>
            <td data-label="Tom"><span class="clip-tom ${escapar(n.sentimento || "neutro")}">${escapar(
              ROTULO_TOM[n.sentimento] || "Neutro"
            )}</span></td>
          </tr>`
        )
        .join("")
    : '<tr><td colspan="6">Nenhuma notícia atende aos filtros selecionados.</td></tr>';

  renderizarPaginacao(filtradas.length, totalPaginas);
  if (nota) {
    const ativos = Object.entries(estado.filtros).filter(([, v]) => v).length;
    nota.textContent = filtradas.length
      ? `Mostrando ${inicio + 1}–${inicio + visiveis.length} de ${filtradas.length.toLocaleString("pt-BR")} notícias${
          ativos ? " filtradas" : ""
        } (${base.length.toLocaleString("pt-BR")} no período).`
      : `Nenhuma das ${base.length.toLocaleString("pt-BR")} notícias do período atende aos filtros.`;
  }
}

function renderizarPaginacao(total, totalPaginas) {
  const alvo = document.getElementById("paginacaoClipping");
  if (!alvo) return;
  if (totalPaginas <= 1) {
    alvo.innerHTML = "";
    return;
  }
  const p = estado.pagina;
  alvo.innerHTML = `
    <button type="button" class="btn-texto" data-clipgov-pagina="${p - 1}" ${p <= 1 ? "disabled" : ""}>‹ Anterior</button>
    <span class="paginacao-info">Página ${p} de ${totalPaginas}</span>
    <button type="button" class="btn-texto" data-clipgov-pagina="${p + 1}" ${p >= totalPaginas ? "disabled" : ""}>Próxima ›</button>`;
}

function csv(valor) {
  const t = String(valor ?? "");
  return /[";\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
}

/** CSV exatamente do recorte filtrado (abre no Excel em pt-BR). */
export function exportarCsv() {
  const linhas = aplicarFiltros(noticiasDoPeriodo());
  const cabecalho = ["data", "titulo", "veiculo", "secretarias", "municipios", "pessoas", "escopo", "tom", "valor_midia", "url"];
  const corpo = linhas.map((n) =>
    [
      dataCurta(n.data),
      tituloLimpo(n),
      n.veiculo,
      (n.siglas || []).join(" | "),
      (n.municipios || []).join(" | "),
      (n.alvos || []).map((a) => ROTULO_PESSOA[a] || a).join(" | "),
      ROTULO_ESCOPO[n.escopo] || n.escopo,
      ROTULO_TOM[n.sentimento] || n.sentimento,
      String(n.valor ?? 0).replace(".", ","),
      n.url,
    ]
      .map(csv)
      .join(";")
  );
  const blob = new Blob(["﻿" + [cabecalho.join(";"), ...corpo].join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const sufixo = [estado.filtros.secretaria, estado.filtros.municipio, estado.periodo]
    .filter(Boolean)
    .join("-")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `clipping-governo-mt${sufixo ? "-" + sufixo : ""}.csv`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(a.href);
    a.remove();
  }, 0);
}

/** Liga os controles da tela (uma vez) e sincroniza com os filtros atuais. */
export function ativarControles() {
  const ids = {
    filtroClipSecretaria: "secretaria",
    filtroClipMunicipio: "municipio",
    filtroClipPessoa: "pessoa",
    filtroClipEscopo: "escopo",
    filtroClipTom: "tom",
    filtroClipVeiculo: "veiculo",
  };
  Object.entries(ids).forEach(([id, chave]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.dataset.filtro = chave;
    if (el.dataset.clipgov) return;
    el.dataset.clipgov = "1";
    el.addEventListener("change", () => {
      if (!ativo()) return;
      estado.filtros[chave] = el.value;
      estado.pagina = 1;
      escreverFiltrosNaUrl();
      renderizar();
    });
  });
  const busca = document.getElementById("filtroClipBusca");
  if (busca && !busca.dataset.clipgov) {
    busca.dataset.clipgov = "1";
    let timer = null;
    busca.addEventListener("input", () => {
      if (!ativo()) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        estado.filtros.busca = busca.value;
        estado.pagina = 1;
        renderizar();
      }, 180);
    });
  }
  const limpar = document.getElementById("btnLimparClipping");
  if (limpar && !limpar.dataset.clipgov) {
    limpar.dataset.clipgov = "1";
    limpar.addEventListener("click", () => {
      Object.keys(estado.filtros).forEach((k) => (estado.filtros[k] = ""));
      if (busca) busca.value = "";
      estado.pagina = 1;
      escreverFiltrosNaUrl();
      renderizar();
    });
  }
  const btnCsv = document.getElementById("btnCsvClipping");
  if (btnCsv && !btnCsv.dataset.clipgov) {
    btnCsv.dataset.clipgov = "1";
    btnCsv.addEventListener("click", () => ativo() && exportarCsv());
  }
  document.getElementById("paginacaoClipping")?.addEventListener("click", (e) => {
    const botao = e.target.closest("[data-clipgov-pagina]");
    if (!botao || !ativo()) return;
    estado.pagina = Number(botao.dataset.clipgovPagina) || 1;
    renderizar();
    document.getElementById("tela-clipping")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  // sincroniza selects fixos com o estado (link direto)
  ["pessoa", "escopo", "tom"].forEach((chave) => {
    const el = document.querySelector(`[data-filtro="${chave}"]`);
    if (el) el.value = estado.filtros[chave];
  });
  if (busca) busca.value = estado.filtros.busca;
}

/** A tela de clipping está no modo Governo? */
export function ativo() {
  return document.body.dataset.orgao === "governo-mt";
}

/** Recorte atual (filtros + notícias) para o documento em PDF. */
export function recorteAtual() {
  return {
    carregado: !!estado.indice && estado.partes.size > 0,
    filtros: { ...estado.filtros },
    periodo: estado.periodo,
    noticias: estado.indice ? aplicarFiltros(noticiasDoPeriodo()) : [],
    total_periodo: estado.indice ? noticiasDoPeriodo().length : 0,
    secretarias: estado.indice?.secretarias || {},
    tituloLimpo,
  };
}

/** Para o teste de ponta a ponta. */
export const _teste = { estado, aplicarFiltros, tituloLimpo };
