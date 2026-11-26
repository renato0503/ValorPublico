/**
 * Documentos em PDF do ValorPúblico (plano 22).
 *
 * Cada exportação vira um documento próprio, diagramado para A4 (capa,
 * indicadores, seções numeradas, gráficos para papel, tabelas e nota de
 * método), em vez de imprimir a tela. O documento é montado em `#documento`,
 * o navegador imprime só ele (css/documento.css) e ele é removido depois.
 *
 * Uso: imprimir("executivo" | "governo" | "clipping" | "redes" | "semana" |
 *               "governador" | "tendencias" | "personas")
 */
import * as telas from "./telas.js";
import * as governo from "./governo.js";
import * as clippingGoverno from "./clipping-governo.js";
import * as personas from "./personas.js";

/* ------------------------------------------------------------------ */
/* utilidades                                                          */
/* ------------------------------------------------------------------ */

const esc = (t) =>
  String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (n) => Number(n || 0).toLocaleString("pt-BR");
const pct = (v, total) => (total ? Math.round((100 * Number(v || 0)) / total) : 0);
const dinheiro = (n) =>
  Number(n || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

/** Data dd/mm/aaaa sem deslocar o dia por fuso. */
function data(valor) {
  if (!valor) return "—";
  if (valor.toDate) valor = valor.toDate();
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) return valor.split("-").reverse().join("/");
  const d = new Date(valor);
  return isNaN(d) ? String(valor).slice(0, 10) : d.toLocaleDateString("pt-BR", { timeZone: "America/Cuiaba" });
}

function semVeiculo(titulo, veiculo) {
  const t = String(titulo || "");
  const sufixo = ` - ${veiculo || ""}`;
  return veiculo && t.endsWith(sufixo) ? t.slice(0, -sufixo.length) : t.replace(/\s-\s[^-]{2,60}$/, "");
}

/** Assinatura da fonte (· veículo) só quando o veículo não está no próprio título. */
function fonteDe(noticia) {
  const veiculo = String(noticia?.veiculo || "").trim();
  const titulo = semVeiculo(noticia?.titulo, noticia?.veiculo);
  if (!veiculo) return "";
  if (titulo.toLowerCase().includes(veiculo.toLowerCase())) return "";
  return ` · <em>${esc(veiculo)}</em>`;
}

const ROTULO_PERIODO = { "": "Todo o período", hoje: "Hoje", "7d": "Últimos 7 dias", "15d": "Últimos 15 dias", "30d": "Últimos 30 dias" };

function intervaloDaSerie(dados) {
  const dias = Object.keys(dados?.serie_sentimento || dados?.dias || {}).sort();
  return dias.length ? `${data(dias[0])} a ${data(dias[dias.length - 1])}` : "";
}

function tons(dados) {
  const d = dados?.distribuicao_sentimento || {};
  const p = Number(d.positivo || 0);
  const n = Number(d.neutro || 0);
  const g = Number(d.negativo || 0);
  return { positivo: p, neutro: n, negativo: g, total: p + n + g };
}

const saldoDe = (t) => (t.total ? Math.round((100 * (t.positivo - t.negativo)) / t.total) : 0);

/* ------------------------------------------------------------------ */
/* componentes do documento                                            */
/* ------------------------------------------------------------------ */

const LOGO = `<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="2.5" y="2.5" width="59" height="59" rx="7" fill="#ffffff" stroke="#c9a227" stroke-width="2.4"/><rect x="12" y="16" width="40" height="4.4" rx="1.2" fill="#0b2a52"/><rect x="14.5" y="22.5" width="7" height="26" fill="#0b2a52"/><rect x="28.5" y="22.5" width="7" height="26" fill="#0b2a52"/><rect x="42.5" y="22.5" width="7" height="26" fill="#0b2a52"/><rect x="12" y="50.5" width="40" height="4.4" rx="1.2" fill="#c9a227"/><circle cx="32" cy="11" r="2.6" fill="#c9a227"/></svg>`;

