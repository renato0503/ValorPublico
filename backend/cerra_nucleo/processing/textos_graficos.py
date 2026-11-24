"""Texto verificado de cada grafico (plano 10 §6) e do discurso (plano 09).

Fluxo:
  1. o Python gera um **JSON de fatos** (numeros que existem no grafico);
  2. o Ollama (local, sem API paga) escreve 3–5 frases;
  3. **verificacao automatica**: todo numero do texto precisa existir no JSON
     (com tolerancia de arredondamento) e toda palavra entre aspas precisa
     estar nas formas do grafico;
  4. se falhar, tenta de novo (no maximo 2) e, se ainda falhar, usa o
     **texto de modelo** (template deterministico).

O LLM nao recebe o corpus bruto: so o JSON de fatos. Ele nao pode inventar.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from cerra_nucleo.core.logger import get_logger

logger = get_logger(__name__)

# Palavras que o modelo nao pode usar sem explicar (plano 17 §12.2).
SIGLAS = {
    "SoV": "fatia da conversa",
    "AVE": "valor da mídia espontânea",
    "CHD": "grupos de assuntos",
    "AFC": "mapa de proximidade",
    "SLA": "tempo de atendimento",
}

PROMPT = """Você é o analista de comunicação de um gabinete público.
Escreva um texto curto (3 a 5 frases) sobre o gráfico cujos fatos estão no JSON.

Regras:
- Use SOMENTE os números do JSON. Não calcule, não estime, não invente.
- Frases de até 20 palavras, português claro, sem jargão.
- Diga: o que o gráfico mostra, o que isso significa para quem lê, e 1 ponto de atenção.
- Não use estas siglas sem explicar: SoV, AVE, CHD, AFC, SLA.
- Responda APENAS com o texto, sem título e sem aspas em volta.

Fatos do gráfico:
{fatos}
"""


def _ollama(url: str, modelo: str, prompt: str, timeout: float, formato: str = "") -> str:
    """Chama o Ollama local e devolve o texto."""
    import requests

    payload: dict = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 8192, "seed": 7},
    }
    if formato:
        payload["format"] = formato
    resp = requests.post(f"{url.rstrip('/')}/api/generate", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def numeros_do_json(fatos: dict) -> set[float]:
    """Todos os numeros que existem nos fatos (para a verificacao)."""
    numeros: set[float] = set()

    def _varrer(valor):
        if isinstance(valor, bool):
            return
        if isinstance(valor, (int, float)):
            numeros.add(float(valor))
            return
        if isinstance(valor, str):
            for achado in re.findall(r"-?\d+(?:[.,]\d+)?", valor):
                try:
                    numeros.add(float(achado.replace(",", ".")))
                except ValueError:
                    pass
            return
        if isinstance(valor, dict):
            for item in valor.values():
                _varrer(item)
            return
        if isinstance(valor, list):
            for item in valor:
                _varrer(item)

    _varrer(fatos)
    return numeros


def _sem_acento(texto: str) -> str:
    """minusculas, sem acento (para comparar 'Cuiabá' com 'cuiaba')."""
    import unicodedata

    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def formas_do_grafico(fatos: dict) -> set[str]:
    """Todas as palavras citadas no grafico (para checar as entre aspas)."""
    formas: set[str] = set()
    for chave in ("formas", "rotulos", "classes", "itens", "palavras", "frequencias"):
        valores = fatos.get(chave)
        if not isinstance(valores, list):
            continue
        for item in valores:
            if isinstance(item, dict):
                for chave_item in ("f", "forma", "rotulo", "palavra", "nome", "termo"):
                    if chave_item in item:
                        formas.add(_sem_acento(str(item[chave_item])))
            elif isinstance(item, str):
                formas.add(_sem_acento(item))
    return formas


def verificar(texto: str, fatos: dict) -> tuple[bool, list[str]]:
    """Confere se o texto so usa numeros e palavras do grafico.

    Devolve (ok, problemas).
    """
    problemas: list[str] = []
    numeros = numeros_do_json(fatos)
    formas = formas_do_grafico(fatos)

    # Numeros citados no texto (percentuais e valores).
    for achado in re.findall(r"-?\d+(?:[.,]\d+)?", texto or ""):
        try:
            valor = float(achado.replace(",", "."))
        except ValueError:
            continue
        if any(abs(valor - n) <= 0.051 for n in numeros):
            continue
        # tolerancia de arredondamento: 12,3 bate com 12,34
        if any(abs(valor - n) <= max(0.51, abs(n) * 0.01) for n in numeros):
            continue
        problemas.append(f"numero fora do grafico: {achado}")

    # Palavras entre aspas precisam existir nas formas do grafico (sem acento).
    for citada in re.findall(r"[\"“”']([^\"“”']{2,40})[\"“”']", texto or ""):
        alvo = _sem_acento(citada).strip()
        if not alvo or " " in alvo:
            continue
        if any(alvo == forma or alvo in forma.split("-") for forma in formas):
            continue
        problemas.append(f"palavra fora do grafico: {citada}")

    # Siglas sem explicar.
    for sigla in SIGLAS:
        if re.search(rf"\b{sigla}\b", texto or ""):
            problemas.append(f"sigla sem explicar: {sigla}")

    return (not problemas), problemas


def texto_de_modelo(fatos: dict, titulo: str = "o grafico") -> str:
    """Template deterministico (usado quando o LLM falha)."""
    partes = []
    if "classes" in fatos and isinstance(fatos["classes"], list) and fatos["classes"]:
        maior = max(fatos["classes"], key=lambda c: float(c.get("pct", 0)))
        partes.append(
            f"O grupo mais forte e {maior.get('forma', 'a classe principal').upper()} "
            f"({maior.get('pct', 0):.0f}% dos segmentos da semana)."
        )
    if "total" in fatos:
        partes.append(f"Foram {fatos['total']} itens no periodo.")
    if "variacao" in fatos:
        partes.append(f"A variacao foi de {fatos['variacao']}.")
    if "observacao" in fatos:
        partes.append(str(fatos["observacao"]))
    if not partes:
        partes.append(f"Este grafico resume {titulo} do periodo analisado.")
    return " ".join(partes)


def escrever_texto(
    fatos: dict,
    titulo: str = "o grafico",
    url_ollama: str = "http://127.0.0.1:11434",
    modelo: str = "qwen3:8b",
    timeout: float = 120.0,
    tentativas: int = 2,
    usar_llm: bool = True,
) -> dict:
    """Gera o texto do grafico (LLM local + verificacao + template).

    Devolve {"texto", "verificado", "problemas", "fonte"}.
    """
    fatos_texto = json.dumps(fatos, ensure_ascii=False)[:4000]
    problemas: list[str] = []

    if usar_llm:
        for tentativa in range(1, max(1, tentativas) + 1):
            try:
                bruto = _ollama(
                    url_ollama, modelo, PROMPT.format(fatos=fatos_texto), timeout
                )
            except Exception as exc:  # noqa: BLE001
                logger.info("Ollama indisponivel (%s): uso o texto de modelo.", exc)
                break
            texto = bruto.strip()
            ok, problemas = verificar(texto, fatos)
            if ok:
                return {"texto": texto, "verificado": True, "problemas": [], "fonte": "ollama"}
            logger.warning(
                "Texto do grafico reprovou na verificacao (tentativa %d): %s",
                tentativa,
                problemas[:3],
            )
        else:
            texto = ""

    texto = texto_de_modelo(fatos, titulo)
    return {"texto": texto, "verificado": False, "problemas": problemas, "fonte": "modelo"}


# --------------------------------------------------------------------------
# Discurso (plano 09 §5)
# --------------------------------------------------------------------------
PROMPT_DISCURSO = """Você redige o discurso de um agente público a partir do briefing.

