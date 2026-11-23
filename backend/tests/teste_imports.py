"""Teste de import: garante que todo script referencia modulos locais existentes.

Reproduz o achado A4 (core/quota.py ausente no ValorPublico) sem executar os
scripts e sem exigir as dependencias de terceiros instaladas.

Uso: python backend/tests/teste_imports.py
"""
import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SCRIPTS = BACKEND / "scripts"

# Pacotes internos do backend (qualquer import com estes prefixos precisa existir).
PREFIXOS_LOCAIS = {
    "config", "core", "processing", "scraper", "storage", "scripts", "utils",
}

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


def resolve(nome: str) -> bool:
    """True se o modulo (ou pacote) `nome` existe dentro de backend/."""
    base = BACKEND
    for parte in nome.split("."):
        modulo = base / f"{parte}.py"
        pacote = base / parte
        if modulo.exists():
            base = base
            return True
        if (pacote / "__init__.py").exists():
            base = pacote
        else:
            return False
    return True


def imports_do_arquivo(caminho: Path):
    """Devolve os nomes de modulos importados, incluindo `from pkg import mod`."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"), filename=str(caminho))
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                nomes.add(alias.name)
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                continue
            if not no.module:
                continue
            nomes.add(no.module)
            for alias in no.names:
                if alias.name != "*":
                    nomes.add(f"{no.module}.{alias.name}")
    return nomes


def usa_sem_importar(caminho: Path, nome: str) -> bool:
    """True se `nome` e chamado mas nao foi importado (NameError em runtime)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"), filename=str(caminho))
    importado = any(
        isinstance(no, (ast.Import, ast.ImportFrom))
        and any(alias.name == nome or alias.asname == nome for alias in no.names)
        for no in ast.walk(arvore)
    )
    atribuido = any(
        isinstance(no, ast.Name) and no.id == nome and not isinstance(no.ctx, ast.Load)
        for no in ast.walk(arvore)
    )
    usado = any(
        isinstance(no, ast.Name) and no.id == nome and isinstance(no.ctx, ast.Load)
        for no in ast.walk(arvore)
    )
    return usado and not importado and not atribuido


print("== imports dos scripts ==")
arquivos = sorted(p for p in SCRIPTS.glob("*.py") if p.name != "__init__.py")
checa("scripts encontrados", len(arquivos) > 0, f"{len(arquivos)} arquivos")

faltando = {}
for caminho in arquivos:
    try:
        nomes = imports_do_arquivo(caminho)
    except SyntaxError as exc:
        faltando[caminho.name] = [f"SyntaxError: {exc.msg}"]
        continue
    ausentes = []
    for nome in sorted(nomes):
        raiz = nome.split(".")[0]
        if raiz in PREFIXOS_LOCAIS and not resolve(nome):
            ausentes.append(nome)
    if ausentes:
        faltando[caminho.name] = ausentes

checa(
    "todos os modulos locais importados existem",
    not faltando,
    "; ".join(f"{arq}: {', '.join(mods)}" for arq, mods in faltando.items()),
)

print("== simbolos usados sem import (NameError em runtime) ==")
simbolos = ("main_com_cota",)
sem_import = {}
for caminho in arquivos:
    ausentes = [s for s in simbolos if usa_sem_importar(caminho, s)]
    if ausentes:
        sem_import[caminho.name] = ausentes
checa(
    "main_com_cota sempre importado quando usado",
    not sem_import,
    "; ".join(f"{arq}: {', '.join(simb)}" for arq, simb in sem_import.items()),
)

print(f"\nRESULTADO: {ok} passaram, {len(falhas)} falharam")
sys.exit(1 if falhas else 0)
