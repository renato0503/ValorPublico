/**
 * Vocabulário das análises lexicais (plano 22).
 *
 * - `assets/dados/lexico.json` (o mesmo arquivo do backend): palavras sem
 *   assunto e o dicionário de temas que dá nome aos grupos.
 * - Filtro do usuário: além da lista padrão, cada pessoa pode ocultar
 *   palavras que não fazem sentido para ela (fica salvo neste navegador).
 */

const CHAVE_OCULTAS = "vp_lex_ocultas";
const CHAVE_PADRAO = "vp_lex_filtro_padrao";

const estado = {
  semAssunto: new Set(),
  temas: [],
  ocultas: new Set(),
  filtroPadrao: true,
  pronto: null,
};

function norm(texto) {
  return String(texto || "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function lerPreferencias() {
  try {
    const ocultas = JSON.parse(localStorage.getItem(CHAVE_OCULTAS) || "[]");
    estado.ocultas = new Set(Array.isArray(ocultas) ? ocultas.map(norm) : []);
    estado.filtroPadrao = localStorage.getItem(CHAVE_PADRAO) !== "0";
  } catch {
    estado.ocultas = new Set();
    estado.filtroPadrao = true;
  }
}

function salvarPreferencias() {
  try {
    localStorage.setItem(CHAVE_OCULTAS, JSON.stringify([...estado.ocultas]));
    localStorage.setItem(CHAVE_PADRAO, estado.filtroPadrao ? "1" : "0");
  } catch {
    /* sem armazenamento: vale só nesta sessão */
  }
}

/** Carrega o vocabulário (uma vez). */
export function carregar() {
  if (!estado.pronto) {
    lerPreferencias();
    estado.pronto = fetch("assets/dados/lexico.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        estado.semAssunto = new Set((d.sem_assunto || []).map(norm));
        estado.temas = d.temas || [];
      })
      .catch(() => {});
  }
  return estado.pronto;
}

/** A palavra deve aparecer nos gráficos? */
export function relevante(palavra) {
  const p = norm(palavra);
  if (!p || p.length < 3 || /^\d+$/.test(p)) return false;
  if (estado.ocultas.has(p)) return false;
  if (estado.filtroPadrao && estado.semAssunto.has(p)) return false;
  return true;
}

function casa(palavra, radical) {
  const p = norm(palavra);
  const r = norm(radical);
  if (!p || !r) return false;
  return r.length <= 3 ? p === r : p.startsWith(r);
}

/** Tema de uma lista de palavras (as primeiras pesam mais). */
export function tema(palavras) {
  let melhor = null;
  let nota = 0;
  estado.temas.forEach((t) => {
    let n = 0;
    palavras.slice(0, 12).forEach((p, i) => {
      if ((t.radicais || []).some((r) => casa(p, r))) n += 1 / (1 + i * 0.35);
    });
    if (n > nota) {
      melhor = t;
      nota = n;
    }
  });
  return nota >= 0.6 ? melhor : null;
}

/** Nome e explicação de um grupo, quando o backend ainda não os gravou. */
export function descreverGrupo(palavras, pct) {
  const uteis = palavras.filter(relevante);
  const t = tema(uteis);
  const pctTxt = String(Number(pct || 0).toFixed(1)).replace(".", ",");
  const peso =
    pct >= 25 ? "é o assunto dominante" : pct >= 8 ? "é um assunto relevante" : pct >= 2 ? "é um assunto secundário" : "é uma pauta pontual";
  if (!uteis.length) {
    return {
      nome: "Mensagens genéricas",
      explicacao: `Frases genéricas, sem assunto de governo. Reúne ${pctTxt}% dos trechos; pode ser ignorado na leitura.`,
    };
  }
  const chave = uteis.slice(0, 4).join(", ");
  return t
    ? {
        nome: `${t.nome}: ${uteis.slice(0, 2).join(", ")}`,
        explicacao: `Notícias sobre ${t.descricao}. Palavras que marcam o grupo: ${chave}. Reúne ${pctTxt}% dos trechos e ${peso}.`,
      }
    : {
        nome: `Assunto: ${uteis.slice(0, 2).join(", ")}`,
        explicacao: `Grupo sem um tema único; palavras que o marcam: ${chave}. Reúne ${pctTxt}% dos trechos e ${peso}.`,
      };
}

