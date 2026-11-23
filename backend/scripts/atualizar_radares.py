"""Publica a Camada DSM: radar de propaganda publica, alertas e cobertura/SLA.

Grava tres colecoes novas (leitura publica pelo PWA):

  radares/<escopo>     -> radar de propaganda publica/institucional
  alertas/<escopo>     -> alertas acionaveis (negativa direta, compliance, valor alto)
  cobertura/<escopo>   -> SLA, cobertura por veiculo/tier e fontes ausentes

Os escopos seguem o padrao ja usado em `releases_ia`: `geral`,
`cidade-<slug>` e `agente-<id>`, com janelas `periodo-hoje|7d|15d|30d`.

Uso:
    python scripts/atualizar_radares.py
    python scripts/atualizar_radares.py --periodos hoje,7d
"""

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (  # noqa: E402
    ALERTA_VALOR_ALTO,
    COLLECTION_ALERTAS,
    COLLECTION_COBERTURA,
    COLLECTION_RADARES,
    TIER1_VEICULOS,
    VEICULOS_ESPERADOS,
)
from core.firebase_client import init_firebase  # noqa: E402
from core.logger import get_logger  # noqa: E402
from core.quota import main_com_cota  # noqa: E402
from processing.alertas import detectar_alertas  # noqa: E402
from processing.alertas import resumir as _resumir_alertas  # noqa: E402
from processing.cobertura import TIER1_PADRAO, analisar_cobertura  # noqa: E402
from processing.mencao import resumir_mencoes  # noqa: E402
from processing.propaganda_publica import resumo as _resumo_radar  # noqa: E402
from scripts.atualizar_metricas import (  # noqa: E402
    _dentro_janela,
    coletar_clippings,
    slugify_cidade,
)

logger = get_logger(__name__)

PERIODOS = {"hoje": 0, "7d": 7, "15d": 15, "30d": 30}
MAX_ITENS_RADAR = 60
MAX_ITENS_ALERTAS = 80


def _janelas(clippings: list[dict]) -> dict[str, list[dict]]:
    """Divide os clippings por janela temporal.

    Itens sem data de publicacao (fontes oficiais, por exemplo) entram na
    janela "hoje" — foram coletados agora e precisam aparecer no painel.
    A janela "todas" cobre o acervo inteiro.
    """
    janelas: dict[str, list[dict]] = {chave: [] for chave in PERIODOS}
    janelas["todas"] = list(clippings)
    hoje = datetime.now(timezone.utc).date().isoformat()
    for clipping in clippings:
        data = clipping.get("data_publicacao")
        if not data:
            janelas["hoje"].append(clipping)
            continue
        dia = str(data)[:10]
        if dia == hoje:
            janelas["hoje"].append(clipping)
        for chave, dias in PERIODOS.items():
            if dias and _dentro_janela(clipping.get("data_publicacao"), dias):
                janelas[chave].append(clipping)
    return janelas


def _item_radar(clipping: dict) -> dict:
    radar = clipping.get("propaganda_publica") or {}
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    if not radar and clipping.get("radar"):
        radar = clipping.get("radar") or {}
    return {
        "id_clipping": clipping.get("id_clipping") or clipping.get("id_externo") or "",
        "classe": clipping.get("classe") or radar.get("classe", ""),
        "orgao": radar.get("orgao", "") or clipping.get("orgao", ""),
        "tipo": clipping.get("tipo") or radar.get("tipo", ""),
        "simbolos_publicos": bool(radar.get("simbolos_publicos") or clipping.get("simbolos_publicos")),
        "titulo": (clipping.get("texto_limpo") or "")[:220],
        "veiculo": metadados.get("veiculo") or clipping.get("autor") or "",
        "data_publicacao": clipping.get("data_publicacao"),
        "valor_estimado": float(clipping.get("valor_estimado") or 0.0),
        "valor_avpe": float(clipping.get("valor_avpe") or 0.0),
        "url": clipping.get("url") or "",
        "agente": clipping.get("nome_agente") or "",
        "cidade": clipping.get("cidade") or "",
    }


