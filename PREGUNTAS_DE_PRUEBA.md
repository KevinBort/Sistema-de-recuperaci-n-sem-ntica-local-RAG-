# Preguntas de prueba del sistema RAG

Este archivo NO va en la carpeta `data/`: si se indexara, el sistema "encontraría" las respuestas aquí y las pruebas dejarían de ser válidas.

Los documentos de `data/` describen Tolvak, un producto ficticio. Como el modelo no puede conocerlo, cualquier respuesta correcta solo puede salir de la recuperación, y cualquier respuesta a una pregunta trampa que no sea "No lo sé" es una alucinación.

## Preguntas cuya respuesta SÍ está en los documentos

### 1. ¿Qué puertos usa un nodo de Tolvak y para qué sirve cada uno?

- **Respuesta esperada:** 7710 para clientes (productores y consumidores, con TLS); 7711 para administración y el panel Brújula (HTTPS); 7712 para métricas; 7720 para la comunicación entre nodos del clúster.
- **Fuente:** `01_introduccion_y_arquitectura.md` (Puertos de red) y `02_instalacion_y_configuracion.md` (Red y puertos).

### 2. ¿Cuál es el tamaño máximo de un mensaje y cómo se cambia?

- **Respuesta esperada:** 2 MB por defecto; se cambia con el parámetro `mensaje.tamano_max_kb`, hasta un máximo de 16 MB (16384 KB).
- **Fuente:** `02_instalacion_y_configuracion.md` (El archivo de configuración); también aparece en `01` y `04`.

### 3. ¿Qué significa el error TVK-412 y cómo se resuelve?

- **Respuesta esperada:** el mensaje supera el tamaño máximo. Se resuelve dividiendo el mensaje o publicando solo una referencia al contenido grande, o aumentando `mensaje.tamano_max_kb` hasta 16 MB. No se debe reintentar sin cambios.
- **Fuente:** `04_errores_y_soporte.md` (TVK-412).

### 4. ¿Cada cuánto se toman los snapshots automáticos y cuánto tiempo se conservan?

- **Respuesta esperada:** cada 6 horas, y se conservan 14 días.
- **Fuente:** `03_operacion_y_monitoreo.md` (Snapshots automáticos).

### 5. ¿Cuánto disco necesita un clúster que recibe 5 GB por hora con la configuración por defecto?

- **Respuesta esperada:** unos 1296 GB (alrededor de 1,3 TB) en total: 5 × 72 × 3 × 1,2.
- **Fuente:** `03_operacion_y_monitoreo.md` (Cálculo de capacidad de disco).

### 6. ¿Qué pasa si un clúster pierde la mayoría de sus nodos?

- **Respuesta esperada:** pierde el quórum y pasa a modo de solo lectura; los productores reciben el error TVK-611. Se recupera al restablecer la mayoría de nodos.
- **Fuente:** `04_errores_y_soporte.md` (TVK-611) y `01_introduccion_y_arquitectura.md` (Clúster de nodos).

## Preguntas trampa: la respuesta NO está en los documentos

En todas, la respuesta esperada es **"No lo sé"** (o la frase equivalente que defina el prompt), sin referencias.

### T1. ¿Cuánto cuesta la licencia de la edición Empresarial? (trampa difícil)

Del mismo tema: la búsqueda recuperará fragmentos sobre las ediciones, pero los documentos nunca mencionan precios. Es la prueba más exigente del prompt.

### T2. ¿Tolvak tiene un operador oficial para Kubernetes? (trampa difícil)

Los documentos mencionan contenedores solo para desarrollo en Windows y macOS, pero nunca hablan de Kubernetes. El modelo podría sentirse tentado a deducir una respuesta.

### T3. ¿Cuál es la capital de Australia? (trampa fácil)

Sin relación con el tema. El modelo conoce la respuesta por su entrenamiento, así que sirve para comprobar que responde solo con el contexto y no con su conocimiento general.
