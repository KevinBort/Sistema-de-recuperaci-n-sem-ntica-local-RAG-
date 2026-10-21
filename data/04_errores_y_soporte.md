# Tolvak · Manual técnico · Parte 4: Errores frecuentes y soporte

> Documento ficticio creado con fines educativos. Tolvak y Lumbra Systems no existen: cualquier parecido con productos reales es casual.

## Cómo leer un código de error

Todos los errores de Tolvak tienen un código con el formato `TVK-` seguido de tres dígitos. El primer dígito indica la categoría del problema:

- **1:** conexión de red.
- **2:** autenticación y permisos.
- **3:** recursos, como canales o grupos de lectura.
- **4:** mensajes y cuotas.
- **5:** almacenamiento.
- **6:** estado del clúster.

Además del código, cada error indica si el cliente puede reintentar la operación. Reintentar tiene sentido cuando el problema es temporal, como una cuota excedida; no tiene sentido cuando el problema es permanente, como un mensaje demasiado grande, porque fallará siempre igual.

A continuación se describen los errores más frecuentes.

## TVK-101: conexión rechazada

**Qué significa:** el cliente no pudo establecer conexión con el nodo.

**Causas habituales:** el cliente intenta conectarse a un puerto equivocado (las aplicaciones deben usar el puerto 7710, no el 7711, que es el de administración); el cliente no tiene configurado TLS, que es obligatorio desde la versión 3.0; o un cortafuegos bloquea el puerto 7710.

**Cómo resolverlo:** comprobar que el cliente apunta al puerto 7710 con TLS activado y que confía en el certificado del clúster. Si el clúster usa los certificados autofirmados que genera la instalación, el cliente debe recibir una copia del certificado de la autoridad incluido en `/etc/tolvak/certs/`.

**¿Se puede reintentar?** Sí, una vez corregida la configuración. Si el error aparece de forma intermitente, puede deberse a un nodo que se está reiniciando.

## TVK-204: autenticación fallida

**Qué significa:** el token de acceso del cliente no es válido.

**Causas habituales:** la causa más frecuente es que el token caducó. Los tokens duran 24 horas por defecto, según el parámetro `seguridad.token_duracion_h`. Otras causas son que el usuario fue eliminado o que se le quitó el permiso sobre el canal.

**Cómo resolverlo:** obtener un token nuevo con `tolvakctl token renovar --usuario <nombre>`. Las aplicaciones de larga duración deben renovar su token automáticamente antes de que caduque, por ejemplo cada 20 horas.

**¿Se puede reintentar?** Solo después de obtener un token nuevo.

## TVK-309: canal inexistente

**Qué significa:** el cliente intentó publicar en un canal, o leer de un canal, que no existe.

**Causas habituales:** un error de escritura en el nombre del canal, o un despliegue en el que la aplicación arrancó antes de que se creara el canal.

**Cómo resolverlo:** crear el canal con `tolvakctl canal crear <nombre>`. Como alternativa, se puede activar la creación automática con el parámetro `canal.autocrear = true`, aunque Lumbra Systems no lo recomienda en producción, porque un error de escritura en un nombre crearía un canal nuevo sin que nadie lo note.

**¿Se puede reintentar?** Solo después de crear el canal.

## TVK-412: mensaje demasiado grande

**Qué significa:** el mensaje supera el tamaño máximo permitido.

**Causas habituales:** el tamaño máximo es de 2 MB por defecto, según el parámetro `mensaje.tamano_max_kb`. Este error suele aparecer cuando una aplicación intenta enviar archivos o colecciones muy grandes dentro de un único mensaje.

**Cómo resolverlo:** hay dos opciones. La primera, y la recomendada, es reducir el mensaje: dividirlo en varios mensajes más pequeños o guardar el contenido grande en un sistema de almacenamiento de archivos y publicar solo su referencia. La segunda es aumentar el parámetro `mensaje.tamano_max_kb`, hasta un máximo absoluto de 16384 kilobytes (16 MB). Ese cambio se aplica con `tolvakctl config recargar`, sin reiniciar.

**¿Se puede reintentar?** No sin cambios: el mismo mensaje fallará siempre.

## TVK-429: cuota excedida

**Qué significa:** el productor superó el límite de escritura del canal, definido con el parámetro `canal.cuota_mb_s`.

**Causas habituales:** un pico de tráfico legítimo o un productor con un error que publica en bucle.

