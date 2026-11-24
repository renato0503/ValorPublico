"""Testes da classificacao de demandas (E5 / plano 13 A4-V5, plano 14 §2.4).

Cobre:
  - pedido verdadeiro por tema (saude, obras, transporte);
  - bairro reconhecido (Cuiabá/VG);
  - urgencia (alta/media/baixa);
  - elogio, spam e texto generico NAO entram como demanda;
  - agregacao por tema/bairro sem nome de cidadao.

Uso (a partir de `backend/`):
    python tests/teste_demandas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from cerra_nucleo.processing.demandas import (  # noqa: E402
    classificar_demanda,
    temais_de_demanda,
)
from cerra_nucleo.processing.bairros import bairros_conhecidos, detectar_bairro  # noqa: E402

PASSOU: list[str] = []
FALHOU: list[str] = []


def checar(desc: str, condicao: bool, extra: str = "") -> None:
    if condicao:
        PASSOU.append(desc)
        print(f"  PASS  {desc}")
    else:
        FALHOU.append(desc)
        print(f"  FAIL  {desc} {extra}")


def main() -> int:
    print("== pedidos por tema ==")

    saude = classificar_demanda(
        "Preciso com urgencia de atendimento na UPA do Jardim das Americas, "
        "o medico nao atende e a fila esta enorme"
    )
    checar("saude e demanda", saude["e_demanda"] is True, str(saude))
    checar("tema saude", saude["tema"] == "saude", saude["tema"])
    checar("bairro identificado", saude["bairro"] == "Jardim das Americas", str(saude["bairro"]))
    checar("urgencia alta", saude["urgencia"] == "alta", saude["urgencia"])
    checar("acao sugerida", bool(saude["acao_sugerida"]))

    obras = classificar_demanda(
        "O asfalto da rua esta cheio de buracos e a pavimentacao nunca foi feita no bairro Centro"
    )
    checar("obras e demanda", obras["e_demanda"] is True)
    checar("tema obras", obras["tema"] == "obras", obras["tema"])

    transporte = classificar_demanda(
        "O onibus passa a cada hora e o ponto de onibus do bairro Jequitibara nao tem cobertura"
    )
    checar("transporte e demanda", transporte["e_demanda"] is True)
    checar("tema transporte", transporte["tema"] == "transporte", transporte["tema"])
    checar("bairro VG", transporte["bairro"] == "Jequitibara", str(transporte["bairro"]))

    print("== nao demandas ==")
    elogio = classificar_demanda("Parabens pelo trabalho da equipe, continue assim sempre")
    checar("elogio nao e demanda", elogio["e_demanda"] is False, elogio["motivo"])

    spam = classificar_demanda("Clique aqui https://oferta.example.com e ganhe dinheiro agora mesmo")
    checar("spam nao e demanda", spam["e_demanda"] is False, spam["motivo"])

    curto = classificar_demanda("Bom dia!")
    checar("texto curto nao e demanda", curto["e_demanda"] is False, curto["motivo"])

    generico = classificar_demanda(
        "O vereador participou da sessao e falou sobre o orcamento do municipio nesta semana"
    )
    checar("noticia generica nao e demanda", generico["e_demanda"] is False, generico["motivo"])

    print("== bairros ==")
    checar("bairro com acento", detectar_bairro("rua do Jardim das Américas") == "Jardim das Americas")
    checar("bairro sem bairro", detectar_bairro("orcamento da camara municipal") is None)
    checar("lista de bairros nao vazia", len(bairros_conhecidos()) > 60, str(len(bairros_conhecidos())))

    print("== agregado ==")
    agregado = temais_de_demanda(
        [
            "Preciso de atendimento na UPA, a fila esta enorme e demora muito",
            "O asfalto da rua esta cheio de buracos e precisa de pavimentacao",
            "Parabens pelo trabalho, continue assim",
        ]
    )
    checar("agregado conta 2 demandas", agregado["total"] == 2, str(agregado["total"]))
    checar("agregado por tema", set(agregado["por_tema"]) >= {"saude", "obras"}, str(agregado["por_tema"]))
    checar("agregado sem nome de pessoa", all("@" not in k for k in agregado["por_tema"]))

    print()
    print(f"RESULTADO: {len(PASSOU)} passaram, {len(FALHOU)} falharam")
    if FALHOU:
        for item in FALHOU:
            print("  FALHOU:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
