"""Publica os agregados do clipping do Governo de Mato Grosso (F5).

Grava (com merge=True, em lote de 400):
  * `metricas_por_cidade/governo-de-mato-grosso` -> o Governo do Estado como um todo
  * `metricas_por_casa/governo-mt`             -> a Casa (soma do Executivo)
  * `metricas_por_secretaria/<slug>`          -> uma pasta por secretaria/autarquia
  * `metricas_por_agente/governador-otaviano-pivetta` -> o governador
  * `metricas_por_agente/interino-max-russi`         -> o interino

Reusa o agregador do `atualizar_metricas.py` (mesmo formato do front).
Nao mexe em `metricas/geral` nem nos escopos das Camaras e da ALMT: cada orgao
fica no seu proprio escopo (muralha de dados).

Uso (a partir de `backend/`):
    python scripts/atualizar_metricas_governo.py --jsonl data/governo_mt/noticias-2026-11-24.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from processing.governo_filtros import id_da_noticia, linhas_da_base, sanear_itens
from processing import governo_imagem
from processing.veiculos_mt import classificar as classificar_veiculo
from config.settings import BASE_DIR
from scripts.atualizar_metricas import agregar, slugify_cidade

logger = get_logger(__name__)

SEED = BASE_DIR / "data" / "seeds" / "governo_mt.json"
PASTA_PADRAO = BASE_DIR / "data" / "governo_mt"


def carregar_itens(caminho: Path | None) -> list[dict]:
    """Base do Governo (um arquivo ou a uniao de todos os JSONL), saneada."""
    itens = []
    for item in linhas_da_base(PASTA_PADRAO, caminho):
        data = item.get("data")
        if isinstance(data, str):
            try:
                data = datetime.fromisoformat(data.replace("Z", "+00:00"))
            except ValueError:
                data = None
        item["data_publicacao"] = data
        itens.append(item)
    itens, removidos = sanear_itens(itens)
    if removidos:
        print(f"ignorados {len(removidos)} itens de veiculos de fora de MT")
    return itens


def como_clipping(item: dict) -> dict:
    """Converte o item coletado no formato de clipping esperado pelo agregador."""
    return {
        "id_externo": item.get("url", "")[:120],
        "plataforma": "Web",
        "tipo": "Noticia",
        "texto_limpo": f"{item.get('titulo', '')}\n{item.get('resumo', '')}".strip(),
        "titulo": item.get("titulo", ""),
        "data_publicacao": item.get("data_publicacao"),
        "url": item.get("url", ""),
        "autor": item.get("veiculo", ""),
        "alcance": 0,
        "sentimento": item.get("sentimento", "neutro"),
        "tema": (item.get("temas") or ["geral"])[0],
        "valor_estimado": 0.0,
        "valor_avpe": 0.0,
        "metadados": {
            "veiculo": item.get("veiculo", ""),
            "secretarias": item.get("secretarias", []),
            "siglas": item.get("siglas", []),
            "municipios": item.get("municipios", []),
            "alvos": item.get("alvos", []),
            "escopo": item.get("escopo", ""),
            "confianca_secretaria": item.get("confianca_secretaria", 0),
            "origem": item.get("origem", ""),
            "tier": classificar_veiculo(item.get("veiculo", "")).get("tier", ""),
        },
    }


def por_municipio(itens: list[dict]) -> dict:
    """{municipio: {total, positivo, neutro, negativo, ibge}} das noticias."""
    from processing.municipios_mt import por_nome

    ibge = {nome: m["ibge"] for nome, m in por_nome().items()}
    saida: dict[str, dict] = {}
    for item in itens:
        tom = item.get("sentimento") or "neutro"
        for nome in item.get("municipios") or []:
            linha = saida.setdefault(
                nome,
                {"total": 0, "positivo": 0, "neutro": 0, "negativo": 0, "ibge": ibge.get(nome, "")},
            )
            linha["total"] += 1
            if tom in ("positivo", "neutro", "negativo"):
                linha[tom] += 1
    return dict(sorted(saida.items(), key=lambda kv: -kv[1]["total"]))


# Clipping completo para o app: documentos mensais compactos (so os campos da
# tela), legiveis apenas pelo orgao governo-mt. A colecao bruta continua fechada.
LIMITE_PARTE_BYTES = 800_000


def partes_do_clipping(itens: list[dict], clippings: list[dict]) -> dict[str, dict]:
    por_mes: dict[str, list[dict]] = defaultdict(list)
    for item, clip in zip(itens, clippings):
        data = item.get("data_publicacao")
        mes = data.strftime("%Y-%m") if data else "sem-data"
        por_mes[mes].append(
            {
                "id": id_da_noticia(item),
                "titulo": item.get("titulo", ""),
                "url": item.get("url", ""),
                "veiculo": item.get("veiculo", ""),
                "data": data.isoformat() if data else "",
                "siglas": item.get("siglas") or [],
                "municipios": item.get("municipios") or [],
                "alvos": [a for a in (item.get("alvos") or []) if a in ("governador", "interino")],
                "escopo": item.get("escopo", ""),
                "sentimento": item.get("sentimento", "neutro"),
                "valor": round(float(clip.get("valor_estimado") or 0), 2),
                "tier": classificar_veiculo(item.get("veiculo", "")).get("tier", ""),
            }
        )
    partes: dict[str, dict] = {}
    for mes, lista in sorted(por_mes.items()):
        lista.sort(key=lambda n: n["data"], reverse=True)
        bloco: list[dict] = []
        tamanho = 0
        numero = 1
        for noticia in lista:
            peso = len(json.dumps(noticia, ensure_ascii=False).encode("utf-8")) + 4
            if bloco and tamanho + peso > LIMITE_PARTE_BYTES:
                partes[f"{mes}-{numero}"] = {"mes": mes, "noticias": bloco}
                bloco, tamanho, numero = [], 0, numero + 1
            bloco.append(noticia)
            tamanho += peso
        if bloco:
            partes[f"{mes}-{numero}"] = {"mes": mes, "noticias": bloco}
    return partes


def aplicar_valoracao(db, clippings: list[dict]) -> None:
    """Aplica a valoracao do app (mesma tabela de veiculos e regras do Assessor)."""
    import pandas as pd
    from processing.valoracao import Valorador

    valorador = Valorador(db)
    df = pd.DataFrame(clippings)
    if df.empty:
        return
    df = valorador.aplicar_dataframe(df)
    for indice, linha in df.iterrows():
        clippings[indice]["valor_estimado"] = float(linha.get("valor_estimado") or 0)
        clippings[indice]["valor_avpe"] = float(linha.get("valor_avpe") or 0)


def _equidade(contagens: list[int]) -> float:
    """Entropia normalizada (0–1) da distribuição entre secretarias."""
    valores = [float(c) for c in contagens if c and c > 0]
    if len(valores) < 2:
        return 0.0
    total = sum(valores)
    entropia = -sum((v / total) * math.log(v / total) for v in valores)
    return round(entropia / math.log(len(valores)), 3)


def _data_clip(c: dict):
    valor = c.get("data_publicacao")
    if isinstance(valor, datetime):
        return valor.astimezone(timezone.utc).date() if valor.tzinfo else valor.date()
    if isinstance(valor, str) and valor:
        try:
            return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _previsao(clippings: list[dict], dias: int = 30, horizonte: int = 7) -> dict:
    """Série diária + projeção simples (média móvel de 7 dias com margem)."""
    hoje = datetime.now(timezone.utc).date()
    inicio = hoje - timedelta(days=dias - 1)
    contagem: dict = {}
    for clipping in clippings:
        dia = _data_clip(clipping)
        if dia and inicio <= dia <= hoje:
            contagem[dia] = contagem.get(dia, 0) + 1
    if sum(contagem.values()) < 5:
        return {}
    historico = []
    for i in range(dias):
        dia = inicio + timedelta(days=i)
        historico.append({"data": dia.isoformat(), "valor": contagem.get(dia, 0)})
    ultimos = [historico[-i]["valor"] for i in range(1, min(8, len(historico) + 1))]
    media = sum(ultimos) / len(ultimos)
    variancia = sum((v - media) ** 2 for v in ultimos) / len(ultimos)
    desvio = math.sqrt(variancia)
    previsao = []
    for i in range(1, horizonte + 1):
        dia = hoje + timedelta(days=i)
        previsao.append(
            {
                "data": dia.isoformat(),
                "valor": round(media, 2),
                "superior": round(media + desvio, 2),
                "inferior": max(0, round(media - desvio, 2)),
            }
        )
    return {
        "historico": historico,
        "previsao": previsao,
        "metodo": "media_movel_7d",
    }


# Contas oficiais no Instagram (coleta pública em docs/instagram, já no Firestore)
CONTAS_INSTAGRAM = {
    "governo-mt": "@govmatogrosso",
    "governador-otaviano-pivetta": "@otavianopivetta",
}


def ler_instagram(db) -> list[dict]:
    """Posts e comentários do Instagram das contas oficiais do Governo."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    saida = []
    for agente_id, conta in CONTAS_INSTAGRAM.items():
        colecao = db.collection("agentes_publicos").document(agente_id).collection("clippings")
        for doc in colecao.where(filter=FieldFilter("plataforma", "==", "Instagram")).stream():
            dados = doc.to_dict() or {}
            # só o que foi coletado das próprias contas (a busca social traz
            # perfis e páginas de terceiros, ex.: @governoms)
            if (dados.get("metadados") or {}).get("origem_coleta") not in ("navegador", "manual"):
                continue
            dados["agente_id"] = agente_id
            dados["nome_agente"] = conta
            dados["conta"] = conta
            saida.append(dados)
    return saida


