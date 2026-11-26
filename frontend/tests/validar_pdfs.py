"""Gera e confere todos os PDFs exportáveis do ValorPúblico (frente do Governo).

Para cada botão de PDF: abre a tela, aciona o botão (a impressão é interceptada),
gera o PDF A4 como o navegador faria, converte as páginas em PNG e mede
problemas objetivos: páginas em branco, texto cortado na margem, elementos
de interface (botões, filtros) que vazaram para o documento.

    python frontend/tests/validar_pdfs.py --url http://localhost:8765/ --saida <pasta>

Cria um usuário temporário `qa.pdf.*` (papel secom, órgão governo-mt) e o apaga no fim.
"""

import argparse
import json
import os
import random
import string
import subprocess
import tempfile
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

# (nome do arquivo, rota, passos antes do botão, seletor do botão)
RELATORIOS = [
    ("01-relatorio-executivo", "relatorios", ["#btnAbrirRelatorio"], "#btnExportarPdf", "executivo"),
    ("02-governo", "governo", [], "#btnBaixarPdfGoverno", "governo"),
    ("03-clipping", "clipping", [], "#btnBaixarPdfClipping", "clipping"),
    ("04-redes", "redes", [], "#btnBaixarPdfRedes", "redes"),
    ("05-semana", "semana", [], "#btnBaixarPdfSemanal", "semana"),
    ("06-governador", "governador", [], "#btnBaixarPdfGovernador", "governador"),
    ("07-tendencias", "tendencias", [], "#btnBaixarPdfTendencias", "tendencias"),
    ("08-personas", "personas", [], "#btnBaixarPdfPersonas", "personas"),
]


def token():
    t = os.getenv("GCLOUD_TOKEN", "").strip()
    return t or subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True, shell=os.name == "nt").strip()


def analisar_pdf(caminho: Path, pasta_png: Path) -> dict:
    import pymupdf as fitz

    doc = fitz.open(caminho)
    info = {"paginas": doc.page_count, "em_branco": [], "texto_fora": [], "interface": [], "pngs": []}
    vazou = ("Baixar PDF", "Exportar CSV", "Limpar filtros", "Todas as secretarias", "Buscar título", "Sair", "Atualizar")
    for i, pagina in enumerate(doc):
        texto = pagina.get_text().strip()
        if len(texto) < 20 and not pagina.get_images():
            info["em_branco"].append(i + 1)
        largura = pagina.rect.width
        for bloco in pagina.get_text("blocks"):
            if bloco[2] > largura - 8 or bloco[0] < 8:
                info["texto_fora"].append((i + 1, bloco[4][:40]))
        for termo in vazou:
            if termo in texto:
                info["interface"].append((i + 1, termo))
        png = pasta_png / f"{caminho.stem}-p{i + 1}.png"
        pagina.get_pixmap(dpi=70).save(png)
        info["pngs"].append(str(png))
    return info