function capa({ tipo, titulo, subtitulo, meta }) {
  return `<header class="doc-capa">
    <div class="doc-faixa">
      <span class="doc-marca">${LOGO}<b>ValorPúblico</b><small>Painel institucional de mídia</small></span>
      <span class="doc-tipo">${esc(tipo)}</span>
    </div>
    <div class="doc-capa-corpo">
      <h1>${esc(titulo)}</h1>
      ${subtitulo ? `<p class="doc-subtitulo">${esc(subtitulo)}</p>` : ""}
      <div class="doc-regra"></div>
    </div>
    <div class="doc-capa-pe">
      <dl class="doc-meta">${meta
        .filter(([, v]) => v)
        .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`)
        .join("")}</dl>
      <p class="doc-capa-credito">Documento institucional gerado pelo ValorPúblico · desenvolvido por Cerrado Tech</p>
    </div>
  </header>`;
}

let contadorSecao = 0;
function secao(titulo, intro, corpo, { quebra = false } = {}) {
  contadorSecao += 1;
  return `<section class="doc-secao${quebra ? " doc-quebra" : ""}">
    <h2><span class="doc-num">${String(contadorSecao).padStart(2, "0")}</span>${esc(titulo)}</h2>
    ${intro ? `<p class="doc-intro">${intro}</p>` : ""}
    ${corpo}
  </section>`;
}

function kpis(itens) {
  const lista = itens.filter(Boolean);
  const colunas = lista.length && lista.length <= 4 ? lista.length : 3;
  return `<div class="doc-kpis" style="--col:${colunas}">${lista
    .map(
      (k) => `<div class="doc-kpi${k.destaque ? " destaque" : ""}">
        <span class="doc-kpi-rotulo">${esc(k.rotulo)}</span>
        <b>${esc(k.valor)}</b>
        ${k.sub ? `<small>${esc(k.sub)}</small>` : ""}
      </div>`
    )
    .join("")}</div>`;
}

function leitura(html, rotulo = "Leitura") {
  return html ? `<div class="doc-leitura"><span>${esc(rotulo)}</span><p>${html}</p></div>` : "";
}

function barraTom(t, { legenda = false } = {}) {
  const total = t.positivo + t.neutro + t.negativo;
  if (!total) return '<span class="doc-vazio">—</span>';
  return `<span class="doc-tom" title="positivo ${pct(t.positivo, total)}% · neutro ${pct(t.neutro, total)}% · negativo ${pct(t.negativo, total)}%">
      <i class="pos" style="width:${(100 * t.positivo) / total}%"></i><i class="neu" style="width:${(100 * t.neutro) / total}%"></i><i class="neg" style="width:${(100 * t.negativo) / total}%"></i>
    </span>${
      legenda
        ? `<span class="doc-tom-leg"><b class="pos">${pct(t.positivo, total)}%</b> positivas · ${pct(t.neutro, total)}% neutras · <b class="neg">${pct(t.negativo, total)}%</b> negativas</span>`
        : ""
    }`;
}

const LEGENDA_TOM = `<div class="doc-legenda"><span><i class="pos"></i>positivo</span><span><i class="neu"></i>neutro</span><span><i class="neg"></i>negativo</span></div>`;

function barras(itens, { max, sufixo = "" } = {}) {
  const maior = max || Math.max(1, ...itens.map((i) => Number(i.valor || 0)));
  return `<div class="doc-barras">${itens
    .map(
      (i) => `<div class="doc-barra">
        <span class="rot">${esc(i.rotulo)}</span>
        <span class="trilho"><i style="width:${Math.max(1.5, (100 * Number(i.valor || 0)) / maior)}%"></i></span>
        <span class="val">${num(i.valor)}${sufixo}</span>
      </div>`
    )
    .join("")}</div>`;
}

function tabela(colunas, linhas, { classe = "" } = {}) {
  return `<table class="doc-tabela ${classe}">
    <thead><tr>${colunas.map((c) => `<th class="${c.classe || ""}">${esc(c.titulo)}</th>`).join("")}</tr></thead>
    <tbody>${linhas
      .map((l) => `<tr>${l.map((cel, i) => `<td class="${colunas[i]?.classe || ""}">${cel}</td>`).join("")}</tr>`)
      .join("")}</tbody>
  </table>`;
}

function link(titulo, url) {
  return url ? `<a href="${esc(url)}">${esc(titulo)}</a>` : esc(titulo);
}

/** Evolução semanal em colunas empilhadas (positivo/neutro/negativo), em SVG. */
function evolucaoSemanal(dados, semanas = 18) {
  const serie = dados?.serie_sentimento || {};
  const porSemana = new Map();
  Object.entries(serie).forEach(([dia, v]) => {
    const d = new Date(`${dia}T12:00:00Z`);
    if (isNaN(d)) return;
    const seg = new Date(d);
    seg.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    const chave = seg.toISOString().slice(0, 10);
    const atual = porSemana.get(chave) || { positivo: 0, neutro: 0, negativo: 0 };
    ["positivo", "neutro", "negativo"].forEach((t) => (atual[t] += Number(v?.[t] || 0)));
    porSemana.set(chave, atual);
  });
  const lista = [...porSemana.entries()].sort((a, b) => a[0].localeCompare(b[0])).slice(-semanas);
  if (!lista.length) return { svg: "", lista: [] };
  const W = 640;
  const H = 170;
  const base = 140;
  const maior = Math.max(1, ...lista.map(([, v]) => v.positivo + v.neutro + v.negativo));
  const passo = (W - 40) / lista.length;
  const larg = Math.min(26, passo * 0.68);
  const cores = { positivo: "#12805c", neutro: "#9aa6b6", negativo: "#c0392b" };
  let barrasSvg = "";
  lista.forEach(([seg, v], i) => {
    const x = 34 + i * passo + (passo - larg) / 2;
    let y = base;
    ["negativo", "neutro", "positivo"].forEach((t) => {
      const h = ((v[t] || 0) / maior) * (base - 14);
      y -= h;
      barrasSvg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${larg.toFixed(1)}" height="${h.toFixed(1)}" fill="${cores[t]}"/>`;
    });
    const total = v.positivo + v.neutro + v.negativo;
    barrasSvg += `<text x="${(x + larg / 2).toFixed(1)}" y="${(y - 3).toFixed(1)}" text-anchor="middle" class="v">${total}</text>`;
    if (i % 2 === 0 || lista.length <= 10)
      barrasSvg += `<text x="${(x + larg / 2).toFixed(1)}" y="${base + 13}" text-anchor="middle" class="e">${data(seg).slice(0, 5)}</text>`;
  });
  const grade = [0.25, 0.5, 0.75, 1]
    .map((f) => {
      const y = base - f * (base - 14);
      return `<line x1="30" x2="${W}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="g"/><text x="26" y="${(y + 3).toFixed(1)}" text-anchor="end" class="e">${Math.round(f * maior)}</text>`;
    })
    .join("");
  return {
    lista,
    svg: `<svg class="doc-grafico" viewBox="0 0 ${W} ${H}" role="img" aria-label="Notícias por semana e tom">${grade}<line x1="30" x2="${W}" y1="${base}" y2="${base}" class="eixo"/>${barrasSvg}</svg>`,
  };
}

/** Nome da fonte tanto em string ("MT HOJE, 2026-11-24") quanto em objeto ({veiculo}). */
function fonteNome(fonte) {
  if (typeof fonte === "string") return fonte.split(",")[0].trim();
  if (fonte && typeof fonte === "object") {
    return String(fonte.veiculo || fonte.fonte || fonte.source || fonte.titulo || "").split(",")[0].trim();
  }
  return "";
}

/** Nomes das fontes do discurso ("MT HOJE, 2026-11-24" -> "MT HOJE"). */
function nomesDeFontes(fontes) {
  return new Set((fontes || []).map(fonteNome).map((n) => n.toLowerCase()).filter(Boolean));
}

/** Bloco "fontes" do discurso: notícias que embasam a versão ou nomes das fontes. */
function blocoFontes(v) {
  const fontes = v.fontes || [];
  if (!fontes.length) return "";
  if (typeof fontes[0] === "string") {
    const nomes = [...new Set(fontes.map(fonteNome).filter(Boolean))];
    return `<p class="doc-fontes">Fontes desta versão: ${nomes.map((f) => esc(f)).join(" · ")}.</p>`;
  }
  const itens = fontes
    .map(
      (f) =>
        `<li><time>${data(f.data || f.data_publicacao || "")}</time>${link(f.frase || f.titulo || fonteNome(f), f.url)} <em>${esc(f.veiculo || "")}</em></li>`
    )
    .join("");
  return `<div class="doc-fontes-bloco"><h4>Notícias que embasam esta versão</h4><ul class="doc-lista">${itens}</ul></div>`;
}

