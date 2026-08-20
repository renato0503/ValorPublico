"""Classificacao de temas/assuntos por clipping (estilo "Categorias" da DSM).

Cada clipping pode receber um ou mais temas a partir de regras de palavras-chave
aplicadas sobre o `texto_limpo` (e o veiculo). Os temas sao usados em:
  - filtros da pesquisa avancada (Relatorios);
  - distribuicao de temas no dashboard/analise;
  - exportacao CSV.

Temas conhecidos (curaveis por regra):
  Saude, Educacao, Seguranca, Urbanismo/Obras, Transporte, Meio Ambiente,
  Economia, Agricultura, Cultura/Esporte, Politica/Camara, Eleicoes, CPI,
  Justica, Social/Assistencia, Tecnologia, Governo/Administracao.
"""

import re
import unicodedata

_TEMAS_REGRA = {
    "Saude": ["saude", "sus", "hospital", "medico", "medica", "clinica", "uasf",
              "posto de saude", "upas", "vacina", "sindico", "odonto"],
    "Educacao": ["educacao", "escola", "professor", "professora", "aluno", "aluna",
                 "ensino", "universidade", "faculdade", "creche", "merenda", "bolsa escola"],
    "Seguranca": ["seguranca", "policia", "polical", "crime", "criminalidade", "violencia",
                  "ronda", "guardas", "guardia", "cftv", "monitoramento", "fronteira"],
    "Urbanismo/Obras": ["urbanismo", "obra", "obras", "asfalto", "buraco", "loteamento",
                        "calçada", "calcada", "pavimentacao", "praça", "praça",
                        "limpeza", "iluminacao", "poste"],
    "Transporte": ["transporte", "onibus", "mobilidade", "terminal", "btr", "trilho",
                   "corredor", "taxi", "aplicativo", "mtu", "transito"],
    "Meio Ambiente": ["meio ambiente", "ambiental", "sustentabilidade", "recilclagem",
                      "lixo", "residuos", "ar verde", "parque", "poluicao", "desmatamento"],
    "Economia": ["economia", "emprego", "salario", "empresa", "empresario", "comercio",
                 "imposto", "tributo", "orcamento", "fiscal", "inflacao", "investimento"],
    "Agricultura": ["agricultura", "agricultor", "rural", "pecuaria", "agronegocio",
                    "fazenda", "plantio", "colheita", "pmaf"],
    "Cultura/Esporte": ["cultura", "esporte", "evento", "festival", "shows", "show",
                        "musica", "futebol", "ginastica", "praça", "carnaval", "feira"],
    "Politica/Camara": ["camara", "vereador", "vereadora", "sessao", "plenario",
                        "lei", "projeto de lei", "emenda", "comissao", "frente",
                        "presidencia", "mesa diretora"],
    "Eleicoes": ["eleicao", "eleicoes", "candidato", "voto", "urna", "campanha",
                 "reeleicao", "pesquisa eleitoral", "coligacao", "partido"],
    "CPI": ["cpi", "comissao parlamentar", "depoimento", "investigacao", "tachamento",
            "requerimento", "quebra de sigilo", "comissao de inquérito"],
    "Justica": ["justica", "tribunal", "juiz", "juiza", "sentença", "sentenca", "promotor",
                "ministerio publico", "defensoria", "advogado", "acao judicial", "decisao"],
    "Social/Assistencia": ["assistencia", "social", "cras", "creas", "bolsa", "auxilio",
                           "beneficio", "fila", "vulnerabilidade", "idoso", "crianca",
                           "materno", "alimentacao"],
    "Tecnologia": ["tecnologia", "digital", "internet", "software", "app", "inteligencia",
                   "dados", "sistema", "inovacao"],
    "Governo/Administracao": ["governo", "prefeitura", "secretaria", "administracao",
                              "funcionario", "servidor", "concurso", "licitacao",
                              "contrato", "gestao", "servico publico"],
}


def _norm(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in t if not unicodedata.combining(c))


def classificar_temas(texto: str) -> list[str]:
    """Retorna a lista de temas detectados em um texto (ordenada por relevancia)."""
    t = _norm(texto)
    encontrados = []
    for tema, palavras in _TEMAS_REGRA.items():
        for p in palavras:
            if f" {_norm(p)} " in f" {t} ":
                encontrados.append(tema)
                break
    return encontrados


def aplicar_temas(clipping: dict) -> list[str]:
    """Classifica um clipping e retorna a lista de temas (mantem os existentes)."""
    texto = clipping.get("texto_limpo", "")
    temas = list(clipping.get("categorias") or [])
    for tema in classificar_temas(texto):
        if tema not in temas:
            temas.append(tema)
    return temas