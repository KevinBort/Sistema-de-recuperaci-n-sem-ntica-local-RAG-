# Tolvak · Manual técnico · Parte 3: Operación y monitoreo

> Documento ficticio creado con fines educativos. Tolvak y Lumbra Systems no existen: cualquier parecido con productos reales es casual.

## Monitoreo del clúster

Cada nodo de Tolvak expone sus métricas en el puerto 7712, en la ruta `/metricas`, en un formato de texto que pueden leer los sistemas de monitoreo habituales. Como ese puerto no exige autenticación, debe ser accesible solo desde la red interna.

Las cinco métricas más importantes, y los umbrales de alerta recomendados por Lumbra Systems, son estas.

### Latencia de entrega

La métrica `tolvak_latencia_p99_ms` indica el percentil 99 del tiempo, en milisegundos, que tarda un mensaje desde que se publica hasta que se entrega a un consumidor. Es decir, el 99 % de los mensajes tarda menos que ese valor.

Se recomienda una alerta de advertencia si supera los 250 milisegundos durante 5 minutos seguidos, y una alerta crítica si supera los 1000 milisegundos. Una latencia alta suele indicar que los consumidores no dan abasto o que un nodo tiene problemas de disco.

### Mensajes pendientes

La métrica `tolvak_mensajes_pendientes` indica cuántos mensajes de un canal todavía no ha procesado un grupo de lectura. Se mide por separado para cada grupo.

Se recomienda una alerta si un grupo acumula más de 100.000 mensajes pendientes durante 10 minutos. Un valor que crece sin parar indica que el grupo consume más despacio de lo que se produce. Las soluciones habituales son añadir consumidores al grupo o, si ya hay tantos consumidores como celdas, ampliar primero el número de celdas del canal.

Hay que vigilar esta métrica junto con la retención: si un grupo acumula mensajes más antiguos que el tiempo de retención, esos mensajes se eliminarán sin haber sido procesados.

### Uso de disco

La métrica `tolvak_disco_uso_pct` indica el porcentaje de disco ocupado en cada nodo. Se recomienda una alerta de advertencia al 80 % y una alerta crítica al 90 %.

Al llegar al 95 %, umbral definido por el parámetro `disco.umbral_rechazo_pct`, el nodo deja de aceptar nuevas escrituras para no quedarse sin espacio, y los productores reciben el error TVK-503. Por eso conviene actuar al recibir la alerta crítica, antes de llegar al umbral de rechazo.

### Nodos activos

La métrica `tolvak_nodos_activos` indica cuántos nodos del clúster están funcionando. Debe ser igual al número de nodos configurados. Cualquier valor menor merece una alerta inmediata, porque el clúster pierde capacidad de replicación, y si se pierde la mayoría de los nodos, pasa a modo de solo lectura.

### Réplicas desincronizadas

La métrica `tolvak_replicas_desincronizadas` indica cuántas réplicas de celdas van atrasadas respecto de su réplica principal. En condiciones normales vale 0. Si se mantiene por encima de 0 durante 15 minutos, hay que investigar: lo más habitual es un nodo con el disco lento o un problema de red entre nodos.

## Registros (logs)

Cada nodo escribe su registro en el archivo `/var/log/tolvak/tolvak-core.log`. El archivo rota cada día y se conservan los últimos 7 archivos.

El nivel de registro por defecto es `info`. Para investigar un problema se puede subir temporalmente al nivel de depuración con:

```
tolvakctl log nivel depurar
```

Para evitar que el disco se llene de registros, el nivel de depuración vuelve automáticamente a `info` pasados 60 minutos.

## Snapshots y recuperación

Un snapshot es una copia completa del estado de un nodo en un momento dado: sus mensajes, sus canales y su configuración.

### Snapshots automáticos

Tolvak toma un snapshot automático cada 6 horas y conserva cada snapshot durante 14 días. Ambos valores se controlan con los parámetros `snapshot.intervalo_horas` y `snapshot.retencion_dias`.

Por defecto, los snapshots se guardan en el directorio `/var/lib/tolvak/snapshots`, en el mismo disco que los datos. Se recomienda configurar el parámetro `snapshot.destino` para que apunte a un almacenamiento externo, porque un snapshot guardado en el mismo disco no sirve si ese disco falla.

### Snapshots manuales

Antes de cualquier operación arriesgada, como una actualización, conviene tomar un snapshot manual:

