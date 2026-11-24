"""Gera o discurso do governador/interino via API DeepSeek em formato fechado.

O modelo NÃO decide o formato: ele preenche um JSON com 3 variantes (A/B/C),
tribuna/vídeo/post e fontes. O script valida o schema, os limites de palavras,
as fontes e os termos proibidos; se falhar, tenta 1 vez com os erros.

A chave fica em `backend/.env` (gitignored) como `DEEPSEEK_API_KEY`.
Nunca é impressa, logada ou enviada ao frontend.

Uso (a partir de `backend/`):
    python scripts/semanal/discurso_deepseek.py --alvo governador --semana 2026-W48 \
        --jsonl data/governo_mt/noticias-2026-11-24.jsonl
    python scripts/semanal/discurso_deepseek.py --alvo interino --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from config import settings  # noqa: E402
from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

ALVOS = {
    "governador": {
        "escopo": "agente-governador-otaviano-pivetta",
        "rotulo": "Governador do Estado de Mato Grosso",
        "tese": "Agenda, entregas e resposta do governador na semana",
    },
    "interino": {
        "escopo": "agente-interino-max-russi",
        "rotulo": "Governador Interino de Mato Grosso",
        "tese": "Agenda, entregas e resposta do governador interino na semana",
    },
}

TERMOS_PROIBIDOS = re.compile(
    r"(IRaMuTeQ|IRAMUTEQ|an[aá]lise lexical|metodologia|\bclasses?\b|"
    r"\bsegmentos?\b|termo\s+[\"']de[\"']|vote em|pe[cç]a voto|"
    r"campanha eleitoral|urna eletr[oô]nica)",
    re.IGNORECASE,
)

SYSTEM = (
    "Você é um redator sênior de discursos institucionais do Governo de Mato Grosso. "
    "Responda APENAS com JSON válido, sem markdown, seguindo exatamente o schema."
)

SCHEMA = """{
  "variantes": [
    {
      "id": "A",
      "angulo": "propositiva",
      "tese": "frase curta",
      "tribuna": "texto de 600 a 900 palavras",
      "video": "texto de 120 a 160 palavras",
      "post": "texto de 60 a 100 palavras com 3 hashtags",
      "fontes": [
        {"frase": "fato citado", "veiculo": "veículo", "data": "AAAA-MM-DD", "url": "https://..."}
      ]
    },
    {
      "id": "B",
      "angulo": "prestacao_contas",
      "tese": "frase curta",
      "tribuna": "texto de 600 a 900 palavras",
      "video": "texto de 120 a 160 palavras",
      "post": "texto de 60 a 100 palavras com 3 hashtags",
      "fontes": []
    },
    {
      "id": "C",
      "angulo": "resposta",
      "tese": "frase curta",
      "tribuna": "texto de 600 a 900 palavras",
      "video": "texto de 120 a 160 palavras",
      "post": "texto de 60 a 100 palavras com 3 hashtags",
      "fontes": []
    }
  ]
}"""

REGRAS = """
REGRAS OBRIGATÓRIAS:
1. Use SOMENTE os fatos do briefing. Se não está no briefing, não escreva.
2. NUNCA fale de metodologia, IRaMuTeQ, "análise lexical", classes, "termo", "segmentos" ou "de".
3. Cada variante deve ter pelo menos 3 fontes da lista, com o URL exato do briefing.
4. Tribuna: 600–900 palavras, linguagem falada de tribuna. Vídeo: 120–160 palavras (60 s).
   Post: 60–100 palavras + exatamente 3 hashtags.
5. A variante A é propositiva (agenda/soluções); B é prestação de contas (o que foi feito);
   C é resposta/defesa (crises e cobranças), sem ataque pessoal.
