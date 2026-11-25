import argparse
import json
import os
import random
import re
import string
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
MAP = {
    "edicao": "edicao", "midia": "midia", "parlamentares": "parlamentares",
    "radar": "radar", "inteligencia": "analise", "clipping": "clipping",
    "imagem": "imagem", "ouvidoria": "ouvidoria", "governo": "governo",
    "governador": "governador", "simulacao": "simulacao", "personas": "personas",
    "semana": "semana", "redes": "redes", "conformidade": "conformidade",
    "tendencias": "tendencias", "relatorios": "relatorios", "sistema": "sistema",
}


def access_token():
    token = os.getenv("GCLOUD_TOKEN", "").strip()
    if token:
        return token
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()


def api_key():
    cfg = (ROOT / "frontend" / "firebase-config.js").read_text(encoding="utf-8")
    return re.search(r'apiKey:\s*"([^"]+)"', cfg).group(1)


def close_ui(page):
    page.evaluate("""() => {
      document.querySelectorAll('.modal-overlay').forEach((e) => {
        e.classList.add('oculto'); e.setAttribute('aria-hidden', 'true');
      });
      document.querySelectorAll('.popup-explicacao').forEach((e) => e.remove());
      document.body.classList.remove('filtros-aberto', 'menu-aberto',
        'print-clipping', 'print-redes', 'print-tendencias', 'print-personas',
        'print-governo', 'print-relatorio');
    }""")


def overflow(page):
    return page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")


