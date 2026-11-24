"""Fase 0 manual da E3: mede o tempo de cada passo do pipeline semanal.

Passos (plano 09 §2):
  1. corpus (montagem a partir dos clippings do Firestore)
  2. CHD de Reinert (rainette via Rscript)
  3. briefing (fatos estruturados)
  4. discurso (3 variantes x 3 formatos, Ollama local)
  5. textos dos graficos (Ollama local + verificacao)
  6. PDF (Playwright)

Mede o tempo de cada passo e grava em `data/semanal/<semana>/fase0.json`.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.core.logger import get_logger
from cerra_nucleo.processing import corpus_iramuteq, reinert, textos_graficos
from config import settings
from core.firebase_client import init_firebase

logger = get_logger(__name__)


def cronometrar(nome: str, funcao):
    inicio = time.monotonic()
    resultado = funcao()
    duracao = time.monotonic() - inicio
    logger.info("[Fase 0] %-22s %6.1f s", nome, duracao)
    return resultado, duracao


def coletar_clippings(db, escopo: str, dias: int = 400) -> list[dict]:
    """Le os clippings do escopo (agente ou casa).

    `dias` = janela de comparacao do corpus (padrao 400 dias: o acervo atual
    tem lacuna entre outubro e novembro, e o filtro curto zeraria o corpus).
    """
    from datetime import timedelta

    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    saida: list[dict] = []
    if escopo.startswith("agente-"):
        refs = [db.collection("agentes_publicos").document(escopo[len("agente-"):])]
    elif escopo.startswith("casa-"):
        refs = [db.collection("agentes_publicos").document(escopo[len("casa-"):])]
    else:
        refs = list(db.collection("agentes_publicos").stream())
    for ref in refs:
        agente = {}
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
                    "semana": dados.get("semana", ""),
                    "autor": dados.get("autor", ""),
                    "url": dados.get("url", ""),
                    "veiculo": dados.get("veiculo", ""),
                }
            )
    return saida


def main() -> int:
    escopo = sys.argv[1] if len(sys.argv) > 1 else "geral"
    modelo = sys.argv[2] if len(sys.argv) > 2 else "qwen3:8b"

    db = init_firebase()
    tempos: dict[str, float] = {}

    # --- passo 1: corpus ---
    clippings, t = cronometrar(
        "1. coletar clippings", lambda: coletar_clippings(db, escopo)
    )
    tempos["1_coleta"] = t

    corpus, t = cronometrar(
        "1b. montar corpus", lambda: corpus_iramuteq.montar_corpus(clippings)
    )
    tempos["1b_corpus"] = t

    est = corpus_iramuteq.estatisticas(corpus)
    logger.info("        corpus: %s", est)

    pasta = Path(settings.DATA_DIR) / "semanal" / datetime.now(timezone.utc).strftime("%Y-W%W")
    pasta.mkdir(parents=True, exist_ok=True)
    caminho_txt = pasta / f"corpus-{escopo}.txt"
    corpus_iramuteq.exportar_txt(corpus, str(caminho_txt))
    logger.info("        corpus gravado em %s", caminho_txt)

    # --- passo 2: CHD de Reinert ---
    chd, t = cronometrar(
        "2. CHD (rainette)",
        lambda: reinert.executar(
            caminho_txt.read_text(encoding="utf-8"),
            k=6,
            min_segment_size=10,
            min_split_members=10,
        ),
    )
    tempos["2_chd"] = t
    logger.info("        classes: %d | erro: %s", len(chd["classes"]), chd["erro"][:120])

    # --- passo 3: briefing ---
    def _montar_briefing():
        classes = chd["classes"]
        return {
            "escopo": escopo,
            "semana": datetime.now(timezone.utc).strftime("%G-W%V"),
            "estatisticas": est,
            "classes": [
                {"id": c["id"], "pct": c["pct"], "forma": c["forma"], "chi2": c["chi2"]}
                for c in classes
            ],
            "fatos": [
                {"id": f"c{i}", "texto": f"Classe {c['pct']}% ({c['forma']})", "fonte": "IRaMuTeQ"}
                for i, c in enumerate(classes)
            ],
            "demandas_top": [],
            "tendencias": [],
        }

    briefing, t = cronometrar("3. briefing", _montar_briefing)
    tempos["3_briefing"] = t

    # --- passo 4: discurso (3 variantes) ---
    ANGULOS = [
        ("A", "propositiva"),
        ("B", "prestacao de contas"),
        ("C", "resposta a repercussao"),
    ]

    def _falar(variante_id: str, angulo: str) -> dict:
        prompt_briefing = dict(briefing)
        prompt_briefing["tese"] = f"A prioridade da semana (variante {variante_id}, angulo {angulo})"
        return textos_graficos.gerar_discurso(
            prompt_briefing,
            formato="tribuna",
            modelo=modelo,
            url_ollama=settings.IA_LOCAL_URL if hasattr(settings, "IA_LOCAL_URL") else "http://127.0.0.1:11434",
        )

    discursos = []
    for variante_id, angulo in ANGULOS:
        resultado, t = cronometrar(f"4. discurso {variante_id}", lambda v=variante_id, a=angulo: _falar(v, a))
        tempos[f"4_discurso_{variante_id}"] = t
        discursos.append(
            {
                "id": variante_id,
                "angulo": angulo,
                "tese": resultado.get("texto", "")[:200],
                "tribuna": resultado.get("texto", ""),
                "fontes": resultado.get("fontes", []),
                "avisos": resultado.get("avisos", []),
                "ok": resultado.get("ok", False),
            }
        )
        logger.info("        variante %s: %d caracteres", variante_id, len(resultado.get("texto", "")))

    # --- passo 5: textos dos graficos ---
    def _textos():
        saida = {}
        for classe in chd["classes"][:6]:
            fatos = {
                "classes": chd["classes"],
                "total": est["st"],
                "rotulos": [c["forma"] for c in chd["classes"]],
            }
            saida[f"classe_{classe['id']}"] = textos_graficos.escrever_texto(
                fatos,
                titulo=f"o grupo de assuntos {classe['id']}",
                modelo=modelo,
            )
        return saida

    textos, t = cronometrar("5. textos dos graficos", _textos)
    tempos["5_textos"] = t
    verificados = sum(1 for v in textos.values() if v.get("verificado"))
    logger.info("        textos verificados: %d de %d", verificados, len(textos))

    # --- resumo ---
    resumo = {
        "escopo": escopo,
        "modelo": modelo,
        "medido_em": datetime.now(timezone.utc).isoformat(),
        "tempos_segundos": {k: round(v, 2) for k, v in tempos.items()},
        "total_segundos": round(sum(tempos.values()), 2),
        "estatisticas": est,
        "classes": chd["classes"][:8],
        "discursos": [{"id": d["id"], "ok": d["ok"], "chars": len(d["tribuna"])} for d in discursos],
        "textos_verificados": f"{verificados}/{len(textos)}",
    }
    saida_json = pasta / f"fase0-{escopo}-{modelo.replace(':', '-')}.json"
    saida_json.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[Fase 0] total: %.1f s | resumo em %s", resumo["total_segundos"], saida_json)
    return 0


if __name__ == "__main__":
    from core.quota import main_com_cota

    raise SystemExit(main_com_cota(main, "fase0"))
