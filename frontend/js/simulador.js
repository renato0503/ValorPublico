/**
 * Simulador de discurso próprio.
 *
 * O usuário cola um discurso na tela Personas e as 12 personas sintéticas do
 * Governo de MT reagem de uma vez: aderência, risco, o que funcionou, o que
 * incomoda e o que reescrever antes de publicar.
 *
 * Contrato da API (Cloud Run `personas-api`):
 *   POST /v1/discurso/simular  { discurso: string }
 *   -> { resumo, veredito, pontos_fortes, melhorias[], personas[] }
 */

import { escapar } from "./componentes.js";
import { estadoAuth } from "./auth.js";

const MIN_CARACTERES = 80;

const estado = {
  rodando: false,
  ultimo: null,
};

function apiUrl() {
  return (
    window.__PERSONAS_API_URL ||
    document.querySelector('meta[name="personas-api"]')?.content ||
    ""
  );
}

function campo() {
  return document.getElementById("discursoProprio");
}

function alvo() {
  return document.getElementById("simDiscursoResultado");
}

function numero(valor, casas = 1) {
  const n = Number(valor || 0);
  return n.toFixed(casas).replace(".", ",");
}

/** Contador de palavras/caracteres do campo de discurso. */
function atualizarContador() {
  const texto = (campo()?.value || "").trim();
  const palavras = texto ? texto.split(/\s+/).length : 0;
  const marca = document.getElementById("discursoContador");
  if (marca) {
    marca.textContent = `${palavras} ${palavras === 1 ? "palavra" : "palavras"} · ${texto.length} caracteres`;
    marca.classList.toggle("sim-contador-curto", texto.length > 0 && texto.length < MIN_CARACTERES);
  }
  const botao = document.getElementById("btnDiscursoAvaliar");
  if (botao && !estado.rodando) {
    botao.disabled = !apiUrl() || texto.length < MIN_CARACTERES;
  }
}

function faixaAderencia(valor) {
  const n = Number(valor || 0);
  if (n >= 7) return "sim-faixa-alta";
  if (n >= 4) return "sim-faixa-media";
  return "sim-faixa-baixa";
}

function prioridadeClasse(p) {
  if (p === "alta") return "sim-prio-alta";
  if (p === "baixa") return "sim-prio-baixa";
  return "sim-prio-media";
}

function prioridadeTexto(p) {
  if (p === "alta") return "Prioridade alta";
  if (p === "baixa") return "Ajuste fino";
  return "Prioridade média";
}

function cartaoKpi(rotulo, valor, unidade, nota) {
  return `<div class="sim-kpi">
    <span class="sim-kpi-rotulo">${escapar(rotulo)}</span>
    <span class="sim-kpi-valor">${escapar(valor)}${unidade ? `<small>${escapar(unidade)}</small>` : ""}</span>
    <span class="sim-kpi-nota">${escapar(nota)}</span>
  </div>`;
}

function renderizarKpis(resumo, dados) {
  return `<div class="sim-kpis">
    ${cartaoKpi(
      "Aderência média",
      numero(resumo?.aderencia_media),
      "/10",
      `entre ${numero(resumo?.aderencia_min)} e ${numero(resumo?.aderencia_max)}`
    )}
    ${cartaoKpi(
      "Personas que aderiram",
      String(resumo?.personas_alta ?? 0),
      `/${resumo?.total_personas ?? 0}`,
      `${resumo?.personas_baixa ?? 0} não se convenceram`
    )}
    ${cartaoKpi(
      "Risco de rejeição",
      numero((Number(resumo?.risco_medio || 0) * 100), 0),
      "%",
      "média das 12 personas"
    )}
    ${cartaoKpi("Melhorias apontadas", String((dados?.melhorias || []).length), "", "em ordem de impacto")}
  </div>`;
}

function renderizarMelhorias(melhorias) {
  if (!melhorias.length) {
    return `<p class="sim-vazio">Nenhuma melhoria apontada.</p>`;
  }
  return `<ol class="sim-melhorias">${melhorias
    .map(
      (m) => `<li class="sim-melhoria">
        <div class="sim-melhoria-cab">
          <span class="sim-prio ${prioridadeClasse(m.prioridade)}">${escapar(prioridadeTexto(m.prioridade))}</span>
          <strong>${escapar(m.titulo || "")}</strong>
        </div>
        ${m.como_reescrever ? `<p class="sim-melhoria-como">${escapar(m.como_reescrever)}</p>` : ""}
        ${
          (m.personas || []).length
            ? `<span class="sim-melhoria-personas">Apontado por: ${escapar(m.personas.join(", "))}</span>`
            : ""
        }
      </li>`
    )
    .join("")}</ol>`;
}

