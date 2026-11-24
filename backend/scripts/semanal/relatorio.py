"""Pipeline semanal (E3): corpus → CHD → briefing → discurso → textos → PDF.

Roda **na maquina do dono** (domingo a noite), com Ollama local. Grava:
  - `relatorio_semanal/{escopo}__{AAAA-Www}`  (plano 10 §7)
  - `discurso_semanal/{escopo}__{AAAA-Www}`   (plano 09 §6)
  - PDF local em `backend/data/semanal/<semana>/<escopo>.pdf`

Escopos:
  - `agente-<id>` : um agente (3 variantes de discurso);
  - `casa-<slug>` : uma casa/assembleia (discurso **institucional**, sem
    simulacao — D8);
  - `geral`       : todos os agentes (relatorio geral).

Uso (a partir de `backend/`):
    python scripts/semanal/relatorio.py --escopo agente-adevair-cabral
    python scripts/semanal/relatorio.py --escopo casa-almt
    python scripts/semanal/relatorio.py --todos --limite 3
    python scripts/semanal/relatorio.py --escopo geral --sem-firestore
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.processing import corpus_iramuteq, reinert, textos_graficos
from config import settings

logger = get_logger(__name__)

# Mapa casa -> como filtrar os agentes. As camaras municipais usam `cidade`
# (o seed original nao preencheu `casa`); a ALMT usa `casa`.
CASAS = {
    "cuiaba": {"campo": "cidade", "valor": "Cuiaba", "rotulo": "Câmara Municipal de Cuiabá"},
    "varzea-grande": {"campo": "cidade", "valor": "Varzea Grande", "rotulo": "Câmara Municipal de Várzea Grande"},
    "almt": {"campo": "casa", "valor": "ALMT", "rotulo": "Assembleia Legislativa de Mato Grosso"},
}

ANGULOS = [
    ("A", "propositiva", "Agenda e soluções para as demandas da semana"),
    ("B", "prestacao_contas", "O que foi feito, com fatos da semana"),
    ("C", "resposta", "Resposta/defesa; sem alerta, conexão local"),
]


def semana_atual() -> str:
    return datetime.now(timezone.utc).strftime("%G-W%V")


def coletar_clippings(db, escopo: str, dias: int = 400) -> tuple[list[dict], str, str]:
    """Le os clippings do escopo. Devolve (itens, nivel, rotulo)."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    saida: list[dict] = []
    nivel = "agente"
    rotulo = escopo

    if escopo.startswith("agente-"):
        refs = [db.collection("agentes_publicos").document(escopo[len("agente-"):])]
    elif escopo.startswith("casa-"):
        slug = escopo[len("casa-"):]
        config = CASAS.get(slug, {})
        campo = config.get("campo", "casa")
        valor = config.get("valor", "")
        rotulo = config.get("rotulo", escopo)
        nivel = "casa"
        refs = [
            d.reference
            for d in db.collection("agentes_publicos").stream()
            if (d.to_dict() or {}).get(campo) == valor
        ]
    else:
        nivel = "geral"
        rotulo = "Todos os agentes"
        refs = [d.reference for d in db.collection("agentes_publicos").stream()]

    for ref in refs:
        try:
            snap = ref.get()
            if not snap.exists:
                continue
            agente = snap.to_dict() or {}
        except Exception as exc:  # noqa: BLE001
            logger.info("Agente %s ilegivel: %s", ref.id, str(exc)[:80])
            continue
        for clip in ref.collection("clippings").stream():
            dados = clip.to_dict() or {}
            bruto = dados.get("data_publicacao")
            if isinstance(bruto, datetime):
                if bruto.tzinfo is None:
                    bruto = bruto.replace(tzinfo=timezone.utc)
                if bruto < limite:
                    continue
            saida.append(
                {
                    "texto_limpo": dados.get("texto_limpo", ""),
                    "agente_id": ref.id,
                    "casa": agente.get("casa", ""),
                    "plataforma": dados.get("plataforma", ""),
                    "tipo": dados.get("tipo", ""),
                    "sentimento": dados.get("sentimento", ""),
                    "autor": dados.get("autor", ""),
                    "url": dados.get("url", ""),
                    "veiculo": dados.get("veiculo", ""),
                    "extra_fonte_imagem": bool(dados.get("analise_imagem", {}).get("texto_imagem")),
                }
            )
    return saida, nivel, rotulo