def resumo_contas(instagram: list[dict]) -> list[dict]:
    """Uma linha por conta: posts, comentários, tom do público e post de maior alcance."""
    contas = []
    for agente_id, conta in CONTAS_INSTAGRAM.items():
        itens = [c for c in instagram if c.get("agente_id") == agente_id]
        posts = [c for c in itens if c.get("tipo") == "Postagem"]
        comentarios = [c for c in itens if c.get("tipo") == "Comentario"]
        tons = {t: sum(1 for c in comentarios if (c.get("sentimento") or "neutro") == t) for t in ("positivo", "neutro", "negativo")}
        curtidas = sum(int((p.get("metadados") or {}).get("curtidas") or 0) for p in posts)
        datas = sorted(
            (p.get("data_publicacao") for p in posts if p.get("data_publicacao")), reverse=True
        )
        destaque = max(posts, key=lambda p: int((p.get("metadados") or {}).get("curtidas") or 0), default=None)
        total_tom = sum(tons.values())
        contas.append(
            {
                "conta": conta,
                "agente_id": agente_id,
                "rede": "Instagram",
                "posts": len(posts),
                "comentarios": len(comentarios),
                "curtidas": curtidas,
                "media_curtidas": round(curtidas / len(posts)) if posts else 0,
                "tom_publico": tons,
                "saldo_publico": round(100 * (tons["positivo"] - tons["negativo"]) / total_tom) if total_tom else None,
                "ultimo_post": datas[0] if datas else None,
                "destaque": {
                    "texto": (destaque.get("texto_limpo") or "")[:160],
                    "url": destaque.get("url") or "",
                    "curtidas": int((destaque.get("metadados") or {}).get("curtidas") or 0),
                }
                if destaque
                else None,
            }
        )
    return contas