def main():
    parser = argparse.ArgumentParser(description="Auditoria de cliente do ValorPúblico.")
    parser.add_argument("--url", default="https://valorpublico.web.app/")
    parser.add_argument("--project", default="valorpublico-b1e6d")
    parser.add_argument("--saida", default="")
    args = parser.parse_args()

    out = Path(args.saida or tempfile.mkdtemp(prefix="valor-cliente-"))
    out.mkdir(parents=True, exist_ok=True)
    email = "qa.cliente." + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10)) + "@example.com"
    password = "".join(random.choice(string.ascii_letters + string.digits + "!@#%") for _ in range(24))
    admin = {"Authorization": f"Bearer {access_token()}", "x-goog-user-project": args.project}
    base = "https://identitytoolkit.googleapis.com/v1"
    uid = None
    result = {"screens": {}, "actions": [], "falhas": [], "errors": [], "console": [], "http": []}

    def ok(name, detail=""):
        result["actions"].append({"name": name, "ok": True, "detail": str(detail)})

    def fail(name, detail):
        result["actions"].append({"name": name, "ok": False, "detail": str(detail)[:300]})
        result["falhas"].append({"name": name, "detail": str(detail)[:300]})

    try:
        response = requests.post(f"{base}/projects/{args.project}/accounts", headers=admin, json={"email": email, "password": password, "emailVerified": True}, timeout=30)
        response.raise_for_status()
        uid = response.json()["localId"]
        requests.post(f"{base}/projects/{args.project}/accounts:update", headers=admin, json={"localId": uid, "customAttributes": json.dumps({"orgao": "governo-mt", "papel": "secom"})}, timeout=30).raise_for_status()
        requests.patch(f"https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/usuarios/{uid}", headers=admin, json={"fields": {"orgao": {"stringValue": "governo-mt"}, "papel": {"stringValue": "secom"}, "email": {"stringValue": email}}}, timeout=30).raise_for_status()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True, permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            page.on("pageerror", lambda e: result["errors"].append(str(e)))
            page.on("console", lambda m: result["console"].append(m.text) if m.type == "error" else None)
            page.on("response", lambda r: result["http"].append({"status": r.status, "url": r.url}) if r.status >= 400 else None)
            page.goto(args.url, wait_until="domcontentloaded")
            page.fill("#loginEmail", email)
            page.fill("#loginSenha", password)
            page.wait_for_function("() => { const b = document.getElementById('btnEntrar'); return b && !b.disabled; }", timeout=30000)
            page.click("#btnEntrar")
            page.wait_for_function("() => !!window.__app_test?.estado?.db", timeout=60000)
            page.wait_for_timeout(1000)
            if page.locator('#orgaoCards a[data-orgao="governo-mt"]').count():
                page.click('#orgaoCards a[data-orgao="governo-mt"]')
                page.wait_for_timeout(700)
            page.evaluate("() => { window.print = () => { window.__prints = (window.__prints || 0) + 1; }; }")

            for tela, rota in MAP.items():
                page.evaluate("(r) => window.__app_test.irPara(r)", rota)
                page.wait_for_timeout(550)
                result["screens"][tela] = {"ativo": page.evaluate("() => document.querySelector('.tela.ativa')?.dataset.tela"), "desktop_overflow": overflow(page)}
                page.screenshot(path=str(out / f"{tela}-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(300)
                result["screens"][tela]["mobile_overflow"] = overflow(page)
                page.screenshot(path=str(out / f"{tela}-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 900})
                page.wait_for_timeout(200)
                close_ui(page)

            def click(selector, name, timeout=2500):
                el = page.locator(selector)
                if not el.count():
                    fail(name, "elemento ausente"); return
                if not el.first.is_visible():
                    fail(name, "elemento invisivel"); return
                if not el.first.is_enabled():
                    fail(name, "elemento desabilitado"); return
                try:
                    el.first.click(timeout=timeout); page.wait_for_timeout(220); ok(name)
                except Exception as exc:
                    fail(name, exc)

            def go(rota):
                page.evaluate("(r) => window.__app_test.irPara(r)", rota)
                page.wait_for_timeout(450)
                close_ui(page)

            go("edicao")
            click("#btnTema", "tema")
            click("#btnSidebar", "sidebar")
            click("#btnFiltros", "filtros")
            page.select_option("#filtroPeriodo", "7d")
            click("#btnFecharFiltros", "fechar_filtros")
            click("#btnRelatorio", "relatorio")
            close_ui(page)

            go("clipping")
            page.fill("#filtroClipBusca", "saúde")
            click("#btnBaixarPdfClipping", "clipping_pdf")
            close_ui(page)

            go("redes")
            page.fill("#filtroRedesBusca", "Pivetta")
            page.select_option("#filtroRedesTom", "negativo")
            click("#btnBaixarPdfRedes", "redes_pdf")
            close_ui(page)

            go("governo")
            page.select_option("#filtroGovSecretaria", index=1)
            click("#btnBaixarPdfGoverno", "governo_pdf")
            for selector, name in [("#btnExportarGoverno", "governo_csv"), ("#btnExportarSecretarias", "secretarias_csv"), ("#btnExportarGovernador", "governador_csv")]:
                try:
                    with page.expect_download(timeout=4000):
                        page.locator(selector).click()
                    ok(name)
                except Exception as exc:
                    fail(name, exc)
            close_ui(page)

            go("governador")
            page.select_option("#filtroSemanaGovernador", index=1)
            click("#btnBaixarPdfGovernador", "governador_pdf")
            click("#btnCopiarDiscursoGovernador", "governador_copiar")
            close_ui(page)

            go("semana")
            page.select_option("#filtroSemana", index=1)
            page.locator("[data-semana-aba='discurso']").click()
            click("#btnBaixarPdfSemanal", "semana_pdf")
            close_ui(page)

            go("radar")
            click("#btnNewsletterDsm", "radar_newsletter")
            close_ui(page)

            go("analise")
            page.locator(".lex-tab[data-lex='chd']").click()
            page.locator("[data-lex-dados]").first.click()
            close_ui(page)

            go("personas")
            page.select_option("#chatPersona", index=1)
            click("#btnBaixarPdfPersonas", "personas_pdf")
            close_ui(page)

            go("tendencias")
            page.select_option("#filtroTendGeo", index=1)
            click("#btnBaixarPdfTendencias", "tendencias_pdf")
            close_ui(page)

            go("relatorios")
            click("#btnAbrirRelatorio", "relatorios_abrir")
            close_ui(page)
            click("#btnAbrirNewsletter", "relatorios_newsletter")
            close_ui(page)

            go("conformidade")
            investigar = page.locator("#btnInvestigar")
            if investigar.count() and investigar.first.is_disabled():
                ok("conformidade_investigar_desabilitado")
            else:
                fail("conformidade_investigar_desabilitado", "botao deveria estar desabilitado")

            go("sistema")
            click("#btnTemaConta", "sistema_tema")
            click("#toggleValorMidia", "sistema_valor_midia")

            page.locator("#btnAuth").click(timeout=4000)
            page.wait_for_timeout(500)
            result["logout"] = page.locator("#btnEntrar").is_visible()
            browser.close()
    finally:
        if uid:
            try:
                requests.delete(f"https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/usuarios/{uid}", headers=admin, timeout=30)
            except Exception:
                pass
            try:
                requests.post(f"{base}/projects/{args.project}/accounts:delete", headers=admin, json={"localId": uid}, timeout=30).raise_for_status()
            except Exception:
                pass

    noise = ("firestore.googleapis.com/google.firestore.v1.Firestore/Listen", "assets/motion/")
    result["http"] = [item for item in result["http"] if not any(n in item["url"] for n in noise)]
    result["screens_com_overflow"] = [name for name, data in result["screens"].items() if data.get("desktop_overflow") or data.get("mobile_overflow")]
    result["actualizado_em"] = datetime.now().isoformat()
    (out / "resultado.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "saida": str(out),
        "telas": len(result["screens"]),
        "acoes_ok": sum(1 for a in result["actions"] if a["ok"]),
        "falhas": len(result["falhas"]),
        "screens_com_overflow": result["screens_com_overflow"],
        "pageerrors": result["errors"][:3],
        "console_errors": result["console"][:3],
        "http_errors": result["http"][:3],
        "logout": result.get("logout"),
    }, ensure_ascii=False, indent=2))
    return 1 if result["falhas"] or result["errors"] or result["screens_com_overflow"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