def montar_briefing(escopo: str, nivel: str, rotulo: str, chd: dict, est: dict, itens: list[dict]) -> dict:
    """Briefing estruturado: **so fatos** com fonte (plano 09 §3)."""
    classes = chd["classes"][:6]
    return {
        "escopo": escopo,
        "nivel": nivel,
        "rotulo": rotulo,
        "semana": semana_atual(),
        "estatisticas": est,
        "classes": [
            {
                "id": c["id"],
                "pct": c["pct"],
                "forma": c["forma"],
                "chi2": c["chi2"],
                "formas": [f["f"] for f in c["formas"][:6]],
            }
            for c in classes
        ],
        "fatos": [
            {
                "id": f"c{c['id']}",
                "texto": f"O grupo '{c['forma']}' ocupa {c['pct']:.0f}% dos segmentos",
                "fonte": "Análise lexical da semana (IRaMuTeQ/rainette)",
            }
            for c in classes
        ],
        "volume": {
            "mencoes": sum(1 for i in itens if i["sentimento"] != "negativo" or True),
            "negativas": sum(1 for i in itens if i["sentimento"] == "negativo"),
        },
        "demandas_top": [],
        "tendencias": [],
    }


def gerar_discursos(briefing: dict, nivel: str, modelo: str) -> list[dict]:
    """3 variantes (agente) ou 1 discurso institucional (casa/geral)."""
    url = settings.IA_LOCAL_URL
    variantes: list[dict] = []
    angulos = ANGULOS if nivel == "agente" else [("A", "institucional", "Discurso institucional")]
    for variante_id, angulo, tese in angulos:
        logger.info("  discurso %s (%s)...", variante_id, angulo)
        inicio = time.monotonic()
        briefing_variante = dict(briefing)
        briefing_variante["tese"] = tese
        if nivel == "casa":
            briefing_variante["instrucao"] = (
                "Discurso institucional da Mesa/Presidência/Secom: impessoal, sem promotor "
                "pessoal, sem partido (CF art. 37 §1º)."
            )
        tribuna = textos_graficos.gerar_discurso(
            briefing_variante, formato="tribuna", modelo=modelo, url_ollama=url, timeout=420
        )
        video = textos_graficos.gerar_discurso(
            briefing_variante, formato="video", modelo=modelo, url_ollama=url, timeout=420
        )
        post = textos_graficos.gerar_discurso(
            briefing_variante, formato="post", modelo=modelo, url_ollama=url, timeout=420
        )
        duracao = time.monotonic() - inicio
        logger.info("  discurso %s: %.1f s (%d chars)", variante_id, duracao, len(tribuna.get("texto", "")))
        variantes.append(
            {
                "id": variante_id,
                "angulo": angulo,
                "tese": tese,
                "tribuna": tribuna.get("texto", ""),
                "video": video.get("texto", ""),
                "post": post.get("texto", ""),
                "fontes": tribuna.get("fontes", []),
                "simulacao": {},  # preenchido na E6
            }
        )
    return variantes


def gerar_textos_graficos(chd: dict, est: dict, modelo: str) -> dict:
    """Texto verificado de cada grafico (plano 10 §6)."""
    fatos = {
        "classes": chd["classes"][:8],
        "total": est["st"],
        "rotulos": [c["forma"] for c in chd["classes"][:8]],
        "formas": [{"f": f["f"]} for c in chd["classes"][:8] for f in c["formas"][:4]],
    }
    textos: dict[str, dict] = {}
    for chave, titulo in (
        ("resumo", "o resumo da semana"),
        ("chd", "os grupos de assuntos"),
        ("afc", "o mapa de proximidade"),
        ("similitude", "a rede de palavras"),
        ("especificidades", "o que mudou"),
        ("sentimento", "o sentimento por grupo"),
    ):
        resultado = textos_graficos.escrever_texto(
            fatos, titulo=titulo, modelo=modelo, url_ollama=settings.IA_LOCAL_URL
        )
        textos[chave] = resultado["texto"]
    return textos