/**
 * Tira do texto as marcas de fonte que o gerador deixa entre parênteses
 * (ex.: "(MT HOJE, 2026-11-24)", "[Estimado MT, 2026-11-24]", "(JBNEWS)").
 * O conteúdo continua o mesmo; as fontes ficam na seção "Fontes".
 */
function limparReferencias(texto, nomes = new Set()) {
  return String(texto || "")
    .replace(/\s*\[[^\[\]]{0,90}?\d{4}-\d{2}-\d{2}\s*\]/g, "")
    .replace(/\s*\(([^()]{1,90})\)/g, (todo, dentro) => {
      const bruto = dentro.trim();
      const chave = bruto.split(",")[0].trim().toLowerCase();
      if (!bruto) return todo;
      if (/\d{4}-\d{2}-\d{2}/.test(bruto)) return "";
      if (nomes.has(chave)) return "";
      if (/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(chave)) return ""; // site
      if (/^[A-ZÀ-Ú0-9 ._/-]{2,40}$/.test(bruto)) return ""; // nome em caixa alta
      return todo;
    })
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function notaMetodo(extra = "") {
  return `<footer class="doc-nota">
    <h3>Como estes números são produzidos</h3>
    <p>As notícias são coletadas automaticamente de portais, agregadores e sites oficiais e associadas ao órgão, às secretarias,
    às pessoas e aos municípios citados. O tom (positivo, neutro ou negativo) é classificado automaticamente pelo texto de cada
    notícia: é uma leitura de apoio, não substitui a análise da equipe. Saldo de opinião = (positivas − negativas) ÷ total × 100.
    ${extra}</p>
    <p class="doc-assina">Documento gerado pelo ValorPúblico · desenvolvido por Cerrado Tech</p>
  </footer>`;
}

/* ------------------------------------------------------------------ */
/* blocos reutilizados                                                 */
/* ------------------------------------------------------------------ */

function blocoResumo(d) {
  const t = tons(d);
  const saldo = saldoDe(t);
  const itens = [
    { rotulo: "Notícias no período", valor: num(d.total_clippings), sub: d.total_veiculos ? `em ${num(d.total_veiculos)} veículos` : "", destaque: true },
    { rotulo: "Saldo de opinião", valor: `${saldo > 0 ? "+" : ""}${saldo}`, sub: "de −100 a +100" },
    d.imagem_institucional !== undefined && d.imagem_institucional !== null
      ? { rotulo: "Índice de imagem", valor: String(d.imagem_institucional), sub: "0 a 100 · 50 = neutro" }
      : null,
    d.pct_tier1 !== undefined && d.pct_tier1 !== null
      ? { rotulo: "Em grandes veículos", valor: `${Math.round(d.pct_tier1)}%`, sub: "Tier 1" }
      : null,
    d.valoracao_total ? { rotulo: "Valor de mídia", valor: dinheiro(d.valoracao_total), sub: "estimativa por tabela" } : null,
    d.por_municipio ? { rotulo: "Municípios citados", valor: num(Object.keys(d.por_municipio).length), sub: "de 142 em MT" } : null,
  ];
  const texto =
    `No período, ${num(d.total_clippings)} notícias${d.total_veiculos ? ` de ${num(d.total_veiculos)} veículos` : ""} citaram o órgão. ` +
    `O tom foi predominantemente neutro (${pct(t.neutro, t.total)}%), com ${pct(t.positivo, t.total)}% positivas e ${pct(t.negativo, t.total)}% negativas, ` +
    `o que dá um saldo de opinião de <b>${saldo > 0 ? "+" : ""}${saldo}</b>` +
    (saldo > 10 ? ": o noticiário é mais favorável do que crítico." : saldo < -10 ? ": o noticiário está mais crítico do que favorável." : ": o noticiário está equilibrado.");
  return kpis(itens) + `<div class="doc-linha">${barraTom(t, { legenda: true })}</div>` + leitura(texto, "Em síntese");
}

function blocoEvolucao(d) {
  const { svg, lista } = evolucaoSemanal(d);
  if (!svg) return "";
  const totais = lista.map(([seg, v]) => ({ seg, total: v.positivo + v.neutro + v.negativo, neg: v.negativo }));
  const pico = [...totais].sort((a, b) => b.total - a.total)[0];
  const maisNeg = [...totais].filter((x) => x.total >= 10).sort((a, b) => b.neg / b.total - a.neg / a.total)[0];
  const texto =
    `A semana com mais notícias começou em ${data(pico.seg)} (${num(pico.total)} notícias).` +
    (maisNeg ? ` A proporção mais alta de negativas foi na semana de ${data(maisNeg.seg)} (${pct(maisNeg.neg, maisNeg.total)}%).` : "");
  return secao("Evolução semanal e tom", "Cada coluna é uma semana (a data é a segunda-feira); as cores mostram o tom das notícias.", svg + LEGENDA_TOM + leitura(texto));
}

function blocoSecretarias(g, limite = 12, todas = false) {
  const pastas = (g?.secretarias || [])
    .map((p) => {
      const t = tons(p);
      return { sigla: p.pasta?.sigla || p.id, nome: p.pasta?.nome || "", titular: p.pasta?.titular || "", total: Number(p.total_clippings || t.total), t, saldo: saldoDe(t) };
    })
    .filter((p) => p.total > 0)
    .sort((a, b) => b.total - a.total);
  if (!pastas.length) return "";
  const lista = todas ? pastas : pastas.slice(0, limite);
  const linhas = lista.map((p) => [
    `<b>${esc(p.sigla)}</b><small>${esc(p.nome)}${p.titular ? ` · ${esc(p.titular)}` : ""}</small>`,
    num(p.total),
    barraTom(p.t),
    `<span class="${p.saldo > 0 ? "pos" : p.saldo < 0 ? "neg" : ""}">${p.saldo > 0 ? "+" : ""}${p.saldo}</span>`,
  ]);
  const critica = [...pastas].filter((p) => p.total >= 10).sort((a, b) => a.saldo - b.saldo)[0];
  const favoravel = [...pastas].filter((p) => p.total >= 10).sort((a, b) => b.saldo - a.saldo)[0];
  const texto =
    `${esc(pastas[0].sigla)} é a pasta mais citada (${num(pastas[0].total)} notícias).` +
    (favoravel ? ` Entre as pastas com ao menos 10 notícias, a de saldo mais favorável é ${esc(favoravel.sigla)} (${favoravel.saldo > 0 ? "+" : ""}${favoravel.saldo})` : "") +
    (critica && critica !== favoravel ? ` e a mais pressionada é ${esc(critica.sigla)} (${critica.saldo > 0 ? "+" : ""}${critica.saldo}).` : ".");
  return secao(
    "Secretarias e autarquias",
    todas ? "Todas as pastas com notícias no período, da mais citada para a menos citada." : `As ${lista.length} pastas mais citadas no período.`,
    tabela(
      [{ titulo: "Pasta" }, { titulo: "Notícias", classe: "n" }, { titulo: "Tom", classe: "tom" }, { titulo: "Saldo", classe: "n" }],
      linhas
    ) + LEGENDA_TOM + leitura(texto)
  );
}

function blocoPessoas(g) {
  const pessoas = [
    ["Governador · Otaviano Pivetta", g?.governador],
    ["Governador interino · Max Russi", g?.interino],
  ].filter(([, d]) => d && Number(d.total_clippings || 0) > 0);
  if (!pessoas.length) return "";
  const cartoes = pessoas
    .map(([nome, d]) => {
      const t = tons(d);
      const saldo = saldoDe(t);
      const manchetes = (d.noticias_recentes || []).slice(0, 4);
      return `<div class="doc-cartao">
        <h3>${esc(nome)}</h3>
        <div class="doc-mini-kpis"><span><b>${num(d.total_clippings)}</b> notícias</span><span><b>${saldo > 0 ? "+" : ""}${saldo}</b> saldo</span></div>
        ${barraTom(t, { legenda: true })}
        ${
          manchetes.length
            ? `<ul class="doc-lista">${manchetes
                .map((n) => `<li><time>${data(n.data_publicacao || n.data)}</time>${link(semVeiculo(n.titulo, n.veiculo), n.url)}${fonteDe(n)}</li>`)
                .join("")}</ul>`
            : ""
        }
      </div>`;
    })
    .join("");
  return secao("Governador e interino", "A pessoa e o cargo, medidos separadamente. O interino só é contado no período em que exerce o cargo.", `<div class="doc-duas">${cartoes}</div>`);
}

function blocoMunicipios(d, limite = 15) {
  const mun = Object.entries(d?.por_municipio || {})
    .map(([nome, v]) => ({ nome, ...v }))
    .sort((a, b) => b.total - a.total);
  if (!mun.length) return "";
  const lista = mun.slice(0, limite);
  const linhas = lista.map((m, i) => [`${i + 1}`, esc(m.nome), num(m.total), barraTom(m)]);
  const fora = mun.slice(1, 6).map((m) => esc(m.nome)).join(", ");
  return secao(
    "Notícias por município",
    `Municípios de Mato Grosso citados nas notícias (${num(mun.length)} no total). As demais notícias falam do Estado como um todo.`,
    tabela([{ titulo: "#", classe: "n" }, { titulo: "Município" }, { titulo: "Notícias", classe: "n" }, { titulo: "Tom", classe: "tom" }], linhas) +
      leitura(`${esc(mun[0].nome)} concentra a cobertura (${num(mun[0].total)} notícias). No interior, aparecem mais ${fora}.`)
  );
}

function blocoCanais(d) {
  const canais = Object.entries(d?.por_canal || {})
    .map(([canal, v]) => ({ canal, ...v, total: Number(v.positivo || 0) + Number(v.neutro || 0) + Number(v.negativo || 0) }))
    .filter((c) => c.total > 0)
    .sort((a, b) => b.total - a.total);
  if (!canais.length) return "";
  const linhas = canais.map((c) => [
    esc(c.canal.replace(/Comentários no Instagram \((@[^)]+)\)/, "Público no Instagram $1")),
    num(c.total),
    barraTom(c),
    `${pct(c.negativo, c.total)}%`,
  ]);
  return secao(
    "Tom por canal",
    "Imprensa por porte do veículo, sites do próprio Governo, outras instituições e o público nos comentários do Instagram oficial.",
    tabela([{ titulo: "Canal" }, { titulo: "Itens", classe: "n" }, { titulo: "Tom", classe: "tom" }, { titulo: "Negativas", classe: "n" }], linhas) + LEGENDA_TOM
  );
}

