"""Prueba la cadena RAG SIN Ollama: un modelo falso con respuestas guionadas y embeddings simulados."""

import asyncio
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import ollama
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

import config
import ingest
import rag
import recuperacion
from schemas import NO_LO_SE

resultados = []


def comprobar(descripcion: str, condicion: bool) -> None:
    resultados.append(condicion)
    print(f"  [{'OK' if condicion else 'FALLA'}] {descripcion}")


def ejecutar(coro):
    return asyncio.run(coro)


def lanza(excepcion, coro_fn) -> bool:
    try:
        ejecutar(coro_fn())
    except excepcion:
        return True
    except Exception as error:
        print(f"      (lanzó {type(error).__name__}: {error})")
        return False
    return False


class EmbeddingsSimulados(Embeddings):
    def _vector(self, texto: str) -> list[float]:
        v = [0.0] * 64
        for palabra in re.findall(r"\w+", texto.lower()):
            v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % 64] += 1.0
        return v

    def embed_documents(self, textos):
        return [self._vector(t) for t in textos]

    def embed_query(self, texto):
        return self._vector(texto)


class ModeloFalso:
    """Imita al modelo de lenguaje: devuelve, en orden, las respuestas guionadas (y cuenta las llamadas)."""

    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), 0

    def como_runnable(self):
        def responder(_prompt):
            self.llamadas += 1
            actual = self.respuestas[min(self.llamadas - 1, len(self.respuestas) - 1)]
            if isinstance(actual, Exception):
                raise actual
            return AIMessage(content=actual)
        return RunnableLambda(responder)


def json_modelo(encontrada, respuesta, fragmentos):
    return json.dumps({"encontrada": encontrada, "respuesta": respuesta, "fragmentos": fragmentos})


def consultar(pregunta, modelo, **extra):
    cadena = rag.construir_cadena(modelo.como_runnable())
    return ejecutar(rag.get_rag_response(pregunta, cadena=cadena, embeddings=emb, **extra))


config.DIR_VECTORES = Path(tempfile.mkdtemp()) / "vectorstore"
config.COLECCION = "prueba"
config.EMBEDDING_MODEL = "modelo-A"
emb = EmbeddingsSimulados()
PREGUNTA = "¿qué puerto usan los clientes?"

textos = [
    ("a.md", "el puerto 7710 recibe las conexiones de los clientes con cifrado {TLS}"),
    ("a.md", "el puerto 7711 es para la administración y el panel web"),
    ("b.md", "los snapshots se toman cada seis horas y se conservan catorce días"),
    ("b.md", "la retención por defecto de los mensajes es de setenta y dos horas"),
    ("c.md", "el error de cuota excedida ocurre cuando el productor escribe demasiado rápido"),
    ("c.md", "el error de almacenamiento lleno ocurre cuando el disco supera el noventa y cinco por ciento"),
]
muestra = [Document(page_content=t, metadata={"archivo": a, "fragmento": n, "id": f"{a}::{n}"})
           for n, (a, t) in enumerate(textos, 1)]

print("Prompt y contexto")
render = rag.PROMPT.invoke({"pregunta": "¿p?", "contexto": "dato con {llaves} sueltas"})
sistema, humano = render.messages[0].content, render.messages[1].content
comprobar("el prompt solo pide 'contexto' y 'pregunta'", sorted(rag.PROMPT.input_variables) == ["contexto", "pregunta"])
comprobar("el prompt ordena responder 'No lo sé' si no está en el contexto", NO_LO_SE in sistema)
comprobar("el prompt incluye las instrucciones de formato del parser", '"encontrada"' in sistema)
comprobar("un contexto con llaves { } no rompe el prompt", "dato con {llaves} sueltas" in humano)
frag = [recuperacion.Fragmento(archivo="a.md", numero=3, texto="uno", distancia=0.1),
        recuperacion.Fragmento(archivo="b.md", numero=1, texto="dos", distancia=0.2)]
ctx = rag.formatear_contexto(frag)
comprobar("el contexto numera los fragmentos [1], [2]", "[1] (fuente: a.md, fragmento 3)" in ctx and "[2] (fuente: b.md" in ctx)

ingest.indexar(muestra, emb)
recuperados = recuperacion.recuperar(PREGUNTA, embeddings=emb)

print("\nRespuesta con respuesta en los documentos")
r = consultar(PREGUNTA, ModeloFalso(json_modelo(True, "El puerto 7710.", [1, 2])))
comprobar("devuelve encontrada=True con el texto del modelo", r.encontrada and r.respuesta == "El puerto 7710.")
comprobar("las referencias son los fragmentos reales que citó el modelo",
          [(x.archivo, x.fragmento) for x in r.referencias] == [(recuperados[0].archivo, recuperados[0].numero),
                                                                (recuperados[1].archivo, recuperados[1].numero)])
comprobar("el extracto viene del documento, no del modelo", "puerto" in r.referencias[0].extracto)