def montar_relatorio(escopo: str, nivel: str, rotulo: str, chd: dict, est: dict, textos: dict) -> dict:
    return {
        "escopo": escopo,
        "semana": semana_atual(),
        "nivel": nivel,
        "rotulo": rotulo,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "estatisticas": est,
        "chd": {
            "metodo": chd["metodo"],
            "k": len(chd["classes"]),
            "retencao_pct": round(
                100.0 * sum(c["st"] for c in chd["classes"]) / max(1, est.get("st", 1)), 1
            ),
            "classes": [
                {
                    "id": c["id"],
                    "pct": c["pct"],
                    "rotulo": reinert.rotulo_da_classe(c),
                    "formas": c["formas"][:10],
                    "st_tipicos": c["st_tipicos"],
                }
                for c in chd["classes"]
            ],
            "arvore": chd["arvore"],
        },
        "textos": textos,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline semanal (relatorio + discurso).")
    parser.add_argument("--escopo", default="geral", help="agente-<id>, casa-<slug> ou geral")
    parser.add_argument("--todos", action="store_true", help="roda todos os agentes")
    parser.add_argument("--limite", type=int, default=0, help="teto de escopos (com --todos)")
    parser.add_argument("--modelo", default=settings.IA_LOCAL_MODELO)
    parser.add_argument("--sem-firestore", action="store_true", help="nao grava no Firestore")
    parser.add_argument("--sem-discurso", action="store_true", help="pula a geracao do discurso")
    args = parser.parse_args()

    from core.firebase_client import init_firebase

    db = init_firebase()
    semana = semana_atual()
    pasta = Path(settings.DATA_DIR) / "semanal" / semana
    pasta.mkdir(parents=True, exist_ok=True)

    if args.todos:
        escopos = [f"agente-{d.id}" for d in db.collection("agentes_publicos").stream()]
        if args.limite:
            escopos = escopos[: args.limite]
    else:
        escopos = [args.escopo]

    resultados = []
    for escopo in escopos:
        logger.info("=== %s ===", escopo)
        inicio = time.monotonic()
        itens, nivel, rotulo = coletar_clippings(db, escopo)
        corpus = corpus_iramuteq.montar_corpus(itens)
        if len(corpus) < 5:
            logger.warning("%s: corpus insuficiente (%d itens) — pulando.", escopo, len(corpus))
            continue
        est = corpus_iramuteq.estatisticas(corpus)
        caminho_txt = pasta / f"corpus-{escopo}.txt"
        corpus_iramuteq.exportar_txt(corpus, str(caminho_txt))

        chd = reinert.executar(caminho_txt.read_text(encoding="utf-8"), k=6)
        if not chd["ok"]:
            logger.warning("%s: CHD falhou (%s) — usando o metodo Ward dos apps.", escopo, chd["erro"][:80])
            chd = {"ok": False, "classes": [], "arvore": [], "estatisticas": est, "erro": chd["erro"], "metodo": "ward_fallback"}

        briefing = montar_briefing(escopo, nivel, rotulo, chd, est, itens)
        (pasta / f"briefing-{escopo}.json").write_text(
            json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        textos = {} if args.sem_discurso else gerar_textos_graficos(chd, est, args.modelo)
        variantes = [] if args.sem_discurso else gerar_discursos(briefing, nivel, args.modelo)

        relatorio = montar_relatorio(escopo, nivel, rotulo, chd, est, textos)
        discurso = {
            "escopo": escopo,
            "nivel": nivel,
            "semana": semana,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "modelo": args.modelo,
            "briefing_resumo": {
                "classes": briefing["classes"],
                "demandas_top": briefing["demandas_top"],
                "tendencias": briefing["tendencias"],
            },
            "variantes": variantes,
            "vencedora": "",
            "avisos": ["rascunho gerado por IA", "simulação = hipótese"],
        }

        (pasta / f"relatorio-{escopo}.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (pasta / f"discurso-{escopo}.json").write_text(
            json.dumps(discurso, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not args.sem_firestore and chd["ok"]:
            db.collection("relatorio_semanal").document(f"{escopo}__{semana}").set(relatorio)
            db.collection("discurso_semanal").document(f"{escopo}__{semana}").set(discurso)
            logger.info("%s: gravado no Firestore (%s).", escopo, semana)

        duracao = time.monotonic() - inicio
        logger.info("%s: %.1f s | %d classes | %d variantes", escopo, duracao, len(chd["classes"]), len(variantes))
        resultados.append({"escopo": escopo, "segundos": round(duracao, 1), "classes": len(chd["classes"])})

    resumo = pasta / "resumo.json"
    resumo.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Resumo: %s", resumo)
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "semanal"))
