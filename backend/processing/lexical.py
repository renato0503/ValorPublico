"""Analises lexicais estilo IRAMUTEQ sobre o corpus de clippings.

Implementa, com numpy/scipy/sklearn, as principais tecnicas do IRAMUTEQ:

  - Frequencia lexical global e por periodo (mes).
  - Especificidade por periodo (qui-quadrado de cada palavra x periodo).
  - Matriz de co-ocorrencia e grafo de similaridade entre termos.
  - Analise Fatorial de Correspondencias (AFC) sobre a tabela palavra x periodo.
  - Classificacao Hierarquica Descendente (CHD) via agrupamento de Ward sobre
    TF-IDF dos segmentos de texto (UCE), com palavras caracteristicas por classe.

Saidas geradas em `backend/data/export/lexical/` pelo script `analise_lexical.py`.
"""

from collections import Counter, defaultdict

import numpy as np

from processing.nuvem import extrair_palavras, _STOPWORDS

__all__ = [
    "frequencia_global",
    "frequencia_por_periodo",
    "especificidade_por_periodo",
    "coocorrencia",
    "analise_correspondencias",
    "segmentar",
    "chd",
]


def _mes(dt) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m")
    return str(dt)[:7]


def _contar_por_periodo(clippings) -> dict[str, Counter]:
    por_mes: defaultdict[str, Counter] = defaultdict(Counter)
    for c in clippings:
        palavras = extrair_palavras(c.get("texto_limpo") or "")
        mes = _mes(c.get("data_publicacao"))
        if mes:
            por_mes[mes].update(palavras)
    return dict(sorted(por_mes.items()))


def frequencia_global(clippings, top: int = 300) -> dict[str, int]:
    cont: Counter = Counter()
    for c in clippings:
        cont.update(extrair_palavras(c.get("texto_limpo") or ""))
    return dict(cont.most_common(top))


def frequencia_por_periodo(clippings, top_por_periodo: int = 300) -> dict[str, dict[str, int]]:
    por_mes = _contar_por_periodo(clippings)
    return {
        mes: dict(cont.most_common(top_por_periodo))
        for mes, cont in por_mes.items()
    }


def especificidade_por_periodo(clippings, chi_min: float = 3.84) -> list[dict]:
    """Teste de especificidade (qui-quadrado) de cada palavra por periodo.

    Retorna lista ordenada por chi2 desc: palavra, periodo, frequencia
    observada, esperada, chi2 e sinal (sobre/sub-representada).
    """
    por_mes = _contar_por_periodo(clippings)
    meses = sorted(por_mes.keys())
    if not meses:
        return []
    palavras = sorted({p for cont in por_mes.values() for p in cont})
    idx = {p: i for i, p in enumerate(palavras)}
    tabela = np.zeros((len(palavras), len(meses)), dtype=float)
    for j, mes in enumerate(meses):
        for palavra, freq in por_mes[mes].items():
            tabela[idx[palavra], j] = freq

    total_geral = float(tabela.sum())
    if total_geral <= 0:
        return []
    tot_linha = tabela.sum(axis=1)
    tot_col = tabela.sum(axis=0)

    resultados: list[dict] = []
    for i, palavra in enumerate(palavras):
        for j, mes in enumerate(meses):
            observado = tabela[i, j]
            if observado <= 0:
                continue
            esperado = tot_linha[i] * tot_col[j] / total_geral
            if esperado <= 0:
                continue
            chi = (observado - esperado) ** 2 / esperado
            if chi >= chi_min:
                resultados.append(
                    {
                        "palavra": palavra,
                        "periodo": mes,
                        "frequencia": int(observado),
                        "esperado": round(esperado, 2),
                        "chi2": round(chi, 2),
                        "sinal": "sobre" if observado > esperado else "sub",
                    }
                )
    resultados.sort(key=lambda r: (-r["chi2"], r["palavra"]))
    return resultados


def coocorrencia(clippings, top_n: int = 50) -> dict:
    """Matriz de co-ocorrencia dos N termos mais frequentes (janela = clipping)."""
    freq: Counter = Counter()
    docs: list[set[str]] = []
    for c in clippings:
        palavras = extrair_palavras(c.get("texto_limpo") or "")
        freq.update(palavras)
        docs.append(set(palavras))

    top = [p for p, _ in freq.most_common(top_n)]
    idx = {p: i for i, p in enumerate(top)}
    n = len(top)
    mat = np.zeros((n, n), dtype=int)
    for doc in docs:
        presentes = [idx[p] for p in doc if p in idx]
        for a in presentes:
            for b in presentes:
                if a != b:
                    mat[a, b] += 1

    arestas = [
        {"a": top[a], "b": top[b], "peso": int(mat[a, b])}
        for a in range(n)
        for b in range(a + 1, n)
        if mat[a, b] > 0
    ]
    arestas.sort(key=lambda e: -e["peso"])
    return {
        "nos": [{"id": p, "peso": int(freq[p])} for p in top],
        "arestas": arestas,
    }