def main() -> int:
    parser = argparse.ArgumentParser(description="Agregados do Governo de MT.")
    parser.add_argument("--jsonl", default="", help="um arquivo; sem ele, a uniao de todas as coletas")
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    itens = carregar_itens(Path(args.jsonl) if args.jsonl else None)
    if not itens:
        logger.error("Nada coletado ainda. Rode coletar_governo_mt.py.")
        return 1
    clippings = [como_clipping(i) for i in itens]
    logger.info("Clippings do Governo: %d", len(clippings))

    # por pasta
    por_pasta: dict[str, list[dict]] = defaultdict(list)
    for item, clipping in zip(itens, clippings):
        for sigla in item.get("siglas") or []:
            if sigla:
                por_pasta[sigla].append(clipping)

    # por alvo (governador / interino)
    por_alvo: dict[str, list[dict]] = defaultdict(list)
    for item, clipping in zip(itens, clippings):
        for alvo in item.get("alvos") or []:
            if alvo in ("governador", "interino"):
                por_alvo[alvo].append(clipping)

    municipios_geral = por_municipio(itens)
    partes = partes_do_clipping(itens, clippings)

    if args.sem_firestore:
        print(f"dry-run: {len(clippings)} clippings | {len(por_pasta)} pastas | {len(por_alvo)} alvos")
        print(f"  municipios citados: {len(municipios_geral)} | partes do clipping: {len(partes)}")
        for chave, parte in partes.items():
            tamanho = len(json.dumps(parte, ensure_ascii=False).encode("utf-8"))
            print(f"    {chave}: {len(parte['noticias'])} noticias, {tamanho // 1024} KB")
        for sigla, lista in sorted(por_pasta.items(), key=lambda p: -len(p[1])):
            print(f"  {sigla:16s} {len(lista)}")
        return 0

    from core.firebase_client import init_firebase

    db = init_firebase()
    aplicar_valoracao(db, clippings)
    lote = db.batch()
    escritas = 0

    def gravar(colecao: str, doc_id: str, dados: dict) -> None:
        nonlocal lote, escritas
        lote.set(db.collection(colecao).document(doc_id), dados, merge=True)
        escritas += 1
        if escritas % 400 == 0:
            lote.commit()
            lote = db.batch()

    agora = datetime.now(timezone.utc).isoformat()

    # 1) o Governo do Estado como um todo (cidade) + a Casa
    agregado = agregar(clippings)
    # Tela "Imagem": índice, Tier 1, canais, o que mudou e picos negativos (plano 22)
    from scripts.atualizar_metricas import _redes_sociais

    instagram = ler_instagram(db)
    comentarios_ig = [c for c in instagram if c.get("tipo") == "Comentario"]
    agregado.update(governo_imagem.imagem_e_canais(itens, comentarios_ig))
    agregado["especificidades"] = {"semana_vs_base": governo_imagem.semana_vs_base(itens)}
    agregado["crise_eventos"] = governo_imagem.eventos_crise(itens)
    agregado["negativos_media_dia"] = governo_imagem.media_negativos(itens)
    # Tela "Redes": Instagram oficial do Governo e do governador
    redes = _redes_sociais(instagram, com_posts=True, limite_posts=80, limite_comentarios=8)
    redes["contas"] = resumo_contas(instagram)
    redes["fonte"] = "Instagram público de @govmatogrosso e @otavianopivetta (posts e comentários)"
    agregado["redes_sociais"] = redes
    logger.info(
        "Imagem %s | Tier 1 %s%% | Instagram: %d posts, %d comentários",
        agregado.get("imagem_institucional"),
        agregado.get("pct_tier1"),
        sum(1 for c in instagram if c.get("tipo") == "Postagem"),
        len(comentarios_ig),
    )
    agregado["atualizado_em"] = agora
    agregado["escopo"] = "governo-estado"
    agregado["orgao"] = "governo-mt"
    agregado["equidade_visibilidade"] = _equidade(
        [len(lista) for lista in por_pasta.values()]
    )
    previsao = _previsao(clippings)
    if previsao:
        agregado["previsao"] = {"mencoes": previsao}
    agregado["por_municipio"] = municipios_geral
    gravar("metricas_por_cidade", slugify_cidade("Governo de Mato Grosso"), agregado)
    gravar("metricas_por_casa", "governo-mt", agregado)

    # 2) uma pasta por secretaria/autarquia
    nomes = {
        s["sigla"]: s.get("nome", "")
        for s in seed.get("secretarias", []) + seed.get("autarquias", [])
    }
    titulares = {
        s["sigla"]: s.get("titular", "")
        for s in seed.get("secretarias", []) + seed.get("autarquias", [])
    }
    itens_por_pasta: dict[str, list[dict]] = defaultdict(list)
    for item in itens:
        for sigla in item.get("siglas") or []:
            if sigla:
                itens_por_pasta[sigla].append(item)
    for sigla, lista in por_pasta.items():
        pasta_doc = agregar(lista)
        pasta_doc["por_municipio"] = por_municipio(itens_por_pasta[sigla])
        pasta_doc["atualizado_em"] = agora
        pasta_doc["orgao"] = "governo-mt"
        pasta_doc["pasta"] = {
            "sigla": sigla,
            "nome": nomes.get(sigla, sigla),
            "titular": titulares.get(sigla, ""),
        }
        gravar("metricas_por_secretaria", _slug(sigla), pasta_doc)

    # 3) governador e interino
    slugs_alvo = {
        "governador": seed.get("governador", {}).get("slug", "governador-otaviano-pivetta"),
        "interino": seed.get("interino", {}).get("slug", "interino-max-russi"),
    }
    for alvo, lista in por_alvo.items():
        doc = agregar(lista)
        doc["atualizado_em"] = agora
        doc["orgao"] = "governo-mt"
        gravar("metricas_por_agente", slugs_alvo[alvo], doc)

    # 4) clipping completo, por mes (substitui as partes antigas)
    colecao_clip = db.collection("clipping_governo")
    antigas = {d.id for d in colecao_clip.list_documents()} - {"_indice"}
    for chave, parte in partes.items():
        parte["orgao"] = "governo-mt"
        parte["atualizado_em"] = agora
        gravar("clipping_governo", chave, parte)
    for chave in antigas - set(partes):
        lote.delete(colecao_clip.document(chave))
        escritas += 1
    gravar(
        "clipping_governo",
        "_indice",
        {
            "orgao": "governo-mt",
            "atualizado_em": agora,
            "total": len(itens),
            "partes": [
                {"id": chave, "mes": parte["mes"], "total": len(parte["noticias"])}
                for chave, parte in partes.items()
            ],
            "secretarias": {sigla: nomes.get(sigla, sigla) for sigla in sorted(por_pasta)},
            "municipios": list(municipios_geral),
        },
    )

    if escritas % 400:
        lote.commit()

    # `set(merge=True)` junta mapas e deixava chaves velhas (ex.: canais de
    # gravações antigas). `update` substitui cada campo do Governo por inteiro.
    for colecao, doc_id in (
        ("metricas_por_casa", "governo-mt"),
        ("metricas_por_cidade", slugify_cidade("Governo de Mato Grosso")),
    ):
        db.collection(colecao).document(doc_id).update(dict(agregado))

    logger.info("Documentos gravados: %d", escritas)
    logger.info(
        "  metricas_por_cidade/governo-de-mato-grosso · metricas_por_casa/governo-mt · "
        "metricas_por_secretaria/* (%d) · metricas_por_agente/%s",
        len(por_pasta),
        ", ".join(slugs_alvo.values()),
    )
    return 0


def _slug(texto: str) -> str:
    import re
    import unicodedata

    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8").lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "atualizar_metricas_governo"))
