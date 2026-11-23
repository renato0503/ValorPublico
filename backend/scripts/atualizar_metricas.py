"""Recalcula metricas agregadas do dashboard e grava no Firestore.

Produz documentos otimizados para leitura em tempo real no PWA:
  metricas/geral               -> visao global (KPIs + series + top fontes)
  metricas_por_cidade/<slug>   -> visao por cidade
  metricas_por_agente/<id>     -> visao por parlamentar

Uso: python backend/scripts/atualizar_metricas.py
"""

import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unicodedata import normalize

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import COLLECTION_AGENTES, SUBCOLLECTION_CLIPPINGS
from core.firebase_client import init_firebase
from core.logger import get_logger
from processing.classificador_midia import classificar_clipping
from processing.nuvem import frequencia
logger = get_logger(__name__)


def slugify_cidade(cidade: str) -> str:
    cidade = normalize("NFKD", cidade).encode("ascii", "ignore").decode("utf-8")
    return "-".join(cidade.strip().lower().split())


def _chave_dia(dt) -> str:
    if dt is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).date().isoformat()
    return str(dt)[:10]


def _espaco_de(c: dict) -> dict:
    """Espaco ocupado por um clipping, por tipo de midia.

    - Site/Web: caracteres do texto (metadado espaco_carac ou len(texto)).
    - TV/Radio/YouTube: duracao em segundos (metadado duracao_seg).
    - Impresso: area em cm² (metadado espaco_cm2).
    """
    met = c.get("metadados", {}) or {}
    plataforma = c.get("plataforma", "Web")
    texto = c.get("texto_limpo") or ""

    espaco_carac = int(met.get("espaco_carac") or 0)
    if not espaco_carac and plataforma in ("Web", "Impresso"):
        espaco_carac = len(texto)

    duracao_seg = int(met.get("duracao_seg") or 0)
    if not duracao_seg and plataforma in ("TV", "Radio", "YouTube"):
        # estimativa: ~15 caracteres por segundo de fala transcrita
        duracao_seg = max(0, round(len(texto) / 15))

    cm2 = float(met.get("espaco_cm2") or 0)
    if not cm2 and plataforma == "Impresso":
        cm2 = round(espaco_carac / 12, 1)

    return {
        "caracteres": espaco_carac if plataforma in ("Web", "Impresso") else 0,
        "duracao_seg": duracao_seg if plataforma in ("TV", "Radio", "YouTube") else 0,
        "cm2": cm2 if plataforma == "Impresso" else 0,
    }


def _dentro_janela(dt, dias: int) -> bool:
    """True se a data esta dentro dos ultimos `dias` dias (a partir de hoje)."""
    if dt is None:
        return False
    try:
        if isinstance(dt, datetime):
            data = dt.astimezone(timezone.utc).date()
        else:
            data = str(dt)[:10]
        hoje = datetime.now(timezone.utc).date()
        return (hoje - data).days <= dias and (hoje - data).days >= 0
    except Exception:
        return False


def _insights(agregado: dict, categorias: dict, veiculos: Counter,
              audiencia_por_veiculo: dict, valor_por_veiculo: dict) -> dict:
    """Insights principais (estilo DSM): maior cobertura, veiculo destaque, tendencia."""
    sent = agregado.get("distribuicao_sentimento", {})
    total_sent = sum(sent.values()) or 1
    pct_positivo = round(100 * sent.get("positivo", 0) / total_sent, 2)
    pct_negativo = round(100 * sent.get("negativo", 0) / total_sent, 2)

    # maior cobertura: categoria com mais menções
    maior_cobertura = max(categorias.items(), key=lambda kv: kv[1]) if categorias else ("", 0)

    # veiculo em destaque: top 1 por quantidade (desempatando por valor)
    veiculo_destaque = ""
    if veiculos:
        top = veiculos.most_common(1)[0]
        veiculo_destaque = top[0]

    # tendencia: comparando 7 dias recentes vs 7 anteriores (se houver serie)
    serie = agregado.get("serie_sentimento", {})
    chaves = sorted(serie.keys())
    def _soma(ks):
        tot = 0
        for k in ks:
            tot += sum((serie[k] or {}).values())
        return tot
    tendencia = None
    if len(chaves) >= 14:
        anterior = _soma(chaves[:-7])
        recente = _soma(chaves[-7:])
        if anterior > 0:
            tendencia = round(100 * (recente - anterior) / anterior, 1)

    return {
        "maior_cobertura": {"categoria": maior_cobertura[0], "mencoes": maior_cobertura[1]},
        "veiculo_destaque": veiculo_destaque,
        "tendencia_positiva": tendencia,
        "pct_positivo": pct_positivo,
        "pct_negativo": pct_negativo,
    }


