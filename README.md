# Sistema de recuperación semántica local (RAG)

Asistente que responde preguntas sobre un manual técnico **usando solo el contenido de esos documentos**. Si la respuesta no está, contesta "No lo sé". Funciona **100 % en local y sin API keys**: el modelo de lenguaje y los embeddings corren con [Ollama](https://ollama.com), y los vectores se guardan en ChromaDB.

El dataset de ejemplo es el manual de **Tolvak**, una plataforma de mensajería **ficticia** (creada para este ejercicio). Se eligió ficticia a propósito: el modelo no puede conocerla, así que una respuesta correcta solo puede salir de la recuperación, y una respuesta a una pregunta trampa que no sea "No lo sé" es una alucinación evidente.

## Cómo funciona

```
INGESTA (una vez)
  data/*.md  ->  chunks de 500 tokens (50 de solapamiento)  ->  embeddings (bge-m3)  ->  ChromaDB (./vectorstore)

CONSULTA (cada pregunta)
  pregunta -> embedding (el MISMO modelo) -> los 4 fragmentos más cercanos
           -> prompt con las reglas + contexto numerado -> qwen3:4b-instruct
           -> PydanticOutputParser -> RespuestaRAG (texto + referencias)
```

La función principal es `get_rag_response(query)` en `rag.py`: es asíncrona y devuelve un objeto `RespuestaRAG` con la respuesta, un indicador `encontrada` y la lista de `referencias` (archivo, número de fragmento y extracto).

## Requisitos

- Python 3.12 o superior
- [Ollama](https://ollama.com) instalado y en ejecución
- Unos 5 GB libres de disco (los dos modelos ocupan unos 3,7 GB) y 16 GB de RAM recomendados
- Ninguna API key

## Instalación

```bash
# 1. Entorno virtual y dependencias
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Modelos de Ollama (en Linux, Ollama se instala con: curl -fsSL https://ollama.com/install.sh | sh)
ollama pull bge-m3
ollama pull qwen3:4b-instruct

# 3. Configuración
cp .env.example .env
```

**Usa `qwen3:4b-instruct` y no `qwen3:4b`.** La etiqueta corta `qwen3:4b` apunta a una variante que siempre razona antes de responder, y ese comportamiento no se puede desactivar: mezcla el razonamiento con la respuesta.

Comprueba que todo está listo:

```bash
python verificar_ollama.py
```

## Cómo ejecutarlo

```bash
# 1. Indexar los documentos de data/ (la primera vez tarda por los embeddings)
python ingest.py

# 2. Hacer una pregunta
python rag.py "¿Cuál es el tamaño máximo de un mensaje y cómo se cambia?"

# 3. Pruebas con el modelo real
python probar_rag.py              # las 2 pruebas de la consigna: una con respuesta y una trampa
python probar_rag.py --todas      # las 9 preguntas de PREGUNTAS_DE_PRUEBA.md
python probar_recuperacion.py     # solo la búsqueda, sin modelo de lenguaje
```

Si la base ya existe, `python ingest.py` no vuelve a indexar. Para reconstruirla (por ejemplo, tras cambiar un documento o el modelo de embeddings): `python ingest.py --rebuild`.

## Pruebas automáticas (no necesitan Ollama)

```bash
python test_schemas.py        # esquemas Pydantic
python test_ingesta.py        # chunking, persistencia e idempotencia (embeddings simulados)
python test_recuperacion.py   # búsqueda, validaciones y asincronía
python test_rag.py            # cadena completa con un modelo falso: trampas, reintentos, fallos del entorno
```

## Resultados con el modelo real

Las dos pruebas que pide la consigna, ejecutadas con `python probar_rag.py` (`qwen3:4b-instruct`, `top_k = 4`, `bge-m3`):

**Pregunta cuya respuesta está en los documentos** (23 s)

```
pregunta  : ¿Cuál es el tamaño máximo de un mensaje y cómo se cambia?
respuesta : El tamaño máximo de un mensaje es de 2 MB por defecto, y se puede aumentar hasta un
            máximo absoluto de 16 MB mediante la configuración del parámetro `mensaje.tamano_max_kb`,
            aplicando el cambio con `tolvakctl config recargar`.
encontrada: True
fuente    : 02_instalacion_y_configuracion.md #4
fuente    : 01_introduccion_y_arquitectura.md #2
```

**Pregunta trampa, cuya respuesta no está en los documentos** (13 s)

```
pregunta  : ¿Cuánto cuesta la licencia de la edición Empresarial?
respuesta : No lo sé
encontrada: False
```

El modelo no inventó un precio, aunque la búsqueda sí recuperó fragmentos sobre las ediciones del producto (el tema es el mismo, pero los documentos nunca mencionan precios).

## Estructura del repositorio

| Archivo | Para qué sirve |
|---|---|
| `data/` | Dataset de ejemplo: 4 documentos `.md` del manual de Tolvak |
| `PREGUNTAS_DE_PRUEBA.md` | 6 preguntas con respuesta y 3 trampas, con las respuestas esperadas. Está fuera de `data/` a propósito: si se indexara, las pruebas dejarían de ser válidas |
| `ingest.py` | Ingesta: lectura, chunking, embeddings y persistencia en ChromaDB |
| `rag.py` | La cadena RAG asíncrona y `get_rag_response()` |
| `recuperacion.py` | La capa de recuperación (`recuperar` y `arecuperar`) |
| `base_vectorial.py` | Acceso a ChromaDB y protección contra embeddings distintos |
| `schemas.py` | Esquemas Pydantic: `SalidaLLM` (lo que completa el modelo), `Referencia` y `RespuestaRAG` |
| `config.py` | Configuración compartida: modelos, rutas y parámetros de chunking y generación |
| `probar_rag.py`, `probar_recuperacion.py`, `verificar_ollama.py` | Scripts para comprobar el sistema con Ollama |
| `test_*.py` | Pruebas automáticas sin Ollama |
| `.env.example` | Plantilla de configuración |

## Decisiones de diseño

| Decisión | Motivo |
|---|---|
| **Chunks de 500 tokens con 50 de solapamiento**, medidos con `tiktoken` (`cl100k_base`) | La consigna pide tokens, no caracteres: `RecursiveCharacterTextSplitter` mide caracteres por defecto, así que se usa `from_tiktoken_encoder`. `bge-m3` usa su propio tokenizador; `cl100k_base` es una medida de referencia |
| **Se corta por párrafos, no por títulos** | Cortar también por títulos daba chunks más cortos (media de unos 300 tokens, según una medición con un contador aproximado) y casi sin solapamiento. Por párrafos, los chunks se acercan a 500 y el solapamiento es frecuente. Se cambia en `config.SEPARADORES` |
| **El modelo de embeddings se guarda en la colección** | Indexar con un modelo y consultar con otro da resultados sin sentido. Si el `.env` no coincide con la base, `base_vectorial.py` se niega a abrirla |
| **Persistencia sin duplicados** | La ingesta no reindexa si la base ya tiene datos; además usa IDs fijos (`archivo::n`) con `upsert`, así que repetirla no duplica nada |
| **`top_k = 4`** (acotado a 10) | Dentro del rango de 3 a 5 que pide la consigna; pasar demasiados fragmentos degrada la respuesta. En las 6 preguntas con respuesta, el dato esperado apareció siempre entre los 4 fragmentos |
| **Prompt "grounded"** | Ordena responder solo con el contexto, escribir exactamente "No lo sé" si no está, y tratar el contexto como datos y no como instrucciones |
| **Salida con `PydanticOutputParser`, más el esquema como `format` de Ollama** | El parser valida el resultado; el parámetro `format` hace que el servidor obligue al modelo a producir un JSON con la forma de `SalidaLLM`, lo que ayuda a un modelo pequeño |
| **Las referencias las construye el código** | El modelo solo indica los números de los fragmentos que usó; el código los convierte en referencias reales a partir de los metadatos de ChromaDB. Una referencia nunca puede ser inventada |
| **Respuesta sin fuente verificable = "No lo sé"** | Si el modelo dice haber encontrado la respuesta pero no cita ningún fragmento real, no se puede comprobar de dónde sale, así que se descarta |
| **Reintentos solo ante fallos de formato** | `.with_retry()` repite hasta 3 veces si el modelo devuelve algo que el parser no acepta. Los errores de entorno (Ollama caído, modelo no descargado) no se reintentan: repetirlos no los arregla |
| **Asincronía** | `get_rag_response` y `arecuperar` son `async`. La búsqueda vectorial corre en un hilo aparte (`asyncio.to_thread`) para no bloquear el event loop, y la llamada al modelo lleva un `asyncio.timeout` |
| **Temperatura 0,1 y ventana de 8192 tokens** | Respuestas fieles al contexto. Si la ventana fuera menor de lo que ocupa el prompt, Ollama descartaría el principio, es decir, las reglas |
| **Sin API keys** | Todo corre en local. El `.env` solo contiene nombres de modelos y la dirección de Ollama, y aun así está en el `.gitignore` |

## Limitaciones

- **Las referencias son los fragmentos que el modelo declara haber usado**, no una auditoría: puede apoyarse en un fragmento recuperado y no citarlo.
- **Un modelo de 4B parámetros puede equivocarse** más que uno grande, sobre todo con preguntas ambiguas. Los esquemas, la verificación de fuentes y los reintentos reducen el riesgo, pero no lo eliminan.
- **La velocidad depende del equipo.** En el equipo de las pruebas (16 núcleos y 15 GB de RAM) cada pregunta tardó entre 13 y 23 segundos; en equipos más modestos puede tardar bastante más.
- **No hay filtro por distancia.** La búsqueda siempre devuelve fragmentos, aunque nada responda la pregunta; lo que evita inventar es el prompt. Un umbral de distancia es una mejora posible, pero con pocas preguntas de calibración sería frágil.
- **Dataset pequeño** (4 documentos, unas 5.700 palabras, ficticios y en español). No hay memoria de conversación ni reordenamiento de resultados.
