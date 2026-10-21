# Tolvak · Manual técnico · Parte 1: Introducción y arquitectura

> Documento ficticio creado con fines educativos. Tolvak y Lumbra Systems no existen: cualquier parecido con productos reales es casual.

## Qué es Tolvak

Tolvak es una plataforma de mensajería distribuida desarrollada por Lumbra Systems. Su función es recibir mensajes de las aplicaciones que los producen, guardarlos de forma duradera y entregarlos a las aplicaciones que los consumen, aunque productores y consumidores no estén activos al mismo tiempo.

Dicho de otro modo, Tolvak actúa como un buzón intermedio entre servicios. Un servicio deja un mensaje en Tolvak y sigue con su trabajo; otro servicio lo recoge cuando puede procesarlo. Ninguno de los dos necesita conocer la dirección del otro, ni esperar a que el otro responda.

Los usos más habituales de Tolvak son tres. El primero es desacoplar servicios: por ejemplo, una tienda en línea publica cada pedido nuevo y los servicios de facturación, inventario y envíos lo procesan por separado. El segundo es registrar flujos de eventos, como las lecturas de sensores de una planta industrial. El tercero es repartir tareas pesadas entre varios trabajadores, de modo que, si llegan muchas tareas a la vez, se acumulen en Tolvak en lugar de saturar a quien las procesa.

Este manual describe la versión 3.4 de Tolvak. La versión 1.0 ofrecía un único nodo sin replicación. La versión 2.0 introdujo las celdas, que permiten repartir un canal entre varios consumidores. La versión 3.0 incorporó Tolvak Relay para replicar datos entre centros de datos, y activó el cifrado TLS por defecto en todas las conexiones de clientes.

El manual está dividido en cuatro partes:

- Parte 1: Introducción y arquitectura (este documento).
- Parte 2: Instalación y configuración.
- Parte 3: Operación y monitoreo.
- Parte 4: Errores frecuentes y soporte.

## Conceptos fundamentales

Antes de instalar u operar Tolvak conviene entender seis conceptos. Todo el resto del manual se apoya en ellos.

### Mensaje

Un mensaje es la unidad de información que circula por Tolvak. Tiene dos partes: los encabezados y el cuerpo. Los encabezados incluyen una clave opcional, la marca de tiempo de publicación y el identificador del productor que lo envió. El cuerpo es el contenido en sí, y Tolvak lo trata como una secuencia de bytes sin interpretarla: puede ser texto, JSON o cualquier formato binario.

El tamaño máximo de un mensaje es de 2 MB por defecto. Ese límite se puede aumentar hasta un máximo absoluto de 16 MB mediante configuración, tal como se explica en la Parte 2. Tolvak no está pensado para transportar archivos grandes: si una aplicación necesita enviar un archivo de más de 16 MB, lo recomendable es guardarlo en un sistema de almacenamiento de archivos y publicar en Tolvak solo la referencia a su ubicación.

### Canal

Un canal es una categoría con nombre en la que se publican mensajes de un mismo tipo. Por ejemplo, una tienda podría tener los canales `pedidos.nuevos`, `pedidos.cancelados` y `pagos.confirmados`.

Los nombres de canal solo pueden contener letras minúsculas, números, puntos y guiones, y tienen un máximo de 120 caracteres. El punto se usa por convención para expresar jerarquías, aunque Tolvak no le da ningún significado especial.

Por defecto, los canales se crean de forma explícita con la herramienta `tolvakctl`. Si una aplicación intenta publicar en un canal que no existe, recibe el error TVK-309, salvo que se haya activado la creación automática de canales con el parámetro `canal.autocrear`, que está desactivado por defecto.

### Celda

Cada canal se divide en celdas. Una celda es una secuencia ordenada de mensajes: dentro de una misma celda, los mensajes se entregan exactamente en el orden en que fueron publicados. En cambio, entre celdas distintas no hay ningún orden garantizado.

Cuando un mensaje tiene clave, Tolvak calcula a qué celda va a partir de esa clave, de modo que todos los mensajes con la misma clave terminan en la misma celda y conservan su orden. Por ejemplo, si la clave es el identificador del cliente, todos los mensajes de un mismo cliente se procesan en orden. Los mensajes sin clave se reparten entre las celdas de forma rotativa.

Un canal nuevo tiene 6 celdas por defecto, y el máximo es de 256 celdas por canal. El número de celdas de un canal se puede aumentar después de crearlo, pero nunca se puede reducir. Por eso conviene empezar con un número moderado y ampliarlo cuando haga falta.

### Productor y consumidor

Un productor es cualquier aplicación que publica mensajes en un canal. Un consumidor es cualquier aplicación que lee mensajes de un canal. Una misma aplicación puede ser productora de un canal y consumidora de otro.

### Grupo de lectura

Los consumidores se organizan en grupos de lectura. Todos los consumidores de un mismo grupo se reparten el trabajo de un canal: cada celda se asigna a un único consumidor del grupo en cada momento, de modo que cada mensaje lo procesa un solo miembro del grupo.

Esto tiene una consecuencia práctica importante: si un grupo tiene más consumidores que celdas tiene el canal, los consumidores sobrantes quedan inactivos, sin trabajo asignado. Para paralelizar más, primero hay que aumentar el número de celdas del canal.

Distintos grupos de lectura son independientes entre sí. Si los servicios de facturación y de envíos forman dos grupos distintos, ambos reciben todos los mensajes del canal `pedidos.nuevos`, cada uno a su propio ritmo.

