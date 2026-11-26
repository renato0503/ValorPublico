"""Classifica comentarios de cidadaos em demandas e grava a colecao `demandas`.

Plano 05 §9, plano 13 (A4 Base / V5 Ouvidoria), plano 14 §2.4.

O que faz:
  1. le **somente comentarios** dos clippings (nao noticia/post) dos ultimos N dias;
  2. descarta comentarios escritos pela propria conta oficial (mesma autora do post);
  3. classifica cada um com `processing/demandas.py` (tema, bairro, urgencia);
  4. grava **so os que sao demanda** em `demandas/{escopo}__{hash}`:
     - id estavel (dedup por texto + agente);
     - `orgao` (para a tela filtrar a Casa), `status`, `origem`, `pasta_sugerida`;
     - `municipios_mencionados`: nomes de municipios citados **no texto** (nao e a
       origem do cidadao; sem inferencia);
     - resumo sem arroba/link e **sem autor** (fila sem identificacao);
  5. recalcula os KPIs K-24..K-27 nos `metricas*` (geral, por agente e por orgao).

Uso (a partir de `backend/`):
    python scripts/processar_demandas.py --orgao governo-mt --dias 400
    python scripts/processar_demandas.py --sem-firestore
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.processing.demandas import (
    RE_NAO_DEMANDA,
    RE_SPAM,
    TEMAS,
    classificar_demanda,
)
from cerra_nucleo.processing.bairros import detectar_bairro
from config import settings
from core.logger import get_logger
from processing.municipios_mt import detectar as detectar_municipios

logger = get_logger(__name__)

STATUS_VALIDOS = {"nova", "andamento", "respondida", "encaminhada"}

# Conta oficial do proprio orgao: o que ela escreve e resposta, nao pedido.
AUTORES_OFICIAIS = {"govmatogrosso", "otavianopivetta", "maxrussi", "interino-max-russi"}

# Pasta sugerida por tema (triagem; o encaminhamento real e humano).
PASTA_POR_TEMA = {
    "saude": "Secretaria de Saúde",
    "educacao": "Secretaria de Educação",
    "transporte": "Mobilidade / Transporte",
    "obras": "Obras / Infraestrutura",
    "seguranca": "Segurança Pública",
    "meio_ambiente": "Meio Ambiente",
    "habitacao": "Habitação / Regularização fundiária",
    "cultura": "Cultura / Esporte",
    "servicos": "Atendimento / Protocolo",
    "outros": "Ouvidoria (triagem)",
}

# Onde gravar o agregado do orgao (mesmo mapa do front).
ORGAO_PARA_DOCS = {
    "cuiaba": ("camara-cuiaba", "cuiaba"),
    "varzea-grande": ("camara-vg", "varzea-grande"),
    "almt": ("almt", "mato-grosso"),
    "governo-mt": ("governo-mt", "governo-de-mato-grosso"),
}



def _id_demanda(escopo: str, texto: str) -> str:
    """ID estavel (dedup por escopo + texto normalizado)."""
    digest = hashlib.sha1(texto.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{escopo}__{digest}"


def coletar_comentarios(db, dias: int = 30, orgao: str = "") -> list[dict]:
    """Comentarios de cidadaos nos clippings (ultimos N dias).

    Somente `Comentario`: noticia e post nao sao pedido do cidadao. Comentarios
    escritos pela propria conta oficial (mesma autora do post) sao descartados.
    """
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    saida: list[dict] = []
    for doc in db.collection("agentes_publicos").stream():
        agente = doc.to_dict() or {}
        if orgao and str(agente.get("orgao") or "") != orgao:
            continue
        clippings = doc.reference.collection("clippings")
        autores_post: dict[str, str] = {}
        for clip in clippings.stream():
            dados = clip.to_dict() or {}
            if str(dados.get("tipo", "")) != "Postagem":
                continue
            autores_post[str(dados.get("id_externo") or "")] = str(dados.get("autor") or "").lower()
        for clip in clippings.stream():
            dados = clip.to_dict() or {}
            if str(dados.get("tipo", "")) != "Comentario":
                continue
            bruto = dados.get("data_publicacao")
            if isinstance(bruto, datetime):
                if bruto.tzinfo is None:
                    bruto = bruto.replace(tzinfo=timezone.utc)
                if bruto < limite:
                    continue
            texto = str(dados.get("texto_limpo") or "").strip()
            if not texto:
                continue
            autor = str(dados.get("autor") or "").strip()
            shortcode = str((dados.get("metadados") or {}).get("post_shortcode") or "")
            origem_oficial = autores_post.get(shortcode, "") or ""
            if autor and (
                autor.lower() == origem_oficial
                or autor.lower() in AUTORES_OFICIAIS
            ):
                continue
            saida.append(
                {
                    "agente_id": doc.id,
                    "orgao": str(agente.get("orgao") or ""),
                    "casa": agente.get("casa") or agente.get("cidade") or "",
                    "texto": texto,
                    "rede": dados.get("plataforma", ""),
                    "url": dados.get("url", ""),
                    "autor": autor,
                    "data": bruto,
                }
            )
    return saida


def _resumo_pedido(texto: str, limite: int = 160) -> str:
    """Trecho do pedido sem arroba/link, para a fila (sem autor)."""
    limpo = re.sub(r"@[\w.]+", "", texto or "")
    limpo = re.sub(r"https?://\S+", "", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) <= limite:
        return limpo
    return limpo[:limite].rstrip() + "…"


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _tema_do_texto(texto: str) -> str | None:
    limpo = _sem_acento(texto)
    melhor = ""
    pontos = 0
    for nome, termos in TEMAS.items():
        achados = sum(1 for termo in termos if termo in limpo)
        if achados > pontos:
            melhor, pontos = nome, achados
    return melhor or None


def _manifestacao_leve(texto: str) -> dict | None:
    """Pergunta/reclamação/sugestão com tema, mesmo sem o verbo de pedido.

    A fila da Ouvidoria não deve ficar só com os pedidos formais: a população
    também cobra e sugere. O que não tem tema, é elogio ou é spam fica de fora.
    """
    bruto = (texto or "").strip()
    if len(bruto) < 20 or RE_SPAM.search(bruto) or RE_NAO_DEMANDA.search(bruto):
        return None
    limpo = _sem_acento(bruto)
    tema = _tema_do_texto(bruto)
    if not tema:
        return None
    pergunta = "?" in bruto or any(
        limpo.startswith(p)
        for p in ("quando", "onde", "por que", "porque", "como", "qual", "quais", "quem", "cade", "cadê")
    )
    reclamacao = any(
        p in limpo
        for p in (
            "problema", "falta", "demora", "atras", "ruim", "pessimo", "horrivel",
            "vergonha", "abandono", "crise", "greve", "aumento", "corte",
            "parado", "quebrad", "nao funciona", "nao atende", "descaso",
        )
    )
    sugestao = any(
        p in limpo
        for p in ("sugiro", "sugestao", "deveria", "poderia", "precisa", "seria bom", "devia", "propo")
    )
    if not (pergunta or reclamacao or sugestao):
        return None
    tipo = "reclamacao" if reclamacao else "sugestao" if sugestao else "pergunta"
    urgencia = (
        "alta"
        if any(p in limpo for p in ("urgente", "emergencia", "risco", "acidente", "desabo", "infec", "doente", "internad"))
        else "media"
        if reclamacao or "demora" in limpo or "atras" in limpo
        else "baixa"
    )
    return {
        "tipo": tipo,
        "tema": tema,
        "urgencia": urgencia,
        "bairro": detectar_bairro(bruto),
        "motivo": f"Texto com tema '{tema}' classificado como {tipo}.",
    }


def _municipios_dos_comentarios(comentarios: list[dict]) -> tuple[dict[str, int], int]:
    """{municipio: menções} em todos os comentários de cidadãos + nº de comentários com citação."""
    por_municipio: dict[str, int] = {}
    com_municipio = 0
    for item in comentarios:
        achados = detectar_municipios(item["texto"])
        if achados:
            com_municipio += 1
        for municipio in achados:
            por_municipio[municipio] = por_municipio.get(municipio, 0) + 1
    return dict(sorted(por_municipio.items(), key=lambda kv: -kv[1])), com_municipio



def _agregado_demandas(
    itens: list[dict],
    agora: str,
    municipios_comentarios: dict[str, int] | None = None,
    comentarios_total: int | None = None,
    comentarios_com_municipio: int | None = None,
) -> dict:
    if municipios_comentarios is None:
        por_municipio: dict[str, int] = {}
        for demanda in itens:
            for municipio in demanda.get("municipios_mencionados") or []:
                por_municipio[municipio] = por_municipio.get(municipio, 0) + 1
        com_municipio = len([d for d in itens if d.get("municipios_mencionados")])
        fonte = "manifestacoes"
        base_pct = len(itens)
    else:
        por_municipio = municipios_comentarios
        com_municipio = int(comentarios_com_municipio or 0)
        fonte = "comentarios"
        base_pct = int(comentarios_total or 0)
    return {
        "novas": len(itens),
        "abertas": len([d for d in itens if d.get("status") != "respondida"]),
        "encaminhadas": len([d for d in itens if d.get("status") == "encaminhada"]),
        "tempo_medio_resposta_horas": None,
        "por_tema": _contar(itens, "tema"),
        "por_tipo_manifestacao": _contar(itens, "tipo_manifestacao"),
        "por_bairro": {
            chave: valor
            for chave, valor in _contar(itens, "bairro").items()
            if chave != "—"
        },
        "por_urgencia": _contar(itens, "urgencia"),
        "por_origem": _contar(itens, "origem"),
        "por_pasta_sugerida": _contar(itens, "pasta_sugerida"),
        "por_municipio_mencionado": dict(
            sorted(por_municipio.items(), key=lambda kv: -kv[1])
        ),
        "municipios_fonte": fonte,
        "comentarios_cidadaos": comentarios_total,
        "comentarios_com_municipio": com_municipio,
        "com_municipio_mencionado": com_municipio,
        "pct_com_municipio_mencionado": round(100 * com_municipio / base_pct) if base_pct else 0,
        "atualizado_em": agora,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classifica comentarios em demandas.")
    parser.add_argument("--dias", type=int, default=30)
    parser.add_argument("--orgao", default="", help="Limita a um orgao (ex.: governo-mt).")
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    comentarios = coletar_comentarios(db, args.dias, args.orgao)
    logger.info("Comentarios de cidadaos lidos: %d", len(comentarios))

    demandas: list[dict] = []
    vistos: set[str] = set()
    for item in comentarios:
        resultado = classificar_demanda(item["texto"])
        if resultado["e_demanda"]:
            tipo_manifestacao = "pedido"
        else:
            leve = _manifestacao_leve(item["texto"])
            if not leve:
                continue
            resultado = {**resultado, **leve}
            tipo_manifestacao = leve["tipo"]
        escopo = f"agente-{item['agente_id']}"
        ident = _id_demanda(escopo, item["texto"])
        if ident in vistos:
            continue
        vistos.add(ident)
        demandas.append(
            {
                "id": ident,
                "escopo": escopo,
                "orgao": item["orgao"],
                "casa": item["casa"],
                "agente_id": item["agente_id"],
                "tema": resultado["tema"],
                "tipo_manifestacao": tipo_manifestacao,
                "bairro": resultado["bairro"],
                # Origem nao e inferida: fica vazia. `municipios_mencionados`
                # registra apenas os nomes de municipio citados no texto.
                "municipio": "",
                "municipios_mencionados": detectar_municipios(item["texto"]),
                "urgencia": resultado["urgencia"],
                "status": "nova",
                "origem": item["rede"] or "comentário",
                "rede": item["rede"],
                "url": item["url"],
                "resumo": _resumo_pedido(item["texto"]),
                "motivo": resultado["motivo"],
                "texto": item["texto"][:800],
                "sem_identificacao": True,
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "data_fonte": item["data"].isoformat() if item["data"] else "",
                "pasta_sugerida": PASTA_POR_TEMA.get(resultado["tema"], PASTA_POR_TEMA["outros"]),
            }
        )

    agora = datetime.now(timezone.utc).isoformat()
    municipios_comentarios, comentarios_com_municipio = _municipios_dos_comentarios(comentarios)
    agregado = _agregado_demandas(
        demandas,
        agora,
        municipios_comentarios,
        len(comentarios),
        comentarios_com_municipio,
    )
    logger.info("Manifestacoes classificadas: %d", len(demandas))
    logger.info("Por tema: %s", agregado["por_tema"])
    logger.info(
        "Municipios nos comentarios: %s | comentarios que citam municipio: %d/%d",
        agregado["por_municipio_mencionado"],
        comentarios_com_municipio,
        len(comentarios),
    )

    if args.sem_firestore:
        print("Dry-run: demandas classificadas (sem gravar).")
        return 0

    # Grava em lote de 400 (regra da cota).
    lote = db.batch()
    contador = 0
    for demanda in demandas:
        ref = db.collection("demandas").document(demanda["id"])
        lote.set(ref, demanda, merge=True)
        contador += 1
        if contador % 400 == 0:
            lote.commit()
            lote = db.batch()
    if contador % 400:
        lote.commit()
    logger.info("demandas gravadas: %d", contador)

    # KPIs (K-24..K-27) no agregado geral e por escopo.
    if not args.orgao:
        db.collection("metricas").document("geral").set({"demandas": agregado}, merge=True)

    comentarios_por_escopo: dict[str, list[dict]] = {}
    comentarios_por_orgao: dict[str, list[dict]] = {}
    for item in comentarios:
        comentarios_por_escopo.setdefault(f"agente-{item['agente_id']}", []).append(item)
        comentarios_por_orgao.setdefault(item["orgao"], []).append(item)

    por_escopo: dict[str, list[dict]] = {}
    for demanda in demandas:
        por_escopo.setdefault(demanda["escopo"], []).append(demanda)
    for escopo, itens in por_escopo.items():
        if escopo.startswith("agente-"):
            coments = comentarios_por_escopo.get(escopo, [])
            mpor, mcom = _municipios_dos_comentarios(coments)
            db.collection("metricas_por_agente").document(escopo[len("agente-"):]).set(
                {
                    "demandas": _agregado_demandas(
                        itens, agora, mpor, len(coments), mcom
                    )
                },
                merge=True,
            )

    # Agregado do orgao (mesmos documentos que o front le nas telas da Casa).
    por_orgao: dict[str, list[dict]] = {}
    for demanda in demandas:
        por_orgao.setdefault(demanda["orgao"], []).append(demanda)
    for orgao, itens in por_orgao.items():
        docs = ORGAO_PARA_DOCS.get(orgao)
        if not docs:
            continue
        coments = comentarios_por_orgao.get(orgao, [])
        mpor, mcom = _municipios_dos_comentarios(coments)
        dados = {
            "demandas": _agregado_demandas(
                itens, agora, mpor, len(coments), mcom
            )
        }
        casa, cidade = docs
        db.collection("metricas_por_casa").document(casa).set(dados, merge=True)
        db.collection("metricas_por_cidade").document(cidade).set(dados, merge=True)

    logger.info(
        "KPIs de demandas gravados (%s%d escopos + %d orgaos).",
        "geral + " if not args.orgao else "",
        len(por_escopo),
        len(por_orgao),
    )
    return 0


def _contar(itens: list[dict], campo: str) -> dict:
    contagem: dict[str, int] = {}
    for item in itens:
        chave = item.get(campo) or "—"
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "processar_demandas"))
