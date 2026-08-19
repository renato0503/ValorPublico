import re
import sys
from pathlib import Path
from unicodedata import normalize

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import COLLECTION_AGENTES
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

CARGO_MASCULINO = "Vereador"
CARGO_FEMININO = "Vereadora"

# (nome_urna, cidade, partido, genero, votos_2024)
# Cuiaba: 21ª legislatura (eleitos 20ª, posse 01/01/2024, mandato ate 31/01/2028).
# Votos nominais conforme lista oficial da Camara Municipal.
ROSTER = [
    # --- Camara Municipal de Cuiaba (27) ---
    ("Samantha Iris", "Cuiaba", "PL", "F", 7460),
    ("Maysa Leao", "Cuiaba", "Republicanos", "F", 5615),
    ("Alex Rodrigues", "Cuiaba", "PV", "M", 5556),
    ("Paula Calil", "Cuiaba", "PL", "F", 5460),
    ("Cezinha Nascimento", "Cuiaba", "Uniao Brasil", "M", 4733),
    ("Ilde Taques", "Cuiaba", "PSB", "M", 4731),
    ("Michellly Alencar", "Cuiaba", "Uniao Brasil", "F", 4514),
    ("Maria Avalone", "Cuiaba", "PSDB", "F", 4347),
    ("Marcrean Santos", "Cuiaba", "MDB", "M", 3685),
    ("Tenente Coronel Dias", "Cuiaba", "Cidadania", "M", 3659),
    ("Dra. Mara", "Cuiaba", "Podemos", "F", 3500),
    ("Adevair Cabral", "Cuiaba", "Solidariedade", "M", 3481),
    ("Dilemario Alencar", "Cuiaba", "Uniao Brasil", "M", 3370),
    ("Rafael Ranalli", "Cuiaba", "PL", "M", 3360),
    ("Eduardo Magalhaes", "Cuiaba", "Republicanos", "M", 3274),
    ("Kassio Coelho", "Cuiaba", "Podemos", "M", 3262),
    ("Demilson Nogueira", "Cuiaba", "Progressistas", "M", 3211),
    ("Didimo Vovo", "Cuiaba", "PSB", "M", 3137),
    ("Chico 2000", "Cuiaba", "PL", "M", 3098),
    ("Sargento Joelson", "Cuiaba", "PSB", "M", 2945),
    ("Baixinha Giraldelli", "Cuiaba", "Solidariedade", "F", 2843),
    ("Katiuscia Manteli", "Cuiaba", "PSB", "F", 2785),
    ("Mario Nadaf", "Cuiaba", "PV", "M", 2747),
    ("Marcus Brito Junior", "Cuiaba", "PV", "M", 2558),
    ("Daniel Monteiro", "Cuiaba", "Republicanos", "M", 2537),
    ("Jeferson Siqueira", "Cuiaba", "PSD", "M", 2468),
    ("Wilson Quero Quero", "Cuiaba", "PMB", "M", 1964),
    # --- Camara Municipal de Varzea Grande (23) ---
    # votos_2024 = 0 (lista oficial nao fornecida ainda)
    ("Adilsinho", "Varzea Grande", "Republicanos", "M", 0),
    ("Alessandro Moreira", "Varzea Grande", "MDB", "M", 0),
    ("Braz Jaciro", "Varzea Grande", "PSDB", "M", 0),
    ("Bruno Rios", "Varzea Grande", "PL", "M", 0),
    ("Caio Cordeiro", "Varzea Grande", "Partido Novo", "M", 0),
    ("Carlinhos Figueiredo", "Varzea Grande", "Republicanos", "M", 0),
    ("Charles da Educacao", "Varzea Grande", "Uniao", "M", 0),
    ("Cilcinho", "Varzea Grande", "PV", "M", 0),
    ("Cleyton Nassarden", "Varzea Grande", "MDB", "M", 0),
    ("Enfermeiro Emerson", "Varzea Grande", "PP", "M", 0),
    ("Feitoza", "Varzea Grande", "PSB", "M", 0),
    ("Sargento Galibert", "Varzea Grande", "PSB", "M", 0),
    ("Gisa Barros", "Varzea Grande", "Podemos", "F", 0),
    ("Janio Calistro", "Varzea Grande", "Uniao", "M", 0),
    ("Jero Neto", "Varzea Grande", "MDB", "M", 0),
    ("Lucelia Oliveira", "Varzea Grande", "AGIR", "F", 0),
    ("Dr. Miguel Junior", "Varzea Grande", "Cidadania", "M", 0),
    ("Lucas Chapeu do Sol", "Varzea Grande", "PL", "M", 0),
    ("Rosy Prado", "Varzea Grande", "UB", "F", 0),
    ("Raul Curvo", "Varzea Grande", "Republicanos", "M", 0),
    ("Wanderley Cerqueira", "Varzea Grande", "MDB", "M", 0),
    ("Wender Madureira", "Varzea Grande", "Republicanos", "M", 0),
    ("Joaquim Antunes de Souza", "Varzea Grande", "Sem Partido", "M", 0),
]

