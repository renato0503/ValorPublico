/**
 * Roteador por hash — ValorPúblico (seções do painel institucional).
 */

const TELAS = {
  painel: { titulo: "Painel", eyebrow: "Edição institucional" },
  midia: { titulo: "Mídia", eyebrow: "Veículos e audiência" },
  parlamentares: { titulo: "Parlamentares", eyebrow: "Espaço e tom" },
  inteligencia: { titulo: "Inteligência", eyebrow: "Radar e conteúdo" },
  relatorios: { titulo: "Relatórios", eyebrow: "Pranchas" },
  sistema: { titulo: "Sistema", eyebrow: "Operação" },
};

const APP = "ValorPúblico";

function rotaDoHash() {
  const bruta = window.location.hash.replace(/^#\/?/, "").trim();
  return TELAS[bruta] ? bruta : "painel";
}

function aplicar(rota) {
  const alvo = TELAS[rota] ? rota : "painel";

  document.querySelectorAll(".tela").forEach((tela) => {
    tela.classList.toggle("ativa", tela.dataset.tela === alvo);
  });

  document.querySelectorAll("[data-rota]").forEach((link) => {
    const ativo = link.dataset.rota === alvo;
    link.classList.toggle("ativo", ativo);
    if (ativo) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  const info = TELAS[alvo];
  document.title = `${info.titulo} · ${APP}`;
  window.scrollTo({ top: 0 });
  document.documentElement.dataset.rota = alvo;
  document.dispatchEvent(new CustomEvent("rota:changed", { detail: { rota: alvo } }));
}

export function iniciarRouter() {
  const irPara = (rota) => {
    if (!TELAS[rota]) return;
    const hash = `#/${rota}`;
    if (window.location.hash === hash) aplicar(rota);
    else window.location.hash = hash;
  };

  window.addEventListener("hashchange", () => aplicar(rotaDoHash()));
  if (!window.location.hash) {
    history.replaceState(null, "", "#/" + rotaDoHash());
  }
  aplicar(rotaDoHash());

  document.getElementById("btnFiltros")?.addEventListener("click", (e) => {
    const aberto = document.querySelector(".masthead")?.classList.toggle("filtros-aberto");
    e.currentTarget.setAttribute("aria-expanded", String(!!aberto));
  });

  window.__router = { irPara, rotaAtual: rotaDoHash };
}
