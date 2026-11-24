"""Teste de cobertura das explicacoes (plano 17 §12.1).

Falha se algum KPI (K-), grafico (G-), tabela (T-) ou relatorio (R-) usado no
front nao tiver entrada em `frontend/js/explicacoes.js`.

Como o front e JS puro, o teste:
  1. le `explicacoes.js` e extrai os codigos definidos;
  2. varre o HTML e os JS do front em busca de `data-explicacao="K-xx"`,
     `codigo: "K-xx"`, `id="kpi..."`, `codigo` usado em `cartaoKpi(...)` e
     os nomes de arquivo/rotulao que citam os codigos;
  3. tambem confere as **palavras proibidas** (§12.2): as explicacoes nao podem
     usar sigla sem explicar (SoV, AVE, CHD, AFC, IC, SLA, KPI);
  4. confere o limite de tamanho (cada explicacao ate 300 caracteres).

Uso (a partir de `frontend/`):
    python tests/teste_explicacoes.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent

PASSOU: list[str] = []
FALHOU: list[str] = []

# Siglas que o plano 17 §12.2 proibe sem explicacao.
SIGLAS_PROIBIDAS = {
    "SoV": "Share of Voice",
    "AVE": "valoração",
    "CHD": "classificação hierárquica descendente",
    "AFC": "análise fatorial de correspondência",
    "SLA": "tempo de atendimento",
    "KPI": "indicador",
}


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


def main() -> int:
    explicacoes = FRONTEND / "js" / "explicacoes.js"
    if not explicacoes.exists():
        print("  FAIL  frontend/js/explicacoes.js nao encontrado")
        return 1

    texto = explicacoes.read_text(encoding="utf-8")
    definidos = set(re.findall(r'^\s*"([KGTR]-\d{2})":\s*\{', texto, re.MULTILINE))
    print(f"== explicacoes definidas: {len(definidos)} ==")
    checar("registro com K-xx, G-xx, T-xx e R-xx", len(definidos) >= 60, str(len(definidos)))

    # --- cobertura: todo codigo usado no front precisa estar definido ---
    print("== cobertura dos codigos usados no front ==")
    usados: set[str] = set()
    for arquivo in list(FRONTEND.glob("*.html")) + list((FRONTEND / "js").glob("*.js")):
        if arquivo.name == "explicacoes.js":
            continue
        conteudo = arquivo.read_text(encoding="utf-8")
        usados |= set(re.findall(r'["\']([KGTR]-\d{2})["\']', conteudo))
        usados |= set(re.findall(r'data-explicacao="([KGTR]-\d{2})"', conteudo))

    faltando = sorted(usados - definidos)
    checar(
        f"todos os {len(usados)} codigos usados tem explicacao",
        not faltando,
        f"faltando: {faltando}",
    )

    # --- linguagem: tamanho e siglas ---
    print("== linguagem das explicacoes ==")
    blocos = re.findall(r'"([KGTR]-\d{2})":\s*\{(.*?)\n  \},', texto, re.DOTALL)
    longas = []
    for codigo, corpo in blocos:
        campos = re.findall(r'(oQueE|comoLer|porque):\s*"([^"]*)"', corpo)
        if not campos:
            continue
        total = sum(len(v) for _, v in campos)
        if total > 300:
            longas.append(f"{codigo} ({total} chars)")
    checar("todas as explicacoes cabem em 300 caracteres", not longas, str(longas[:5]))

    frases_longas = []
    for codigo, corpo in blocos:
        for nome, valor in re.findall(r'(oQueE|comoLer|porque):\s*"([^"]*)"', corpo):
            if len(valor.split()) > 20:
                frases_longas.append(f"{codigo}.{nome}")
    checar("nenhuma frase passa de 20 palavras", not frases_longas, str(frases_longas[:5]))

    siglas = []
    for codigo, corpo in blocos:
        for nome, valor in re.findall(r'(oQueE|comoLer|porque):\s*"([^"]*)"', corpo):
            for sigla, significado in SIGLAS_PROIBIDAS.items():
                if re.search(rf"\b{sigla}\b", valor):
                    siglas.append(f"{codigo}.{nome} usa {sigla}")
    checar("nenhuma sigla sem explicar", not siglas, str(siglas[:5]))

    # --- cada K/G tem nome amigavel ---
    print("== nomes amigaveis ==")
    sem_nome = [
        codigo
        for codigo, corpo in blocos
        if codigo.startswith(("K-", "G-")) and not re.search(r'\bnome:\s*"', corpo)
    ]
    checar("todo KPI e grafico tem nome amigavel", not sem_nome, str(sem_nome[:8]))

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