Regras obrigatórias:
- Use SOMENTE os fatos do briefing. Se não está no briefing, não escreva.
- Cite a fonte entre parênteses quando usar um número (ex.: (G1, 22/11)).
- Português natural, falado, ~5 minutos de tribuna.
- Sem promessa impossível de cumprir pelo cargo.
- Não ataque pessoal.

BRIEFING (JSON):
{briefing}

Escreva o discurso (só o texto):
"""


def gerar_discurso(
    briefing: dict,
    formato: str = "tribuna",
    url_ollama: str = "http://127.0.0.1:11434",
    modelo: str = "qwen3:8b",
    timeout: float = 180.0,
    tentar_reverificar: bool = True,
) -> dict:
    """Gera um discurso a partir do briefing (fatos com fonte).

    Devolve {"texto", "fontes", "avisos", "ok"}.
    """
    avisos = ["rascunho gerado por IA"]
    prompt = PROMPT_DISCURSO.format(briefing=json.dumps(briefing, ensure_ascii=False)[:6000])
    if formato == "video":
        prompt += "\n(Escrita para um video de 60 segundos: cerca de 150 palavras.)\n"
    elif formato == "post":
        prompt += "\n(Escrita para uma rede social: cerca de 80 palavras e 3 hashtags.)\n"

    try:
        texto = _ollama(url_ollama, modelo, prompt, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama indisponivel para o discurso: %s", exc)
        return {"texto": "", "fontes": [], "avisos": avisos, "ok": False, "erro": str(exc)[:120]}

    texto = texto.strip()
    fontes = extrair_fontes(texto)
    if tentar_reverificar:
        problemas = verificar_fontes(texto, briefing)
        if problemas:
            avisos.append("conferir as fontes citadas")
    return {"texto": texto, "fontes": fontes, "avisos": avisos, "ok": bool(texto)}


RE_FONTE = re.compile(r"\(([^()]{2,80})\)")


def extrair_fontes(texto: str) -> list[str]:
    """Extrai as fontes citadas entre parenteses."""
    saida = []
    for achado in RE_FONTE.findall(texto or ""):
        limpo = achado.strip()
        if limpo and limpo not in saida:
            saida.append(limpo)
    return saida[:40]


def verificar_fontes(texto: str, briefing: dict) -> list[str]:
    """Checa se as fontes citadas aparecem no briefing.

    Devolve a lista de fontes nao encontradas (para o aviso "conferir").
    """
    disponiveis = " ".join(
        str(v) for v in briefing.values()
    ).lower()
    problemas = []
    for fonte in extrair_fontes(texto):
        alvo = fonte.lower()
        if alvo in disponiveis:
            continue
        # tenta casar pela URL ou pelo veiculo
        if any(alvo in str(v).lower() for v in briefing.values()):
            continue
        problemas.append(fonte)
    return problemas


def carimbo() -> str:
    """Data/hora do geracao (o rodape do relatorio)."""
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
