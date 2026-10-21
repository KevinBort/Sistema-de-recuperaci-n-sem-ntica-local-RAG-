# Tolvak · Manual técnico · Parte 2: Instalación y configuración

> Documento ficticio creado con fines educativos. Tolvak y Lumbra Systems no existen: cualquier parecido con productos reales es casual.

## Requisitos de hardware

Los requisitos dependen del uso. Para pruebas y desarrollo basta con los requisitos mínimos; para producción se recomiendan los valores más altos.

Requisitos mínimos por nodo:

- 4 núcleos de CPU virtuales.
- 8 GB de memoria RAM.
- 100 GB de disco SSD.

Requisitos recomendados por nodo para producción:

- 8 núcleos de CPU virtuales.
- 32 GB de memoria RAM.
- 500 GB de disco NVMe.

El disco es el recurso más crítico, porque cada mensaje se guarda en él durante todo el tiempo de retención. La Parte 3 incluye una fórmula para calcular cuánto espacio necesita un clúster según su volumen de mensajes.

## Sistemas operativos soportados

Tolvak Core funciona en Linux, en arquitecturas x86_64 y ARM64, con versión de kernel 5.10 o superior. Se prueba en distribuciones basadas en Debian y en distribuciones basadas en Red Hat.

Tolvak no ofrece instalación nativa en Windows ni en macOS. En esos sistemas solo se puede ejecutar dentro de un contenedor, y esa modalidad se admite únicamente para desarrollo, no para producción.

## Red y puertos

Cada nodo necesita los cuatro puertos TCP descritos en la Parte 1, con estas reglas de acceso:

- **7710 (clientes):** debe ser accesible desde todas las aplicaciones que producen o consumen mensajes. Las conexiones usan TLS.
- **7711 (administración y Brújula):** debe ser accesible solo desde la red de administración. No debe exponerse a internet.
- **7712 (métricas):** debe ser accesible solo desde el sistema de monitoreo. Este puerto no exige autenticación, por lo que nunca debe exponerse fuera de la red interna.
- **7720 (entre nodos):** debe ser accesible solo entre los nodos del mismo clúster.

Los nodos de un mismo clúster deben estar en el mismo centro de datos, con una latencia de red entre ellos inferior a 10 milisegundos. Para conectar clústeres situados en centros de datos distintos se usa Tolvak Relay, no un clúster extendido.

## Instalación paso a paso

El procedimiento para crear un clúster de tres nodos es el siguiente.

**Paso 1. Instalar el paquete.** En cada nodo se instala el paquete `tolvak-core` desde el repositorio oficial de Lumbra Systems. El paquete instala el servicio Tolvak Core y la herramienta `tolvakctl`.

**Paso 2. Inicializar el clúster en el primer nodo.** En el primer nodo se ejecuta:

```
tolvakctl init --cluster produccion
```

Este comando crea el clúster con el nombre indicado y muestra un token de unión. El token de unión es válido durante 1 hora. Si caduca antes de unir todos los nodos, se puede generar uno nuevo con `tolvakctl token-union`.

**Paso 3. Unir el resto de los nodos.** En cada uno de los otros nodos se ejecuta:

```
tolvakctl unir --token <token-de-union> --semilla <ip-del-primer-nodo>
```

La semilla es la dirección del primer nodo, que el nuevo nodo usa para encontrar al clúster.

**Paso 4. Iniciar el servicio.** En cada nodo se inicia el servicio `tolvak-core` con el gestor de servicios del sistema.

**Paso 5. Verificar el estado.** Desde cualquier nodo se ejecuta `tolvakctl estado`. El comando debe mostrar todos los nodos con el estado "activo" y uno de ellos marcado como coordinador.

**Paso 6. Crear el usuario administrador.** Tolvak no trae ningún usuario ni contraseña por defecto. El primer administrador se crea con:

```
tolvakctl usuario crear --nombre admin --rol administrador
```

El comando pide la contraseña de forma interactiva. A partir de ese momento, ese usuario puede entrar en el panel Brújula, en `https://<ip-del-nodo>:7711`.

## Primeros pasos tras la instalación

Para comprobar que todo funciona, se puede crear un canal, publicar un mensaje y leerlo:

```
tolvakctl canal crear pedidos.nuevos --celdas 12
tolvakctl publicar pedidos.nuevos --mensaje "mensaje de prueba"
tolvakctl leer pedidos.nuevos --grupo prueba
```

Si el último comando muestra el mensaje publicado, el clúster está listo para recibir tráfico.