AGENTES_ESPERADOS = {"Cuiaba": 27, "Varzea Grande": 23}
LEGISLATURA = "21ª (2024-2028)"


def _sem_acento(texto: str) -> str:
    return normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")


def _normalizar_partido(partido: str) -> str:
    p = partido.strip()
    if p.isupper() and len(p) > 4:
        return p.title()
    return p


def gerar_termos_de_busca(nome_urna: str, cargo: str, partido: str) -> list[str]:
    """Gera variacoes de busca: nome, cargo+nome, nome+partido, cargo+nome+partido.

    Cada variacao e gerada com e sem acentos, tudo em minusculas, para
    maximizar o match em textos brutos de postagens e comentarios.
    """
    nome = nome_urna.lower()
    cargo_limpo = cargo.lower()
    partido_norm = _normalizar_partido(partido).lower()

    variantes = {nome, _sem_acento(nome)}
    termos: set[str] = set()
    for nome_v in variantes:
        termos.add(nome_v)
        termos.add(f"{cargo_limpo} {nome_v}")
        for partido_v in {partido_norm, _sem_acento(partido_norm)}:
            termos.add(f"{nome_v} {partido_v}")
            termos.add(f"{cargo_limpo} {nome_v} {partido_v}")
    return sorted(termos)


def slugify(value: str) -> str:
    value = _sem_acento(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def montar_documento(nome_urna: str, cidade: str, partido: str, genero: str, votos_2024: int) -> dict:
    cargo = CARGO_FEMININO if genero.upper() == "F" else CARGO_MASCULINO
    partido_norm = _normalizar_partido(partido)
    return {
        "nome_urna": nome_urna,
        "cidade": cidade,
        "partido": partido_norm,
        "cargo": cargo,
        "genero": genero.upper(),
        "votos_2024": int(votos_2024 or 0),
        "legislatura": LEGISLATURA,
        "mandato_ate": "2028-01-31",
        "termos_de_busca": gerar_termos_de_busca(nome_urna, cargo, partido_norm),
    }


def validar_escopo() -> None:
    contagem: dict[str, int] = {}
    for _, cidade, *_ in ROSTER:
        contagem[cidade] = contagem.get(cidade, 0) + 1
    for cidade, esperado in AGENTES_ESPERADOS.items():
        atual = contagem.get(cidade, 0)
        if atual != esperado:
            raise ValueError(
                f"Cobertura invalida em {cidade}: {atual} cadastrados, esperado {esperado}"
            )
    logger.info("Escopo validado: %d Cuiaba + %d Varzea Grande = %d agentes.",
                contagem.get("Cuiaba", 0), contagem.get("Varzea Grande", 0),
                len(ROSTER))


def _remover_orfanos(db, ids_validos: set[str]) -> None:
    """Remove documentos de Cuiaba/VG que nao estao mais no roster (nomes antigos)."""
    existentes = list(db.collection(COLLECTION_AGENTES).stream())
    removidos = 0
    for doc in existentes:
        if doc.id not in ids_validos:
            doc.reference.delete()
            removidos += 1
            logger.info("Removido orfao: %s (%s)", doc.id, doc.to_dict().get("nome_urna"))
    if removidos:
        logger.info("Total de documentos orfaos removidos: %d", removidos)


def main() -> None:
    db = init_firebase()
    validar_escopo()
    ids_validos: set[str] = set()
    for nome_urna, cidade, partido, genero, votos in ROSTER:
        doc = montar_documento(nome_urna, cidade, partido, genero, votos)
        doc_id = slugify(nome_urna)
        ids_validos.add(doc_id)
        db.collection(COLLECTION_AGENTES).document(doc_id).set(doc, merge=True)
        logger.info("Gravado: %s (%s, %s) - id=%s",
                    doc["nome_urna"], doc["cidade"], doc["partido"], doc_id)
    _remover_orfanos(db, ids_validos)
    logger.info("Seed concluido: %d documentos em '%s'.", len(ROSTER), COLLECTION_AGENTES)


if __name__ == "__main__":
    main()