def fundo_nome(com_fundo: bool) -> str:
    return "com-fundo" if com_fundo else "sem-fundo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://valorpublico.web.app/")
    ap.add_argument("--project", default="valorpublico-b1e6d")
    ap.add_argument("--saida", default="")
    ap.add_argument("--apenas", default="", help="nomes separados por vírgula (ex.: 03-clipping)")
    ap.add_argument("--fundo", default="sim", choices=["sim", "nao", "ambos"],
                    help="sim = com gráficos de fundo (padrão do teste); nao = como o Chrome "
                         "imprime quando a opção 'Gráficos de plano de fundo' está desmarcada")
    args = ap.parse_args()
    out = Path(args.saida or tempfile.mkdtemp(prefix="valor-pdfs-"))
    out.mkdir(parents=True, exist_ok=True)
    apenas = {a.strip() for a in args.apenas.split(",") if a.strip()}

    email = "qa.pdf." + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10)) + "@example.com"
    senha = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(20)) + "!9a"
    admin = {"Authorization": f"Bearer {token()}", "x-goog-user-project": args.project}
    base = "https://identitytoolkit.googleapis.com/v1"
    uid = None
    resultado = {"relatorios": {}, "erros_js": []}
    try:
        r = requests.post(f"{base}/projects/{args.project}/accounts", headers=admin,
                          json={"email": email, "password": senha, "emailVerified": True}, timeout=30)
        r.raise_for_status()
        uid = r.json()["localId"]
        requests.patch(
            f"https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/usuarios/{uid}",
            headers=admin,
            json={"fields": {"orgao": {"stringValue": "governo-mt"}, "papel": {"stringValue": "secom"},
                             "email": {"stringValue": email}}},
            timeout=30,
        ).raise_for_status()
        with sync_playwright() as p:
            nav = p.chromium.launch(headless=True, channel="chrome")
            ctx = nav.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.on("pageerror", lambda e: resultado["erros_js"].append(str(e)))
            page.goto(args.url, wait_until="domcontentloaded")
            page.fill("#loginEmail", email)
            page.fill("#loginSenha", senha)
            page.wait_for_function("() => { const b = document.getElementById('btnEntrar'); return b && !b.disabled; }", timeout=30000)
            page.click("#btnEntrar")
            page.wait_for_function("() => !!window.__app_test?.estado?.db", timeout=60000)
            page.wait_for_timeout(1500)
            if page.locator('#orgaoCards a[data-orgao="governo-mt"]').count():
                page.click('#orgaoCards a[data-orgao="governo-mt"]')
            page.wait_for_timeout(4000)
            # a impressão vira um registro; o PDF é gerado pelo próprio navegador
            page.evaluate("""() => { window.print = () => {
                window.__pedidoImpressao = (window.__pedidoImpressao || 0) + 1;
                window.__classesImpressao = document.body.className;
            }; }""")
            for nome, rota, passos, botao, tipo in RELATORIOS:
                if apenas and nome not in apenas:
                    continue
                page.evaluate("(r) => window.__app_test.irPara(r)", rota)
                page.wait_for_timeout(2500)
                for passo in passos:
                    page.click(passo, timeout=5000)
                    page.wait_for_timeout(1200)
                antes = page.evaluate("() => window.__pedidoImpressao || 0")
                page.click(botao, timeout=5000)
                page.wait_for_timeout(1500)
                pedido = page.evaluate("() => window.__pedidoImpressao || 0") > antes
                # no navegador real o diálogo de impressão bloqueia: o estado do
                # momento da impressão é o que vai para o PDF
                classes = page.evaluate("() => { if (window.__classesImpressao !== undefined) document.body.className = window.__classesImpressao; return document.body.className; }")
                page.emulate_media(media="print")
                variantes = [True, False] if args.fundo == "ambos" else [args.fundo == "sim"]
                info = {"pedido_de_impressao": pedido, "classes_no_body": classes, "variantes": {}}
                for com_fundo in variantes:
                    if not com_fundo:
                        # o afterprint do navegador real desmonta o documento: remonta
                        page.evaluate("(t) => { window.__documentos.montar(t); document.body.classList.add('imprimindo-doc'); }", tipo)
                        page.wait_for_timeout(700)
                    sufixo = "" if com_fundo else "-sem-fundo"
                    caminho = out / f"{nome}{sufixo}.pdf"
                    page.pdf(path=str(caminho), format="A4", print_background=com_fundo, prefer_css_page_size=True)
                    medidas = analisar_pdf(caminho, out)
                    medidas["pedido_de_impressao"] = pedido
                    medidas["classes_no_body"] = classes
                    medidas["com_fundo"] = com_fundo
                    info["variantes"][fundo_nome(com_fundo)] = medidas
                    if not com_fundo:
                        info.update({k: v for k, v in medidas.items() if k in ("paginas", "em_branco", "texto_fora", "interface")})
                page.emulate_media(media="screen")
                page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
                page.wait_for_timeout(600)
                resultado["relatorios"][nome] = info
                page.keyboard.press("Escape")
            nav.close()
    finally:
        if uid:
            try:
                requests.delete(f"https://firestore.googleapis.com/v1/projects/{args.project}/databases/(default)/documents/usuarios/{uid}", headers=admin, timeout=30)
                requests.post(f"{base}/projects/{args.project}/accounts:delete", headers=admin, json={"localId": uid}, timeout=30)
            except Exception:
                pass
    (out / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    for nome, info in resultado["relatorios"].items():
        for variante, medidas in info.get("variantes", {}).items():
            print(f"{nome} [{variante}]: {medidas['paginas']} pág. | branco {medidas['em_branco']} | "
                  f"fora {len(medidas['texto_fora'])} | interface {medidas['interface'][:3]} | "
                  f"pedido {medidas['pedido_de_impressao']}")
    print("erros JS:", resultado["erros_js"][:3] or "nenhum")
    print("saida:", out)


if __name__ == "__main__":
    main()
