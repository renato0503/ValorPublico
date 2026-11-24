"""CHD pelo metodo de Reinert (plano 10 §3.3), via `rainette` (R, GPL-3).

O `rainette` e o pacote R que reproduz o metodo do IRaMuTeQ (Hierarchical
Descending Classification). O Python so:
  1. escreve o corpus `.txt` no formato do IRaMuTeQ;
  2. chama `Rscript`, que importa o corpus, faz `split_segments()`, monta o
     `dfm` e roda `rainette::rainette()`;
  3. recebe a **matriz de frequencias** (segmentos x formas) e a **classe de
     cada segmento** (`rainette` devolve `group` por documento e `uce_groups`
     por nivel);
  4. calcula em Python o que o IRaMuTeQ mostra: % de segmentos por classe,
     chi2 e p das formas mais tipicas de cada classe e a arvore de fusao.

Se o R ou o rainette nao estiverem disponiveis, o modulo **nao quebra**: devolve
um aviso e o chamador cai no metodo alternativo (Ward sobre TF-IDF, como o
`processing/lexical.py` dos apps).

Parametros iniciais (plano 10 §3.3): k=6, min_segment_size=10, min_split_members=10.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from cerra_nucleo.core.logger import get_logger

logger = get_logger(__name__)

RSCRIPT = "Rscript"
CANDIDATOS_RSCRIPT = [
    r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe",
    "/usr/bin/Rscript",
    "/usr/local/bin/Rscript",
]

# Script R executado pelo Python: le o corpus, roda o rainette e exporta
# a matriz de frequencias + a classe de cada segmento.
SCRIPT_R = r"""
args <- commandArgs(trailingOnly = TRUE)
corpus_path <- args[1]
saida <- args[2]
k <- as.integer(args[3])
min_segment_size <- as.integer(args[4])
min_split_members <- as.integer(args[5])

suppressWarnings(suppressMessages({
  library(rainette)
  library(quanteda)
  library(jsonlite)
}))

resultado <- list(ok = FALSE, erro = "", k = k)

tryCatch({
  corpus <- rainette::import_corpus_iramuteq(corpus_path)
  corpus <- rainette::split_segments(corpus)
  tok <- quanteda::tokens(corpus, remove_punct = TRUE)
  dtm <- quanteda::dfm(tok, tolower = TRUE)
  res <- rainette::rainette(
    dtm,
    k = k,
    min_segment_size = min_segment_size,
    min_split_members = min_split_members
  )

  m <- as.matrix(dtm)
  # `uce_groups` traz o grupo (classe) de cada segmento, por nivel do dendrograma.
  # O ultimo nivel corresponde ao k maximo pedido.
  niveis <- res$uce_groups
  grupos_segmento <- niveis[[length(niveis)]]

  resultado$ok <- TRUE
  resultado$matriz <- lapply(seq_len(nrow(m)), function(i) as.integer(m[i, ]))
  resultado$formas <- as.character(colnames(m))
  resultado$classes <- as.integer(grupos_segmento)
  resultado$altura <- as.numeric(res$height)
  resultado$merge <- as.numeric(res$merge)
  resultado$ordem <- as.integer(res$order)
  resultado$rotulos <- as.character(res$labels)
  resultado$n_segmentos <- nrow(m)
  resultado$n_textos <- length(unique(rownames(dtm)))
}, error = function(e) {
  resultado$erro <- conditionMessage(e)
})

