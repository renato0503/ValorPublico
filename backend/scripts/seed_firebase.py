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

# (nome_urna, cidade, partido, genero)
ROSTER = [
    # --- Camara Municipal de Cuiaba (27) ---
    ("Samantha Iris", "Cuiaba", "PL", "F"),
    ("Maysa Leao", "Cuiaba", "Republicanos", "F"),
    ("Alex Rodrigues", "Cuiaba", "PV", "M"),
    ("Paula Calil", "Cuiaba", "PL", "F"),
    ("Cezinha Nascimento", "Cuiaba", "Uniao", "M"),
    ("Ilde Taques", "Cuiaba", "PSB", "M"),
    ("Michellly Alencar", "Cuiaba", "Uniao", "F"),
    ("Maria Avalone", "Cuiaba", "PSDB", "F"),
    ("Marcrean Santos", "Cuiaba", "MDB", "M"),
    ("T. Coronel Dias", "Cuiaba", "Cidadania", "M"),
    ("Dra Mara", "Cuiaba", "Pode", "F"),
    ("Adevair Cabral", "Cuiaba", "Solidariedade", "M"),
    ("Dilemario Alencar", "Cuiaba", "Uniao", "M"),
    ("Policial Federal Rafael Ranalli", "Cuiaba", "PL", "M"),
    ("Eduardo Magalhaes", "Cuiaba", "Republicanos", "M"),
    ("Kassio Coelho", "Cuiaba", "Pode", "M"),
    ("Demilson Nogueira", "Cuiaba", "PP", "M"),
    ("Didimo Vovo", "Cuiaba", "PSB", "M"),
    ("Chico 2000", "Cuiaba", "PL", "M"),
    ("Sargento Joelson", "Cuiaba", "PSB", "M"),
    ("Baixinha Giraldelli", "Cuiaba", "Solidariedade", "F"),
    ("Katiuscia", "Cuiaba", "PSB", "F"),
    ("Mario Nadaf", "Cuiaba", "PV", "M"),
    ("Marcus Brito Jr", "Cuiaba", "PV", "M"),
    ("Daniel Monteiro", "Cuiaba", "Republicanos", "M"),
    ("Jefferson Siqueira", "Cuiaba", "PSD", "M"),
    ("Wilson Kero Kero", "Cuiaba", "PMB", "M"),
    # --- Camara Municipal de Varzea Grande (23) ---
    ("Adilsinho", "Varzea Grande", "Republicanos", "M"),
    ("Alessandro Moreira", "Varzea Grande", "MDB", "M"),
    ("Braz Jaciro", "Varzea Grande", "PSDB", "M"),
    ("Bruno Rios", "Varzea Grande", "PL", "M"),
    ("Caio Cordeiro", "Varzea Grande", "Partido Novo", "M"),
    ("Carlinhos Figueiredo", "Varzea Grande", "Republicanos", "M"),
    ("Charles da Educacao", "Varzea Grande", "Uniao", "M"),
    ("Cilcinho", "Varzea Grande", "PV", "M"),
    ("Cleyton Nassarden", "Varzea Grande", "MDB", "M"),
    ("Enfermeiro Emerson", "Varzea Grande", "PP", "M"),
    ("Feitoza", "Varzea Grande", "PSB", "M"),
    ("Sargento Galibert", "Varzea Grande", "PSB", "M"),
    ("Gisa Barros", "Varzea Grande", "Podemos", "F"),
    ("Janio Calistro", "Varzea Grande", "Uniao", "M"),
    ("Jero Neto", "Varzea Grande", "MDB", "M"),
    ("Lucelia Oliveira", "Varzea Grande", "AGIR", "F"),
    ("Dr. Miguel Junior", "Varzea Grande", "Cidadania", "M"),
    ("Lucas Chapeu do Sol", "Varzea Grande", "PL", "M"),
    ("Rosy Prado", "Varzea Grande", "UB", "F"),
    ("Raul Curvo", "Varzea Grande", "Republicanos", "M"),
    ("Wanderley Cerqueira", "Varzea Grande", "MDB", "M"),
    ("Wender Madureira", "Varzea Grande", "Republicanos", "M"),
    ("Joaquim Antunes de Souza", "Varzea Grande", "Sem Partido", "M"),
]

AGENTES_ESPERADOS = {"Cuiaba": 27, "Varzea Grande": 23}


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


def montar_documento(nome_urna: str, cidade: str, partido: str, genero: str) -> dict:
    cargo = CARGO_FEMININO if genero.upper() == "F" else CARGO_MASCULINO
    partido_norm = _normalizar_partido(partido)
    return {
        "nome_urna": nome_urna,
        "cidade": cidade,
        "partido": partido_norm,
        "cargo": cargo,
        "genero": genero.upper(),
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


def main() -> None:
    db = init_firebase()
    validar_escopo()
    for nome_urna, cidade, partido, genero in ROSTER:
        doc = montar_documento(nome_urna, cidade, partido, genero)
        doc_id = slugify(nome_urna)
        db.collection(COLLECTION_AGENTES).document(doc_id).set(doc, merge=True)
        logger.info("Gravado: %s (%s, %s) - id=%s",
                    doc["nome_urna"], doc["cidade"], doc["partido"], doc_id)
    logger.info("Seed concluido: %d documentos em '%s'.", len(ROSTER), COLLECTION_AGENTES)


if __name__ == "__main__":
    main()