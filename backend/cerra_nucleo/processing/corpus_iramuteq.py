"""Corpus no formato IRaMuTeQ (plano 10 §2).

Cada item (clipping, post, comentario, transcricao) vira uma linha de cabecalho
com variaveis:

    **** *agente_123 *casa_almt *rede_instagram *sent_neg *semana_2026w48
    texto limpo do item...

Os segmentos de texto (ST) tem ~40 formas, respeitando a pontuacao.
O arquivo `.txt` exportado e o mesmo que o IRaMuTeQ le (UTF-8), o que permite a
validacao mensal contra o software de referencia (plano 10 §9).

Lematizacao: regex de sufixos + dicionario de excecoes do projeto (nomes de
agentes e siglas: ALMT, VG, SUS, UPA, BRT, VLT) para nao lematizar nome proprio.

Comentarios de cidadao entram **com o autor** (liberado pelo dono em 24/11/2026),
sempre com a proveniencia (rede + URL) na variavel `*fonte`.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

# Siglas e nomes proprios que NAO devem ser lematizados.
EXCECOES = {
    "almt", "vg", "sus", "upa", "brt", "vlt", "mt", "ms", "cuiaba", "ui", "api",
    "ui", "ips", "cnpj", "cpf", "mei", "eua", "onu", "iso", "dvb", "5g",
}

# Sufixos removidos na lematizacao (simplificada, sem dicionario externo).
SUFIXOS = [
    "mente", "mente", "coes", "mente",
]

RE_PONTUACAO = re.compile(r"([.;:!?,\)\"])")
RE_NUMERO = re.compile(r"^\d+$")
RE_URL = re.compile(r"https?://\S+")
RE_MENTION = re.compile(r"@\w+")
RE_HTML = re.compile(r"<[^>]+>")


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def limpar_texto(texto: str) -> str:
    """Remove HTML, URLs e mencoes; normaliza espacos."""
    # S0 (plano 22): entidades HTML (inclusive escapadas duas vezes) e sobras de "nbsp"
    limpo = html.unescape(html.unescape(texto or "")).replace(chr(160), " ")
    limpo = re.sub(r"&?\bnbsp\b;?", " ", limpo, flags=re.IGNORECASE)
    limpo = RE_HTML.sub(" ", limpo)
    limpo = RE_URL.sub(" ", limpo)
    limpo = RE_MENTION.sub(" ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return limpo


def lematizar(texto: str) -> str:
    """Lematizacao simples por sufixo (sem dicionario externo)."""
    palavras = []
    for palavra in texto.split():
        base = _sem_acento(palavra)
        if not base or RE_NUMERO.match(base) or base in EXCECOES:
            palavras.append(palavra.lower())
            continue
        # plural simples -> singular
        if len(base) > 4 and base.endswith("s") and not base.endswith("ss"):
            base = base[:-1]
        palavras.append(base)
    return " ".join(palavras)


def segmentar(texto: str, tamanho_st: int = 40) -> list[str]:
    """Divide o texto em segmentos de ~40 formas, respeitando a pontuacao.

    Um ST do IRaMuTeQ tem no maximo ~40 formas e termina em fronteira de
    pontuacao. O resto do paragrafo (sem pontuacao) vira um ST proprio, sem
    passar do limite.
    """
    if not texto:
        return []
    partes = re.split(r"(?<=[.;:!?])\s+", texto)
    segmentos: list[str] = []
    atual: list[str] = []
    for parte in partes:
        for palavra in parte.split():
            atual.append(palavra)
            if len(atual) >= tamanho_st:
                segmentos.append(" ".join(atual))
                atual = []
    if atual:
        # O resto entra no ST anterior so se ele estiver longe do limite
        # (caso contrario vira um ST curto, como no IRaMuTeQ).
        if segmentos and len(segmentos[-1].split()) < tamanho_st // 2:
            segmentos[-1] = f"{segmentos[-1]} {' '.join(atual)}"
        else:
            segmentos.append(" ".join(atual))
    return [s for s in segmentos if s.strip()]


@dataclass
class ItemCorpus:
    """Um item do corpus, com as variaveis do IRaMuTeQ."""

    texto: str
    agente_id: str = ""
    casa: str = ""
    rede: str = ""
    tipo: str = ""
    sentimento: str = ""
    semana: str = ""
    autor: str = ""
    url: str = ""
    veiculo: str = ""
    data: str = ""
    extras: dict = field(default_factory=dict)

    def variaveis(self) -> list[str]:
        """Lista de variaveis (`*nome` ou `*nome_valor`)."""
        saida = []
        if self.agente_id:
            saida.append(f"*agente_{self.agente_id}")
        if self.casa:
            saida.append(f"*casa_{self.casa}")
        if self.rede:
            saida.append(f"*rede_{self.rede}")
        if self.tipo:
            saida.append(f"*tipo_{self.tipo}")
        if self.sentimento:
            saida.append(f"*sent_{self.sentimento}")
        if self.semana:
            saida.append(f"*semana_{self.semana}")
        if self.autor:
            saida.append(f"*autor_{_sem_acento(self.autor).replace(' ', '_')}")
        if self.veiculo:
            saida.append(f"*veiculo_{_sem_acento(self.veiculo).replace(' ', '_')}")
        if self.fonte_imagem:
            saida.append("*fonte_imagem")
        for chave, valor in self.extras.items():
            saida.append(f"*{chave}_{_sem_acento(str(valor)).replace(' ', '_')}")
        return saida

    @property
    def fonte_imagem(self) -> bool:
        return bool(self.extras.get("fonte_imagem"))


def cabecalho(item: ItemCorpus) -> str:
    """Monta a linha de cabecalho (variaveis + `****`)."""
    variaveis = " ".join(item.variaveis())
    return f"**** {variaveis}" if variaveis else "**** *sem_escopo"


def _sem_veiculo(texto: str, veiculo: str) -> str:
    """Tira o nome do veiculo que o agregador cola no titulo ("... - Fatos de MT")."""
    veiculo = (veiculo or "").strip()
    if len(veiculo) < 3:
        return texto
    padrao = re.compile(r"(?:\s[-|]\s)?" + re.escape(veiculo), re.IGNORECASE)
    return re.sub(r"\s+", " ", padrao.sub(" ", texto)).strip()


def _sem_repeticao(texto: str) -> str:
    """Remove o titulo repetido no resumo (o agregador manda titulo + titulo).

    Compara palavras sem pontuacao e aceita a segunda copia truncada.
    """
    palavras = [p for p in texto.split() if re.search(r"\w", p)]
    chave = [re.sub(r"\W+", "", p.lower()) for p in palavras]
    n = len(chave)
    for k in range(n // 2, 4, -1):
        resto = chave[k : 2 * k]
        if len(resto) >= 5 and chave[: len(resto)] == resto:
            return " ".join(palavras[:k] + palavras[k + len(resto) :])
    # copia truncada: o resumo comeca com o titulo e termina antes dele
    for k in range(n - 5, 4, -1):
        resto = chave[k:]
        if len(resto) >= 5 and chave[: len(resto) - 1] == resto[:-1]:
            return " ".join(palavras[:k])
    return " ".join(palavras)


def montar_corpus(itens: list[dict]) -> list[ItemCorpus]:
    """Converte uma lista de clippings em itens de corpus.

    Aceita dicionarios com as chaves: `texto_limpo`/`texto`, `agente_id`,
    `casa`, `plataforma`, `tipo`, `sentimento`, `autor`, `url`, `veiculo`.
    """
    corpus: list[ItemCorpus] = []
    for bruto in itens or []:
        texto = limpar_texto(bruto.get("texto_limpo") or bruto.get("texto") or "")
        texto = _sem_veiculo(texto, str(bruto.get("veiculo") or ""))
        texto = _sem_repeticao(texto)
        if len(texto.split()) < 5:
            continue
        corpus.append(
            ItemCorpus(
                texto=texto,
                agente_id=str(bruto.get("agente_id") or ""),
                casa=str(bruto.get("casa") or bruto.get("cidade") or ""),
                rede=str(bruto.get("plataforma") or ""),
                tipo=str(bruto.get("tipo") or ""),
                sentimento=str(bruto.get("sentimento") or ""),
                semana=str(bruto.get("semana") or ""),
                autor=str(bruto.get("autor") or ""),
                url=str(bruto.get("url") or ""),
                veiculo=str(bruto.get("veiculo") or ""),
                data=str(bruto.get("data") or ""),
                extras={k: v for k, v in bruto.items() if k.startswith("extra_")},
            )
        )
    return corpus


def exportar_txt(corpus: list[ItemCorpus], caminho: str) -> str:
    """Grava o corpus no formato `.txt` do IRaMuTeQ (UTF-8)."""
    linhas = []
    for item in corpus:
        linhas.append(cabecalho(item))
        for segmento in segmentar(lematizar(item.texto)):
            linhas.append(segmento)
    conteudo = "\n".join(linhas) + "\n"
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    return caminho


def estatisticas(corpus: list[ItemCorpus]) -> dict:
    """Estatisticas textuais (plano 10 §3.1)."""
    from collections import Counter

    formas = Counter()
    Hapax = 0
    ocorrencias = 0
    segmentos = 0
    for item in corpus:
        for segmento in segmentar(lematizar(item.texto)):
            segmentos += 1
            palavras = segmento.split()
            ocorrencias += len(palavras)
            formas.update(palavras)
    hapax = sum(1 for v in formas.values() if v == 1)
    return {
        "textos": len(corpus),
        "st": segmentos,
        "ocorrencias": ocorrencias,
        "formas": len(formas),
        "hapax": hapax,
        "media_palavras_por_texto": round(ocorrencias / len(corpus), 1) if corpus else 0,
    }
