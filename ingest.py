"""Ingesta: lee data/, parte los documentos en chunks de ~500 tokens y los guarda en ChromaDB.

Uso:
    python ingest.py             # indexa; si la base ya existe, no hace nada
    python ingest.py --rebuild   # borra la base y vuelve a indexar todo
"""

import argparse
import statistics
from pathlib import Path

import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from base_vectorial import abrir_base, borrar_coleccion, cantidad_indexada


def cargar_documentos(carpeta: Path) -> list[Document]:
    """Lee cada .md y .txt de la carpeta como un Document con su nombre de archivo."""
    documentos = []
    for ruta in sorted([*carpeta.glob("*.md"), *carpeta.glob("*.txt")]):
        texto = ruta.read_text(encoding="utf-8").strip()
        documentos.append(Document(page_content=texto, metadata={"archivo": ruta.name}))
    return documentos


def crear_splitter() -> RecursiveCharacterTextSplitter:
    """Junta párrafos hasta ~500 tokens; solo corta una frase si un párrafo no cabe."""
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=config.TOKENIZADOR,  # sin esto usaría un tokenizador antiguo (gpt2)
        chunk_size=config.CHUNK_TOKENS,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=config.SEPARADORES,
    )


def partir(documentos: list[Document], splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    """Parte cada documento y numera sus fragmentos: 'archivo.md::3' es el tercero de ese archivo."""
    fragmentos = []
    for documento in documentos:
        for numero, parte in enumerate(splitter.split_documents([documento]), start=1):
            parte.metadata["fragmento"] = numero
            parte.metadata["id"] = f"{parte.metadata['archivo']}::{numero}"
            fragmentos.append(parte)
    return fragmentos


def hay_solapamiento(anterior: str, siguiente: str, minimo: int = 15) -> bool:
    """True si el final del chunk anterior se repite al principio del siguiente."""
    for largo in range(min(len(anterior), len(siguiente)), minimo - 1, -1):
        if siguiente.startswith(anterior[-largo:]):
            return True
    return False


def contar_solapamientos(fragmentos: list[Document]) -> tuple[int, int]:
    """Devuelve (fronteras con solapamiento, fronteras totales), dentro de cada archivo."""
    con_solape = total = 0
    for anterior, siguiente in zip(fragmentos, fragmentos[1:]):
        if anterior.metadata["archivo"] == siguiente.metadata["archivo"]:
            total += 1
            con_solape += hay_solapamiento(anterior.page_content, siguiente.page_content)
    return con_solape, total


def mostrar_estadisticas(fragmentos: list[Document]) -> None:
    """Muestra cuántos tokens tiene cada chunk, para comprobar el tamaño pedido."""
    codificador = tiktoken.get_encoding(config.TOKENIZADOR)
    por_archivo: dict[str, list[int]] = {}
    for f in fragmentos:
        por_archivo.setdefault(f.metadata["archivo"], []).append(len(codificador.encode(f.page_content)))
    print(f"\n{'archivo':42} {'chunks':>6} {'mín':>5} {'media':>6} {'máx':>5}   (tokens por chunk)")
    for archivo, tokens in por_archivo.items():
        print(f"{archivo:42} {len(tokens):6} {min(tokens):5} {statistics.mean(tokens):6.0f} {max(tokens):5}")
    todos = [t for lista in por_archivo.values() for t in lista]
    print(f"{'TOTAL':42} {len(todos):6} {min(todos):5} {statistics.mean(todos):6.0f} {max(todos):5}")
    con_solape, fronteras = contar_solapamientos(fragmentos)
    print(f"\nFronteras entre chunks con solapamiento: {con_solape} de {fronteras}")


def indexar(fragmentos: list[Document], embeddings=None) -> int:
    """Guarda los fragmentos en Chroma. Con IDs fijos, repetir la operación no duplica nada."""
    base = abrir_base(embeddings)
    base.add_documents(fragmentos, ids=[f.metadata["id"] for f in fragmentos])
    return cantidad_indexada()


def main() -> None:
    lector = argparse.ArgumentParser(description="Indexa los documentos de data/ en ChromaDB")
    lector.add_argument("--rebuild", action="store_true", help="borra la base y vuelve a indexar todo")
    argumentos = lector.parse_args()
    config.exigir_config()

    if argumentos.rebuild:
        borrar_coleccion()
        print("Base borrada: se indexará desde cero.")

    existentes = cantidad_indexada()
    if existentes > 0:
        print(f"La base ya tiene {existentes} fragmentos: no se vuelve a indexar.")
        print("(Si cambiaste los documentos o el modelo de embeddings: python ingest.py --rebuild)")
        return

    documentos = cargar_documentos(config.DIR_DATOS)
    if not documentos:
        raise SystemExit(f"ERROR: no hay archivos .md ni .txt en {config.DIR_DATOS}")
    print(f"Documentos leídos: {len(documentos)}")

    fragmentos = partir(documentos, crear_splitter())
    mostrar_estadisticas(fragmentos)

    print(f"\nGenerando embeddings con {config.EMBEDDING_MODEL} (puede tardar un poco)...", flush=True)
    total = indexar(fragmentos)
    print(f"Listo: {total} fragmentos guardados en {config.DIR_VECTORES.name}/")


if __name__ == "__main__":
    main()