```
tolvakctl snapshot crear --etiqueta antes-de-actualizar
```

Para ver los snapshots disponibles se usa `tolvakctl snapshot listar`.

### Restaurar un snapshot

Restaurar un snapshot reemplaza el estado actual del nodo por el del snapshot. El procedimiento es:

1. Detener los productores que escriben en el clúster.
2. Ejecutar `tolvakctl snapshot restaurar <id-del-snapshot>`.
3. Verificar con `tolvakctl estado` que todos los nodos están activos.
4. Volver a poner en marcha los productores.

### Cuándo se pierden datos

Con el factor de replicación por defecto, que es 3, la caída de un solo nodo no provoca pérdida de datos: las otras réplicas siguen teniendo todos los mensajes. Restaurar un snapshot solo es necesario ante fallos más graves, como la pérdida simultánea de varios nodos o un error humano que borre datos. En esos casos, la pérdida máxima equivale al tiempo transcurrido desde el último snapshot: hasta 6 horas con la configuración por defecto.

## Escalado del clúster

### Añadir nodos

Para añadir un nodo a un clúster existente se usa el mismo procedimiento de unión de la instalación: `tolvakctl unir` con un token de unión vigente. El nodo nuevo no recibe celdas automáticamente. Para repartir las celdas entre todos los nodos hay que ejecutar:

```
tolvakctl rebalancear
```

Durante el rebalanceo, Tolvak copia celdas de un nodo a otro. Para no afectar al tráfico normal, la copia está limitada a 50 megabytes por segundo por defecto, valor que se controla con el parámetro `rebalanceo.limite_mbps`.

### Ampliar las celdas de un canal

Para aumentar el número de celdas de un canal se usa:

```
tolvakctl canal ampliar <canal> --celdas <nuevo-numero>
```

Recuerda que el número de celdas solo puede aumentar, nunca reducirse, y que el máximo es de 256 celdas por canal. Al ampliar las celdas, los mensajes con clave que lleguen a partir de ese momento pueden ir a una celda distinta que los anteriores con la misma clave, por lo que durante la transición puede perderse temporalmente el orden entre mensajes antiguos y nuevos de una misma clave.

## Cálculo de capacidad de disco

Para estimar cuánto disco necesita un clúster en total, Lumbra Systems recomienda esta regla:

**Disco total = volumen de mensajes por hora × horas de retención × factor de replicación × 1,2**

El factor 1,2 añade un margen del 20 % para snapshots, registros y picos de tráfico.

Por ejemplo, un clúster que recibe 5 GB de mensajes por hora, con la retención por defecto de 72 horas y el factor de replicación por defecto de 3, necesita: 5 × 72 × 3 × 1,2 = 1296 GB, es decir, unos 1,3 TB repartidos entre todos sus nodos. Con 3 nodos, cada uno necesitaría alrededor de 432 GB solo para datos.

## Cuotas por canal

Para evitar que un productor descontrolado sature el clúster, se puede fijar un límite de escritura por canal con el parámetro `canal.cuota_mb_s`, en megabytes por segundo. El valor por defecto es 0, que significa sin límite.

Cuando un productor supera la cuota de un canal, recibe el error TVK-429. El productor debe esperar y reintentar con esperas crecientes entre intentos, en lugar de reintentar de inmediato.

## Actualizaciones de versión

Tolvak se actualiza mediante actualizaciones progresivas: un nodo por vez, sin detener el clúster completo. El procedimiento es:

1. Tomar un snapshot manual de cada nodo.
2. En el nodo a actualizar, ejecutar `tolvakctl nodo drenar <nombre-del-nodo>`. Este comando traslada sus celdas a otros nodos para que deje de recibir tráfico.
3. Detener el servicio, instalar la nueva versión del paquete `tolvak-core` y volver a iniciarlo.
4. Verificar con `tolvakctl estado` que el nodo vuelve a estar activo.
5. Repetir con el siguiente nodo solo cuando todos los nodos estén activos.

Una regla importante: nunca se debe saltar una versión menor. Para pasar de la versión 3.2 a la 3.4, primero hay que actualizar todo el clúster a la 3.3. Saltar versiones puede dejar el formato de datos en un estado incompatible.

Se recomienda hacer las actualizaciones en los momentos de menor tráfico y con el equipo de operaciones disponible para revertir si algo falla.