def analise_correspondencias(clippings, top_palavras: int = 80) -> dict:
    """AFC sobre a tabela palavra x periodo (SVD da matriz de desvios).

    Retorna coordenadas (2 eixos) de palavras e periodos para o mapa fatorial.
    """
    por_mes = _contar_por_periodo(clippings)
    meses = sorted(por_mes.keys())
    if not meses:
        return {"palavras": [], "periodos": [], "coord_palavras": [], "coord_periodos": [], "valores": []}

    freq: Counter = Counter()
    for cont in por_mes.values():
        freq.update(cont)
    top = [p for p, _ in freq.most_common(top_palavras)]

    tabela = np.zeros((len(top), len(meses)), dtype=float)
    for j, mes in enumerate(meses):
        for palavra, f in por_mes[mes].items():
            if palavra in top:
                tabela[top.index(palavra), j] = f

    tot = float(tabela.sum())
    if tot <= 0:
        return {"palavras": top, "periodos": meses, "coord_palavras": [], "coord_periodos": [], "valores": []}

    P = tabela / tot
    r = P.sum(axis=1)
    c = P.sum(axis=0)
    r_safe = np.where(r == 0, 1e-12, r)
    c_safe = np.where(c == 0, 1e-12, c)
    S = (np.diag(1.0 / r_safe) @ (P - np.outer(r, c)) @ np.diag(1.0 / c_safe))

    U, sing, Vt = np.linalg.svd(S, full_matrices=False)
    escala = np.sqrt(np.maximum(sing, 0))
    coord_palavras = np.diag(1.0 / r_safe) @ U * escala
    coord_periodos = np.diag(1.0 / c_safe) @ Vt.T * escala

    return {
        "palavras": top,
        "periodos": meses,
        "coord_palavras": coord_palavras[:, :2].tolist(),
        "coord_periodos": coord_periodos[:, :2].tolist(),
        "valores": sing[:2].tolist(),
    }


def segmentar(texto: str, tamanho: int = 60) -> list[str]:
    """Divide um texto em segmentos de ~`tamanho` palavras (UCE, estilo IRAMUTEQ)."""
    palavras = extrair_palavras(texto)
    return [" ".join(palavras[i : i + tamanho]) for i in range(0, len(palavras), tamanho)]


def chd(clippings, n_classes: int = 4, min_segmentos: int = 100) -> dict:
    """Classificacao Hierarquica Descendente (Ward) sobre TF-IDF dos segmentos.

    Retorna as classes com as palavras caracteristicas (qui-quadrado).
    Requer `scipy` e `sklearn`.
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from sklearn.feature_extraction.text import TfidfVectorizer

    segmentos: list[str] = []
    for c in clippings:
        segmentos.extend(segmentar(c.get("texto_limpo") or ""))
    if len(segmentos) < min_segmentos:
        return {
            "segmentos": len(segmentos),
            "classes": [],
            "aviso": "corpus pequeno para CHD (min. 100 segmentos).",
        }

    vec = TfidfVectorizer(token_pattern=r"[a-z0-9]{3,}", min_df=2)
    X = vec.fit_transform(segmentos)
    Z = linkage(X.toarray(), method="ward")
    rotulos = fcluster(Z, t=n_classes, criterion="maxclust")

    features = [f for f in vec.get_feature_names_out() if f not in _STOPWORDS]
    col_idx = {f: i for i, f in enumerate(vec.get_feature_names_out()) if f in set(features)}
    total_geral = float(X.sum())

    classes: list[dict] = []
    for k in range(1, n_classes + 1):
        membros = np.where(rotulos == k)[0]
        if len(membros) < 5:
            continue
        presenca = X[membros].sum(axis=0)
        presenca_arr = np.asarray(presenca).ravel()
        total_classe = float(presenca_arr.sum())

        palavras_classe: list[dict] = []
        for nome, j in col_idx.items():
            obs = presenca_arr[j]
            if obs <= 0:
                continue
            total_termo = float(X[:, j].sum())
            esperado = total_classe * total_termo / max(total_geral, 1e-9)
            if esperado <= 0:
                continue
            chi = (obs - esperado) ** 2 / esperado
            if chi >= 3.84:
                palavras_classe.append({"palavra": nome, "chi2": round(chi, 2), "frequencia": int(obs)})
        palavras_classe.sort(key=lambda p: -p["chi2"])
        classes.append(
            {
                "classe": int(k),
                "n_segmentos": int(len(membros)),
                "pct": round(100 * len(membros) / len(segmentos), 1),
                "palavras": palavras_classe[:20],
            }
        )
    classes.sort(key=lambda cl: -cl["n_segmentos"])
    return {"segmentos": len(segmentos), "classes": classes}