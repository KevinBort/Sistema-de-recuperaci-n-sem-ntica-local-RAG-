"""Configuración compartida por la ingesta y la consulta.

Todo lo que debe ser IGUAL en las dos fases se define aquí, una sola vez:
el modelo de embeddings, la carpeta de la base vectorial y el nombre de la colección.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # el .env manda, aunque la terminal tenga valores viejos

RAIZ = Path(__file__).parent
DIR_DATOS = RAIZ / "data"
DIR_VECTORES = RAIZ / "vectorstore"
COLECCION = "manual_tolvak"

LLM_MODEL = os.getenv("LLM_MODEL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Recuperación: cuántos fragmentos se le pasan al modelo (la consigna pide entre 3 y 5)
TOP_K = 4
K_MAXIMO = 10  # tope de seguridad: demasiados fragmentos degradan la respuesta

# Generación (modelo de lenguaje)
TEMPERATURA = 0.1          # baja: queremos respuestas fieles al contexto, no creativas
NUM_CTX = 8192             # ventana de contexto que se le pide a Ollama (su valor por defecto puede ser menor)
MAX_TOKENS_RESPUESTA = 400  # tope de la respuesta: red de seguridad contra generación sin fin
TIMEOUT_LLM_S = 300        # segundos máximos esperando al modelo (en CPU puede tardar bastante)
REINTENTOS = 3             # intentos si el modelo no devuelve una respuesta con el formato pedido

# Chunking: tamaño máximo y solapamiento, medidos en TOKENS (no en caracteres)
CHUNK_TOKENS = 500
CHUNK_OVERLAP = 50
TOKENIZADOR = "cl100k_base"

# Por dónde se corta, en orden de preferencia: primero párrafos, luego líneas, frases y palabras.
# Alternativa: añadir "\n## " y "\n### " al principio para cortar también por títulos.
# Eso mantiene cada sección entera, pero da chunks más cortos y casi sin solapamiento.
SEPARADORES = ["\n\n", "\n", ". ", " ", ""]


def exigir_config() -> None:
    """Se detiene con un mensaje claro si falta algo en el .env."""
    if not LLM_MODEL or not EMBEDDING_MODEL:
        sys.exit("ERROR: faltan LLM_MODEL o EMBEDDING_MODEL en el .env (cópialo de .env.example)")
