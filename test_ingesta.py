"""Prueba la ingesta SIN Ollama: usa embeddings simulados y una carpeta temporal.

No toca tu carpeta vectorstore/ ni gasta tiempo de modelo.
"""

import hashlib
import re
import sys
import tempfile
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import base_vectorial
import config
import ingest

resultados = []
omitidas = []


def comprobar(descripcion: str, condicion: bool) -> None:
    resultados.append(condicion)
    print(f"  [{'OK' if condicion else 'FALLA'}] {descripcion}")


class EmbeddingsSimulados(Embeddings):
    """Vectores de juguete: una bolsa de palabras con hash. Solo sirve para probar la mecánica."""

    def _vector(self, texto: str) -> list[float]:
        v = [0.0] * 64
        for palabra in re.findall(r"\w+", texto.lower()):
            v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % 64] += 1.0
        return v

    def embed_documents(self, textos):
        return [self._vector(t) for t in textos]

    def embed_query(self, texto):
        return self._vector(texto)


# Todo se prueba en una carpeta temporal, con un modelo de embeddings ficticio
config.DIR_VECTORES = Path(tempfile.mkdtemp()) / "vectorstore"
config.COLECCION = "prueba"
config.EMBEDDING_MODEL = "modelo-A"

print("Lectura de documentos")
documentos = ingest.cargar_documentos(config.DIR_DATOS)
comprobar(f"se leen los documentos de data/ ({len(documentos)} archivos)", len(documentos) >= 1)
comprobar("cada documento conoce su archivo", all(d.metadata.get("archivo") for d in documentos))

print("\nNumeración de fragmentos (con un divisor simple por caracteres)")
simple = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80)
fragmentos = ingest.partir(documentos, simple)
ids = [f.metadata["id"] for f in fragmentos]
comprobar(f"hay varios fragmentos ({len(fragmentos)})", len(fragmentos) > len(documentos))
comprobar("los IDs son únicos", len(set(ids)) == len(ids))
primero = documentos[0].metadata["archivo"]
comprobar("en cada archivo la numeración empieza en 1 y es consecutiva",
          [f.metadata["fragmento"] for f in fragmentos if f.metadata["archivo"] == primero]
          == list(range(1, sum(f.metadata["archivo"] == primero for f in fragmentos) + 1)))

print("\nTamaño de los chunks en TOKENS (con el tokenizador real)")
try:
    splitter = ingest.crear_splitter()
    reales = ingest.partir(documentos, splitter)
    import tiktoken
    codificador = tiktoken.get_encoding(config.TOKENIZADOR)
    tokens = [len(codificador.encode(f.page_content)) for f in reales]
    comprobar(f"ningún chunk pasa de {config.CHUNK_TOKENS} tokens (el mayor: {max(tokens)})",
              max(tokens) <= config.CHUNK_TOKENS)
    comprobar(f"cada archivo se parte en varios chunks ({len(reales)} en total)", len(reales) > len(documentos))
    con_solape, fronteras = ingest.contar_solapamientos(reales)
    comprobar(f"hay solapamiento entre chunks consecutivos ({con_solape} de {fronteras} fronteras)", con_solape >= 1)
except Exception as error:
    omitidas.append("tamaño en tokens")
    print(f"  [OMITIDA] no se pudo cargar el tokenizador ({type(error).__name__}). "
          "Conéctate a internet la primera vez: tiktoken lo descarga y lo guarda.")

print("\nBase vectorial (con embeddings simulados)")
muestra = [Document(page_content=t, metadata={"archivo": a, "fragmento": n, "id": f"{a}::{n}"})
           for a, n, t in [("x.md", 1, "el puerto 7710 es para clientes"),
                           ("x.md", 2, "los snapshots se toman cada seis horas"),
                           ("y.md", 1, "la retención por defecto es de 72 horas")]]
emb = EmbeddingsSimulados()
comprobar("la base empieza vacía", base_vectorial.cantidad_indexada() == 0)
comprobar("indexar guarda los 3 fragmentos", ingest.indexar(muestra, emb) == 3)
comprobar("indexar OTRA vez no duplica (sigue en 3)", ingest.indexar(muestra, emb) == 3)
comprobar("los datos persisten al volver a abrir la base", base_vectorial.cantidad_indexada() == 3)
comprobar("la base recuerda con qué modelo de embeddings se creó", base_vectorial.modelo_de_la_base() == "modelo-A")

print("\nProtección contra embeddings distintos")
config.EMBEDDING_MODEL = "modelo-B"
try:
    base_vectorial.abrir_base(emb)
    comprobar("si el .env cambia de modelo, la base se niega a abrirse", False)
except base_vectorial.EmbeddingsDistintos as error:
    comprobar("si el .env cambia de modelo, la base se niega a abrirse", "modelo-A" in str(error))
config.EMBEDDING_MODEL = "modelo-A"

print("\nReconstrucción")
base_vectorial.borrar_coleccion()
comprobar("--rebuild vacía la colección", base_vectorial.cantidad_indexada() == 0)

print(f"\n{sum(resultados)} de {len(resultados)} comprobaciones superadas"
      + (f" ({len(omitidas)} omitida: {', '.join(omitidas)})" if omitidas else ""))
sys.exit(0 if all(resultados) else 1)
