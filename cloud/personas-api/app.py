"""API das personas do Governo de MT.

- FastAPI + BM25 local (pacote `data/personas_export`).
- Firebase ID token + perfil `usuarios/{uid}.orgao`.
- DeepSeek para a resposta (chave só no ambiente/Secret Manager).
- Nunca loga prompt, resposta ou chave.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("personas-api")

BASE = Path(__file__).resolve().parent
DATA = Path(os.getenv("PERSONAS_DATA", BASE / "data" / "personas_export"))
PROJECT = os.getenv("FIREBASE_PROJECT_ID", "valorpublico-b1e6d")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ALLOWED = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://valorpublico.web.app,http://localhost:8080,http://127.0.0.1:8080,http://127.0.0.1:8000",
    ).split(",")
    if o.strip()
]
LIMITE_MINUTO = int(os.getenv("LIMITE_MINUTO", "30"))
LIMITE_DIA = int(os.getenv("LIMITE_DIA", "500"))
LIMITE_SIMULACAO_HORA = int(os.getenv("LIMITE_SIMULACAO_HORA", "8"))
TOP_K = int(os.getenv("TOP_K", "6"))
DISCURSO_MIN_CHARS = int(os.getenv("DISCURSO_MIN_CHARS", "80"))
DISCURSO_MAX_CHARS = int(os.getenv("DISCURSO_MAX_CHARS", "12000"))
PARALELISMO = int(os.getenv("PARALELISMO", "6"))

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "no",
    "na", "nos", "nas", "por", "para", "com", "sem", "e", "ou", "que", "se", "ao",
    "aos", "à", "às", "é", "foi", "ser", "são", "como", "mais", "menos", "muito",
    "já", "não", "sim", "sobre", "entre", "depois", "antes", "pelo", "pela",
}


def _normalizar(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def tokenizar(texto: str) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9]{3,}", _normalizar(texto))
        if t not in STOPWORDS
    ]


class BM25:
    def __init__(self, documentos: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.tokens = [tokenizar(d) for d in documentos]
        self.k1 = k1
        self.b = b
        self.N = len(self.tokens)
        self.avgdl = sum(len(t) for t in self.tokens) / max(1, self.N)
        self.df: Counter = Counter()
        for tokens in self.tokens:
            for termo in set(tokens):
                self.df[termo] += 1
        self.idf = {
            termo: math.log(1 + (self.N - freq + 0.5) / (freq + 0.5))
            for termo, freq in self.df.items()
        }

    def pontuar(self, consulta: list[str], indice: int) -> float:
        tokens = self.tokens[indice]
        dl = len(tokens)
        freq = Counter(tokens)
        score = 0.0
        for termo in consulta:
            if termo not in freq:
                continue
            idf = self.idf.get(termo, 0.0)
            tf = freq[termo]
            score += idf * (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * dl / max(1, self.avgdl))
            )
        return score


class Estado:
    def __init__(self) -> None:
        self.manifest: dict[str, Any] = {}
        self.perfis: dict[str, dict] = {}
        self.chunks: dict[str, list[dict]] = {}
        self.indices: dict[str, BM25] = {}
        self.uso: dict[str, list[float]] = defaultdict(list)
        self.uso_dia: dict[str, list[float]] = defaultdict(list)
        self.uso_simulacao: dict[str, list[float]] = defaultdict(list)
        self.cache: dict[tuple, tuple[float, dict]] = {}
        self._carregar()

    def _carregar(self) -> None:
        manifesto = DATA / "manifest.json"
        if not manifesto.exists():
            raise RuntimeError(f"Manifesto RAG ausente: {manifesto}")
        self.manifest = json.loads(manifesto.read_text(encoding="utf-8"))
        for item in self.manifest.get("personas", []):
            pid = item["id"]
            perfil_path = DATA / pid / "perfil.json"
            chunks_path = DATA / pid / "chunks.jsonl"
            self.perfis[pid] = (
                json.loads(perfil_path.read_text(encoding="utf-8"))
                if perfil_path.exists()
                else {"id": pid, "rotulo": item.get("rotulo", pid)}
            )
            chunks = []
            if chunks_path.exists():
                for linha in chunks_path.read_text(encoding="utf-8").splitlines():
                    if linha.strip():
                        chunks.append(json.loads(linha))
            self.chunks[pid] = chunks
            self.indices[pid] = BM25([c.get("texto", "") for c in chunks])
        logger.info(
            "RAG carregada: %d personas, versao %s",
            len(self.perfis),
            self.manifest.get("versao_rag"),
        )

    def buscar(self, pid: str, pergunta: str, k: int = TOP_K) -> list[dict]:
        if pid not in self.indices:
            return []
        consulta = tokenizar(pergunta)
        if not consulta:
            return []
        index = self.indices[pid]
        scores = [
            (index.pontuar(consulta, i), i) for i in range(len(self.chunks[pid]))
        ]
        scores.sort(reverse=True)
        escolhidos = []
        vistos = set()
        for score, i in scores:
            if score <= 0 and escolhidos:
                break
            chunk = self.chunks[pid][i]
            chave = chunk.get("hash") or chunk.get("url") or chunk.get("texto", "")[:80]
            if chave in vistos:
                continue
            vistos.add(chave)
            escolhidos.append({**chunk, "score": round(score, 3)})
            if len(escolhidos) >= k:
                break
        return escolhidos

    def permitir(self, uid: str) -> bool:
        agora = time.time()
        minuto = [t for t in self.uso[uid] if agora - t < 60]
        dia = [t for t in self.uso_dia[uid] if agora - t < 86400]
        self.uso[uid] = minuto
        self.uso_dia[uid] = dia
        if len(minuto) >= LIMITE_MINUTO or len(dia) >= LIMITE_DIA:
            return False
        self.uso[uid].append(agora)
        self.uso_dia[uid].append(agora)
        return True

    def permitir_simulacao(self, uid: str) -> bool:
        """Simular um discurso custa 12 chamadas de IA: limite próprio por hora."""
        agora = time.time()
        janela = [t for t in self.uso_simulacao[uid] if agora - t < 3600]
        if len(janela) >= LIMITE_SIMULACAO_HORA:
            self.uso_simulacao[uid] = janela
            return False
        janela.append(agora)
        self.uso_simulacao[uid] = janela
        return True


estado = Estado()
app = FastAPI(title="Personas API — ValorPúblico", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _init_firebase():
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return firebase_admin.get_app()
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "")
    if not raw and b64:
        try:
            raw = base64.b64decode(b64).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_B64 inválido.") from exc
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON inválido.") from exc
        return firebase_admin.initialize_app(
            credentials.Certificate(info), {"projectId": PROJECT}
        )
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return firebase_admin.initialize_app(
            credentials.ApplicationDefault(), {"projectId": PROJECT}
        )
    return firebase_admin.initialize_app(options={"projectId": PROJECT})


def _orgao_do_usuario(uid: str) -> str:
    from firebase_admin import firestore

    try:
        db = firestore.client()
        doc = db.collection("usuarios").document(uid).get()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="Não foi possível validar seu perfil agora. Tente novamente.",
        ) from exc
    if not doc.exists:
        return ""
    dados = doc.to_dict() or {}
    if dados.get("papel") in ("admin", "owner"):
        return "admin"
    return str(dados.get("orgao") or "")


def _autenticar(authorization: str | None) -> tuple[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token ausente.")
    from firebase_admin import auth

    _init_firebase()
    try:
        decoded = auth.verify_id_token(authorization.split(" ", 1)[1], check_revoked=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Token inválido.") from exc
    uid = decoded.get("uid") or decoded.get("sub") or ""
    papel = str(decoded.get("papel") or "")
    orgao = "admin" if papel in ("admin", "owner") else str(decoded.get("orgao") or "")
    if not orgao:
        orgao = _orgao_do_usuario(uid)
    if not orgao:
        raise HTTPException(status_code=403, detail="Perfil sem órgão.")
    if orgao not in ("governo-mt", "admin"):
        raise HTTPException(status_code=403, detail="Sem acesso a esta frente.")
    return uid, orgao


def _deepseek(
    messages: list[dict],
    temperatura: float = 0.4,
    max_tokens: int = 700,
    json_mode: bool = False,
) -> str:
    """Chamada única ao DeepSeek. Levanta HTTPException(503) se a IA falhar."""
    if not DEEPSEEK_KEY:
        raise HTTPException(status_code=503, detail="IA indisponível (chave ausente).")
    payload: dict[str, Any] = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperatura,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    ultima = None
    for _ in range(2):
        try:
            resp = requests.post(
                DEEPSEEK_BASE.rstrip("/") + "/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code >= 400:
                ultima = resp.status_code
                continue
            dados = resp.json()
            return (
                dados.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except requests.RequestException as exc:
            ultima = str(exc)[:80]
    raise HTTPException(status_code=503, detail=f"IA indisponível ({ultima}).")


def _chamar_deepseek(perfil: dict, pergunta: str, trechos: list[dict]) -> str:
    contexto = "\n\n".join(
        f"[{i+1}] ({t.get('fonte','fonte')}, {t.get('data','')}) {t.get('texto','')[:1200]}"
        for i, t in enumerate(trechos)
    )
    prompt = f"""Você é {perfil.get('rotulo')}, uma persona SINTÉTICA do Governo de Mato Grosso.