function blocoMudou(d) {
  const m = d?.especificidades?.semana_vs_base;
  if (!m || (!(m.mais || []).length && !(m.menos || []).length)) return "";
  const lista = (itens, classe) =>
    `<ul class="doc-palavras ${classe}">${itens
      .slice(0, 8)
      .map((p) => `<li><b>${esc(p.palavra)}</b><span>${num(p.semana)} nesta semana · ${num(p.antes)} antes</span></li>`)
      .join("")}</ul>`;
  return secao(
    "O que mudou nesta semana",
    "Palavras das manchetes que apareceram muito mais (ou muito menos) nos últimos 7 dias do que nas semanas anteriores.",
    `<div class="doc-duas"><div><h3>Ganharam espaço</h3>${lista(m.mais || [], "sobe")}</div><div><h3>Perderam espaço</h3>${lista(m.menos || [], "desce")}</div></div>`
  );
}

function blocoAtencao(d) {
  const ev = d?.crise_eventos || [];
  if (!ev.length) return "";
  const itens = ev
    .map(
      (e) => `<div class="doc-evento">
        <div class="doc-evento-cab"><time>${data(e.data)}</time><b>${e.pct_negativas}% negativas</b><span>${num(e.negativos)} de ${num(e.total)} notícias · normal: ${e.pct_normal}%</span></div>
        <ul>${(e.manchetes || []).map((m) => `<li>${link(m.titulo, m.url)}${fonteDe(m)}</li>`).join("")}</ul>
      </div>`
    )
    .join("");
  return secao("Dias de atenção", "Dias em que a proporção de notícias negativas saiu da faixa normal, com as manchetes que puxaram o tom.", itens);
}

