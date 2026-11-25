"""Coleta o clipping do Governo de Mato Grosso (janela de N dias).

Fontes (todas oficiais e gratuitas):
  * **RSS oficial do portal** `https://portal.mt.gov.br/api/rss-api/v1/rss`
    ("Notícias do Governo do Estado de Mato Grosso");
  * **Google News RSS** com `when:Nd` — cobre a janela completa (o RSS oficial
    só entrega os 20 mais recentes) e traz a imprensa que نشر;
  * **DOE/IOnews** (já no radar) entra pelas fontes oficiais.

Cada item recebe:
  * `secretarias` (multi-label, com `motivo`), `alvos` (governo-mt / governador /
    interino), `confianca`;
  * deduplicação por URL canônica e por (título normalizado + dia).

NÃO grava no Firestore: a saída é local (JSONL) para revisão antes de publicar.

Uso (a partir de `backend/`):
    python scripts/coletar_governo_mt.py --dias 150
    python scripts/coletar_governo_mt.py --dias 150 --com-texto 300
    python scripts/coletar_governo_mt.py --dias 30 --saida data/governo_mt/teste
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests

from cerra_nucleo.processing.secretarias import classificar, carregar_secretarias
from config.settings import BASE_DIR
from core.logger import get_logger

logger = get_logger(__name__)

UA = {"User-Agent": "CerraClippingBot/1.0 (+https://github.com/renato0503)"}
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
RSS_OFICIAL = "https://portal.mt.gov.br/api/rss-api/v1/rss"
SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"

PAUSA_ENTRE_CONSULTAS = 0.7


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _normalizar_titulo(titulo: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(titulo)).strip()


def _url_canonica(url: str) -> str:
    """Remove parametros de rastreamento (utm_*, gclid, fbclid...)."""
    try:
        partes = urllib.parse.urlparse(url)
    except Exception:  # noqa: BLE001
        return url
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(partes.query)
        if not k.lower().startswith("utm_") and k.lower() not in ("gclid", "fbclid", "oc")
    ]
    return urllib.parse.urlunparse(
        (partes.scheme, partes.netloc, partes.path, partes.params, urllib.parse.urlencode(query), "")
    )


def _parse_data(valor: str | None, parsed=None) -> datetime | None:
    """Aceita ISO 8601 ou struct_time do feedparser (RFC 822)."""
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        pass
    for formato in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(valor, formato).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


# Marcadores de Mato Grosso: usados para descartar materia de outro estado
# (as consultas do agregador trazem, por exemplo, "Goias.GOV" e "Agencia Minas").
MARCADORES_MT = (
    "mato grosso",
    "mato-grosso",
    "mt.gov.br",
    "cuiaba",
    "varzea grande",
    "rondonopolis",
    "sinop",
    "caceres",
    "sorriso",
    "primavera do leste",
    "barra do garcas",
    "juina",
    "pocone",
    "colider",
    "diamantino",
    "nova mutum",
    "confresa",
    "sao simao",
    "guarantã",
    "barra do bugres",
    "lambari",
    "pontes e condemnation",
    "gov mt",
    "governo de mt",
    "governo do estado de mato grosso",
    "al.mt.gov.br",
    "mt",
)


def contexto_mt(texto: str) -> bool:
    """True se o texto tem marcadores de Mato Grosso."""
    limpo = _sem_acento(texto)
    for marcador in MARCADORES_MT:
        alvo = _sem_acento(marcador)
        if alvo == "mt":
            if re.search(r"(?<![a-z0-9])mt(?![a-z0-9])", limpo):
                return True
        elif alvo in limpo:
            return True
    return False


# ----------------------------------------------------------------------
# Consultas
# ----------------------------------------------------------------------
def _janela(dias: int, depois: str = "", antes: str = "") -> str:
    if depois and antes:
        return f"after:{depois} before:{antes}"
    return f"when:{dias}d"


def consultas_do_seed(
    seed: dict, dias: int, depois: str = "", antes: str = ""
) -> list[tuple[str, str]]:
    """Monta (rotulo, consulta) para o agregador, opcionalmente por intervalo."""
    consultas: list[tuple[str, str]] = []
    janela = _janela(dias, depois, antes)

    for pasta in seed.get("secretarias", []) + seed.get("autarquias", []):
        nome = pasta.get("nome", "")
        sigla = pasta.get("sigla", "")
        consultas.append((sigla or nome, f'"{nome}" {janela}'))
        consultas.append((sigla or nome, f'"{sigla}" "mato grosso" {janela}'))
        for alias in pasta.get("alias", []) or []:
            consultas.append((sigla or nome, f'"{alias}" "mato grosso" {janela}'))

    for chave in ("governador", "interino"):
        alvo = seed.get(chave)
        if not alvo:
            continue
        for termo in alvo.get("termos", []):
            consultas.append((alvo.get("nome", termo), f'"{termo}" {janela}'))

    for termo in (
        "governo de mato grosso",
        "governo do estado de mato grosso",
        "governo mt",
        "palacio paiaguas",
    ):
        consultas.append(("GOVERNO MT", f'"{termo}" {janela}'))

    # remove duplicatas preservando a ordem
    vistos = set()
    saida = []
    for rotulo, consulta in consultas:
        chave = consulta.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append((rotulo, consulta))
    return saida


def _janelas_historicas(dias: int, recente: int = 3) -> list[tuple[str, str]]:
    """Blocos mensais entre o limite antigo e a janela recente."""
    hoje = datetime.now(timezone.utc).date()
    inicio = hoje - timedelta(days=dias)
    fim_recente = hoje - timedelta(days=recente)
    janelas: list[tuple[str, str]] = []
    cursor = inicio
    while cursor < fim_recente:
        fim = min(cursor + timedelta(days=30), fim_recente)
        if fim > cursor:
            janelas.append((cursor.isoformat(), fim.isoformat()))
        cursor = fim
    return janelas


CONSULTAS_RECENTES_EXTRAS = (
    ("G1 MT", '"governo de mato grosso" site:g1.globo.com'),
    ("Olhar Direto", '"governo de mato grosso" site:olhardireto.com.br'),
    ("Folha Max", '"governo de mato grosso" site:folhamax.com'),
    ("Caldeirão", '"governo de mato grosso" site:caldeiraopolitico.com.br'),
    ("Estadão MT", '"governo de mato grosso" site:estadao.com.br'),
    ("Secom MT", '"governo de mato grosso" site:secom.mt.gov.br'),
    ("ALMT", '"governo de mato grosso" site:al.mt.gov.br'),
)


def buscar_google_news(consulta: str, limite: int = 100) -> list[dict]:
    """Busca no agregador e devolve itens normalizados."""
    import feedparser

    url = GOOGLE_NEWS.format(q=urllib.parse.quote(consulta))
    try:
        resp = requests.get(url, headers=UA, timeout=40)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha na consulta %r: %s", consulta[:50], str(exc)[:80])
        return []
    feed = feedparser.parse(resp.content)
    itens = []
    for entrada in feed.entries:
        itens.append(
            {
                "titulo": (entrada.get("title") or "").strip(),
                "url": (entrada.get("link") or "").strip(),
                "veiculo": (entrada.get("source", {}).get("title") or "").strip(),
                "data": _parse_data(entrada.get("published"), entrada.get("published_parsed")),
                "resumo": re.sub(r"<[^>]+>", " ", entrada.get("summary", "") or "").strip(),
                "origem": "agregador",
                "consulta": consulta,
            }
        )
    return itens[:limite]


def buscar_rss_oficial() -> list[dict]:
    """RSS oficial do portal do Governo (20 itens mais recentes)."""
    import feedparser

    try:
        resp = requests.get(RSS_OFICIAL, headers=UA, timeout=40)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("RSS oficial indisponivel: %s", str(exc)[:80])
        return []
    feed = feedparser.parse(resp.content)
    itens = []
    for entrada in feed.entries:
        resumo = entrada.get("summary", "") or ""
        resumo = re.sub(r"<[^>]+>", " ", resumo).strip()
        itens.append(
            {
                "titulo": (entrada.get("title") or "").strip(),
                "url": (entrada.get("link") or "").strip(),
                "veiculo": "Portal do Governo de MT",
                "data": _parse_data(entrada.get("published"), entrada.get("published_parsed")),
                "resumo": resumo[:600],
                "origem": "oficial",
                "consulta": "rss-oficial",
            }
        )
    return itens


def extrair_texto(url: str) -> str:
    """Texto integral da página original (trafilatura)."""
    try:
        import trafilatura

        resp = requests.get(url, headers=UA, timeout=25)
        if resp.status_code >= 400:
            return ""
        texto = trafilatura.extract(
            resp.text, include_comments=False, include_tables=False, favor_precision=True
        )
        return (texto or "")[:6000]
    except Exception:  # noqa: BLE001
        return ""


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------
def coletar(dias: int, com_texto: int = 0, seed: dict | None = None) -> list[dict]:
    seed = seed or json.loads(SEED.read_text(encoding="utf-8"))
    pastas = seed.get("secretarias", []) + seed.get("autarquias", [])
    governor = seed.get("governador")
    interino = seed.get("interino")
    consultas = consultas_do_seed(seed, min(dias, 3))
    if dias > 3:
        consultas.extend(
            (rotulo, f"{consulta} when:3d")
            for rotulo, consulta in CONSULTAS_RECENTES_EXTRAS
        )
        janelas = _janelas_historicas(dias)
        for depois, antes in janelas:
            consultas.extend(consultas_do_seed(seed, 0, depois, antes))
        logger.info(
            "Janelas historicas: %s",
            ", ".join(f"{d}..{a}" for d, a in janelas),
        )
    vistos_consulta: set[str] = set()
    consultas = [
        (rotulo, consulta)
        for rotulo, consulta in consultas
        if not (consulta.lower() in vistos_consulta or vistos_consulta.add(consulta.lower()))
    ]
    logger.info("Consultas planejadas: %d", len(consultas))

    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    coletados: dict[str, dict] = {}
    por_dia: Counter = Counter()

    def registrar(item: dict) -> bool:
        if not item.get("titulo") or not item.get("url"):
            return False
        # descarta materia de outro estado (as consultas do agregador trazem
        # "Goias.GOV", "Agencia Minas"...)
        if not contexto_mt(f"{item['titulo']} {item.get('resumo', '')} {item.get('veiculo', '')}"):
            return False
        data = item.get("data")
        if data and data < limite:
            return False
        chave = _url_canonica(item["url"])
        if chave in coletados:
            # mantém a versão com texto/resumo mais rico
            atual = coletados[chave]
            if len(item.get("resumo") or "") > len(atual.get("resumo") or ""):
                atual["resumo"] = item["resumo"]
            if item.get("origem") == "oficial":
                atual["origem"] = "oficial"
            return False
        item["url_canonica"] = chave
        item["chave_titulo_dia"] = (
            _normalizar_titulo(item["titulo"]),
            (data.date().isoformat() if data else ""),
        )
        coletados[chave] = item
        return True

    for indice, (rotulo, consulta) in enumerate(consultas, start=1):
        itens = buscar_google_news(consulta)
        novos = sum(1 for i in itens if registrar(i))
        logger.info("[%2d/%2d] %-14s %3d itens (%d novos)", indice, len(consultas), rotulo[:14], len(itens), novos)
        time.sleep(PAUSA_ENTRE_CONSULTAS)

    oficiais = buscar_rss_oficial()
    novos_oficiais = sum(1 for i in oficiais if registrar(i))
    logger.info("RSS oficial: %d itens (%d novos)", len(oficiais), novos_oficiais)

    # dedup secundario: mesmo titulo no mesmo dia (fonte diferente)
    vistos_titulo: dict[tuple, str] = {}
    saida = []
    for item in coletados.values():
        chave = item["chave_titulo_dia"]
        if chave in vistos_titulo:
            continue
        vistos_titulo[chave] = item["url"]
        saida.append(item)

    # classificacao
    from processing.sentiment import AnalisadorSentimento
    from processing.temas import classificar_temas

    analisador = AnalisadorSentimento()
    for item in saida:
        texto_item = f"{item['titulo']} {item.get('resumo', '')}"
        resultado = classificar(
            texto_item,
            pastas,
            governador=governor,
            interino=interino,
        )
        item["secretarias"] = resultado["secretarias"]
        item["siglas"] = resultado["siglas"]
        item["alvos"] = resultado["alvos"]
        item["escopo"] = resultado["escopo"]
        item["confianca_secretaria"] = resultado["confianca"]
        item["motivo_secretaria"] = resultado["motivo"]
        # ferramentas do app (mesmas do Assessor): sentimento e temas
        item["sentimento"] = analisador.classificar(texto_item)
        item["temas"] = classificar_temas(texto_item)
        if item.get("data"):
            por_dia[item["data"].date().isoformat()] += 1

    # texto integral (opcional, limitado)
    if com_texto:
        logger.info("Extraindo texto de %d itens...", com_texto)
        for item in saida[:com_texto]:
            if not item.get("resumo"):
                item["resumo"] = ""
            texto = extrair_texto(item["url"])
            if texto:
                item["texto"] = texto
            time.sleep(0.4)

    saida.sort(key=lambda i: (i.get("data") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return saida


def resumo(itens: list[dict], seed: dict) -> dict:
    por_secretaria = Counter()
    por_veiculo = Counter()
    por_alvo = Counter()
    por_escopo = Counter()
    sem_pasta = 0
    for item in itens:
        por_escopo[item.get("escopo", "geral-mt")] += 1
        if item.get("secretarias") == ["geral-governo"]:
            sem_pasta += 1
        else:
            for sigla in item.get("siglas", []):
                por_secretaria[sigla] += 1
        por_veiculo[item.get("veiculo") or "—"] += 1
        for alvo in item.get("alvos", []):
            por_alvo[alvo] += 1
    datas = [i["data"] for i in itens if i.get("data")]
    do_governo = por_escopo.get("governo-estado", 0)
    return {
        "total": len(itens),
        "periodo": {
            "de": min(datas).isoformat() if datas else None,
            "ate": max(datas).isoformat() if datas else None,
        },
        "por_escopo": dict(por_escopo),
        "do_governo_do_estado": do_governo,
        "com_secretaria": len(itens) - sem_pasta,
        "sem_secretaria": sem_pasta,
        "cobertura_secretaria": round(100 * (len(itens) - sem_pasta) / len(itens), 1) if itens else 0,
        "cobertura_no_escopo_do_governo": round(100 * (len(itens) - sem_pasta) / do_governo, 1) if do_governo else 0,
        "por_secretaria": dict(por_secretaria.most_common()),
        "por_alvo": dict(por_alvo),
        "top_veiculos": dict(por_veiculo.most_common(15)),
        "secretarias_no_seed": len(seed.get("secretarias", [])) + len(seed.get("autarquias", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta o clipping do Governo de MT.")
    parser.add_argument("--dias", type=int, default=60)
    parser.add_argument("--saida", default=str(BASE_DIR / "data" / "governo_mt"))
    parser.add_argument("--com-texto", type=int, default=0, help="extrai texto de N itens")
    args = parser.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    itens = coletar(args.dias, com_texto=args.com_texto, seed=seed)
    resumo_final = resumo(itens, seed)

    pasta = Path(args.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    jsonl = pasta / f"noticias-{marca}.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for item in itens:
            item.pop("chave_titulo_dia", None)
            fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    (pasta / f"resumo-{marca}.json").write_text(
        json.dumps(resumo_final, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print("\n=== RESUMO DA COLETA ===")
    print(f"itens: {resumo_final['total']} | periodo {resumo_final['periodo']['de']} -> {resumo_final['periodo']['ate']}")
    print(f"com secretaria: {resumo_final['com_secretaria']} ({resumo_final['cobertura_secretaria']}%) | sem: {resumo_final['sem_secretaria']}")
    print("por alvo:", resumo_final["por_alvo"])
    print("\npor secretaria:")
    for sigla, n in list(resumo_final["por_secretaria"].items())[:30]:
        print(f"  {sigla:16s} {n}")
    print("\ntop veiculos:", list(resumo_final["top_veiculos"].items())[:10])
    print(f"\nJSONL: {jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