def _agregar(clippings: list[dict]) -> dict:
    """Metricas de um conjunto de clippings (global, cidade ou agente)."""
    veiculos: Counter = Counter()
    audiencia_por_veiculo: defaultdict[str, int] = defaultdict(int)
    valor_por_veiculo: defaultdict[str, float] = defaultdict(float)
    categorias: Counter = Counter()
    sentimentos: Counter = Counter()
    valoracao_por_plataforma: defaultdict[str, float] = defaultdict(float)
    valoracao_por_categoria: defaultdict[str, float] = defaultdict(float)
    serie: defaultdict[str, Counter] = defaultdict(Counter)
    serie_sentimento: defaultdict[str, Counter] = defaultdict(Counter)
    temas: Counter = Counter()
    categoria_por_veiculo: dict[str, str] = {}
    espaco_total = {"caracteres": 0, "duracao_seg": 0, "cm2": 0}

    for c in clippings:
        plataforma = c.get("plataforma", "Web")
        autor = (c.get("autor") or "").strip()
        veiculo = c.get("metadados", {}).get("veiculo") or autor or "Sem fonte"
        valor = float(c.get("valor_estimado") or 0)
        categoria = classificar_clipping(c)
        categoria_por_veiculo.setdefault(veiculo, categoria)

        categorias[categoria] += 1
        sentimentos[c.get("sentimento", "neutro")] += 1
        valoracao_por_plataforma[plataforma] += valor
        valoracao_por_categoria[categoria] += valor

        veiculos[veiculo] += 1
        audiencia_por_veiculo[veiculo] += int(c.get("alcance") or 0)
        valor_por_veiculo[veiculo] += valor

        e = _espaco_de(c)
        espaco_total["caracteres"] += e["caracteres"]
        espaco_total["duracao_seg"] += e["duracao_seg"]
        espaco_total["cm2"] += e["cm2"]

        dia = _chave_dia(c.get("data_publicacao"))
        serie[dia][plataforma] += 1
        serie_sentimento[dia][c.get("sentimento", "neutro")] += 1

        for tema in c.get("categorias") or []:
            temas[tema] += 1

    nuvem_geral, nuvem_por_mes = frequencia(clippings)

    top_veiculos = []
    for nome, qtd in veiculos.most_common(15):
        top_veiculos.append(
            {
                "nome": nome,
                "clippings": qtd,
                "audiencia": audiencia_por_veiculo[nome],
                "valor_estimado": round(valor_por_veiculo[nome], 2),
                "categoria_midia": categoria_por_veiculo.get(nome, "Outros"),
            }
        )

    categorias_dict = dict(categorias)

    # Noticias recentes (detalhe no dashboard / Sprint 24)
    def _ts(c):
        d = c.get("data_publicacao")
        if d is None:
            return 0
        try:
            return d.timestamp()
        except Exception:  # noqa: BLE001
            return 0

    recents = sorted(clippings, key=_ts, reverse=True)[:10]
    noticias_recentes = [
        {
            "id_clipping": c.get("id_clipping") or "",
            "texto_limpo": (c.get("texto_limpo") or "")[:300],
            "veiculo": c.get("metadados", {}).get("veiculo") or c.get("autor") or "Sem fonte",
            "plataforma": c.get("plataforma", "Web"),
            "data_publicacao": c.get("data_publicacao"),
            "sentimento": c.get("sentimento", "neutro"),
            "valor_estimado": round(float(c.get("valor_estimado") or 0), 2),
            "alcance": int(c.get("alcance") or 0),
            "url": c.get("url") or "",
            "categorias": c.get("categorias") or [],
            "agente": c.get("nome_agente") or "",
            "cidade": c.get("cidade") or "",
        }
        for c in recents
    ]

    agregado = {
        "total_clippings": len(clippings),
        "total_veiculos": len(veiculos),
        "audiencia_total": sum(audiencia_por_veiculo.values()),
        "valoracao_total": round(sum(valor_por_veiculo.values()), 2),
        "distribuicao_categorias": categorias_dict,
        "distribuicao_sentimento": dict(sentimentos),
        "distribuicao_temas": dict(temas.most_common()),
        "valoracao_por_plataforma": dict(valoracao_por_plataforma),
        "valoracao_por_categoria": dict(valoracao_por_categoria),
        "espaco_total": espaco_total,
        "top_veiculos": top_veiculos,
        "dias": {dia: dict(contagens) for dia, contagens in sorted(serie.items())},
        "serie_sentimento": {
            dia: dict(contagens) for dia, contagens in sorted(serie_sentimento.items())
        },
        "nuvem_geral": nuvem_geral,
        "nuvem_por_mes": nuvem_por_mes,
        "noticias_recentes": noticias_recentes,
        "atualizado_em": datetime.now(timezone.utc),
    }
    agregado["insights"] = _insights(
        agregado, categorias_dict, veiculos, audiencia_por_veiculo, valor_por_veiculo
    )
    return agregado