## El archivo de configuración

La configuración de cada nodo está en el archivo `/etc/tolvak/tolvak.conf`. El formato es de una línea por parámetro, con la forma `clave = valor`. Las líneas que empiezan con `#` son comentarios.

Estos son los parámetros principales y sus valores por defecto:

- `nodo.nombre`: nombre del nodo dentro del clúster. Por defecto, el nombre del equipo.
- `datos.directorio`: directorio donde se guardan los mensajes. Por defecto, `/var/lib/tolvak`.
- `retencion.horas`: tiempo de retención de los mensajes. Por defecto, 72 horas. Máximo, 720 horas.
- `mensaje.tamano_max_kb`: tamaño máximo de un mensaje, en kilobytes. Por defecto, 2048 (2 MB). Máximo, 16384 (16 MB).
- `canal.celdas_defecto`: número de celdas de un canal nuevo si no se indica otro. Por defecto, 6. Máximo, 256.
- `canal.autocrear`: si está activado, publicar en un canal inexistente lo crea automáticamente. Por defecto, desactivado (`false`).
- `canal.cuota_mb_s`: límite de escritura por canal, en megabytes por segundo. Por defecto, 0, que significa sin límite.
- `replicacion.factor`: número de réplicas de cada celda. Por defecto, 3.
- `consumidor.plazo_acuse_s`: plazo, en segundos, para que un consumidor envíe el acuse de recibo. Por defecto, 30.
- `snapshot.intervalo_horas`: cada cuántas horas se toma un snapshot automático. Por defecto, 6.
- `snapshot.retencion_dias`: cuántos días se conservan los snapshots. Por defecto, 14.
- `snapshot.destino`: dónde se guardan los snapshots. Por defecto, `/var/lib/tolvak/snapshots`.
- `seguridad.token_duracion_h`: duración de los tokens de acceso de los clientes, en horas. Por defecto, 24.
- `disco.umbral_rechazo_pct`: porcentaje de uso de disco a partir del cual el nodo rechaza nuevas escrituras. Por defecto, 95.
- `rebalanceo.limite_mbps`: velocidad máxima de transferencia de datos al rebalancear celdas, en megabytes por segundo. Por defecto, 50.

## Cambios de configuración en caliente

No todos los cambios requieren reiniciar el nodo. Los parámetros de retención, tamaño máximo de mensaje, cuotas y plazo de acuse se pueden aplicar sin reiniciar, con el comando:

```
tolvakctl config recargar
```

En cambio, los cambios de `datos.directorio`, de los puertos y de los certificados TLS requieren reiniciar el servicio. En un clúster, los reinicios deben hacerse de a un nodo por vez, como se explica en la Parte 3 para las actualizaciones.

## Variables de entorno

Cualquier parámetro del archivo de configuración se puede definir también mediante una variable de entorno. El nombre de la variable se forma con el prefijo `TOLVAK_`, el nombre del parámetro en mayúsculas y los puntos reemplazados por guiones bajos. Por ejemplo, el parámetro `retencion.horas` corresponde a la variable `TOLVAK_RETENCION_HORAS`.

Cuando un mismo parámetro se define en varios lugares, Tolvak aplica este orden de prioridad, de mayor a menor:

1. Opciones pasadas por línea de comandos al iniciar el servicio.
2. Variables de entorno.
3. Archivo de configuración `tolvak.conf`.
4. Valores por defecto.

Así, si `tolvak.conf` define `retencion.horas = 72` y la variable `TOLVAK_RETENCION_HORAS` vale 48, el nodo usa 48 horas.

## Seguridad inicial

Al inicializar el clúster, `tolvakctl init` genera certificados TLS autofirmados en el directorio `/etc/tolvak/certs/`. Estos certificados son válidos durante 90 días y están pensados solo para empezar a trabajar. En producción deben reemplazarse por certificados emitidos por la autoridad de certificación de la organización.

Los clientes se autentican con tokens de acceso. Cada token dura 24 horas por defecto, según el parámetro `seguridad.token_duracion_h`. Cuando un token caduca, el cliente recibe el error TVK-204 y debe obtener uno nuevo.

Se recomienda crear usuarios distintos para cada aplicación, con el rol mínimo que necesiten. Tolvak ofrece tres roles: `administrador`, que puede gestionar todo el clúster; `productor`, que solo puede publicar en los canales que se le asignen; y `consumidor`, que solo puede leer de los canales que se le asignen.
