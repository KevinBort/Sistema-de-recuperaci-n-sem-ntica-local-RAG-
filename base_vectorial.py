"""Acceso a la base vectorial (ChromaDB), compartido por la ingesta y la consulta."""

import chromadb
from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

import config


class EmbeddingsDistintos(Exception):
    """La base se creó con un modelo de embeddings distinto del que hay en el .env."""


def crear_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)


def _cliente() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(config.DIR_VECTORES))


def cantidad_indexada() -> int:
    """Cuántos fragmentos hay guardados (0 si la colección todavía no existe)."""
    try:
        return _cliente().get_collection(config.COLECCION).count()
    except NotFoundError:
        return 0


def modelo_de_la_base() -> str | None:
    """El modelo de embeddings con que se creó la colección (None si no existe)."""
    try:
        return (_cliente().get_collection(config.COLECCION).metadata or {}).get("embedding_model")
    except NotFoundError:
        return None


def borrar_coleccion() -> None:
    try:
        _cliente().delete_collection(config.COLECCION)
    except NotFoundError:
        pass


def abrir_base(embeddings=None) -> Chroma:
    """Abre (o crea) la colección. Se niega si los embeddings no coinciden.

    Indexar con un modelo y consultar con otro da resultados sin sentido,
    así que se comprueba antes de hacer nada.
    """
    guardado = modelo_de_la_base()
    if guardado is not None and guardado != config.EMBEDDING_MODEL:
        raise EmbeddingsDistintos(
            f"La base se creó con '{guardado}', pero el .env pide '{config.EMBEDDING_MODEL}'. "
            "Vuelve a indexar con: python ingest.py --rebuild"
        )
    return Chroma(
        client=_cliente(),
        collection_name=config.COLECCION,
        embedding_function=embeddings or crear_embeddings(),
        collection_configuration={"hnsw": {"space": "cosine"}},
        collection_metadata={"embedding_model": config.EMBEDDING_MODEL},
    )
