"""Analise lexical (IRAMUTEQ) por escopo, publicada no Firestore para o dashboard.

Cada escopo vira um documento na colecao `analise_lexical`:

  - `analise_lexical/geral`            -> corpus completo
  - `analise_lexical/cidade-<slug>`    -> por cidade (Cuiaba, Varzea Grande)
  - `analise_lexical/agente-<id>`      -> por parlamentar
  - `analise_lexical/periodo-<chave>`  -> hoje | 7d | 30d

O frontend resolve a chave conforme os filtros ativos (parlamentar > cidade >
periodo > geral) e carrega apenas o documento correspondente.

Estrutura de cada documento:
  {escopo, afc, chd, grafo, dendrograma, resumo, gerado_em}

Uso: python scripts/analise_lexical_escopos.py [--n-classes 4] [--niveis 8]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from unicodedata import normalize

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import settings
from core.firebase_client import init_firebase
from core.logger import get_logger
from core.orgaos import orgao_da_cidade, orgao_do_agente
from processing import lexical

logger = get_logger(__name__)

COLLECTION_LEXICAL = "analise_lexical"
TOP_ARESTAS = 80
MAX_AFC_PALAVRAS = 120

# Docs antigos (formato plano) removidos apos a migracao para escopos.
DOCS_ANTIGOS = ["afc", "chd", "grafo", "dendrograma", "resumo"]


def slugify_cidade(cidade: str) -> str:
    cidade = normalize("NFKD", cidade).encode("ascii", "ignore").decode("utf-8")
    return "-".join(cidade.strip().lower().split())


def _ts(c) -> float:
    d = c.get("data_publicacao")
    if d is None:
        return 0.0
    try:
        return d.timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _dentro_janela(dt, dias: int) -> bool:
    if dt is None:
        return False
    try:
        if isinstance(dt, datetime):
            data = dt.astimezone(timezone.utc).date()
        else:
            data = str(dt)[:10]
        hoje = datetime.now(timezone.utc).date()
        return (hoje - data).days <= dias and (hoje - data).days >= 0
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Computacao de cada analise (sem depender de arquivos locais)
# --------------------------------------------------------------------------

def _calcular_afc(clippings: list[dict]) -> dict:
    afc = lexical.analise_correspondencias(clippings)
    palavras = [
        {"rotulo": p, "eixo1": float(c[0]), "eixo2": float(c[1])}
        for p, c in zip(afc["palavras"], afc["coord_palavras"])
        if len(c) >= 2
    ][:MAX_AFC_PALAVRAS]
    periodos = [
        {"rotulo": m, "eixo1": float(c[0]), "eixo2": float(c[1])}
        for m, c in zip(afc["periodos"], afc["coord_periodos"])
        if len(c) >= 2
    ]
    return {"palavras": palavras, "periodos": periodos}


def _calcular_chd(clippings: list[dict], n_classes: int, preparado) -> dict:
    res = lexical.chd(clippings, n_classes=n_classes, preparado=preparado)
    classes = [
        {
            "classe": cl["classe"],
            "n_segmentos": cl["n_segmentos"],
            "pct_segmentos": cl["pct"],
            "palavras": cl["palavras"],
            # plano 22: nome do assunto, explicacao para leigos e manchetes de exemplo
            "nome": cl.get("nome", ""),
            "tema": cl.get("tema", ""),
            "explicacao": cl.get("explicacao", ""),
            "exemplos": cl.get("exemplos", []),
        }
        for cl in res.get("classes", [])
    ]
    saida = {"classes": classes, "n_segmentos": res.get("segmentos", 0)}
    if res.get("aviso"):
        saida["aviso"] = res["aviso"]
    return saida


def _calcular_grafo(clippings: list[dict]) -> dict:
    grafo = lexical.coocorrencia(clippings)
    arestas = sorted(grafo.get("arestas", []), key=lambda a: a.get("peso", 0), reverse=True)
    arestas_podadas = arestas[:TOP_ARESTAS]
    ids = {a["a"] for a in arestas_podadas} | {a["b"] for a in arestas_podadas}
    nos = [n for n in grafo.get("nos", []) if n.get("id") in ids]
    return {"nos": nos, "arestas": arestas_podadas}


def _calcular_dendrograma(clippings: list[dict], n_classes: int, niveis: int, preparado) -> dict:
    return lexical.dendrograma(clippings, n_classes=n_classes, p=niveis, preparado=preparado)


def _resumo(clippings: list[dict], chd: dict, dendo: dict) -> str:
    freq = lexical.frequencia_global(clippings)
    total_tokens = sum(freq.values())
    meses = set()
    for c in clippings:
        d = c.get("data_publicacao")
        if d is not None:
            meses.add(str(d)[:7])
    linhas = [
        f"Corpus: {len(clippings)} clippings",
        f"Total de ocorrencias (tokens): {total_tokens}",
        f"Vocabulario distinto (types): {len(freq)}",
        f"Periodos: {len(meses)} meses",
        f"CHD: {chd.get('n_segmentos', 0)} segmentos, {len(chd.get('classes', []))} classes",
        f"Dendrograma: {len(dendo.get('polilinhas', []))} ramos (niveis superiores)",
    ]
    if chd.get("aviso"):
        linhas.append(f"Aviso CHD: {chd['aviso']}")
    if dendo.get("aviso"):
        linhas.append(f"Aviso dendrograma: {dendo['aviso']}")
    return "\n".join(linhas)


def _documento(escopo: dict, clippings: list[dict], n_classes: int, niveis: int) -> dict:
    preparado = lexical._preparar_chd(clippings)
    chd = _calcular_chd(clippings, n_classes, preparado)
    dendo = _calcular_dendrograma(clippings, n_classes, niveis, preparado)
    return {
        "escopo": escopo,
        "orgao": escopo.get("orgao", ""),
        "n_clippings": len(clippings),
        "afc": _calcular_afc(clippings),
        "chd": chd,
        "grafo": _calcular_grafo(clippings),
        "dendrograma": dendo,
        "resumo": _resumo(clippings, chd, dendo),
        "gerado_em": datetime.now(timezone.utc),
    }


def _escopos(clippings: list[dict]) -> dict[str, tuple[dict, list[dict]]]:
    """Retorna {chave: (escopo_meta, clippings)} para cada escopo configurado."""
    escopos: dict[str, tuple[dict, list[dict]]] = {}
    escopos["geral"] = (
        {"tipo": "geral", "nome": "Todos", "orgao": ""},
        list(clippings),
    )

    por_cidade: dict[str, list[dict]] = {}
    por_agente: dict[str, list[dict]] = {}
    nome_agente: dict[str, str] = {}
    for c in clippings:
        por_cidade.setdefault(c.get("cidade") or "Sem cidade", []).append(c)
        por_agente.setdefault(c["agente_id"], []).append(c)
        nome_agente[c["agente_id"]] = c.get("nome_agente") or c["agente_id"]

    for cidade, clips in por_cidade.items():
        chave = f"cidade-{slugify_cidade(cidade)}"
        escopos[chave] = (
            {
                "tipo": "cidade",
                "chave": slugify_cidade(cidade),
                "nome": cidade,
                "orgao": orgao_da_cidade(cidade),
            },
            clips,
        )

    for agente_id, clips in por_agente.items():
        orgao = (clips[0].get("orgao") if clips else "") or orgao_do_agente(
            clips[0] if clips else {}
        )
        escopos[f"agente-{agente_id}"] = (
            {
                "tipo": "agente",
                "chave": agente_id,
                "nome": nome_agente[agente_id],
                "orgao": orgao,
            },
            clips,
        )

    hoje = datetime.now(timezone.utc).date().isoformat()
    janelas: dict[str, tuple[dict, list[dict]]] = {
        "periodo-hoje": (
            {"tipo": "periodo", "chave": "hoje", "nome": "Hoje", "orgao": ""},
            [],
        ),
        "periodo-7d": (
            {"tipo": "periodo", "chave": "7d", "nome": "Últimos 7 dias", "orgao": ""},
            [],
        ),
        "periodo-30d": (
            {"tipo": "periodo", "chave": "30d", "nome": "Últimos 30 dias", "orgao": ""},
            [],
        ),
    }
    for c in clippings:
        dt = c.get("data_publicacao")
        if isinstance(dt, datetime):
            dia = dt.astimezone(timezone.utc).date().isoformat()
        elif dt is not None:
            dia = str(dt)[:10]
        else:
            dia = None
        if dia == hoje:
            janelas["periodo-hoje"][1].append(c)
        if _dentro_janela(dt, 7):
            janelas["periodo-7d"][1].append(c)
        if _dentro_janela(dt, 30):
            janelas["periodo-30d"][1].append(c)
    escopos.update(janelas)
    return escopos


def carregar_jsonl(caminho: str) -> list[dict]:
    """Le a base local do Governo sem gastar cota de leitura do Firestore.

    ``caminho`` pode ser um JSONL ou a pasta ``data/governo_mt`` (uniao de todas
    as coletas, sem veiculos de fora de MT, plano 22).
    """
    import json

    from processing.governo_filtros import linhas_da_base, sanear_itens

    alvo = Path(caminho)
    if alvo.is_dir():
        brutos, _ = sanear_itens(linhas_da_base(alvo))
    else:
        brutos = [json.loads(l) for l in alvo.read_text(encoding="utf-8").splitlines() if l.strip()]
    itens: list[dict] = []
    for item in brutos:
        itens.append(
            {
                "agente_id": "governo-mt",
                "cidade": "Governo de Mato Grosso",
                "casa": "Governo MT",
                "orgao": "governo-mt",
                "nome_agente": "Governo de Mato Grosso",
                "texto_limpo": f"{item.get('titulo', '')}\n{item.get('resumo', '')}".strip(),
                "titulo": item.get("titulo", ""),
                "data_publicacao": item.get("data"),
                "plataforma": "Web",
                "tipo": "Noticia",
                "sentimento": item.get("sentimento", ""),
                "url": item.get("url", ""),
                "alvos": item.get("alvos") or [],
            }
        )
    return itens


# Com a base do Governo, o governador e o interino ganham a analise das
# noticias que os citam (e nao dos comentarios de redes).
ALVOS_GOVERNO = {
    "governador": ("governador-otaviano-pivetta", "Otaviano Pivetta (governador)"),
    "interino": ("interino-max-russi", "Max Russi (governador interino)"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica analise lexical por escopo no Firestore.")
    parser.add_argument("--n-classes", type=int, default=4, help="Classes na CHD (padrao 4).")
    parser.add_argument("--niveis", type=int, default=8, help="Niveis do dendrograma (padrao 8).")
    parser.add_argument(
        "--jsonl",
        default="",
        help="Le um JSONL local (ex.: data/governo_mt/noticias-*.jsonl) e evita ler o Firestore.",
    )
    parser.add_argument(
        "--apenas",
        default="",
        help="Lista de escopos a publicar (ex.: cidade-governo-de-mato-grosso).",
    )
    args = parser.parse_args()

    db = init_firebase()
    if args.jsonl:
        clippings = carregar_jsonl(args.jsonl)
    else:
        clippings = []
        for agente in db.collection(settings.COLLECTION_AGENTES).stream():
            ad = agente.to_dict()
            nome_agente = ad.get("nome_urna") or ad.get("nome") or agente.id
            for clip in agente.reference.collection(settings.SUBCOLLECTION_CLIPPINGS).stream():
                clippings.append(
                    {
                        "agente_id": agente.id,
                        "cidade": ad.get("cidade", ""),
                        "casa": ad.get("casa", ""),
                        "orgao": orgao_do_agente(ad),
                        "nome_agente": nome_agente,
                        **clip.to_dict(),
                    }
                )
    logger.info("Corpus carregado: %d clippings.", len(clippings))

    escopos = _escopos(clippings)
    if args.jsonl:
        for alvo, (agente_id, nome) in ALVOS_GOVERNO.items():
            clips = [c for c in clippings if alvo in (c.get("alvos") or [])]
            if clips:
                escopos[f"agente-{agente_id}"] = (
                    {"tipo": "agente", "chave": agente_id, "nome": nome, "orgao": "governo-mt"},
                    clips,
                )
    if args.apenas:
        alvos = {x.strip() for x in args.apenas.split(",") if x.strip()}
        escopos = {k: v for k, v in escopos.items() if k in alvos}
        logger.info("Escopos filtrados: %s", ", ".join(escopos.keys()) or "(nenhum)")
    total = len(escopos)
    publicados = 0
    for i, (chave, (escopo_meta, clips)) in enumerate(escopos.items(), start=1):
        if not clips:
            db.collection(COLLECTION_LEXICAL).document(chave).set(
                {
                    "escopo": escopo_meta,
                    "orgao": escopo_meta.get("orgao", ""),
                    "n_clippings": 0,
                    "afc": {"palavras": [], "periodos": []},
                    "chd": {"classes": [], "n_segmentos": 0, "aviso": "Sem clippings no escopo."},
                    "grafo": {"nos": [], "arestas": []},
                    "dendrograma": {"polilinhas": [], "aviso": "Sem clippings no escopo."},
                    "resumo": "Sem clippings no escopo.",
                    "gerado_em": datetime.now(timezone.utc),
                },
                merge=True,
            )
            publicados += 1
            continue
        try:
            doc = _documento(escopo_meta, clips, args.n_classes, args.niveis)
            db.collection(COLLECTION_LEXICAL).document(chave).set(doc, merge=True)
            publicados += 1
            logger.info(
                "(%d/%d) %s: %d clippings | CHD %d classes | grafo %d arestas | dendo %d ramos",
                i, total, chave, len(clips),
                len(doc["chd"].get("classes", [])),
                len(doc["grafo"]["arestas"]),
                len(doc["dendrograma"].get("polilinhas", [])),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("(%d/%d) %s: falha ao calcular escopo — %s", i, total, chave, e)
            continue

    # Limpa docs antigos do formato plano (afc/chd/grafo/dendrograma/resumo)
    for antigo in DOCS_ANTIGOS:
        try:
            db.collection(COLLECTION_LEXICAL).document(antigo).delete()
        except Exception as e:  # noqa: BLE001
            logger.warning("Falha ao remover doc antigo %s: %s", antigo, e)

    logger.info("Analise lexical por escopo publicada: %d/%d escopos.", publicados, total)


if __name__ == "__main__":
    main()