writeLines(jsonlite::toJSON(resultado, auto_unbox = TRUE, digits = 8), saida)
"""


def rscript_disponivel() -> bool:
    """True se houver um `Rscript` utilizavel."""
    if shutil.which(RSCRIPT):
        return True
    return any(Path(c).exists() for c in CANDIDATOS_RSCRIPT)


def caminho_rscript() -> str:
    if shutil.which(RSCRIPT):
        return RSCRIPT
    for candidato in CANDIDATOS_RSCRIPT:
        if Path(candidato).exists():
            return candidato
    return RSCRIPT


def rainette_instalado() -> bool:
    """True se o pacote `rainette` estiver instalado no R."""
    if not rscript_disponivel():
        return False
    try:
        proc = subprocess.run(
            [caminho_rscript(), "-e", "cat(requireNamespace('rainette', quietly=TRUE))"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.stdout.strip() == "TRUE"
    except Exception:  # noqa: BLE001
        return False


def executar(
    corpus_txt: str,
    k: int = 6,
    min_segment_size: int = 10,
    min_split_members: int = 10,
    timeout: int = 1800,
) -> dict:
    """Roda a CHD de Reinert sobre o corpus `.txt`.

    Devolve {"ok", "classes", "arvore", "estatisticas", "erro", "metodo"}.
    """
    if not rscript_disponivel():
        return _falha("Rscript nao encontrado")
    if not rainette_instalado():
        return _falha("pacote 'rainette' nao instalado no R")

    with tempfile.TemporaryDirectory(prefix="cerra_reinert_") as pasta:
        base = Path(pasta)
        corpus_path = base / "corpus.txt"
        saida = base / "saida.json"
        script = base / "reinert.R"
        corpus_path.write_text(corpus_txt, encoding="utf-8")
        script.write_text(SCRIPT_R, encoding="utf-8")
        try:
            proc = subprocess.run(
                [
                    caminho_rscript(),
                    str(script),
                    str(corpus_path),
                    str(saida),
                    str(k),
                    str(min_segment_size),
                    str(min_split_members),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return _falha(f"rainette excedeu {timeout}s")
        if not saida.exists():
            return _falha(f"rainette nao gravou saida: {proc.stderr[-400:]}")
        try:
            bruto = json.loads(saida.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _falha(f"saida do rainette nao e JSON: {exc}")
        if not bruto.get("ok"):
            return _falha(bruto.get("erro", "erro desconhecido"))
        return _montar_resultado(bruto)


def _falha(erro: str) -> dict:
    return {
        "ok": False,
        "classes": [],
        "arvore": [],
        "estatisticas": {},
        "erro": erro,
        "metodo": "indisponivel",
    }


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _montar_resultado(bruto: dict) -> dict:
    """Calcula %, chi2 e p por classe (o que o IRaMuTeQ mostra)."""
    matriz = bruto.get("matriz", [])
    formas = bruto.get("formas", [])
    classes = bruto.get("classes", [])
    n_segmentos = len(matriz)

    total_forma = [0] * len(formas)
    for linha in matriz:
        for i, v in enumerate(linha):
            total_forma[i] += int(v)
    total_classe: dict[int, int] = {}
    for i, linha in enumerate(matriz):
        c = classes[i] if i < len(classes) else 1
        total_classe[c] = total_classe.get(c, 0) + sum(int(v) for v in linha)

    saida_classes = []
    for classe in sorted(total_classe):
        indices = [
            i for i in range(n_segmentos) if (classes[i] if i < len(classes) else 1) == classe
        ]
        pct = round(100.0 * len(indices) / n_segmentos, 2) if n_segmentos else 0.0

        formas_classe = []
        for j, forma in enumerate(formas):
            dentro = sum(int(matriz[i][j]) for i in indices)
            if dentro == 0:
                continue
            fora = total_forma[j] - dentro
            chi2, p = _chi2(
                dentro,
                fora,
                total_classe[classe],
                n_segmentos - total_classe[classe],
            )
            formas_classe.append({"f": forma, "chi2": round(chi2, 3), "p": round(p, 6)})
        formas_classe.sort(key=lambda x: -x["chi2"])

        saida_classes.append(
            {
                "id": classe,
                "pct": pct,
                "st": len(indices),
                "forma": formas_classe[0]["f"] if formas_classe else "",
                "chi2": formas_classe[0]["chi2"] if formas_classe else 0.0,
                "p": formas_classe[0]["p"] if formas_classe else 0.0,
                "formas": formas_classe[:12],
                "st_tipicos": [],
            }
        )

    # Mantem so as classes com peso relevante (as maiores) para o relatorio.
    saida_classes.sort(key=lambda c: -c["pct"])
    arvore = {
        "altura": bruto.get("altura", []),
        "merge": bruto.get("merge", []),
        "ordem": bruto.get("ordem", []),
        "rotulos": bruto.get("rotulos", []),
    }
    estatisticas = {
        "textos": bruto.get("n_textos", 0),
        "st": bruto.get("n_segmentos", 0),
        "formas": len(formas),
        "ocorrencias": sum(total_forma),
    }
    return {
        "ok": True,
        "classes": saida_classes,
        "arvore": arvore,
        "estatisticas": estatisticas,
        "erro": "",
        "metodo": "reinert/rainette",
    }


def _chi2(dentro_a: int, fora_a: int, dentro_b: int, fora_b: int) -> tuple[float, float]:
    """Chi2 e p-value da tabela 2x2 (forma x classe)."""
    total = dentro_a + fora_a + dentro_b + fora_b
    if total == 0:
        return 0.0, 1.0
    linha_a = dentro_a + fora_a
    linha_b = dentro_b + fora_b
    if linha_a == 0 or linha_b == 0:
        return 0.0, 1.0
    esperado_a = linha_a * (dentro_a + dentro_b) / total
    esperado_b = linha_b * (dentro_a + dentro_b) / total
    esperado_c = linha_a * (fora_a + fora_b) / total
    esperado_d = linha_b * (fora_a + fora_b) / total
    chi2 = 0.0
    for observado, esperado in (
        (dentro_a, esperado_a),
        (fora_a, esperado_c),
        (dentro_b, esperado_b),
        (fora_b, esperado_d),
    ):
        if esperado > 0:
            chi2 += (observado - esperado) ** 2 / esperado
    return chi2, _chi2_p(chi2)


def _chi2_p(chi2: float) -> float:
    """p-value de chi2 com 1 gl (via funcao erro)."""
    if chi2 <= 0:
        return 1.0
    try:
        from math import erfc, sqrt

        return erfc(sqrt(chi2 / 2.0))
    except Exception:  # noqa: BLE001
        return 1.0


def rotulo_da_classe(item: dict) -> str:
    """Nome amigavel da classe (a forma mais tipica, em maiusculas)."""
    formas = item.get("formas") or []
    if formas:
        return str(formas[0].get("f", "")).upper()
    forma = (item.get("forma") or "").strip()
    return forma.upper() if forma else f"Classe {item.get('id', '?')}"