Personalidade: {', '.join(perfil.get('personalidade') or [])}.
Valores: {', '.join(perfil.get('valores') or [])}.
Gatilhos negativos: {', '.join(perfil.get('gatilhos_negativos') or [])}.
Linguagem: {perfil.get('linguagem', '')}.
Responda em primeira pessoa, em até 180 palavras, usando APENAS o CONTEXTO.
Cite as fontes como [1], [2]. Se não houver base, diga "não tenho informação suficiente".
Nunca finja ser pessoa real. Nunca peça voto. Nunca ofenda. Nunca invente números.

CONTEXTO:
{contexto}

PERGUNTA: {pergunta}
"""
    return _deepseek(
        [
            {
                "role": "system",
                "content": "Você é uma persona sintética. Responda em português, no personagem, com citações.",
            },
            {"role": "user", "content": prompt},
        ],
        temperatura=0.4,
        max_tokens=700,
    )


def _extrair_json(texto: str) -> dict | None:
    """Pega o objeto JSON de uma resposta da IA (aceita cerca de ```json)."""
    if not texto:
        return None
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = re.sub(r"^```[a-zA-Z]*\n?", "", limpo)
        limpo = re.sub(r"```\s*$", "", limpo).strip()
    inicio = limpo.find("{")
    fim = limpo.rfind("}")
    if inicio == -1 or fim <= inicio:
        return None
    try:
        dados = json.loads(limpo[inicio : fim + 1])
    except json.JSONDecodeError:
        return None
    return dados if isinstance(dados, dict) else None


def _numero(valor: Any, minimo: float, maximo: float, padrao: float) -> float:
    try:
        numero = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return padrao
    return max(minimo, min(maximo, numero))


def _avaliar_persona(pid: str, discurso: str, trechos: list[dict]) -> dict:
    """Uma persona ouve o discurso e devolve aderência, risco e sugestões."""
    perfil = estado.perfis.get(pid, {})
    rotulo = perfil.get("rotulo") or pid
    contexto = "\n\n".join(
        f"[{i+1}] ({t.get('fonte','fonte')}, {t.get('data','')}) {t.get('texto','')[:600]}"
        for i, t in enumerate(trechos)
    )
    prompt = f"""Você é {rotulo}, uma persona SINTÉTICA do Governo de Mato Grosso.
Personalidade: {', '.join(perfil.get('personalidade') or [])}.
Valores: {', '.join(perfil.get('valores') or [])}.
Gatilhos negativos: {', '.join(perfil.get('gatilhos_negativos') or [])}.
Linguagem: {perfil.get('linguagem', '')}.

Você está ouvindo um discurso institucional e vai dar sua reação honesta, do ponto de vista da sua persona.
Responda APENAS com JSON, neste formato:
{{
  "aderencia": 0.0,
  "risco": 0.0,
  "primeira_impressao": "uma frase",
  "o_que_funciona": "uma frase",
  "o_que_incomoda": "uma frase",
  "sugestao": "uma frase",
  "frase_de_risco": "trecho curto do discurso que soa ruim para você"
}}
Regras:
- aderencia vai de 0 (nada convenceu) a 10 (falei como se fosse para mim).
- risco vai de 0 (nenhum incômodo) a 1 (pode gerar rejeição).
- o_que_funciona e o_que_incomoda: veja o que a persona reconhece e o que a incomoda.
- sugestao: o que você mudaria no texto para falar com a sua realidade (concreto, em uma frase).
- frase_de_risco: cite o trecho literal do discurso, ou "" se não houver.
- Sem preâmbulo, sem markdown.

NOTÍCIAS DA SEMANA PARA VOCÊ (use como base factual):
{contexto}

DISCURSO:
{discurso[:8000]}
"""
    try:
        bruto = _deepseek(
            [
                {
                    "role": "system",
                    "content": "Você avalia um discurso no personagem de uma persona sintética e responde só em JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperatura=0.3,
            max_tokens=600,
            json_mode=True,
        )
    except HTTPException:
        return {"id": pid, "rotulo": rotulo, "erro": "IA indisponível para esta persona."}

    dados = _extrair_json(bruto) or {}
    citacoes = []
    vistos = set()
    for t in trechos:
        chave = t.get("url") or t.get("hash")
        if chave in vistos:
            continue
        vistos.add(chave)
        citacoes.append(
            {
                "titulo": t.get("fonte") or "Fonte",
                "url": t.get("url") or "",
                "data": t.get("data") or "",
            }
        )
    return {
        "id": pid,
        "rotulo": rotulo,
        "stakeholder": perfil.get("stakeholder") or "",
        "aderencia": round(_numero(dados.get("aderencia"), 0, 10, 5.0), 1),
        "risco": round(_numero(dados.get("risco"), 0, 1, 0.3), 2),
        "primeira_impressao": str(dados.get("primeira_impressao") or "").strip(),
        "o_que_funciona": str(dados.get("o_que_funciona") or "").strip(),
        "o_que_incomoda": str(dados.get("o_que_incomoda") or "").strip(),
        "sugestao": str(dados.get("sugestao") or "").strip(),
        "frase_de_risco": str(dados.get("frase_de_risco") or "").strip(),
        "citacoes": citacoes[:3],
    }


def _consolidar(respostas: list[dict], discurso: str) -> dict:
    """Leitura de conjunto: o que funcionou e o que mudar, em ordem de impacto."""
    if not respostas:
        return {"veredito": "", "pontos_fortes": [], "melhorias": []}
    linhas = "\n".join(
        f"- {r['rotulo']} (aderência {r['aderencia']}/10, risco {r['risco']}): "
        f"funciona: {r['o_que_funciona']} | incomoda: {r['o_que_incomoda']} | sugestão: {r['sugestao']}"
        for r in respostas
    )
    prompt = f"""Você é o analista de comunicação do Governo de Mato Grosso.
Você recebeu a reação de {len(respostas)} personas a um discurso institucional.
Escreva para a equipe de comunicação: o que fazer antes de publicar.
Responda APENAS com JSON:
{{
  "veredito": "uma frase com a leitura geral do texto",
  "pontos_fortes": ["até 4 pontos curtos que funcionaram"],
  "melhorias": [
    {{"titulo": "o que mudar", "como_reescrever": "como reescrever no texto", "personas": ["rótulo da persona que apontou"], "prioridade": "alta|media|baixa"}}
  ]
}}
Regras:
- 4 a 6 melhorias, ordenadas da mais impactante para a menos.
- cada melhoria nasce das reações acima: não invente queixa que ninguém teve.
- titulo: uma ação curta na voz da equipe (ex.: "Trocar promessa genérica por número concreto"), até 12 palavras.
- como_reescrever é prático: o que trocar no texto.
- Sem preâmbulo, sem markdown.

REAÇÕES DAS PERSONAS:
{linhas}

TRECHO DO DISCURSO PARA REFERÊNCIA:
{discurso[:3000]}
"""
    try:
        bruto = _deepseek(
            [
                {
                    "role": "system",
                    "content": "Você consolida a leitura de um painel de personas e responde só em JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperatura=0.3,
            max_tokens=1800,
            json_mode=True,
        )
    except HTTPException:
        bruto = ""
    dados = _extrair_json(bruto) or {}
    if not dados:
        # sem consolidação: usa as sugestões das personas mais críticas
        criticas = sorted(respostas, key=lambda r: r["aderencia"])[:5]
        return {
            "veredito": "",
            "pontos_fortes": [
                r["o_que_funciona"] for r in sorted(respostas, key=lambda r: -r["aderencia"])[:3]
            ],
            "melhorias": [
                {
                    "titulo": r["sugestao"],
                    "como_reescrever": r["o_que_incomoda"],
                    "personas": [r["rotulo"]],
                    "prioridade": "alta" if r["aderencia"] < 5 else "media",
                }
                for r in criticas
                if r["sugestao"]
            ],
        }
    pontos = [str(p).strip() for p in (dados.get("pontos_fortes") or []) if str(p).strip()]
    melhorias = []
    for item in dados.get("melhorias") or []:
        if not isinstance(item, dict):
            continue
        titulo = str(item.get("titulo") or "").strip()
        if not titulo:
            continue
        melhorias.append(
            {
                "titulo": titulo,
                "como_reescrever": str(item.get("como_reescrever") or "").strip(),
                "personas": [str(p).strip() for p in (item.get("personas") or []) if str(p).strip()],
                "prioridade": str(item.get("prioridade") or "media").strip().lower(),
            }
        )
    veredito = str(dados.get("veredito") or "").strip()
    if not veredito and bruto:
        achado = re.search(r'"veredito"\s*:\s*"([^"]{10,400})"', bruto)
        if achado:
            veredito = achado.group(1)
    return {
        "veredito": veredito,
        "pontos_fortes": pontos[:4],
        "melhorias": melhorias[:6],
    }



class Pergunta(BaseModel):
    pergunta: str
    semana: str | None = None


class Simulacao(BaseModel):
    discurso: str
    personas: list[str] | None = None


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "personas": len(estado.perfis),
        "versao_rag": estado.manifest.get("versao_rag"),
        "modelo": DEEPSEEK_MODEL,
        "tem_chave": bool(DEEPSEEK_KEY),
        "simulador": True,
    }


@app.post("/v1/discurso/simular")
def simular(
    corpo: Simulacao,
    authorization: str | None = Header(default=None),
) -> dict:
    """As personas do Governo reagem a um discurso enviado pelo usuário."""
    inicio = time.time()
    uid, _ = _autenticar(authorization)
    discurso = (corpo.discurso or "").strip()
    if len(discurso) < DISCURSO_MIN_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Cole um discurso com pelo menos {DISCURSO_MIN_CHARS} caracteres.",
        )
    if len(discurso) > DISCURSO_MAX_CHARS:
        discurso = discurso[:DISCURSO_MAX_CHARS]
    if not estado.permitir_simulacao(uid):
        raise HTTPException(
            status_code=429,
            detail="Limite de simulações por hora atingido. Tente mais tarde.",
        )

    pedidas = [p for p in (corpo.personas or list(estado.perfis.keys())) if p in estado.perfis]
    if not pedidas:
        raise HTTPException(status_code=400, detail="Nenhuma persona válida.")

    respostas: list[dict] = []
    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        futures = [
            pool.submit(_avaliar_persona, pid, discurso, estado.buscar(pid, discurso, k=3))
            for pid in pedidas
        ]
        for futuro in futures:
            try:
                respostas.append(futuro.result())
            except Exception as exc:  # noqa: BLE001
                logger.warning("falha ao avaliar persona: %s", str(exc)[:120])
    respostas.sort(key=lambda r: -float(r.get("aderencia") or 0))

    analise = _consolidar(respostas, discurso)

    aderencias = [float(r.get("aderencia") or 0) for r in respostas]
    riscos = [float(r.get("risco") or 0) for r in respostas]
    resumo = {
        "aderencia_media": round(sum(aderencias) / len(aderencias), 1) if aderencias else 0,
        "aderencia_min": min(aderencias) if aderencias else 0,
        "aderencia_max": max(aderencias) if aderencias else 0,
        "risco_medio": round(sum(riscos) / len(riscos), 2) if riscos else 0,
        "personas_alta": sum(1 for a in aderencias if a >= 7),
        "personas_baixa": sum(1 for a in aderencias if a < 4),
        "total_personas": len(respostas),
    }
    logger.info(
        "simulacao uid=%s personas=%d latencia_ms=%d",
        uid,
        len(respostas),
        int((time.time() - inicio) * 1000),
    )
    return {
        "discurso": {
            "palavras": len(discurso.split()),
            "caracteres": len(discurso),
        },
        "resumo": resumo,
        "veredito": analise.get("veredito", ""),
        "pontos_fortes": analise.get("pontos_fortes", []),
        "melhorias": analise.get("melhorias", []),
        "personas": respostas,
        "aviso": "Simulação (hipótese) — as personas são sintéticas. Não é pesquisa de opinião.",
        "modelo": DEEPSEEK_MODEL,
        "versao_rag": estado.manifest.get("versao_rag"),
        "latencia_ms": int((time.time() - inicio) * 1000),
    }


@app.get("/v1/personas")
def listar(authorization: str | None = Header(default=None)) -> dict:
    _autenticar(authorization)
    return {"personas": estado.manifest.get("personas", []), "versao_rag": estado.manifest.get("versao_rag")}


@app.post("/v1/personas/{persona_id}/perguntar")
def perguntar(
    persona_id: str,
    corpo: Pergunta,
    authorization: str | None = Header(default=None),
) -> dict:
    inicio = time.time()
    uid, _ = _autenticar(authorization)
    if persona_id not in estado.perfis:
        raise HTTPException(status_code=404, detail="Persona não encontrada.")
    if not corpo.pergunta.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia.")
    if not estado.permitir(uid):
        raise HTTPException(status_code=429, detail="Limite de uso atingido.")
    chave_cache = (uid, persona_id, corpo.pergunta.strip().lower(), estado.manifest.get("versao_rag"))
    agora = time.time()
    if chave_cache in estado.cache:
        quando, resposta = estado.cache[chave_cache]
        if agora - quando < 86400:
            return {**resposta, "cache": True}

    trechos = estado.buscar(persona_id, corpo.pergunta)
    if not trechos:
        resposta = {
            "persona": {"id": persona_id, "rotulo": estado.perfis[persona_id].get("rotulo")},
            "resposta": "Não tenho informação suficiente no contexto desta semana para responder com segurança.",
            "citacoes": [],
            "aviso": "Resposta sintética de uma persona. Não é pesquisa nem opinião de pessoa real.",
            "modelo": DEEPSEEK_MODEL,
            "versao_rag": estado.manifest.get("versao_rag"),
            "latencia_ms": int((time.time() - inicio) * 1000),
        }
        estado.cache[chave_cache] = (agora, resposta)
        return resposta

    texto = _chamar_deepseek(estado.perfis[persona_id], corpo.pergunta, trechos)
    citacoes = []
    vistos = set()
    for t in trechos:
        chave = t.get("url") or t.get("hash")
        if chave in vistos:
            continue
        vistos.add(chave)
        citacoes.append(
            {
                "titulo": t.get("fonte") or "Fonte",
                "url": t.get("url") or "",
                "data": t.get("data") or "",
                "trecho": (t.get("texto") or "")[:220],
            }
        )
    resposta = {
        "persona": {"id": persona_id, "rotulo": estado.perfis[persona_id].get("rotulo")},
        "resposta": texto,
        "citacoes": citacoes[:6],
        "aviso": "Resposta sintética de uma persona. Não é pesquisa nem opinião de pessoa real.",
        "modelo": DEEPSEEK_MODEL,
        "versao_rag": estado.manifest.get("versao_rag"),
        "latencia_ms": int((time.time() - inicio) * 1000),
    }
    estado.cache[chave_cache] = (agora, resposta)
    logger.info(
        "pergunta persona=%s uid=%s trechos=%d latencia_ms=%d",
        persona_id,
        uid,
        len(trechos),
        resposta["latencia_ms"],
    )
    return resposta