function blocoRedesResumo(d) {
  const r = d?.redes_sociais || {};
  const contas = r.contas || [];
  if (!contas.length) return "";
  const linhas = contas.map((c) => [
    `<b>${esc(c.conta)}</b><small>${esc(c.rede || "Instagram")}</small>`,
    num(c.posts),
    num(c.comentarios),
    num(c.media_curtidas),
    barraTom({ positivo: c.tom_publico?.positivo || 0, neutro: c.tom_publico?.neutro || 0, negativo: c.tom_publico?.negativo || 0 }),
    c.saldo_publico === null || c.saldo_publico === undefined ? "—" : `${c.saldo_publico > 0 ? "+" : ""}${c.saldo_publico}`,
  ]);
  return secao(
    "Redes oficiais",
    "Instagram do Governo e do governador: o que publicaram e como o público reagiu nos comentários.",
    tabela(
      [{ titulo: "Conta" }, { titulo: "Posts", classe: "n" }, { titulo: "Comentários", classe: "n" }, { titulo: "Curtidas/post", classe: "n" }, { titulo: "Tom do público", classe: "tom" }, { titulo: "Saldo", classe: "n" }],
      linhas
    )
  );
}

function blocoManchetes(d, limite = 12) {
  const lista = (d?.noticias_recentes || []).slice(0, limite);
  if (!lista.length) return "";
  const linhas = lista.map((n) => [
    data(n.data_publicacao || n.data),
    link(semVeiculo(n.titulo || n.texto_limpo, n.veiculo), n.url),
    esc(n.veiculo || n.autor || "—"),
    `<span class="doc-etq ${esc(n.sentimento || "neutro")}">${esc(n.sentimento || "neutro")}</span>`,
  ]);
  return secao("Manchetes mais recentes", "", tabela([{ titulo: "Data", classe: "d" }, { titulo: "Manchete" }, { titulo: "Veículo" }, { titulo: "Tom" }], linhas));
}

/* ------------------------------------------------------------------ */
/* documentos                                                          */
/* ------------------------------------------------------------------ */

