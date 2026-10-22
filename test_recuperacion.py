"""Prueba la recuperación SIN Ollama: embeddings simulados y una carpeta temporal."""

import asyncio
import hashlib
import re
import sys
import tempfile
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

import base_vectorial
import config
import ingest
import recuperacion

resultados = []


def comprobar(descripcion: str, condicion: bool) -> None:
    resultados.append(condicion)
    print(f"  [{'OK' if condicion else 'FALLA'}] {descripcion}")


def lanza(excepcion, funcion) -> bool:
    try:
        funcion()
    except excepcion:
        return True
    except Exception:
        return False
    return False


class EmbeddingsSimulados(Embeddings):
    """Bolsa de palabras con hash: textos con palabras en común quedan cerca."""

    retraso_consulta = 0.0  # segundos que tarda embed_query (para probar que no bloquea)

    def _vector(self, texto: str) -> list[float]:
        v = [0.0] * 64
        for palabra in re.findall(r"\w+", texto.lower()):
            v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % 64] += 1.0
        return v

    def embed_documents(self, textos):
        return [self._vector(t) for t in textos]

    def embed_query(self, texto):
        time.sleep(self.retraso_consulta)
        return self._vector(texto)


config.DIR_VECTORES = Path(tempfile.mkdtemp()) / "vectorstore"
config.COLECCION = "prueba"
config.EMBEDDING_MODEL = "modelo-A"
emb = EmbeddingsSimulados()

textos = [
    ("a.md", "el puerto 7710 recibe las conexiones de los clientes con cifrado TLS"),
    ("a.md", "el puerto 7711 es para la administración y el panel web"),
    ("b.md", "los snapshots se toman cada seis horas y se conservan catorce días"),
    ("b.md", "la retención por defecto de los mensajes es de setenta y dos horas"),
    ("c.md", "el error de cuota excedida ocurre cuando el productor escribe demasiado rápido"),
    ("c.md", "el error de almacenamiento lleno ocurre cuando el disco supera el noventa y cinco por ciento"),
]
muestra = [Document(page_content=t, metadata={"archivo": a, "fragmento": n, "id": f"{a}::{n}"})
           for n, (a, t) in enumerate(textos, 1)]

print("Base vacía")
comprobar("sin indexar, recuperar avisa con BaseVacia",
          lanza(recuperacion.BaseVacia, lambda: recuperacion.recuperar("puerto", embeddings=emb)))
ingest.indexar(muestra, emb)

print("\nRecuperación")
res = recuperacion.recuperar("¿qué puerto usan los clientes?", k=3, embeddings=emb)
comprobar("devuelve k fragmentos", len(res) == 3)
comprobar("el más parecido es el que habla del puerto de los clientes", "7710" in res[0].texto)
comprobar("están ordenados del más parecido al menos parecido",
          [r.distancia for r in res] == sorted(r.distancia for r in res))
comprobar("cada fragmento trae archivo, número, texto y distancia",
          all(r.archivo and r.numero >= 1 and r.texto and r.distancia >= 0 for r in res))
comprobar("pedir más fragmentos de los que hay devuelve solo los existentes",
          len(recuperacion.recuperar("puerto", k=config.K_MAXIMO, embeddings=emb)) == len(muestra))

print("\nValidaciones")
comprobar("consulta vacía se rechaza", lanza(ValueError, lambda: recuperacion.recuperar("   ", embeddings=emb)))
comprobar("k = 0 se rechaza", lanza(ValueError, lambda: recuperacion.recuperar("puerto", k=0, embeddings=emb)))
comprobar(f"k mayor que {config.K_MAXIMO} se rechaza",
          lanza(ValueError, lambda: recuperacion.recuperar("puerto", k=config.K_MAXIMO + 1, embeddings=emb)))
config.EMBEDDING_MODEL = "modelo-B"
comprobar("si el .env cambió de modelo de embeddings, se niega a buscar",
          lanza(base_vectorial.EmbeddingsDistintos, lambda: recuperacion.recuperar("puerto", embeddings=emb)))
config.EMBEDDING_MODEL = "modelo-A"

print("\nVersión asíncrona")
asincrono = asyncio.run(recuperacion.arecuperar("¿qué puerto usan los clientes?", k=3, embeddings=emb))
comprobar("da el mismo resultado que la versión normal", asincrono == res)


async def medir_bloqueo() -> tuple[int, float]:
    """Mientras una búsqueda lenta corre, ¿sigue funcionando el resto del programa?"""
    emb.retraso_consulta = 0.5
    latidos = 0

    async def reloj():
        nonlocal latidos
        while True:
            await asyncio.sleep(0.05)
            latidos += 1

    tarea = asyncio.create_task(reloj())
    inicio = time.perf_counter()
    await recuperacion.arecuperar("puerto", k=2, embeddings=emb)
    duracion = time.perf_counter() - inicio
    tarea.cancel()
    return latidos, duracion


latidos, duracion = asyncio.run(medir_bloqueo())
comprobar(f"una búsqueda de {duracion:.1f} s no bloquea el programa ({latidos} latidos del reloj en ese tiempo)",
          latidos >= 6)


async def en_paralelo() -> float:
    emb.retraso_consulta = 0.4
    inicio = time.perf_counter()
    await asyncio.gather(*(recuperacion.arecuperar(c, k=2, embeddings=emb)
                           for c in ["puerto clientes", "snapshots horas", "error cuota"]))
    return time.perf_counter() - inicio


tiempo = asyncio.run(en_paralelo())
comprobar(f"3 consultas lentas a la vez tardan {tiempo:.1f} s, no los 1,2 s de hacerlas una tras otra", tiempo < 1.0)

print(f"\n{sum(resultados)} de {len(resultados)} comprobaciones superadas")
sys.exit(0 if all(resultados) else 1)
