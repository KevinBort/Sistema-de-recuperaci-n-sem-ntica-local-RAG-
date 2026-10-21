"""Prueba de los esquemas SIN modelo ni base vectorial."""

import json

from pydantic import ValidationError

from schemas import NO_LO_SE, Referencia, RespuestaRAG, SalidaLLM


def mostrar(titulo, salida):
    print(f"{titulo}\n   encontrada={salida.encontrada}, respuesta={salida.respuesta!r}, fragmentos={salida.fragmentos}")


print("== SalidaLLM: lo que llena el modelo ==")
mostrar("1) Respuesta normal",
        SalidaLLM(encontrada=True, respuesta="El tamaño máximo es 2 MB.", fragmentos=[2, 5]))
mostrar("2) No encontrada, pero el modelo escribió texto de más",
        SalidaLLM(encontrada=False, respuesta="Creo que cuesta 100 dólares", fragmentos=[1]))
mostrar("3) Dice 'No lo sé.' pero marcó encontrada=True",
        SalidaLLM(encontrada=True, respuesta="No lo sé.", fragmentos=[3]))
mostrar("4) Fragmentos repetidos o inválidos",
        SalidaLLM(encontrada=True, respuesta="Puerto 7710.", fragmentos=[3, 3, 0, -1, 4]))

try:
    SalidaLLM(encontrada=True, respuesta="   ", fragmentos=[1])
    print("MAL: respuesta vacía no falló")
except ValidationError as e:
    print("5) Respuesta vacía -> rechazada:", e.errors()[0]["msg"])

try:
    SalidaLLM(respuesta="hola")
    print("MAL: faltaba 'encontrada' y no falló")
except ValidationError as e:
    print("6) Falta 'encontrada' -> rechazada:", e.errors()[0]["msg"])

print("\n== RespuestaRAG: lo que devuelve get_rag_response() ==")
final = RespuestaRAG(
    pregunta="¿Cuál es el tamaño máximo de un mensaje?",
    respuesta="2 MB por defecto, configurable hasta 16 MB.",
    encontrada=True,
    referencias=[Referencia(archivo="02_instalacion_y_configuracion.md", fragmento=4,
                            extracto="mensaje.tamano_max_kb: tamaño máximo de un mensaje...")],
)
print(final.model_dump_json(indent=2))

print("\n== Esquema que verá el modelo (descripciones de cada campo) ==")
for campo, info in SalidaLLM.model_json_schema()["properties"].items():
    print(f"   {campo}: {info.get('description')}")