function renderizarPersona(p) {
  const nota = Number(p.aderencia || 0);
  const citacoes = (p.citacoes || [])
    .filter((c) => c.url)
    .slice(0, 2)
    .map((c) => `<a href="${escapar(c.url)}" target="_blank" rel="noopener">${escapar(c.titulo || "fonte")}</a>`)
    .join(" · ");
  return `<article class="sim-persona ${faixaAderencia(nota)}">
    <header class="sim-persona-cab">
      <span class="sim-persona-nome">${escapar(p.rotulo || p.id || "")}</span>
      <span class="sim-persona-nota">${numero(nota)}</span>
    </header>
    <div class="sim-barra"><i style="width:${Math.max(4, Math.min(100, nota * 10))}%"></i></div>
    ${p.primeira_impressao ? `<p class="sim-persona-frase">“${escapar(p.primeira_impressao)}”</p>` : ""}
    <dl class="sim-persona-lista">
      ${
        p.o_que_funciona
          ? `<dt>Convinceu</dt><dd class="sim-ok">${escapar(p.o_que_funciona)}</dd>`
          : ""
      }
      ${
        p.o_que_incomoda
          ? `<dt>Incomodou</dt><dd class="sim-risco">${escapar(p.o_que_incomoda)}</dd>`
          : ""
      }
      ${p.sugestao ? `<dt>Sugestão</dt><dd>${escapar(p.sugestao)}</dd>` : ""}
    </dl>
    ${citacoes ? `<span class="sim-persona-fontes">Fontes: ${citacoes}</span>` : ""}
  </article>`;
}

/** Renderiza um resultado (exportado para teste e para o harness visual). */
export function renderizar(dados) {
  const caixa = alvo();
  if (!caixa) return;
  const resumo = dados?.resumo || {};
  const pontos = dados?.pontos_fortes || [];
  const personas = dados?.personas || [];
  caixa.innerHTML = `
    <div class="sim-resultado">
      ${renderizarKpis(resumo, dados)}
      ${
        dados?.veredito
          ? `<div class="sim-veredito">
              <span class="sim-rotulo">Leitura do texto</span>
              <p>${escapar(dados.veredito)}</p>
            </div>`
          : ""
      }
      <section class="sim-bloco">
        <h3 class="sim-bloco-titulo">O que melhorar antes de publicar</h3>
        ${renderizarMelhorias(dados?.melhorias || [])}
      </section>
      ${
        pontos.length
          ? `<section class="sim-bloco">
              <h3 class="sim-bloco-titulo">O que funcionou</h3>
              <ul class="sim-fortes">${pontos.map((p) => `<li>${escapar(p)}</li>`).join("")}</ul>
            </section>`
          : ""
      }
      <section class="sim-bloco">
        <h3 class="sim-bloco-titulo">Reação de cada persona</h3>
        <div class="sim-personas-grade">${personas.map(renderizarPersona).join("")}</div>
      </section>
      <p class="selo-simulacao">${escapar(
        dados?.aviso || "Simulação (hipótese) — não é pesquisa de opinião."
      )} Nenhuma pessoa real foi consultada.</p>
    </div>`;
}

function renderizarCarregando() {
  const caixa = alvo();
  if (!caixa) return;
  caixa.innerHTML = `
    <div class="sim-resultado sim-carregando">
      <div class="sim-kpis">
        ${Array.from({ length: 4 })
          .map(() => `<div class="sim-kpi sim-kpi-fantasma"><span class="sim-kpi-valor">—</span></div>`)
          .join("")}
      </div>
      <p class="sim-aviso-rodape">As 12 personas estão lendo o texto e escrevendo a reação de cada uma. Isso leva de 20 a 60 segundos.</p>
    </div>`;
}

function renderizarErro(mensagem) {
  const caixa = alvo();
  if (!caixa) return;
  caixa.innerHTML = `
    <div class="sim-resultado sim-erro">
      <p class="sim-erro-texto">${escapar(mensagem)}</p>
      <button class="btn-texto" id="btnDiscursoTentar" type="button">Tentar de novo</button>
    </div>`;
  document.getElementById("btnDiscursoTentar")?.addEventListener("click", () => avaliar());
}

