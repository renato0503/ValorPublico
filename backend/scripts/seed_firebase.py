"""Popula o roster de agentes publicos (vereadores de Cuiaba/VG + deputados ALMT).

Le o roster de vereadores deste arquivo e os deputados estaduais de
``data/seeds/deputados_almt.json`` (fonte oficial: ALMT, ver o proprio JSON).

Regras de seguranca:
  * upsert com ``merge=True`` em lotes de 400 (nao apaga subcolecoes clippings);
  * ``--dry-run`` mostra o que seria gravado sem tocar no Firestore;
  * ``--apenas-almt`` grava somente os 24 deputados (nao mexe nos 50 vereadores);
  * orfaos so sao removidos com ``--remover-orfaos`` e nunca se tiverem clippings.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from unicodedata import normalize

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import BASE_DIR, COLLECTION_AGENTES
from core.firebase_client import init_firebase
from core.logger import get_logger

logger = get_logger(__name__)

CARGO_MASCULINO = "Vereador"
CARGO_FEMININO = "Vereadora"
CARGO_DEPUTADO = "Deputado Estadual"
CARGO_DEPUTADA = "Deputada Estadual"

CASA_POR_CIDADE = {
    "Cuiaba": "Camara Cuiaba",
    "Varzea Grande": "Camara VG",
}
ESFERA_POR_CIDADE = {
    "Cuiaba": "municipal",
    "Varzea Grande": "municipal",
}
LEGISLATURA_VEREADORES = "21ª (2024-2028)"
MANDATO_ATE_VEREADORES = "2028-01-31"

ARQUIVO_DEPUTADOS = BASE_DIR / "data" / "seeds" / "deputados_almt.json"

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

AGENTES_ESPERADOS = {"Cuiaba": 27, "Varzea Grande": 23, "Mato Grosso": 24}
LOTE = 400


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


def gerar_termos_deputado(nome_urna: str, cargo: str) -> list[str]:
    """Termos de busca especificos de deputado estadual (ALMT)."""
    base = gerar_termos_de_busca(nome_urna, cargo, "")
    nome = nome_urna.lower()
    variantes = {nome, _sem_acento(nome)}
    extras: set[str] = set()
    for n in variantes:
        cargo_sing = "deputada" if cargo.endswith("a") else "deputado"
        extras.add(f"{cargo_sing} {n}")
        extras.add(f"{n} almt")
        extras.add(f"{n} assembleia")
        extras.add(f"{n} assembleia legislativa")
        extras.add(f"{n} deputado estadual")
        extras.add(f"{n} deputada estadual")
    return sorted(set(base) | extras)


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
        "casa": CASA_POR_CIDADE.get(cidade, "Camara"),
        "esfera": ESFERA_POR_CIDADE.get(cidade, "municipal"),
        "partido": partido_norm,
        "cargo": cargo,
        "genero": genero.upper(),
        "votos_2024": int(votos_2024 or 0),
        "legislatura": LEGISLATURA_VEREADORES,
        "mandato_ate": MANDATO_ATE_VEREADORES,
        "termos_de_busca": gerar_termos_de_busca(nome_urna, cargo, partido_norm),
    }


def carregar_deputados() -> dict:
    if not ARQUIVO_DEPUTADOS.exists():
        raise FileNotFoundError(f"Seed de deputados ausente: {ARQUIVO_DEPUTADOS}")
    return json.loads(ARQUIVO_DEPUTADOS.read_text(encoding="utf-8"))


def montar_documento_deputado(dep: dict, meta: dict) -> tuple[str, dict]:
    nome = dep["nome_parlamentar"]
    genero = dep.get("genero", "M").upper()
    cargo = CARGO_DEPUTADA if genero == "F" else CARGO_DEPUTADO
    partido_norm = _normalizar_partido(dep.get("partido", ""))
    doc = {
        "nome_urna": nome,
        "nome_civil": dep.get("nome_urna") or nome,
        "cidade": meta["cidade"],
        "casa": meta["casa"],
        "esfera": meta["esfera"],
        "partido": partido_norm,
        "cargo": cargo,
        "genero": genero,
        "votos_2022": dep.get("votos_2022"),
        "situacao": dep.get("situacao", "em exercício"),
        "id_almt": dep.get("id_almt"),
        "perfil_url": dep.get("perfil_url"),
        "legislatura": meta["legislatura"],
        "mandato_ate": meta["mandato_ate"],
        "termos_de_busca": gerar_termos_deputado(nome, cargo),
    }
    return slugify(nome), doc


def montar_todos(apenas_almt: bool) -> list[tuple[str, dict]]:
    docs: list[tuple[str, dict]] = []
    if not apenas_almt:
        for nome_urna, cidade, partido, genero, votos in ROSTER:
            docs.append((slugify(nome_urna), montar_documento(nome_urna, cidade, partido, genero, votos)))
    dados = carregar_deputados()
    meta = {k: dados[k] for k in ("casa", "esfera", "cidade", "legislatura", "mandato_ate")}
    for dep in dados["deputados"]:
        docs.append(montar_documento_deputado(dep, meta))
    return docs


def validar_escopo(apenas_almt: bool) -> None:
    contagem: dict[str, int] = {}
    if not apenas_almt:
        for _, cidade, *_ in ROSTER:
            contagem[cidade] = contagem.get(cidade, 0) + 1
    dados = carregar_deputados()
    contagem["Mato Grosso"] = len(dados["deputados"])
    esperado = dict(AGENTES_ESPERADOS)
    if apenas_almt:
        esperado = {"Mato Grosso": 24}
    for cidade, alvo in esperado.items():
        atual = contagem.get(cidade, 0)
        if atual != alvo:
            raise ValueError(f"Cobertura invalida em {cidade}: {atual} cadastrados, esperado {alvo}")
    total = sum(contagem.values())
    logger.info("Escopo validado: %s = %d agentes.", contagem, total)


def upsert_em_lotes(db, docs: list[tuple[str, dict]]) -> None:
    colecao = db.collection(COLLECTION_AGENTES)
    lote = db.batch()
    n = 0
    for doc_id, dados in docs:
        lote.set(colecao.document(doc_id), dados, merge=True)
        n += 1
        if n % LOTE == 0:
            lote.commit()
            lote = db.batch()
            logger.info("Gravados %d documentos...", n)
    if n % LOTE:
        lote.commit()
    logger.info("Seed concluido: %d documentos gravados em '%s' (lotes de %d).", n, COLLECTION_AGENTES, LOTE)


def remover_orfaos(db, ids_validos: set[str], escopo: set[str]) -> None:
    """Remove apenas documentos do escopo que sumiram do roster E nao tem clippings."""
    removidos = 0
    for doc in db.collection(COLLECTION_AGENTES).stream():
        dados = doc.to_dict() or {}
        if dados.get("cidade") not in escopo:
            continue
        if doc.id in ids_validos:
            continue
        tem_clipping = next(doc.reference.collection("clippings").limit(1).stream(), None)
        if tem_clipping:
            logger.warning("Preservado %s (possui clippings).", doc.id)
            continue
        doc.reference.delete()
        removidos += 1
        logger.info("Removido orfao: %s (%s)", doc.id, dados.get("nome_urna"))
    logger.info("Orfaos removidos: %d", removidos)


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed do roster de agentes publicos.")
    ap.add_argument("--dry-run", action="store_true", help="nao grava; apenas valida e mostra a contagem")
    ap.add_argument("--apenas-almt", action="store_true", help="grava somente os 24 deputados da ALMT")
    ap.add_argument("--remover-orfaos", action="store_true", help="remove orfaos do escopo (sem clippings)")
    args = ap.parse_args()

    validar_escopo(args.apenas_almt)
    docs = montar_todos(args.apenas_almt)

    casas: dict[str, int] = {}
    for _, d in docs:
        casas[d["casa"]] = casas.get(d["casa"], 0) + 1
    logger.info("A gravar por casa: %s", casas)

    if args.dry_run:
        logger.info("[dry-run] %d documentos seriam gravados (merge=True, lotes de %d).", len(docs), LOTE)
        for doc_id, d in docs[:3] + docs[-2:]:
            logger.info("[dry-run] %s -> %s (%s, %s)", doc_id, d["nome_urna"], d["cargo"], d["partido"])
        return

    db = init_firebase()
    upsert_em_lotes(db, docs)
    if args.remover_orfaos:
        escopo = {d["cidade"] for _, d in docs}
        remover_orfaos(db, {doc_id for doc_id, _ in docs}, escopo)


if __name__ == "__main__":
    main()
