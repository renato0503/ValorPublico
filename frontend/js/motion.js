/**
 * Camada de movimento do painel (build-time: Remotion + three.js).
 * - splash do PWA (standalone), uma vez por sessão
 * - faixa 3D na troca de escopo (cidade/agente/período/tema)
 * - faixa 3D na troca de aba da análise
 * - banner do login em 16:9 ou 9:16
 * - painel de filtros no mobile
 * Tudo respeita prefers-reduced-motion.
 */
export function iniciarMotion() {
  const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const topo = document.querySelector(".topo");
  const btnFiltros = document.getElementById("btnFiltros");
  const resumo = document.getElementById("filtrosResumo");
  const banner = document.querySelector(".login-capa video, .login-cena video, .login-banner video");

  const videos = Array.from(document.querySelectorAll("video")).filter(
    (v) => v.closest(".transicao-faixa, .splash-pwa") || v === banner
  );

  const overlayFaixa = document.getElementById("transicaoFaixa");
  const overlayAba = document.getElementById("transicaoAba");
  const splash = document.getElementById("splashPwa");

  if (reduzir) {
    overlayFaixa?.remove();
    overlayAba?.remove();
    splash?.remove();
    videos.forEach((v) => {
      v.autoplay = false;
      v.pause();
    });
    if (btnFiltros) btnFiltros.hidden = true;
    return;
  }

  /** Toca um overlay (faixa/aba) e some ao terminar. */
  const tocar = (overlay) => {
    if (!overlay) return;
    const video = overlay.querySelector("video");
    if (!video || overlay.dataset.tocando === "1") return;
    overlay.dataset.tocando = "1";
    overlay.classList.add("tocando");
    try {
      video.currentTime = 0;
      video.play().catch(() => {});
    } catch {
      /* autoplay bloqueado: só pisca */
    }
    const encerrar = () => {
      overlay.classList.remove("tocando");
      overlay.dataset.tocando = "0";
      video.removeEventListener("ended", encerrar);
    };
    video.addEventListener("ended", encerrar);
    window.setTimeout(encerrar, 1600);
  };

  const tocarFaixa = () => tocar(overlayFaixa);
  const tocarAba = () => tocar(overlayAba);

  // Banner do login: 9:16 no celular em pé, 16:9 no desktop.
  if (banner) {
    if (window.matchMedia("(max-width: 700px) and (orientation: portrait)").matches) {
      banner.src = "assets/motion/splash-vertical.mp4";
    }
    banner.play?.().catch(() => {});
  }

  // Splash só no PWA instalado e uma vez por sessão.
  const standalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  if (splash && standalone && !sessionStorage.getItem("splashVisto")) {
    sessionStorage.setItem("splashVisto", "1");
    const video = splash.querySelector("video");
    if (video) {
      video.src = window.innerHeight >= window.innerWidth
        ? "assets/motion/splash-vertical.mp4"
        : "assets/motion/splash-desktop.mp4";
      splash.classList.add("ativo");
      video.play().catch(() => {});
      let saiu = false;
      const sair = () => {
        if (saiu) return;
        saiu = true;
        splash.classList.add("saindo");
        window.setTimeout(() => splash.remove(), 420);
      };
      video.addEventListener("ended", sair);
      window.setTimeout(sair, 3400);
    }
  } else {
    splash?.remove();
  }

  // A faixa é carregada sob demanda em `tocarFaixa` (evita request abortado).

  const fecharPainel = () => {
    topo?.classList.remove("filtros-aberto");
    btnFiltros?.setAttribute("aria-expanded", "false");
  };

  const atualizarResumo = () => {
    const agente = document.getElementById("filtroParlamentar");
    const periodo = document.getElementById("filtroPeriodo");
    const txtAgente = agente?.selectedOptions?.[0]?.textContent?.trim() ?? "";
    const txtPeriodo = periodo?.selectedOptions?.[0]?.textContent?.trim() ?? "";
    if (resumo) {
      resumo.textContent = [txtAgente, txtPeriodo.toLowerCase()]
        .filter(Boolean)
        .join(" · ");
    }
  };

  ["filtroCidade", "filtroParlamentar", "filtroPeriodo"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      tocarFaixa();
      atualizarResumo();
      fecharPainel();
    });
  });

  document.getElementById("btnTema")?.addEventListener("click", tocarFaixa);

  document.querySelectorAll(".analise-tab").forEach((tab) => {
    tab.addEventListener("click", tocarAba);
  });

  btnFiltros?.addEventListener("click", () => {
    const aberto = topo?.classList.toggle("filtros-aberto") ?? false;
    btnFiltros.setAttribute("aria-expanded", String(aberto));
  });

  document.addEventListener("click", (e) => {
    if (!topo?.classList.contains("filtros-aberto")) return;
    if (topo.contains(e.target)) return;
    fecharPainel();
  });

  atualizarResumo();
  window.__motion = { tocarFaixa, tocarAba };
}