def agregar(clippings: list[dict]) -> dict:
    """Metricas totais + janelas de periodo (hoje/7d/30d) para o dashboard.

    Cada janela e um sub-conjunto dos clippings filtrado por data, permitindo
    ao frontend alternar o período sem nova consulta ao Firestore.
    """
    base = _agregar(clippings)

    hoje = datetime.now(timezone.utc).date().isoformat()
    janelas = {"hoje": [], "7d": [], "30d": []}
    for c in clippings:
        dia = _chave_dia(c.get("data_publicacao"))
        if dia == hoje:
            janelas["hoje"].append(c)
        if _dentro_janela(c.get("data_publicacao"), 7):
            janelas["7d"].append(c)
        if _dentro_janela(c.get("data_publicacao"), 30):
            janelas["30d"].append(c)

    base["por_periodo"] = {
        chave: _agregar(clips)
        for chave, clips in janelas.items()
    }
    return base


def coletar_clippings(db) -> list[dict]:
    clippings = []
    agentes = db.collection(COLLECTION_AGENTES).stream()
    for agente in agentes:
        agente_dict = agente.to_dict()
        cidade = agente_dict.get("cidade", "")
        nome_agente = (
            agente_dict.get("nome_urna")
            or agente_dict.get("nome")
            or agente.id
        )
        for clip in agente.reference.collection(SUBCOLLECTION_CLIPPINGS).stream():
            clippings.append(
                {
                    "agente_id": agente.id,
                    "cidade": cidade,
                    "nome_agente": nome_agente,
                    **clip.to_dict(),
                }
            )
    return clippings


def main() -> None:
    db = init_firebase()
    clippings = coletar_clippings(db)
    logger.info("Lidos %d clippings de todas as subcolecoes.", len(clippings))
    ultima_execucao = None
    historico_ingestao: list[dict] = []
    try:
        execs = (
            db.collection("execucoes_ingestao")
            .order_by("executado_em", direction="DESCENDING")
            .limit(15)
            .stream()
        )
        for exec_doc in execs:
            e = exec_doc.to_dict()
            item = {
                "executado_em": e.get("executado_em"),
                "total_agentes": e.get("total_agentes"),
                "total_brutos": e.get("total_brutos"),
                "total_gravados": e.get("total_gravados"),
                "sucesso": e.get("sucesso", True),
            }
            historico_ingestao.append(item)
            if ultima_execucao is None:
                ultima_execucao = item
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao ler historico de execucoes: %s", e)

    dados_geral = agregar(clippings)
    dados_geral["historico_ingestao"] = historico_ingestao
    if ultima_execucao:
        dados_geral["ultima_execucao"] = ultima_execucao
    db.collection("metricas").document("geral").set(dados_geral)

    por_cidade: dict[str, list[dict]] = defaultdict(list)
    por_agente: dict[str, list[dict]] = defaultdict(list)
    for c in clippings:
        cidade = c.get("cidade") or "Sem cidade"
        por_cidade[cidade].append(c)
        por_agente[c["agente_id"]].append(c)

    for cidade, clips in por_cidade.items():
        db.collection("metricas_por_cidade").document(slugify_cidade(cidade)).set(
            agregar(clips)
        )
    for agente_id, clips in por_agente.items():
        db.collection("metricas_por_agente").document(agente_id).set(
            agregar(clips)
        )

    logger.info(
        "Metricas gravadas: geral + %d cidades + %d agentes. Total de clippings: %d.",
        len(por_cidade), len(por_agente), len(clippings),
    )


if __name__ == "__main__":
    main()