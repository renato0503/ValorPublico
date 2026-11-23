"""Tratamento de cota do Firestore (free tier tem limite diario de leitura/escrita).

Quando a cota do dia estoura (HTTP 429 / ResourceExhausted), o comportamento
correto nao e fatal: a rotina deve terminar de forma limpa e ser reexecutada no
ciclo seguinte. O codigo de saida 75 (EX_TEMPFAIL) sinaliza "tente de novo
depois" para o agendador.
"""

import functools
import sys

from core.logger import get_logger

logger = get_logger(__name__)

EXIT_COTA = 75


def _e_cota(exc: Exception) -> bool:
    texto = str(exc).lower()
    return "quota exceeded" in texto or "resource_exhausted" in texto or "429" in texto


def tolerar_cota(nome_operacao: str = "operacao"):
    """Decorator: converte erro de cota em saida limpa (codigo 75)."""

    def _decorador(funcao):
        @functools.wraps(funcao)
        def _wrapper(*args, **kwargs):
            try:
                return funcao(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                if _e_cota(e):
                    logger.warning(
                        "Cota do Firestore esgotada em %s. Encerrando para "
                        "retentar no proximo ciclo (saida %d).",
                        nome_operacao, EXIT_COTA,
                    )
                    sys.exit(EXIT_COTA)
                raise

        return _wrapper

    return _decorador


def main_com_cota(funcao, nome: str = "rotina") -> None:
    """Executa `funcao` convertendo erro de cota em saida limpa."""
    try:
        funcao()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        if _e_cota(e):
            logger.warning(
                "Cota do Firestore esgotada em %s. Encerrando para retentar "
                "no proximo ciclo (saida %d).", nome, EXIT_COTA,
            )
            sys.exit(EXIT_COTA)
        raise
