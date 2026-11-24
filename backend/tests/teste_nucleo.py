"""Teste de guarda do nucleo compartilhado (D6).

Confere:
  - a copia vendorizada em `backend/cerra_nucleo/` tem a MESMA versao da
    canonica (tag fixa) — sem isso o CI pode rodar codigo divergente;
  - todos os modulos do nucleo importam sem erro;
  - as flags de navegacao/stealth existem e tem os valores esperados;
  - a guarda anti-SSRF e o ritmo do navegador funcionam (19 §3.1).

Uso (a partir de `backend/`):
    python tests/teste_nucleo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

PASSOU: list[str] = []
FALHOU: list[str] = []


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


def main() -> int:
    print("== versao do nucleo (tag fixa) ==")
    try:
        from cerra_nucleo import TAG, VERSION
    except Exception as exc:  # noqa: BLE001
        print("  FAIL  nucleo nao importavel:", exc)
        return 1
    arquivo = BACKEND / "cerra_nucleo" / "VERSION"
    if arquivo.exists():
        checar(
            "VERSION do arquivo bate com o pacote",
            arquivo.read_text(encoding="utf-8").strip() == VERSION,
            f"{arquivo.read_text(encoding='utf-8').strip()} vs {VERSION}",
        )
    else:
        checar("arquivo VERSION presente", False)
    checar("tag no formato vX.Y.Z", TAG.startswith("v") and TAG.count(".") == 2, TAG)

    print("== modulos importam ==")
    modulos = [
        ("cerra_nucleo.scraper.searxng_cliente", "SearXNGCliente"),
        ("cerra_nucleo.scraper.tendencias", "em_alta"),
        ("cerra_nucleo.scraper.telegram_publico", "coletar_canal"),
        ("cerra_nucleo.scraper.ad_library", "consultar"),
        ("cerra_nucleo.scraper.navegador", "SessaoNavegador"),
        ("cerra_nucleo.scraper.previa_publica", "extrair_meta"),
        ("cerra_nucleo.scraper.receitas", "carregar_receitas"),
        ("cerra_nucleo.scraper.evidencia", "capturar"),
        ("cerra_nucleo.processing.demandas", "classificar_demanda"),
        ("cerra_nucleo.processing.bairros", "detectar_bairro"),
        ("cerra_nucleo.processing.indicadores", "indice_crise"),
        ("cerra_nucleo.processing.imagem", "processar_imagem"),
    ]
    for nome, simbolo in modulos:
        try:
            modulo = __import__(nome, fromlist=[simbolo])
            checar(f"{nome}.{simbolo}", hasattr(modulo, simbolo))
        except Exception as exc:  # noqa: BLE001
            checar(f"{nome}.{simbolo}", False, str(exc)[:80])

    print("== indicadores (K-28, K-33) ==")
    from cerra_nucleo.processing.indicadores import indice_crise, projetar

    serie = {f"2026-11-{dia:02d}": 2 for dia in range(1, 26)}
    serie["2026-11-24"] = 12
    crise = indice_crise(serie)
    checar("crise detectada com pico", crise["ativo"] is True, str(crise))
    checar("crise com z-score", crise["z"] >= 3, str(crise.get("z")))
    checar("crise tem mensagem", bool(crise.get("mensagem")))

    serie_plana = {f"2026-11-{dia:02d}": 2 for dia in range(1, 26)}
    normal = indice_crise(serie_plana)
    checar("sem crise na serie normal", normal["ativo"] is False, str(normal))

    resultado = projetar(serie)
    checar("projecao gerada", bool(resultado.get("previsao")), str(resultado.get("erro"))[:80])
    checar("projecao tem faixa", all("inferior" in p and "superior" in p for p in resultado["previsao"][:3]))

    print("== demandas ==")
    from cerra_nucleo.processing.demandas import classificar_demanda

    pedido = classificar_demanda(
        "Preciso de uma UPA no bairro Jardim das Americas, o atendimento esta demorando muito"
    )
    checar("pedido classificado", pedido["e_demanda"] is True, str(pedido))
    checar("tema saude", pedido["tema"] == "saude", pedido["tema"])
    elogio = classificar_demanda("Parabens pelo trabalho da equipe, continue assim pelo trabalho")
    checar("elogio nao e pedido", elogio["e_demanda"] is False)
    spam = classificar_demanda("Clique aqui https://oferta.example.com para ganhar dinheiro agora")
    checar("spam nao e pedido", spam["e_demanda"] is False)

    print("== bairros ==")
    from cerra_nucleo.processing.bairros import detectar_bairro

    checar("bairro detectado", detectar_bairro("problema na Avenida Brasil em Varzea Grande") == "Avenida Brasil")
    checar("bairro com acento", detectar_bairro("rua do Jardim das Américas") == "Jardim das Americas")
    checar("sem bairro devolve None", detectar_bairro("noticia sobre o orçamento municipal") is None)

    print("== navegador: salvaguardas (19 §3.1) ==")
    from cerra_nucleo.scraper.navegador import (
        BloqueioDetectado,
        LIMITE_PAGINAS_AGENTE_DIA,
        PAUSA_MINIMO,
        SessaoNavegador,
    )

    checar("ritmo minimo de 5 s", PAUSA_MINIMO >= 5.0, str(PAUSA_MINIMO))
    checar("limite de 30 paginas/dia", LIMITE_PAGINAS_AGENTE_DIA == 30)

    sessao = SessaoNavegador(stealth=False, conta_propria=False)
    try:
        sessao.registrar_bloqueio("https://instagram.com/p/abc", "login")
        checar("bloqueio registrado", sessao.bloqueado_ate("instagram.com") > 0)
        try:
            sessao.abrir_pagina("https://instagram.com/p/abc")
            checar("pagina bloqueada nao e aberta", False)
        except BloqueioDetectado:
            checar("pagina bloqueada nao e aberta", True)
    finally:
        sessao.fechar()

    print("== anti-SSRF ==")
    from cerra_nucleo.processing.imagem import url_segura

    checar("recusa loopback", not url_segura("http://127.0.0.1/x"))
    checar("recusa privado", not url_segura("http://192.168.0.1/x"))

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