6. Não peça voto, não faça campanha eleitoral, não prometa o impossível.
7. Não invente números, obras, datas ou nomes. Se o briefing não tem, não use.
8. Responda em primeira pessoa (governador), com respeito institucional.
9. Retorne APENAS o JSON do schema, sem comentários e sem markdown.
"""


def semana_atual() -> str:
    return datetime.now(timezone.utc).strftime("%G-W%V")


def carregar_jsonl(caminho: Path, alvo: str) -> list[dict]:
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        item = json.loads(linha)
        if alvo not in (item.get("alvos") or []):
            continue
        itens.append(item)
    return itens


def montar_briefing(itens: list[dict], alvo: str, semana: str) -> dict:
    facts = []
    for indice, item in enumerate(itens[:30], start=1):
        resumo = (item.get("resumo") or "").strip()
        facts.append(
            {
                "id": f"F{indice}",
                "titulo": (item.get("titulo") or "").strip(),
                "resumo": resumo[:400],
                "veiculo": item.get("veiculo") or "",
                "data": str(item.get("data") or "")[:10],
                "url": item.get("url") or "",
                "sentimento": item.get("sentimento") or "",
                "temas": item.get("temas") or [],
            }
        )
    return {
        "alvo": alvo,
        "rotulo": ALVOS[alvo]["rotulo"],
        "tese": ALVOS[alvo]["tese"],
        "semana": semana,
        "fatos": facts,
    }


def montar_prompt(briefing: dict, erros: list[str] | None = None) -> str:
    partes = [
        f"BRIEFING DA SEMANA ({briefing['rotulo']}, {briefing['semana']}):",
        json.dumps(briefing, ensure_ascii=False)[:12000],
        REGRAS,
        "SCHEMA EXATO:",
        SCHEMA,
    ]
    if erros:
        partes.append("CORRIJA OS ERROS DA TENTATIVA ANTERIOR:")
        partes.extend(f"- {erro}" for erro in erros)
    partes.append("Gere o JSON agora.")
    return "\n\n".join(partes)


def _limpar_json(texto: str) -> str:
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto)
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio >= 0 and fim > inicio:
        return texto[inicio : fim + 1]
    return texto


def chamar_deepseek(prompt: str, erros: list[str] | None = None) -> dict:
    chave = settings.DEEPSEEK_API_KEY
    if not chave:
        raise SystemExit(
            "DEEPSEEK_API_KEY ausente. Coloque a chave em backend/.env (gitignored)."
        )
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": montar_prompt(prompt, erros)},
        ],
        "temperature": 0.5,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    url = settings.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    try:
        resposta = requests.post(
            url, headers=headers, json=payload, timeout=settings.DEEPSEEK_TIMEOUT
        )
    except requests.RequestException as exc:
        raise SystemExit(f"Falha de rede na DeepSeek: {str(exc)[:160]}") from exc
    if resposta.status_code == 400 and "response_format" in resposta.text:
        payload.pop("response_format", None)
        resposta = requests.post(
            url, headers=headers, json=payload, timeout=settings.DEEPSEEK_TIMEOUT
        )
    if resposta.status_code in (401, 403):
        raise SystemExit("DeepSeek recusou a chave (401/403). Confira DEEPSEEK_API_KEY.")
    if resposta.status_code >= 400:
        raise SystemExit(
            f"DeepSeek HTTP {resposta.status_code}: {resposta.text[:200]}"
        )
    dados = resposta.json()
    conteudo = (
        dados.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    try:
        return json.loads(_limpar_json(conteudo))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"DeepSeek devolveu JSON inválido: {exc}") from exc


def _palavras(texto: str) -> int:
    return len(re.findall(r"\S+", texto or ""))


def normalizar_fontes(doc: dict, briefing: dict) -> dict:
    """Corrige URLs que o modelo alterou usando o veículo como âncora."""
    urls = {f["url"] for f in briefing["fatos"] if f.get("url")}
    por_veiculo = {}
    for fato in briefing["fatos"]:
        if fato.get("url"):
            por_veiculo.setdefault((fato.get("veiculo") or "").lower(), fato["url"])
    for variante in doc.get("variantes") or []:
        if not isinstance(variante, dict):
            continue
        for fonte in variante.get("fontes") or []:
            if not isinstance(fonte, dict):
                continue
            url = (fonte.get("url") or "").strip()
            if url and url in urls:
                continue
            veiculo = (fonte.get("veiculo") or "").lower()
            if veiculo in por_veiculo:
                fonte["url"] = por_veiculo[veiculo]
            elif url:
                fonte["url"] = ""
    return doc


def validar(doc: dict, briefing: dict) -> list[str]:
    erros: list[str] = []
    variantes = doc.get("variantes")
    if not isinstance(variantes, list) or len(variantes) != 3:
        return ["O JSON precisa ter exatamente 3 variantes (A/B/C)."]
    urls = {f["url"] for f in briefing["fatos"] if f.get("url")}
    ids = [v.get("id") for v in variantes if isinstance(v, dict)]
    if ids != ["A", "B", "C"]:
        erros.append("As variantes precisam ter id A, B e C, nesta ordem.")
    for variante in variantes:
        if not isinstance(variante, dict):
            erros.append("Variante inválida (não é objeto).")
            continue
        vid = variante.get("id", "?")
        for campo, minimo, maximo in (
            ("tribuna", 400, 1200),
            ("video", 80, 250),
            ("post", 30, 180),
        ):
            texto = variante.get(campo) or ""
            n = _palavras(texto)
            if n < minimo or n > maximo:
                erros.append(f"{vid}.{campo}: {n} palavras (esperado {minimo}–{maximo}).")
            if TERMOS_PROIBIDOS.search(texto):
                erros.append(f"{vid}.{campo}: contém termo proibido/metodologia.")
        fontes = variante.get("fontes") or []
        if len(fontes) < 3:
            erros.append(f"{vid}: menos de 3 fontes.")
        for fonte in fontes:
            if not isinstance(fonte, dict):
                erros.append(f"{vid}: fonte inválida.")
                continue
            url = (fonte.get("url") or "").strip()
            if not url and not (fonte.get("veiculo") or "").strip():
                erros.append(f"{vid}: fonte sem veículo/URL.")
            elif url and url not in urls:
                erros.append(f"{vid}: URL fora do briefing ({url[:60]}...).")
        if "vote" in json.dumps(variante, ensure_ascii=False).lower():
            erros.append(f"{vid}: possível pedido de voto.")
    return erros


def documento_final(bruto: dict, briefing: dict, alvo: str, semana: str) -> dict:
    return {
        "escopo": ALVOS[alvo]["escopo"],
        "orgao": "governo-mt",
        "nivel": "agente",
        "semana": semana,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "modelo": settings.DEEPSEEK_MODEL,
        "briefing_resumo": {
            "fatos": len(briefing["fatos"]),
            "fontes": len({f["url"] for f in briefing["fatos"] if f.get("url")}),
        },
        "variantes": bruto.get("variantes") or [],
        "vencedora": "",
        "avisos": ["rascunho gerado por IA", "simulação = hipótese"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discurso do governador via DeepSeek.")
    parser.add_argument("--alvo", choices=sorted(ALVOS), default="governador")
    parser.add_argument("--semana", default=semana_atual())
    parser.add_argument("--jsonl", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sem-firestore", action="store_true")
    args = parser.parse_args()

    if not settings.DEEPSEEK_API_KEY:
        raise SystemExit(
            "DEEPSEEK_API_KEY ausente. Coloque a chave em backend/.env (gitignored)."
        )

    if args.jsonl:
        caminho = Path(args.jsonl)
    else:
        arquivos = sorted((Path(settings.DATA_DIR) / "governo_mt").glob("noticias-*.jsonl"))
        if not arquivos:
            raise SystemExit("Nenhum JSONL do Governo encontrado.")
        caminho = arquivos[-1]
    itens = carregar_jsonl(caminho, args.alvo)
    if len(itens) < 10:
        raise SystemExit(f"Poucas notícias para o alvo {args.alvo}: {len(itens)}.")
    briefing = montar_briefing(itens, args.alvo, args.semana)
    logger.info(
        "Briefing %s/%s: %d fatos, %d URLs.",
        args.alvo,
        args.semana,
        len(briefing["fatos"]),
        len({f["url"] for f in briefing["fatos"] if f.get("url")}),
    )

    if args.dry_run:
        prompt = montar_prompt(briefing)
        print(f"dry-run: {len(briefing['fatos'])} fatos; prompt {len(prompt)} chars")
        return 0

    bruto = normalizar_fontes(chamar_deepseek(briefing), briefing)
    erros = validar(bruto, briefing)
    if erros:
        logger.warning("Primeira tentativa inválida (%d erros); repetindo.", len(erros))
        for erro in erros[:10]:
            logger.warning("  %s", erro)
        bruto = normalizar_fontes(chamar_deepseek(briefing, erros), briefing)
        erros = validar(bruto, briefing)
    if erros:
        for erro in erros[:10]:
            logger.error("  %s", erro)
        raise SystemExit(
            "DeepSeek não entregou o formato fechado; nada foi publicado. "
            "Ajuste o briefing/prompt ou tente novamente."
        )

    doc = documento_final(bruto, briefing, args.alvo, args.semana)
    pasta = Path(settings.DATA_DIR) / "semanal" / args.semana
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"discurso-{doc['escopo']}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (pasta / f"briefing-{doc['escopo']}.json").write_text(
        json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "Gerado %s: %d variantes | tribuna %s palavras | fontes %s.",
        doc["escopo"],
        len(doc["variantes"]),
        [_palavras(v.get("tribuna")) for v in doc["variantes"]],
        [len(v.get("fontes") or []) for v in doc["variantes"]],
    )

    if not args.sem_firestore:
        from core.firebase_client import init_firebase

        db = init_firebase()
        db.collection("discurso_semanal").document(
            f"{doc['escopo']}__{args.semana}"
        ).set(doc, merge=True)
        logger.info("Publicado discurso_semanal/%s__%s", doc["escopo"], args.semana)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