**Cómo resolverlo:** el productor debe reintentar con esperas crecientes entre intentos. Si el tráfico es legítimo y constante, hay que aumentar la cuota del canal. Si no lo es, hay que corregir el productor.

**¿Se puede reintentar?** Sí, con esperas crecientes.

## TVK-503: almacenamiento lleno

**Qué significa:** el nodo rechaza escrituras porque su disco alcanzó el umbral de rechazo, que es del 95 % por defecto, según el parámetro `disco.umbral_rechazo_pct`.

**Causas habituales:** un volumen de mensajes mayor que el previsto, una retención demasiado larga para el disco disponible, o snapshots acumulados en el mismo disco que los datos.

**Cómo resolverlo:** hay tres acciones posibles, que pueden combinarse. Reducir la retención con `retencion.horas` y aplicar el cambio con `tolvakctl config recargar`; mover los snapshots a un almacenamiento externo con `snapshot.destino`; o añadir nodos al clúster y ejecutar `tolvakctl rebalancear`. La fórmula de capacidad de la Parte 3 ayuda a dimensionar el clúster para que el problema no se repita.

**¿Se puede reintentar?** Sí, cuando se libere espacio. Las lecturas siguen funcionando mientras tanto.

## TVK-611: quórum perdido

**Qué significa:** el clúster perdió la mayoría de sus nodos y pasó a modo de solo lectura.

**Causas habituales:** la caída simultánea de varios nodos, o un problema de red que deja aislados a parte de ellos. Por ejemplo, en un clúster de 3 nodos, si solo queda 1 activo, el clúster no tiene quórum.

**Cómo resolverlo:** recuperar los nodos caídos o restablecer la red entre ellos. En cuanto vuelve a haber mayoría, el clúster elige un coordinador y retoma las escrituras de forma automática. No se debe crear un clúster nuevo con los nodos restantes, porque se perderían los mensajes que solo estaban en los nodos caídos.

**¿Se puede reintentar?** Sí, cuando el clúster recupere el quórum. Mientras tanto, los consumidores pueden seguir leyendo.

## Diagnóstico general

Ante cualquier problema que no esté en esta lista, se recomienda seguir este orden:

1. Ejecutar `tolvakctl estado` para ver si todos los nodos están activos y hay coordinador.
2. Revisar las métricas de la Parte 3, en especial el uso de disco y las réplicas desincronizadas.
3. Revisar el registro `/var/log/tolvak/tolvak-core.log`, subiendo temporalmente el nivel a depuración si hace falta.
4. Generar un paquete de diagnóstico con:

```
tolvakctl diagnostico
```

Este comando genera un archivo comprimido llamado `tolvak-diagnostico-<fecha>.tgz`, que incluye la configuración del nodo sin contraseñas ni tokens, los registros de las últimas 24 horas y el estado del clúster. Es el archivo que pide el equipo de soporte.

## Soporte técnico

### Edición Comunidad

El soporte de la edición Comunidad se ofrece a través del foro de la comunidad de Tolvak. No hay tiempos de respuesta garantizados.

### Edición Empresarial

La edición Empresarial incluye soporte con tres niveles de severidad, según la gravedad del problema:

- **P1 (crítico):** el servicio está caído o hay pérdida de datos. Primera respuesta en un máximo de 30 minutos, las 24 horas, todos los días del año.
- **P2 (alto):** el servicio funciona con una degradación grave, por ejemplo una latencia muy superior a la habitual. Primera respuesta en un máximo de 4 horas, en horario laboral.
- **P3 (normal):** consultas, dudas de configuración o problemas menores. Primera respuesta en un máximo de 2 días hábiles.

Los casos se abren en el portal de soporte de Lumbra Systems, en `soporte.lumbra.example`. Para que el caso avance rápido, hay que indicar la severidad, la versión de Tolvak, una descripción cronológica del problema y adjuntar el archivo generado por `tolvakctl diagnostico`.

Si un caso no recibe respuesta dentro del plazo de su severidad, el cliente puede escalarlo a su gerente de cuenta en Lumbra Systems.

## Política de versiones soportadas

Cada versión menor de Tolvak, como la 3.3 o la 3.4, recibe soporte durante 18 meses desde su publicación. Las correcciones de seguridad se publican para las dos últimas versiones menores. Por eso se recomienda no quedarse más de una versión menor por detrás de la más reciente, y seguir siempre el procedimiento de actualización progresiva de la Parte 3, sin saltar versiones.