/** Texto simples para colar no WhatsApp/e-mail da equipe. */
function resumoTexto(dados) {
  const linhas = [];
  const resumo = dados?.resumo || {};
  linhas.push(
    `Simulação de discurso · aderência média ${numero(resumo.aderencia_media)}/10 · ` +
      `${resumo.personas_alta}/${resumo.total_personas} personas aderiram`
  );
  if (dados?.veredito) linhas.push(`Leitura: ${dados.veredito}`);
  if (dados?.melhorias?.length) {
    linhas.push("", "O que melhorar:");
    dados.melhorias.forEach((m, i) => {
      linhas.push(`${i + 1}. ${m.titulo}${m.como_reescrever ? ` — ${m.como_reescrever}` : ""}`);
    });
  }
  if (dados?.pontos_fortes?.length) {
    linhas.push("", "O que funcionou:");
    dados.pontos_fortes.forEach((p) => linhas.push(`- ${p}`));
  }
  linhas.push("", "Simulação (hipótese) — não é pesquisa de opinião.");
  return linhas.join("\n");
}

async function copiarResumo() {
  if (!estado.ultimo) return;
  const texto = resumoTexto(estado.ultimo);
  try {
    await navigator.clipboard.writeText(texto);
    const botao = document.getElementById("btnDiscursoCopiar");
    if (botao) {
      const antes = botao.textContent;
      botao.textContent = "Copiado";
      setTimeout(() => {
        botao.textContent = antes;
      }, 1600);
    }
  } catch {
    console.warn("[Simulador] não foi possível copiar o resumo.");
  }
}

async function avaliar() {
  if (estado.rodando) return;
  const texto = (campo()?.value || "").trim();
  if (texto.length < MIN_CARACTERES) {
    renderizarErro(`Cole um discurso com pelo menos ${MIN_CARACTERES} caracteres para a simulação.`);
    return;
  }
  const url = apiUrl();
  if (!url) {
    renderizarErro("A API das personas ainda não está publicada. A simulação fica disponível em breve.");
    return;
  }
  estado.rodando = true;
  const botao = document.getElementById("btnDiscursoAvaliar");
  if (botao) {
    botao.disabled = true;
    botao.textContent = "Avaliando com as 12 personas…";
  }
  renderizarCarregando();
  try {
    const token = await estadoAuth.usuario?.getIdToken?.();
    const resposta = await fetch(`${url.replace(/\/$/, "")}/v1/discurso/simular`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ discurso: texto }),
    });
    if (!resposta.ok) {
      let detalhe = `HTTP ${resposta.status}`;
      try {
        const corpo = await resposta.json();
        if (corpo?.detail) detalhe = corpo.detail;
      } catch {
        /* resposta sem corpo */
      }
      throw new Error(detalhe);
    }
    const dados = await resposta.json();
    estado.ultimo = dados;
    renderizar(dados);
    const copiar = document.getElementById("btnDiscursoCopiar");
    if (copiar) copiar.disabled = false;
  } catch (erro) {
    console.warn("[Simulador] falha na simulação:", erro?.message || erro);
    renderizarErro(
      erro?.message?.includes("429")
        ? "Limite de simulações por hora atingido. Tente mais tarde."
        : "Não foi possível rodar a simulação agora. Tente novamente em instantes."
    );
  } finally {
    estado.rodando = false;
    if (botao) {
      botao.disabled = false;
      botao.textContent = "Avaliar com as 12 personas";
    }
    atualizarContador();
  }
}

function limpar() {
  if (campo()) campo().value = "";
  estado.ultimo = null;
  const caixa = alvo();
  if (caixa) caixa.innerHTML = "";
  const copiar = document.getElementById("btnDiscursoCopiar");
  if (copiar) copiar.disabled = true;
  atualizarContador();
}

/** Liga os controles da tela (uma vez, no boot). */
export function iniciar() {
  const botao = document.getElementById("btnDiscursoAvaliar");
  if (botao && botao.dataset.simuladorPronto === "1") return;
  botao?.setAttribute("data-simulador-pronto", "1");
  botao?.addEventListener("click", () => avaliar());
  document.getElementById("btnDiscursoLimpar")?.addEventListener("click", () => limpar());
  document.getElementById("btnDiscursoCopiar")?.addEventListener("click", () => copiarResumo());
  campo()?.addEventListener("input", atualizarContador);
  const aviso = document.getElementById("simDiscursoAviso");
  if (aviso) {
    aviso.textContent = apiUrl()
      ? "As 12 personas são sintéticas. Nenhuma pessoa real é consultada e o texto não é publicado."
      : "A simulação será liberada quando a API das personas estiver publicada.";
  }
  atualizarContador();
}

export default { iniciar, avaliar, limpar, renderizar };
