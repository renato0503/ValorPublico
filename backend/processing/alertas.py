"""Motor de alertas (padrao "alertar antes que a narrativa se consolide").

Diferencial de mercado das plataformas modernas de clipping: nao basta publicar
o relatorio do dia, e preciso sinalizar o que exige acao. Regras implementadas:

  A1 NEGATIVA_DIRETA   mencao direta com sentimento negativo -> nivel critico
  A2 VALOR_ALTO       mencao direta com valor acima do limiar -> nivel alto
  A3 TIER1_NEGATIVA   veiculo de alto impacto com tom negativo -> nivel critico
  A4 COMPLIANCE       apontamento de compliance eleitoral -> nivel critico
  A5 RADAR            propaganda publica / institucional detectada -> informativo
  A6 TEMA_NOVO        primeira mencao de um tema no escopo -> informativo
  A7 VOLUME           pico de mencoes no dia -> atencao
  A8 SEM_FONTE        clipping sem veiculo identificado -> atencao (qualidade)

Cada alerta tem chave de deduplicacao (para nao repetir no dia) e o endereco
da fonte, para que a equipe possa agir.
"""

import hashlib
import unicodedata
from datetime import datetime, timezone

NIVEL_CRITICO = "critico"
NIVEL_ALTO = "alto"
NIVEL_ATENCAO = "atencao"
NIVEL_INFO = "info"

_ORDEM_NIVEL = {NIVEL_CRITICO: 0, NIVEL_ALTO: 1, NIVEL_ATENCAO: 2, NIVEL_INFO: 3}

# Limiar padrao de valor (R$) para considered "alto valor" - configuravel
VALOR_ALTO_PADRAO = 1500.0


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def _chave(tipo: str, agente_id: str, url: str) -> str:
    base = f"{tipo}|{agente_id}|{url}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def _timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detectar_alertas(
    clipping: dict,
    contexto: dict | None = None,
) -> list[dict]:
    """Devolve a lista de alertas gerados por um clipping.

    `contexto` aceita:
        valor_alto      float  (limiar de valor, default 1500)
        tier1_veiculos  list   (veiculos considerados de alto impacto)
        temas_conhecidos list  (temas ja vistos no escopo -> detecta tema novo)
    """
    contexto = contexto or {}
    limiar_valor = float(contexto.get("valor_alto", VALOR_ALTO_PADRAO))
    tier1 = {str(v).strip().lower() for v in contexto.get("tier1_veiculos", [])}
    temas_conhecidos = {str(t) for t in contexto.get("temas_conhecidos", [])}

    alertas: list[dict] = []
    texto = clipping.get("texto_limpo") or ""
    metadados = clipping.get("metadados") if isinstance(clipping.get("metadados"), dict) else {}
    veiculo = (metadados.get("veiculo") or clipping.get("autor") or "").strip()
    url = clipping.get("url") or ""
    agente_id = clipping.get("agente_id") or ""
    sentimento = (clipping.get("sentimento") or "neutro").lower()
    mencao = clipping.get("mencao") or {}
    tipo_mencao = mencao.get("tipo", "indeterminada")
    valor = float(clipping.get("valor_estimado") or 0.0)
    data = clipping.get("data_publicacao")
    compliance = clipping.get("compliance") or []
    radar = clipping.get("propaganda_publica") or {}

    def add(tipo: str, nivel: str, titulo: str, detalhe: str, acao: str = "") -> None:
        alertas.append({
            "chave": _chave(tipo, agente_id, url),
            "tipo": tipo,
            "nivel": nivel,
            "titulo": titulo,
            "detalhe": detalhe,
            "acao_sugerida": acao,
            "agente_id": agente_id,
            "cidade": clipping.get("cidade", ""),
            "veiculo": veiculo,
            "url": url,
            "data_publicacao": data,
            "valor_estimado": valor,
            "sentimento": sentimento,
            "criado_em": _timestamp_iso(),
        })

    if tipo_mencao == "direta" and sentimento == "negativo":
        add(
            "NEGATIVA_DIRETA", NIVEL_CRITICO,
            f"Mencao negativa direta em {veiculo or 'midia'}",
            (clipping.get("trecho", {}) or {}).get("trecho", texto[:240])
            or texto[:240],
            "Avaliar resposta/posicionamento nas próximas horas",
        )

    if veiculo and tier1 and veiculo.lower() in tier1 and sentimento == "negativo":
        add(
            "TIER1_NEGATIVA", NIVEL_CRITICO,
            f"Ton negativo em veiculo de alto impacto ({veiculo})",
            texto[:240],
            "Checar repercussao e preparar posicionamento",
        )

    if tipo_mencao == "direta" and valor >= limiar_valor:
        add(
            "VALOR_ALTO", NIVEL_ALTO,
            f"Mencao direta de alto valor (R$ {valor:,.0f})",
            f"Veiculo: {veiculo or 'n/i'} - alcance: {clipping.get('alcance', 0)}",
            "Avaliar a severidade do impacto e usar no relatorio executivo",
        )

    for achado in compliance:
        if achado.get("nivel") == "alerta":
            add(
                "COMPLIANCE", NIVEL_CRITICO,
                f"Compliance eleitoral: {achado.get('artigo', '')}",
                achado.get("motivo", ""),
                "Consultar juridico antes de divulgacao/reply",
            )
            break

    if radar.get("classe") == "propaganda_publica":
        add(
            "RADAR", NIVEL_INFO,
            f"Propaganda publica detectada ({radar.get('tipo', 'n/i')})",
            f"Orgao: {radar.get('orgao', 'n/i')}"
            + (" - usa simbolos publicos" if radar.get("simbolos_publicos") else ""),
            "Registrar no radar de transparencia",
        )

    if tipo_mencao == "direta":
        temas = [t for t in (clipping.get("categorias") or []) if t not in temas_conhecidos]
        if temas:
            add(
                "TEMA_NOVO", NIVEL_INFO,
                f"Novo tema em mencao direta: {', '.join(temas[:3])}",
                texto[:200],
                "Avaliar pauta para divulgacao/uso institucional",
            )

    if not veiculo:
        add(
            "SEM_FONTE", NIVEL_ATENCAO,
            "Clipping sem veiculo identificado",
            url[:200] or texto[:200],
            "Corrigir extracao do veiculo (qualidade da coleta)",
        )

    alertas.sort(key=lambda a: _ORDEM_NIVEL.get(a["nivel"], 9))
    return alertas


def resumir(alertas: list[dict]) -> dict:
    """Resume a lista de alertas para o painel."""
    if not alertas:
        return {"total": 0, "critico": 0, "alto": 0, "atencao": 0, "info": 0, "por_tipo": {}}
    niveis = {NIVEL_CRITICO: 0, NIVEL_ALTO: 0, NIVEL_ATENCAO: 0, NIVEL_INFO: 0}
    por_tipo: dict[str, int] = {}
    for alerta in alertas:
        niveis[alerta.get("nivel", NIVEL_INFO)] = niveis.get(alerta.get("nivel", NIVEL_INFO), 0) + 1
        por_tipo[alerta.get("tipo", "OUTRO")] = por_tipo.get(alerta.get("tipo", "OUTRO"), 0) + 1
    return {
        "total": len(alertas),
        "critico": niveis[NIVEL_CRITICO],
        "alto": niveis[NIVEL_ALTO],
        "atencao": niveis[NIVEL_ATENCAO],
        "info": niveis[NIVEL_INFO],
        "por_tipo": por_tipo,
    }