### Acuse de recibo

Cuando un consumidor termina de procesar un mensaje, envía un acuse de recibo a Tolvak. Si el acuse no llega dentro del plazo configurado, Tolvak considera que el procesamiento falló y vuelve a entregar el mensaje. El plazo de acuse es de 30 segundos por defecto y se controla con el parámetro `consumidor.plazo_acuse_s`.

Este mecanismo hace que la entrega de Tolvak sea "al menos una vez": ningún mensaje se pierde por un fallo del consumidor, pero un mismo mensaje puede llegar más de una vez. Por eso los consumidores deben ser idempotentes, es decir, procesar dos veces el mismo mensaje no debe producir efectos duplicados.

### Retención

Tolvak conserva cada mensaje durante un tiempo de retención, haya sido consumido o no. Pasado ese tiempo, el mensaje se elimina del disco. La retención es de 72 horas por defecto y se puede ampliar hasta un máximo de 720 horas, que equivalen a 30 días.

La retención permite que un grupo de lectura nuevo lea mensajes antiguos, o que un consumidor que estuvo detenido recupere lo que se perdió, siempre que no haya pasado el tiempo de retención.

## Componentes de la plataforma

Tolvak está formado por cuatro componentes.

### Tolvak Core

Tolvak Core es el nodo que almacena y entrega los mensajes. Es el componente central: los demás dependen de él. Cada nodo guarda sus datos en el directorio `/var/lib/tolvak/`.

### Clúster de nodos

En producción, Tolvak Core se ejecuta siempre como un clúster de varios nodos. El mínimo recomendado para producción es de 3 nodos, y el máximo soportado es de 15 nodos por clúster.

Los nodos de un clúster eligen entre ellos a un coordinador por mayoría, también llamada quórum. El coordinador decide cómo se reparten las celdas entre los nodos. Si el clúster pierde la mayoría de sus nodos (por ejemplo, si de 3 nodos quedan activos solo 1), no puede garantizar la consistencia de los datos y pasa a modo de solo lectura. En ese estado, los productores reciben el error TVK-611, descrito en la Parte 4.

### Replicación

Cada celda se replica en varios nodos para que la caída de un nodo no provoque pérdida de datos. El factor de replicación es de 3 por defecto y se controla con el parámetro `replicacion.factor`. Una escritura se confirma al productor cuando la mayoría de las réplicas la ha guardado: con factor 3, cuando 2 de las 3 réplicas la tienen.

### Tolvak Relay

Tolvak Relay replica canales completos entre dos clústeres situados en centros de datos distintos. La replicación de Relay es asíncrona: el clúster de origen no espera a que el de destino confirme cada mensaje. En condiciones normales, el retraso entre ambos clústeres es inferior a 2 segundos.

Relay solo está disponible en la edición Empresarial. Para conectar nodos dentro de un mismo centro de datos no se usa Relay, sino el propio clúster.

### Brújula

Brújula es el panel web de administración de Tolvak. Cada nodo lo sirve por HTTPS en el puerto 7711. Desde Brújula se pueden consultar los canales, las celdas, los grupos de lectura y las métricas principales, y también gestionar los usuarios.

### tolvakctl

`tolvakctl` es la herramienta de línea de comandos para administrar Tolvak. Permite crear el clúster, unir nodos, crear canales, gestionar usuarios, tomar snapshots y obtener diagnósticos. La mayoría de los procedimientos de este manual se describen con comandos de `tolvakctl`.

## Puertos de red

Cada nodo de Tolvak usa cuatro puertos TCP:

- Puerto 7710: conexiones de clientes (productores y consumidores). Usa cifrado TLS.
- Puerto 7711: API de administración y panel Brújula, por HTTPS.
- Puerto 7712: exposición de métricas para sistemas de monitoreo.
- Puerto 7720: comunicación interna entre los nodos del clúster.

La Parte 2 explica qué puertos deben estar accesibles desde dónde.

## Ediciones

Tolvak se distribuye en dos ediciones.

La edición Comunidad es gratuita. Admite clústeres de hasta 3 nodos, no incluye Tolvak Relay y su soporte se ofrece a través del foro de la comunidad, sin tiempos de respuesta garantizados.

La edición Empresarial admite clústeres de hasta 15 nodos, incluye Tolvak Relay y ofrece soporte con niveles de servicio definidos, descritos en la Parte 4.

Ambas ediciones comparten el mismo formato de datos, de modo que un clúster de la edición Comunidad se puede pasar a la edición Empresarial sin migrar los mensajes.

## Cuándo usar Tolvak y cuándo no

Tolvak es adecuado para comunicar servicios de forma asíncrona, absorber picos de carga y conservar flujos de eventos durante días.

No es adecuado como base de datos: no permite buscar mensajes por su contenido ni modificar un mensaje ya publicado. Tampoco es adecuado para transportar archivos de más de 16 MB, ni para casos que exijan latencias de entrega inferiores a 5 milisegundos de forma garantizada.

## Glosario rápido

- **Acuse de recibo:** confirmación que envía un consumidor tras procesar un mensaje.
- **Canal:** categoría con nombre donde se publican mensajes.
- **Celda:** subdivisión ordenada de un canal.
- **Coordinador:** nodo elegido por mayoría que reparte las celdas.
- **Grupo de lectura:** conjunto de consumidores que se reparten el trabajo de un canal.
- **Quórum:** mayoría de nodos necesaria para que el clúster funcione con normalidad.
- **Retención:** tiempo durante el cual Tolvak conserva un mensaje.
