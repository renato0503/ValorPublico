"""Testes do saneamento da base do Governo e do corpus do IRaMuTeQ (plano 22, S0)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cerra_nucleo.processing import corpus_iramuteq as corpus  # noqa: E402
from cerra_nucleo.processing import reinert  # noqa: E402
from processing.governo_filtros import limpar_texto, sanear_itens, titulo_so_de_ms, veiculo_fora_de_mt  # noqa: E402

falhas = []


def checar(nome, condicao):
    print(("  PASS  " if condicao else "  FALHOU  ") + nome)
    if not condicao:
        falhas.append(nome)


print("== veiculos de fora de MT ==")
checar("Assembleia de MS", veiculo_fora_de_mt("Assembleia Legislativa de Mato Grosso do Sul"))
checar("sigla MS isolada", veiculo_fora_de_mt("Investiga MS"))
checar("Campo Grande", veiculo_fora_de_mt("Campo Grande News"))
checar("Fatos de MT fica", not veiculo_fora_de_mt("Fatos de Mato Grosso"))
checar("Secom MT fica", not veiculo_fora_de_mt("Secom MT"))
checar("G1 fica", not veiculo_fora_de_mt("G1"))

checar("Capital News (MS)", veiculo_fora_de_mt("Capital News"))
checar("Midiamax (MS)", veiculo_fora_de_mt("Midiamax"))
checar("titulo so de MS sai", titulo_so_de_ms("Estado destina R$ 100 milhões para rodovias de Mato Grosso do Sul"))
checar("MT e MS fica", not titulo_so_de_ms("MT e MS divergem sobre ponte no Pantanal"))
checar("Pivetta com MS fica", not titulo_so_de_ms("Pivetta e governador de Mato Grosso do Sul assinam acordo"))
checar("titulo de MT fica", not titulo_so_de_ms("Governo de MT anuncia obra em Cuiabá"))

print("== entidades HTML ==")
checar("nbsp escapado duas vezes", limpar_texto("Governo&amp;nbsp;anuncia") == "Governo anuncia")
checar("sobra nbsp;", limpar_texto("obra nbsp; nova") == "obra nova")
checar("acento", limpar_texto("Cuiab&aacute;") == "Cuiabá")
validos, removidos = sanear_itens([
    {"titulo": "A&nbsp;B", "veiculo": "G1"},
    {"titulo": "x", "veiculo": "TCE-MS"},
])
checar("sanear separa e limpa", len(validos) == 1 and len(removidos) == 1 and validos[0]["titulo"] == "A B")

print("== corpus ==")
checar("titulo repetido", corpus._sem_repeticao("a b c d e f a b c d e f g") == "a b c d e f g")
checar(
    "copia truncada com ponto",
    corpus._sem_repeticao("um dois tres quatro cinco seis . um dois tres quatro cinco se")
    == "um dois tres quatro cinco seis",
)
checar("texto normal intacto", corpus._sem_repeticao("texto normal sem repeticao nenhuma aqui") == "texto normal sem repeticao nenhuma aqui")
checar(
    "tira o veiculo",
    corpus._sem_veiculo("Obra nova em Cuiaba - Fatos de Mato Grosso", "Fatos de Mato Grosso") == "Obra nova em Cuiaba",
)
checar("corpus sem nbsp", "nbsp" not in corpus.limpar_texto("x &amp;nbsp;&nbsp; y nbsp; z"))

print("== stopwords da CHD ==")
vazias = reinert.stopwords_pt()
for palavra in ("de", "nao", "não", "nbsp", "mato", "grosso", "governo"):
    checar(f"'{palavra}' e vazia", palavra in vazias)

print("== chi2 so com formas super-representadas ==")
bruto = {
    "formas": ["saude", "escola", "comum"],
    # 4 segmentos: 2 da classe 1 (saude), 2 da classe 2 (escola); "comum" em todos
    "matriz": [[1, 0, 1], [1, 0, 1], [0, 1, 1], [0, 1, 1]],
    "classes": [1, 1, 2, "NA"],
}
res = reinert._montar_resultado(bruto)
por_id = {c["id"]: [f["f"] for f in c["formas"]] for c in res["classes"]}
checar("NA fica de fora", set(por_id) == {1, 2})
checar("classe 1 = saude", por_id.get(1, [None])[0] == "saude")
checar("classe 1 sem escola", "escola" not in por_id.get(1, []))

print(f"\nRESULTADO: {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