function metaPadrao(ctx, extra = []) {
  const intervalo = intervaloDaSerie(ctx.bruto);
  return [
    ["Órgão", ctx.orgao?.rotulo || ctx.orgao?.nome || "—"],
    ["Período", `${ROTULO_PERIODO[ctx.periodo || ""] || ctx.periodo}${!ctx.periodo && intervalo ? ` (${intervalo})` : ""}`],
    ...extra,
    ["Emitido em", new Date().toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short", timeZone: "America/Cuiaba" })],
  ];
}

function docExecutivo(ctx, g) {
  const d = ctx.dados;
  return (
    capa({
      tipo: "Relatório executivo",
      titulo: `${ctx.orgao?.rotulo || "Órgão"} na mídia`,
      subtitulo: "Síntese do noticiário: volume, tom, pastas, pessoas, territórios, canais e pontos de atenção.",
      meta: metaPadrao(ctx, [["Fonte", "Base de notícias do ValorPúblico"]]),
    }) +
    secao("Resumo do período", "", blocoResumo(d)) +
    blocoEvolucao(d) +
    blocoSecretarias(g) +
    blocoPessoas(g) +
    blocoMunicipios(d, 12) +
    blocoCanais(d) +
    blocoMudou(d) +
    blocoAtencao(d) +
    blocoRedesResumo(d) +
    blocoManchetes(d, 10) +
    notaMetodo()
  );
}

function docGoverno(ctx, g) {
  const d = ctx.dados;
  const porPasta = (g?.secretarias || [])
    .filter((p) => (p.noticias_recentes || []).length)
    .sort((a, b) => Number(b.total_clippings || 0) - Number(a.total_clippings || 0))
    .slice(0, 10)
    .map(
      (p) => `<div class="doc-pasta">
        <h3>${esc(p.pasta?.sigla || p.id)} <small>${esc(p.pasta?.nome || "")} · ${num(p.total_clippings)} notícias</small></h3>
        <ul class="doc-lista">${(p.noticias_recentes || [])
          .slice(0, 3)
          .map((n) => `<li><time>${data(n.data_publicacao || n.data)}</time>${link(semVeiculo(n.titulo, n.veiculo), n.url)}${fonteDe(n)}</li>`)
          .join("")}</ul>
      </div>`
    )
    .join("");
  return (
    capa({
      tipo: "Panorama do Governo",
      titulo: "Governo de Mato Grosso na imprensa",
      subtitulo: "Cobertura do Executivo estadual por secretaria, pessoa e município.",
      meta: metaPadrao(ctx),
    }) +
    secao("Resumo do período", "", blocoResumo(d)) +
    blocoEvolucao(d) +
    blocoSecretarias(g, 0, true) +
    blocoPessoas(g) +
    blocoMunicipios(d, 20) +
    (porPasta ? secao("Últimas notícias das pastas mais citadas", "", porPasta) : "") +
    notaMetodo()
  );
}

function docClipping(ctx) {
  const governoMt = ctx.orgao?.slug === "governo-mt";
  const rec = governoMt ? clippingGoverno.recorteAtual() : null;
  const LIMITE = 600;
  let noticias;
  let filtrosTexto = "Nenhum";
  if (rec?.carregado) {
    noticias = rec.noticias;
    const f = rec.filtros;
    const partes = [
      f.secretaria && `Secretaria: ${f.secretaria}`,
      f.municipio && `Município: ${f.municipio}`,
      f.pessoa && `Pessoa: ${f.pessoa === "governador" ? "governador" : "interino"}`,
      f.escopo && `Escopo: ${f.escopo}`,
      f.tom && `Tom: ${f.tom}`,
      f.veiculo && `Veículo: ${f.veiculo}`,
      f.busca && `Busca: “${f.busca}”`,
    ].filter(Boolean);
    if (partes.length) filtrosTexto = partes.join(" · ");
  } else {
    noticias = (ctx.dados?.noticias_recentes || []).map((n) => ({ ...n, data: n.data_publicacao || n.data }));
  }
  const total = noticias.length;
  const t = { positivo: 0, neutro: 0, negativo: 0 };
  const contar = (campo) => {
    const m = new Map();
    noticias.forEach((n) => {
      const v = Array.isArray(n[campo]) ? n[campo] : [n[campo]];
      v.filter(Boolean).forEach((x) => m.set(x, (m.get(x) || 0) + 1));
    });
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  };
  noticias.forEach((n) => {
    if (t[n.sentimento] !== undefined) t[n.sentimento] += 1;
  });
  t.total = total;
  const veiculos = contar("veiculo");
  const secretarias = contar("siglas");
  const municipios = contar("municipios");
  const colunaTop = (titulo, lista) =>
    lista.length ? `<div><h3>${esc(titulo)}</h3>${barras(lista.slice(0, 6).map(([rotulo, valor]) => ({ rotulo, valor })))}</div>` : "";
  const resumo =
    kpis([
      { rotulo: "Notícias no recorte", valor: num(total), sub: rec?.carregado ? `de ${num(rec.total_periodo)} no período` : "mais recentes", destaque: true },
      { rotulo: "Veículos", valor: num(veiculos.length) },
      { rotulo: "Negativas", valor: `${pct(t.negativo, total)}%`, sub: `${num(t.negativo)} notícias` },
      municipios.length ? { rotulo: "Municípios", valor: num(municipios.length) } : null,
    ]) +
    `<div class="doc-linha">${barraTom(t, { legenda: true })}</div>` +
    `<div class="doc-tres">${colunaTop("Veículos que mais publicaram", veiculos)}${colunaTop("Secretarias mais citadas", secretarias)}${colunaTop("Municípios mais citados", municipios)}</div>`;
  const linhas = noticias.slice(0, LIMITE).map((n) => [
    data(n.data),
    link(rec ? rec.tituloLimpo(n) : semVeiculo(n.titulo, n.veiculo), n.url),
    esc(n.veiculo || "—"),
    esc((n.siglas || []).join(", ") || "—"),
    esc((n.municipios || []).join(", ") || "—"),
    `<span class="doc-etq ${esc(n.sentimento || "neutro")}">${esc(n.sentimento || "neutro")}</span>`,
  ]);
  const colunas = rec?.carregado
    ? [{ titulo: "Data", classe: "d" }, { titulo: "Manchete" }, { titulo: "Veículo" }, { titulo: "Secretaria" }, { titulo: "Município" }, { titulo: "Tom" }]
    : [{ titulo: "Data", classe: "d" }, { titulo: "Manchete" }, { titulo: "Veículo" }, { titulo: "Tom" }];
  const linhasFinal = rec?.carregado ? linhas : linhas.map((l) => [l[0], l[1], l[2], l[5]]);
  return (
    capa({
      tipo: "Clipping",
      titulo: governoMt ? "Clipping do Governo de Mato Grosso" : "Clipping",
      subtitulo: "Notícias publicadas no período, com veículo, pasta, município e tom.",
      meta: metaPadrao(ctx, [["Filtros", filtrosTexto]]),
    }) +
    secao("Resumo do recorte", "", resumo) +
    secao(
      "Notícias",
      total > LIMITE
        ? `Lista das ${num(LIMITE)} notícias mais recentes de ${num(total)}. Para a lista completa, exporte o CSV no painel.`
        : "Da mais recente para a mais antiga. O título leva à notícia original.",
      tabela(colunas, linhasFinal, { classe: "doc-tabela-clipping" }),
      { quebra: true }
    ) +
    notaMetodo()
  );
}

function docRedes(ctx) {
  const d = ctx.dados;
  const r = d?.redes_sociais || {};
  const posts = [...(r.posts || [])].sort((a, b) => Number(b.curtidas || 0) - Number(a.curtidas || 0));
  const miniaturas = ctx.miniaturas || new Map();
  const totalCurtidas = posts.reduce((a, p) => a + Number(p.curtidas || 0), 0);
  const contas = r.contas || [];
  const tomPublico = contas.reduce(
    (a, c) => ({ positivo: a.positivo + (c.tom_publico?.positivo || 0), neutro: a.neutro + (c.tom_publico?.neutro || 0), negativo: a.negativo + (c.tom_publico?.negativo || 0) }),
    { positivo: 0, neutro: 0, negativo: 0 }
  );
  tomPublico.total = tomPublico.positivo + tomPublico.neutro + tomPublico.negativo;
  const cards = posts
    .slice(0, 16)
    .map((p) => {
      const thumb = miniaturas.get(String(p.id_externo || p.shortcode || ""))?.thumb;
      const comentarios = (p.comentarios || []).slice(0, 2);
      return `<div class="doc-post">
        ${thumb ? `<img src="data:image/webp;base64,${thumb}" alt="" />` : '<div class="doc-post-sem"></div>'}
        <div>
          <span class="doc-post-meta">${esc(p.agente || "")} · ${data(p.data)}</span>
          <p>${link((p.texto || p.titulo || "").slice(0, 170) + ((p.texto || "").length > 170 ? "…" : ""), p.url)}</p>
          <span class="doc-post-num"><b>${num(p.curtidas)}</b> curtidas · <b>${num(p.comentarios_total || p.comentarios_coletados)}</b> comentários · <span class="doc-etq ${esc(p.sentimento || "neutro")}">${esc(p.sentimento || "neutro")}</span></span>
          ${comentarios.length ? `<ul class="doc-coment">${comentarios.map((c) => `<li>“${esc(String(c.texto || "").slice(0, 120))}”</li>`).join("")}</ul>` : ""}
        </div>
      </div>`;
    })
    .join("");
  return (
    capa({
      tipo: "Redes sociais",
      titulo: "Redes oficiais do Governo",
      subtitulo: "Instagram de @govmatogrosso e @otavianopivetta: publicações, alcance e reação do público.",
      meta: metaPadrao(ctx, [["Fonte", r.fonte || "Coleta pública do Instagram"]]),
    }) +
    secao(
      "Resumo",
      "",
      kpis([
        { rotulo: "Posts monitorados", valor: num(posts.length), destaque: true },
        { rotulo: "Comentários do público", valor: num(r.comentarios_total) },
        { rotulo: "Curtidas por post", valor: num(posts.length ? Math.round(totalCurtidas / posts.length) : 0) },
        { rotulo: "Saldo do público", valor: `${saldoDe(tomPublico) > 0 ? "+" : ""}${saldoDe(tomPublico)}`, sub: "nos comentários" },
      ]) + `<div class="doc-linha">${barraTom(tomPublico, { legenda: true })}</div>`
    ) +
    blocoRedesResumo(d) +
    (cards ? secao("Posts de maior alcance", "Os posts com mais curtidas no período, com dois comentários do público de cada um.", `<div class="doc-posts">${cards}</div>`) : "") +
    notaMetodo("Coleta pública: só posts e comentários abertos; nenhum dado privado ou mensagem direta.")
  );
}

function blocoDiscurso(disc, titulo) {
  const variantes = disc?.variantes || [];
  if (!variantes.length) return "";
  const html = variantes
    .map((v) => {
      const nomes = nomesDeFontes(v.fontes);
      return `<div class="doc-variante">
        <h3>Versão ${esc(v.id)} · ${esc(v.angulo || "")}${disc.vencedora === v.id ? ' <span class="doc-etq positivo">mais bem recebida</span>' : ""}</h3>
        ${v.tese ? `<p class="doc-tese">${esc(v.tese)}</p>` : ""}
        ${v.tribuna ? `<h4>Discurso</h4><div class="doc-texto">${esc(limparReferencias(v.tribuna, nomes)).replace(/\n+/g, "</p><p>").replace(/^/, "<p>")}</p></div>` : ""}
        ${v.video ? `<h4>Vídeo de 60 segundos</h4><div class="doc-texto"><p>${esc(limparReferencias(v.video, nomes))}</p></div>` : ""}
        ${v.post ? `<h4>Post</h4><div class="doc-texto"><p>${esc(limparReferencias(v.post, nomes))}</p></div>` : ""}
        ${blocoFontes(v)}
      </div>`;
    })
    .join("");
  return secao(titulo, "Rascunho gerado a partir das notícias da semana. A revisão da Secom é obrigatória antes de qualquer uso.", html, { quebra: true });
}

function blocoSimulacao(sim, titulo) {
  const vars = sim?.variantes || [];
  if (!vars.length) return "";
  const linhas = vars.map((v) => [
    `<b>Versão ${esc(v.id)}</b>${sim.vencedora === v.id ? ' <span class="doc-etq positivo">vencedora</span>' : ""}`,
    String(v.adesao ?? "—").replace(".", ","),
    Array.isArray(v.adesao_ic90) ? `${String(v.adesao_ic90[0]).replace(".", ",")} a ${String(v.adesao_ic90[1]).replace(".", ",")}` : "—",
    String(v.polarizacao ?? "—").replace(".", ","),
  ]);
  const riscos = (sim.frases_risco || []).slice(0, 5);
  return secao(
    titulo,
    "Leitura do discurso por 12 personas sintéticas de Mato Grosso. Adesão de 1 a 7; margem de 90%. É hipótese para orientar o texto, não pesquisa de opinião.",
    tabela([{ titulo: "Versão" }, { titulo: "Adesão", classe: "n" }, { titulo: "Margem (90%)", classe: "n" }, { titulo: "Polarização", classe: "n" }], linhas) +
      (riscos.length ? `<h3>Frases que geraram ruído</h3><ul class="doc-lista">${riscos.map((f) => `<li>“${esc(f)}”</li>`).join("")}</ul>` : "")
  );
}

function docSemana(ctx) {
  const rel = ctx.relatorio || {};
  const classes = [...(rel.chd?.classes || [])].sort((a, b) => Number(b.pct || 0) - Number(a.pct || 0));
  const assuntos = classes
    .map(
      (c) => `<div class="doc-assunto">
        <div class="doc-assunto-cab"><b>${esc(c.rotulo || `Grupo ${c.id}`)}</b><span>${String(c.pct).replace(".", ",")}% dos trechos</span></div>
        <span class="doc-trilho"><i style="width:${Math.min(100, Number(c.pct || 0))}%"></i></span>
        ${c.explicacao ? `<p>${esc(c.explicacao)}</p>` : ""}
        ${(c.st_tipicos || []).length ? `<ul class="doc-lista">${c.st_tipicos.slice(0, 2).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
      </div>`
    )
    .join("");
  return (
    capa({
      tipo: "Semana & Discurso",
      titulo: `Relatório da semana ${esc(rel.semana || ctx.semana || "")}`,
      subtitulo: "Os assuntos da semana explicados, o discurso institucional e como ele foi recebido.",
      meta: metaPadrao(ctx, [["Base", rel.periodo_dias ? `notícias dos últimos ${rel.periodo_dias} dias` : "notícias da semana"]]),
    }) +
    (rel.textos?.resumo ? secao("Em síntese", "", leitura(esc(rel.textos.resumo), "Leitura da semana")) : "") +
    (assuntos ? secao("Os assuntos da semana", "Método de Reinert (IRaMuTeQ): trechos de notícias que usam as mesmas palavras formam um assunto.", assuntos) : "") +
    blocoDiscurso(ctx.discurso, "Discurso institucional") +
    blocoSimulacao(ctx.simulacao, "Como o discurso seria recebido") +
    notaMetodo("Discursos e simulações são gerados por IA a partir das notícias e devem ser revisados pela equipe.")
  );
}

function docGovernador(ctx) {
  return (
    capa({
      tipo: "Governador",
      titulo: "Discurso da semana do governador",
      subtitulo: "Três versões com fontes, testadas com personas sintéticas, e o discurso do interino.",
      meta: metaPadrao(ctx, [["Semana", ctx.discursoGovernador?.semana || ctx.semana || ""]]),
    }) +
    (blocoDiscurso(ctx.discursoGovernador, "Discurso do governador") || secao("Discurso do governador", "", leitura("O discurso desta semana ainda não foi gerado."))) +
    blocoSimulacao(ctx.simulacaoGovernador, "Recepção pelas personas") +
    blocoDiscurso(ctx.discursoInterino, "Discurso do governador interino") +
    notaMetodo("Discursos e simulações são gerados por IA a partir das notícias e devem ser revisados pela equipe.")
  );
}

function docTendencias(ctx) {
  const t = ctx.dados?.tendencias || {};
  const bloco = (titulo, lista) => {
    if (!(lista || []).length) return "";
    const linhas = lista.slice(0, 15).map((item, i) => {
      const noticia = (item.noticias || [])[0];
      return [
        `${i + 1}`,
        `<b>${esc(item.termo || item.titulo || item.consulta || noticia?.titulo || "—")}</b>`,
        item.trafego || item.volume ? esc(item.trafego || item.volume) : "—",
        noticia ? `${link(noticia.titulo, noticia.url)} <em>${esc(noticia.fonte || "")}</em>` : "—",
      ];
    });
    return secao(titulo, "", tabela([{ titulo: "#", classe: "n" }, { titulo: "Termo" }, { titulo: "Buscas" }, { titulo: "Notícia relacionada" }], linhas));
  };
  return (
    capa({
      tipo: "Tendências",
      titulo: "O que as pessoas estão buscando",
      subtitulo: "Termos em alta no Google em Mato Grosso e no Brasil, com a notícia que explica cada um.",
      meta: metaPadrao(ctx, [["Fonte", `Google Trends${t.atualizado_em ? ` · ${data(t.atualizado_em)}` : ""}`]]),
    }) +
    (bloco("Em alta em Mato Grosso", t.em_alta_mt) || "") +
    (bloco("Em alta no Brasil", t.em_alta_br) || "") +
    notaMetodo("Tendências vêm do Google Trends (dados públicos agregados) e mostram interesse de busca, não opinião.")
  );
}

/** Tom da persona em português legível (a base grava sem acento em alguns). */
const TONS_PERSONA = {
  pragmatico: "pragmático",
  analitico: "analítico",
  critico: "crítico",
  cetico: "cético",
  esperancoso: "esperançoso",
  autonomo: "autônomo",
  lideranca: "liderança",
};

function tomLegivel(persona) {
  const bruto = String(persona?.tom || persona?.tom_base || "").trim();
  if (!bruto) return "—";
  const chave = bruto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return TONS_PERSONA[chave] || bruto.charAt(0).toUpperCase() + bruto.slice(1);
}

function docPersonas(ctx) {
  const lista = personas.contextoDocumentos().personas || [];
  const linhas = lista.map((p) => [
    `<b>${esc(p.rotulo || p.id || "")}</b>`,
    esc([p.idade, p.genero].filter(Boolean).join(" · ")),
    esc(p.regiao || "—"),
    esc(p.escolaridade || "—"),
    esc((Array.isArray(p.interesses) ? p.interesses.join(", ") : p.interesses) || "—"),
    esc(tomLegivel(p)),
  ]);
  return (
    capa({
      tipo: "Laboratório",
      titulo: "Personas sintéticas de Mato Grosso",
      subtitulo: "Perfis usados para testar a recepção dos discursos. Não são pessoas reais nem pesquisa de opinião.",
      meta: metaPadrao(ctx, [["Personas", num(lista.length)]]),
    }) +
    secao(
      "Perfis",
      "Cada perfil reúne idade, região, escolaridade, interesses e o tom de quem é. São hipóteses de trabalho: nenhum número aqui representa a opinião de mattogrossenses.",
      lista.length
        ? tabela([{ titulo: "Persona" }, { titulo: "Idade" }, { titulo: "Região" }, { titulo: "Escolaridade" }, { titulo: "Interesses" }, { titulo: "Tom" }], linhas)
        : leitura("Nenhuma persona publicada para este órgão.")
    ) +
    notaMetodo("Personas sintéticas são hipóteses de trabalho; nenhuma conclusão deve ser apresentada como opinião pública.")
  );
}

const MONTADORES = {
  executivo: docExecutivo,
  governo: docGoverno,
  clipping: docClipping,
  redes: docRedes,
  semana: docSemana,
  governador: docGovernador,
  tendencias: docTendencias,
  personas: docPersonas,
};

const TITULOS = {
  executivo: "Relatório executivo",
  governo: "Panorama do Governo",
  clipping: "Clipping",
  redes: "Redes oficiais",
  semana: "Relatório da semana",
  governador: "Discurso do governador",
  tendencias: "Tendências",
  personas: "Personas",
};

/** Monta o documento em #documento (sem imprimir). */
export function montar(tipo) {
  const ctx = telas.contextoDocumentos();
  const g = ctx.orgao?.slug === "governo-mt" ? governo.contextoDocumentos() : null;
  contadorSecao = 0;
  const html = (MONTADORES[tipo] || docExecutivo)(ctx, g);
  let alvo = document.getElementById("documento");
  if (!alvo) {
    alvo = document.createElement("div");
    alvo.id = "documento";
    document.body.appendChild(alvo);
  }
  alvo.className = `doc doc-${tipo}`;
  alvo.innerHTML = html;
  montarSumario(alvo);
  return alvo;
}

/** Lista as seções do documento na capa (para o leitor saber o que vai encontrar). */
function montarSumario(alvo) {
  const corpo = alvo.querySelector(".doc-capa-corpo");
  if (!corpo) return;
  const secoes = [...alvo.querySelectorAll(".doc-secao > h2")].map((h) => {
    const num = h.querySelector(".doc-num")?.textContent || "";
    const titulo = h.textContent.replace(num, "").trim();
    return { num, titulo };
  });
  if (secoes.length < 2) return;
  corpo.insertAdjacentHTML(
    "beforeend",
    `<ul class="doc-sumario">${secoes.map((s) => `<li><span>${esc(s.num)}</span>${esc(s.titulo)}</li>`).join("")}</ul>`
  );
}

function limpar() {
  document.body.classList.remove("imprimindo-doc");
  document.getElementById("documento")?.remove();
  if (tituloAnterior) document.title = tituloAnterior;
  tituloAnterior = "";
}

let tituloAnterior = "";

/** Monta e imprime (o navegador oferece "Salvar como PDF"). */
export function imprimir(tipo) {
  montar(tipo);
  const ctx = telas.contextoDocumentos();
  tituloAnterior = document.title;
  const dataArq = new Date().toISOString().slice(0, 10);
  document.title = `${TITULOS[tipo] || "Relatório"} - ${ctx.orgao?.rotulo || "ValorPublico"} - ${dataArq}`;
  document.body.classList.add("imprimindo-doc");
  window.addEventListener("afterprint", limpar, { once: true });
  window.print();
}

if (typeof window !== "undefined") {
  window.__documentos = { montar, imprimir, limpar };
}
