"""Lanza las preguntas de PREGUNTAS_DE_PRUEBA.md contra tu base real (necesita Ollama y haber ejecutado ingest.py).

Para cada pregunta con respuesta comprueba si el dato esperado aparece en alguno de los fragmentos recuperados.
Para las preguntas trampa solo muestra qué tan cerca quedan los fragmentos.
"""

import asyncio
import statistics
import time

import config
import recuperacion

# (pregunta, datos que deben aparecer en algún fragmento recuperado; vale cualquiera de ellos)
CON_RESPUESTA = [
    ("¿Qué puertos usa un nodo de Tolvak y para qué sirve cada uno?", ["7710"]),
    ("¿Cuál es el tamaño máximo de un mensaje y cómo se cambia?", ["mensaje.tamano_max_kb"]),
    ("¿Qué significa el error TVK-412 y cómo se resuelve?", ["TVK-412"]),
    ("¿Cada cuánto se toman los snapshots automáticos y cuánto tiempo se conservan?", ["cada 6 horas"]),
    ("¿Cuánto disco necesita un clúster que recibe 5 GB por hora con la configuración por defecto?", ["1296"]),
    ("¿Qué pasa si un clúster pierde la mayoría de sus nodos?", ["TVK-611"]),
]
TRAMPAS = [
    "¿Cuánto cuesta la licencia de la edición Empresarial?",
    "¿Tolvak tiene un operador oficial para Kubernetes?",
    "¿Cuál es la capital de Australia?",
]


def mostrar(fragmentos, hechos=None) -> int | None:
    """Imprime los fragmentos y devuelve en qué posición aparece el dato esperado (o None)."""
    posicion = None
    for rango, f in enumerate(fragmentos, 1):
        tiene_dato = hechos and any(h.lower() in f.texto.lower() for h in hechos)
        if tiene_dato and posicion is None:
            posicion = rango
        marca = "  <- contiene el dato" if tiene_dato else ""
        print(f"      {rango}. {f.archivo} #{f.numero:<2} distancia {f.distancia:.3f}{marca}")
    return posicion


async def main() -> None:
    print(f"top_k = {config.TOP_K} | embeddings = {config.EMBEDDING_MODEL}")
    aciertos = 0
    mejores = []

    print("\n== Preguntas CON respuesta en los documentos ==")
    for numero, (pregunta, hechos) in enumerate(CON_RESPUESTA, 1):
        inicio = time.perf_counter()
        fragmentos = await recuperacion.arecuperar(pregunta)
        ms = (time.perf_counter() - inicio) * 1000
        print(f"\n[{numero}] {pregunta}\n    dato esperado: {hechos[0]!r} ({ms:.0f} ms)")
        posicion = mostrar(fragmentos, hechos)
        if posicion:
            aciertos += 1
            print(f"    ACIERTO: el dato aparece en el fragmento nº {posicion}")
        else:
            print("    FALLO: el dato no aparece en ningún fragmento recuperado")
        mejores.append(fragmentos[0].distancia)

    print("\n== Preguntas TRAMPA (la respuesta NO está en los documentos) ==")
    mejores_trampa = []
    for numero, pregunta in enumerate(TRAMPAS, 1):
        fragmentos = await recuperacion.arecuperar(pregunta)
        print(f"\n[T{numero}] {pregunta}")
        mostrar(fragmentos)
        mejores_trampa.append(fragmentos[0].distancia)

    print("\n== Resumen ==")
    print(f"Aciertos: {aciertos} de {len(CON_RESPUESTA)} (con top_k = {config.TOP_K})")
    print(f"Distancia del mejor fragmento, preguntas con respuesta: media {statistics.mean(mejores):.3f} "
          f"(de {min(mejores):.3f} a {max(mejores):.3f})")
    print("Distancia del mejor fragmento, preguntas trampa:        "
          + ", ".join(f"T{i}: {d:.3f}" for i, d in enumerate(mejores_trampa, 1)))
    print("\nOJO: la búsqueda SIEMPRE devuelve fragmentos, aunque nada responda la pregunta.")
    print("Lo que evita inventar respuestas a las trampas es el prompt (Fase 4), no la recuperación.")


if __name__ == "__main__":
    config.exigir_config()
    asyncio.run(main())
