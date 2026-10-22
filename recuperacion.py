"""Capa de recuperación: de una pregunta a los fragmentos más parecidos.

El camino es:  pregunta -> embedding (mismo modelo que en la ingesta) -> ChromaDB -> top_k fragmentos
"""

import asyncio

from pydantic import BaseModel, Field

import base_vectorial
import config


class BaseVacia(Exception):
    """No hay nada indexado: falta ejecutar la ingesta."""


class Fragmento(BaseModel):
    """Un fragmento recuperado, con lo necesario para citarlo."""

    archivo: str
    numero: int = Field(ge=1, description="número del fragmento dentro de su archivo")
    texto: str
    distancia: float = Field(description="distancia coseno: 0 = idéntico; cuanto mayor, menos parecido")


def recuperar(consulta: str, k: int | None = None, embeddings=None) -> list[Fragmento]:
    """Devuelve los k fragmentos más parecidos a la consulta, del más parecido al menos."""
    if not consulta.strip():
        raise ValueError("la consulta está vacía")
    k = config.TOP_K if k is None else k
    if not 1 <= k <= config.K_MAXIMO:
        raise ValueError(f"k debe estar entre 1 y {config.K_MAXIMO} (se recibió {k})")
    if base_vectorial.cantidad_indexada() == 0:
        raise BaseVacia("La base está vacía: ejecuta primero  python ingest.py")

    base = base_vectorial.abrir_base(embeddings)
    resultados = base.similarity_search_with_score(consulta, k=k)
    return [
        Fragmento(
            archivo=doc.metadata["archivo"],
            numero=doc.metadata["fragmento"],
            texto=doc.page_content,
            distancia=float(distancia),
        )
        for doc, distancia in resultados
    ]


async def arecuperar(consulta: str, k: int | None = None, embeddings=None) -> list[Fragmento]:
    """Versión asíncrona: la búsqueda corre en un hilo aparte para no bloquear el event loop."""
    return await asyncio.to_thread(recuperar, consulta, k, embeddings)