/* ------------------------------------------------------------------ */
/* Filtros sobre os dados de cada gráfico                              */
/* ------------------------------------------------------------------ */

export function filtrarAfc(afc) {
  if (!afc) return afc;
  return { ...afc, palavras: (afc.palavras || []).filter((p) => relevante(p.rotulo)) };
}

export function filtrarGrafo(grafo) {
  if (!grafo) return grafo;
  const nos = (grafo.nos || []).filter((n) => relevante(n.id));
  const ids = new Set(nos.map((n) => n.id));
  return { ...grafo, nos, arestas: (grafo.arestas || []).filter((a) => ids.has(a.a) && ids.has(a.b)) };
}

export function filtrarChd(chd) {
  if (!chd) return chd;
  return {
    ...chd,
    classes: (chd.classes || []).map((cl) => {
      const palavras = (cl.palavras || []).filter((p) => relevante(p.palavra));
      const desc = cl.nome
        ? { nome: cl.nome, explicacao: cl.explicacao }
        : descreverGrupo((cl.palavras || []).map((p) => p.palavra), cl.pct_segmentos);
      return { ...cl, palavras, nome: desc.nome, explicacao: desc.explicacao };
    }),
  };
}

export function filtrarFrequencias(freq) {
  return Object.fromEntries(Object.entries(freq || {}).filter(([p]) => relevante(p)));
}

/* ------------------------------------------------------------------ */
/* Controle "Palavras exibidas"                                         */
/* ------------------------------------------------------------------ */

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** HTML do controle de filtro (vai no topo das análises lexicais). */
export function controleHtml() {
  const ocultas = [...estado.ocultas].sort();
  return `<div class="lex-filtro" role="group" aria-label="Palavras exibidas nos gráficos">
    <label class="lex-filtro-padrao">
      <input type="checkbox" data-lex-filtro-padrao ${estado.filtroPadrao ? "checked" : ""} />
      Esconder palavras sem assunto <span class="lex-filtro-ajuda">(verbos genéricos, cumprimentos, nomes de veículos, datas)</span>
    </label>
    <form class="lex-filtro-ocultar" data-lex-ocultar>
      <input type="text" name="palavra" placeholder="Ocultar outra palavra…" aria-label="Palavra para ocultar dos gráficos" autocomplete="off" />
      <button type="submit" class="btn-texto">Ocultar</button>
    </form>
    ${
      ocultas.length
        ? `<div class="lex-filtro-ocultas" aria-label="Palavras ocultadas por você">Ocultadas por você: ${ocultas
            .map((p) => `<button type="button" class="lex-oculta" data-lex-mostrar="${escapar(p)}" title="Mostrar de novo">${escapar(p)} ✕</button>`)
            .join(" ")}</div>`
        : ""
    }
  </div>`;
}

/** Liga os eventos do controle; `aoMudar` redesenha a análise. */
export function ligarControle(raiz, aoMudar) {
  if (!raiz || raiz.dataset.lexFiltro) return;
  raiz.dataset.lexFiltro = "1";
  raiz.addEventListener("change", (e) => {
    if (e.target.matches("[data-lex-filtro-padrao]")) {
      estado.filtroPadrao = e.target.checked;
      salvarPreferencias();
      aoMudar();
    }
  });
  raiz.addEventListener("submit", (e) => {
    const form = e.target.closest("[data-lex-ocultar]");
    if (!form) return;
    e.preventDefault();
    const palavra = norm(form.palavra.value);
    if (palavra) {
      estado.ocultas.add(palavra);
      salvarPreferencias();
      aoMudar();
    }
  });
  raiz.addEventListener("click", (e) => {
    const botao = e.target.closest("[data-lex-mostrar]");
    if (botao) {
      estado.ocultas.delete(norm(botao.dataset.lexMostrar));
      salvarPreferencias();
      aoMudar();
      return;
    }
    const ocultar = e.target.closest("[data-lex-ocultar-palavra]");
    if (ocultar) {
      estado.ocultas.add(norm(ocultar.dataset.lexOcultarPalavra));
      salvarPreferencias();
      aoMudar();
    }
  });
}