print("\nPregunta trampa y modelo poco fiable")
r = consultar("¿cuánto cuesta?", ModeloFalso(json_modelo(False, "No lo sé", [])))
comprobar("trampa: 'No lo sé', encontrada=False y sin referencias",
          not r.encontrada and r.respuesta == NO_LO_SE and r.referencias == [])
r = consultar("¿cuánto cuesta?", ModeloFalso(json_modelo(False, "Cuesta unos 100 dólares", [1])))
comprobar("si dice no encontrada pero inventa texto, se corrige a 'No lo sé'", r.respuesta == NO_LO_SE and r.referencias == [])
r = consultar(PREGUNTA, ModeloFalso(json_modelo(True, "No lo sé.", [1])))
comprobar("si dice 'no lo sé' pero marca encontrada=True, se corrige", not r.encontrada)
r = consultar(PREGUNTA, ModeloFalso(json_modelo(True, "El puerto 7710.", [])))
comprobar("dice haber encontrado la respuesta sin citar fuente: se descarta", not r.encontrada and r.referencias == [])
r = consultar(PREGUNTA, ModeloFalso(json_modelo(True, "El puerto 7710.", [99, 0])))
comprobar("cita fragmentos que no existen: se descarta", not r.encontrada and r.referencias == [])
r = consultar(PREGUNTA, ModeloFalso(json_modelo(True, "El puerto 7710.", [2, 99])))
comprobar("cita uno real y uno inexistente: se conserva solo el real", r.encontrada and len(r.referencias) == 1)

print("\nFormato inválido y reintentos")
m = ModeloFalso("esto no es json", json_modelo(True, "El puerto 7710.", [1]))
inicio = time.perf_counter()
r = consultar(PREGUNTA, m)
comprobar(f"formato inválido una vez: reintenta y se recupera ({m.llamadas} llamadas, {time.perf_counter() - inicio:.1f} s)",
          r.encontrada and m.llamadas == 2)
m = ModeloFalso("basura")
comprobar(f"formato inválido siempre: se rinde con ErrorRAG tras {config.REINTENTOS} intentos",
          lanza(rag.ErrorRAG, lambda: rag.get_rag_response(
              PREGUNTA, cadena=rag.construir_cadena(m.como_runnable()), embeddings=emb)) and m.llamadas == config.REINTENTOS)

print("\nFallos del entorno")
m = ModeloFalso(ConnectionError("sin conexión"))
comprobar("Ollama caído: ErrorRAG y sin reintentos inútiles",
          lanza(rag.ErrorRAG, lambda: rag.get_rag_response(
              PREGUNTA, cadena=rag.construir_cadena(m.como_runnable()), embeddings=emb)) and m.llamadas == 1)
m = ModeloFalso(ollama.ResponseError("model 'x' not found", 404))
comprobar("modelo no descargado (404): ErrorRAG",
          lanza(rag.ErrorRAG, lambda: rag.get_rag_response(
              PREGUNTA, cadena=rag.construir_cadena(m.como_runnable()), embeddings=emb)))


async def llm_lento(_prompt):
    await asyncio.sleep(2)
    return AIMessage(content=json_modelo(True, "x", [1]))


config.TIMEOUT_LLM_S = 0.3
comprobar("modelo demasiado lento: ErrorRAG por tiempo agotado",
          lanza(rag.ErrorRAG, lambda: rag.get_rag_response(
              PREGUNTA, cadena=rag.construir_cadena(RunnableLambda(llm_lento)), embeddings=emb)))
config.TIMEOUT_LLM_S = 300

print("\nPreguntas inválidas")
comprobar("pregunta vacía: ValueError",
          lanza(ValueError, lambda: rag.get_rag_response("  ", cadena=rag.construir_cadena(ModeloFalso("x").como_runnable()), embeddings=emb)))
config.EMBEDDING_MODEL = "modelo-B"
comprobar("si el .env cambió de modelo de embeddings: se niega (EmbeddingsDistintos)",
          lanza(Exception, lambda: rag.get_rag_response(
              PREGUNTA, cadena=rag.construir_cadena(ModeloFalso("x").como_runnable()), embeddings=emb)))
config.EMBEDDING_MODEL = "modelo-A"

print("\nAsincronía")


async def llm_lento_ok(_prompt):
    await asyncio.sleep(0.5)
    return AIMessage(content=json_modelo(True, "ok", [1]))


async def tres_a_la_vez() -> float:
    cadena = rag.construir_cadena(RunnableLambda(llm_lento_ok))
    inicio = time.perf_counter()
    await asyncio.gather(*(rag.get_rag_response(q, cadena=cadena, embeddings=emb)
                           for q in ["puerto clientes", "snapshots horas", "error cuota"]))
    return time.perf_counter() - inicio


tiempo = ejecutar(tres_a_la_vez())
comprobar(f"3 consultas con un modelo lento (0,5 s cada una) tardan {tiempo:.1f} s, no 1,5 s", tiempo < 1.2)

print(f"\n{sum(resultados)} de {len(resultados)} comprobaciones superadas")
sys.exit(0 if all(resultados) else 1)
