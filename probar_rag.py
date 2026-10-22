"""Prueba el RAG completo con Ollama y tu base real.

    python probar_rag.py                 # las 2 pruebas de la consigna: una con respuesta y una trampa
    python probar_rag.py --todas         # las 9 preguntas de PREGUNTAS_DE_PRUEBA.md (tarda varios minutos)
    python probar_rag.py "tu pregunta"   # una pregunta libre
"""

import argparse
import asyncio
import logging
import time

import config
import rag
from recuperacion import BaseVacia
from schemas import NO_LO_SE

# (pregunta, datos de los que debe aparecer al menos uno en la respuesta)
CON_RESPUESTA = [
    ("¿Cuál es el tamaño máximo de un mensaje y cómo se cambia?", ["2 MB", "2048", "tamano_max_kb"]),
    ("¿Qué puertos usa un nodo de Tolvak y para qué sirve cada uno?", ["7710"]),
    ("¿Qué significa el error TVK-412 y cómo se resuelve?", ["demasiado grande", "tamaño máximo", "supera"]),
    ("¿Cada cuánto se toman los snapshots automáticos y cuánto tiempo se conservan?", ["6 horas", "seis horas"]),
    ("¿Cuánto disco necesita un clúster que recibe 5 GB por hora con la configuración por defecto?", ["1296", "1.296", "1,3 TB"]),
    ("¿Qué pasa si un clúster pierde la mayoría de sus nodos?", ["solo lectura", "TVK-611", "quórum"]),
]
TRAMPAS = [
    "¿Cuánto cuesta la licencia de la edición Empresarial?",
    "¿Tolvak tiene un operador oficial para Kubernetes?",
    "¿Cuál es la capital de Australia?",
]


def mostrar(resultado) -> None:
    print(f"    respuesta : {resultado.respuesta}")
    print(f"    encontrada: {resultado.encontrada}")
    for ref in resultado.referencias:
        print(f"    fuente    : {ref.archivo} #{ref.fragmento} — {ref.extracto[:90]}…")


async def preguntar(pregunta: str):
    inicio = time.perf_counter()
    try:
        resultado = await rag.get_rag_response(pregunta)
    except (rag.ErrorRAG, BaseVacia) as error:
        print(f"    ERROR: {error}")
        return None, time.perf_counter() - inicio
    return resultado, time.perf_counter() - inicio


async def main(preguntas_con_respuesta, trampas) -> None:
    correctas = sin_alucinar = 0
    print(f"modelo = {config.LLM_MODEL} | top_k = {config.TOP_K} | embeddings = {config.EMBEDDING_MODEL}")

    for numero, (pregunta, datos) in enumerate(preguntas_con_respuesta, 1):
        print(f"\n[{numero}] CON respuesta en los documentos\n    pregunta  : {pregunta}")
        resultado, segundos = await preguntar(pregunta)
        if resultado is None:
            continue
        mostrar(resultado)
        ok = resultado.encontrada and any(d.lower() in resultado.respuesta.lower() for d in datos)
        correctas += ok
        print(f"    -> {'CORRECTA' if ok else 'REVISAR: no aparece el dato esperado'} ({segundos:.0f} s)")

    for numero, pregunta in enumerate(trampas, 1):
        print(f"\n[T{numero}] TRAMPA (no está en los documentos)\n    pregunta  : {pregunta}")
        resultado, segundos = await preguntar(pregunta)
        if resultado is None:
            continue
        mostrar(resultado)
        ok = not resultado.encontrada and resultado.respuesta == NO_LO_SE and not resultado.referencias
        sin_alucinar += ok
        print(f"    -> {'SIN ALUCINACIÓN' if ok else 'ALUCINACIÓN: respondió algo que no está en los documentos'} ({segundos:.0f} s)")

    print("\n== Resumen ==")
    if preguntas_con_respuesta:
        print(f"Preguntas con respuesta correctas: {correctas} de {len(preguntas_con_respuesta)}")
    if trampas:
        print(f"Preguntas trampa sin alucinar:     {sin_alucinar} de {len(trampas)}")


if __name__ == "__main__":
    lector = argparse.ArgumentParser(description="Prueba el RAG con Ollama")
    lector.add_argument("pregunta", nargs="*", help="una pregunta libre (opcional)")
    lector.add_argument("--todas", action="store_true", help="las 9 preguntas de prueba")
    args = lector.parse_args()
    logging.basicConfig(level=logging.WARNING)
    config.exigir_config()

    if args.pregunta:
        asyncio.run(main([(" ".join(args.pregunta), ["\0"])], []))  # sin dato esperado: solo muestra la respuesta
    elif args.todas:
        asyncio.run(main(CON_RESPUESTA, TRAMPAS))
    else:
        asyncio.run(main(CON_RESPUESTA[:1], TRAMPAS[:1]))