def coletar_radar(db) -> list[dict]:
    """Le os itens do radar ingeridos (colecao radar_publico)."""
    itens: list[dict] = []
    try:
        docs = db.collection("radar_publico").stream()
    except Exception as e:  # noqa: BLE001
        logger.warning("Sem itens do radar oficial: %s", e)
        return itens
    for doc in docs:
        dados = doc.to_dict() or {}
        dados["id_externo"] = doc.id
        itens.append(dados)
    return itens


def construir_documento(escopo: dict, clippings: list[dict], tier1: set[str]) -> dict:
    """Monta o documento com as janelas de periodo."""
    documento: dict = {"escopo": escopo}
    janelas = _janelas(clippings)

    for chave, itens in janelas.items():
        # --- radar ---
        itens_radar = [_item_radar(c) for c in itens]
        resumo_radar = _resumo_radar(itens_radar)
        documento[f"periodo-{chave}"] = {
            "radar": {
                "resumo": resumo_radar,
                "itens": sorted(
                    itens_radar,
                    key=lambda i: (i["classe"] != "propaganda_publica", -(i["valor_avpe"] or 0)),
                )[:MAX_ITENS_RADAR],
            },
            "mencoes": resumir_mencoes(itens),
        }

        # --- alertas ---
        contexto = {
            "valor_alto": ALERTA_VALOR_ALTO,
            "tier1_veiculos": sorted(tier1),
        }
        alertas: list[dict] = []
        for clipping in itens:
            alertas.extend(detectar_alertas(clipping, contexto))
        alertas = sorted(
            alertas,
            key=lambda a: (a["nivel"] != "critico", a["nivel"] != "alto", a.get("criado_em", "")),
        )
        documento[f"periodo-{chave}"]["alertas"] = {
            "resumo": _resumir_alertas(alertas),
            "itens": alertas[:MAX_ITENS_ALERTAS],
        }

        # --- cobertura / SLA ---
        documento[f"periodo-{chave}"]["cobertura"] = analisar_cobertura(
            itens, tier1=tier1, veiculos_esperados=VEICULOS_ESPERADOS
        )

    documento["gerado_em"] = datetime.now(timezone.utc)
    return documento


def main() -> None:
    db = init_firebase()
    clippings = coletar_clippings(db)
    logger.info("Lidos %d clippings para a camada DSM.", len(clippings))

    tier1 = set(TIER1_PADRAO) | set(TIER1_VEICULOS)

    por_cidade: dict[str, list[dict]] = defaultdict(list)
    por_agente: dict[str, list[dict]] = defaultdict(list)
    for clipping in clippings:
        por_cidade[clipping.get("cidade") or "Sem cidade"].append(clipping)
        por_agente[clipping["agente_id"]].append(clipping)

    # Itens do radar oficial (fontes institucionais) entram no escopo geral e
    # no escopo da cidade correspondente (Cuiaba / Varzea Grande).
    itens_radar = coletar_radar(db)
    if itens_radar:
        clippings = clippings + itens_radar
        for item in itens_radar:
            cidade = item.get("cidade") or ""
            if cidade:
                por_cidade[cidade].extend([item])
        logger.info("Radar oficial: %d itens Somados aos escopos.", len(itens_radar))

    escopos = [
        ({"tipo": "geral", "chave": "geral", "nome": "Geral"}, clippings),
    ]
    for cidade, itens in por_cidade.items():
        slug = slugify_cidade(cidade)
        escopos.append(
            ({"tipo": "cidade", "chave": f"cidade-{slug}", "nome": cidade}, itens)
        )
    for agente_id, itens in por_agente.items():
        nome = itens[0].get("nome_agente") if itens else agente_id
        escopos.append(
            ({"tipo": "agente", "chave": f"agente-{agente_id}", "nome": nome}, itens)
        )

    for escopo, itens in escopos:
        documento = construir_documento(escopo, itens, tier1)
        chave_doc = escopo["chave"]
        db.collection(COLLECTION_RADARES).document(chave_doc).set(documento, merge=True)
        db.collection(COLLECTION_ALERTAS).document(chave_doc).set(documento, merge=True)
        db.collection(COLLECTION_COBERTURA).document(chave_doc).set(documento, merge=True)

    logger.info(
        "Camada DSM publicada: %d escopos em radares/alertas/cobertura.", len(escopos)
    )


if __name__ == "__main__":
    main_com_cota(main, "atualizar_radares")




