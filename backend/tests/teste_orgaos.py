"""Testes do mapa canonico dos quatro orgaos (separacao das frentes).

Uso: python tests/teste_orgaos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orgaos import (  # noqa: E402
    POR_CASA_DOC,
    POR_CIDADE_DOC,
    info,
    orgao_da_casa,
    orgao_da_cidade,
    orgao_do_agente,
    orgao_do_escopo,
)

ok = 0
falhas = []


def checa(nome, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  PASS  {nome}")
    else:
        falhas.append(nome)
        print(f"  FAIL  {nome} {extra}")


print("== cidades -> orgao ==")
checa("Cuiaba", orgao_da_cidade("Cuiaba") == "cuiaba")
checa("Varzea Grande", orgao_da_cidade("Varzea Grande") == "varzea-grande")
checa("Mato Grosso", orgao_da_cidade("Mato Grosso") == "almt")
checa(
    "Governo de Mato Grosso",
    orgao_da_cidade("Governo de Mato Grosso") == "governo-mt",
)
checa("acento tolerado", orgao_da_cidade("Várzea Grande") == "varzea-grande")
checa("desconhecida", orgao_da_cidade("Rondonopolis") == "")

print("== casas -> orgao ==")
checa("Camara Cuiaba", orgao_da_casa("Camara Cuiaba") == "cuiaba")
checa("Camara VG", orgao_da_casa("Camara VG") == "varzea-grande")
checa("ALMT", orgao_da_casa("ALMT") == "almt")
checa("Governo MT", orgao_da_casa("Governo MT") == "governo-mt")

print("== agente (casa tem prioridade sobre cidade legada) ==")
checa(
    "agente com casa",
    orgao_do_agente({"cidade": "Mato Grosso", "casa": "ALMT"}) == "almt",
)
checa(
    "agente legado sem casa",
    orgao_do_agente({"cidade": "Cuiaba"}) == "cuiaba",
)
checa("agente vazio", orgao_do_agente({}) == "")

print("== escopos por id de documento ==")
checa("cidade-cuiaba", orgao_do_escopo("cidade-cuiaba") == "cuiaba")
checa("cidade-mato-grosso", orgao_do_escopo("cidade-mato-grosso") == "almt")
checa(
    "cidade-governo-de-mato-grosso",
    orgao_do_escopo("cidade-governo-de-mato-grosso") == "governo-mt",
)
checa("casa camara-vg", orgao_do_escopo("casa-camara-vg") == "varzea-grande")
checa("geral fica sem orgao", orgao_do_escopo("geral") == "")

print("== ids canonicos ==")
checa("cidade doc almt", POR_CIDADE_DOC["mato-grosso"] == "almt")
checa("casa doc governo", POR_CASA_DOC["governo-mt"] == "governo-mt")
checa("info orgao", info("almt")["casa"] == "ALMT")
checa("info desconhecido", info("x") == {})

print(f"\nRESULTADO: {ok} passaram, {len(falhas)} falharam")
sys.exit(1 if falhas else 0)
