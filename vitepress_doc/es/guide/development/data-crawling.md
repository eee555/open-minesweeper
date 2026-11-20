---
title: "Guía de extracción de datos - Open Minesweeper"
description: "Estrategia completa y sincronización incremental para la extracción de datos de repeticiones públicas, así como descarga y descompresión de archivos de repeticiones y acuerdos sobre límites de interfaz."
---

# Guía de extracción de datos

## Extracción de datos de repeticiones

Este documento explica cómo obtener datos estructurados de repeticiones públicas, así como cómo descargar y descomprimir los archivos de repeticiones. Se puede usar una solicitud GET anónima para acceder a los siguientes interfaces. Las definiciones de campos se basan en la documentación automática generada por Ninja del API.

Ambas estrategias se aplican según el contexto: para crear el primer conjunto de datos local o para sincronizar posteriormente:

- **Extracción completa**: usar `infobulk` para obtener resúmenes, y obtener métricas detalladas según necesidad mediante `detailbulk`.
- **Extracción incremental**: usar `abstractbulk` para actualizar la información del sitio web, y completar los campos de análisis faltantes mediante `staticdetailbatch`.

### Acuerdos sobre interfaces y solicitudes

Todos los siguientes interfaces devuelven un array JSON, sin barra final en la ruta.

Los navegadores pueden acceder a estas interfaces públicas mediante solicitudes GET anónimas desde cualquier origen, sin incluir credenciales de dominio cruzado. El CORS en producción está gestionado por Nginx mediante una lista blanca de APIs públicas existente, permitiendo solo solicitudes GET de dominio cruzado; las solicitudes preflight siguen usando OPTIONS; otros APIs no se abren así.

| Interfaces | Parámetros | Límite por solicitud | Contenido devuelto | Valor aproximado de la respuesta completa (JSON / gzip) | Límite actual |
| --- | --- | --- | --- | --- | --- |
| `GET /api/video/infobulk` | `first`、`count` | 2000 IDs consecutivos | Resumen de la repeticion, incluyendo jugador, estado, hora de subida y métricas principales | 453 KiB / 62 KiB | Una vez por segundo por IP |
| `GET /api/video/detailbulk` | `first`、`count` | 500 IDs consecutivos | Datos más detallados del video, incluyendo clics, estadísticas de partida y tamaño de archivo, etc. | 252 KiB / 40 KiB | Una vez por segundo por IP |
| `GET /api/video/abstractbulk` | `first`、`count` | 10000 IDs consecutivos | `id`、`player`、`upload_time`、`state` | 825 KiB / 86 KiB | Una vez por 2 segundos por IP |
| `GET /api/video/staticdetailbatch` | `ids`, números enteros positivos separados por comas | 100 IDs | Campos estables extraídos del archivo de video, incluyendo software, dificultad, tiempo, clics, estadísticas de partida y identificadores internos, etc. | 48 KiB / 7.2 KiB | Cinco veces por segundo por IP |

Tamaño de respuesta calculado a partir de un snapshot de datos locales públicos, campos actuales y nivel de compresión gzip de Django (nivel 6), asumiendo que se devuelven todos los registros completos, sin incluir encabezados HTTP; `1 KiB = 1024` bytes. El cliente debe enviar `Accept-Encoding: gzip`, y la distribución de datos afecta la tasa real de compresión.

El límite de velocidad se determina según el acceso secuencial, con un ancho de banda promedio de aproximadamente **0.5 Mb/s** comprimido (62.5 KB/s, o alrededor de 61 KiB/s) por IP. Cada interfaz establece su propia frecuencia de solicitud: según muestras completas en la tabla, el ancho de banda para llamar continuamente a `abstractbulk`, `infobulk`, `detailbulk` y `staticdetailbatch` es aproximadamente de 0.35, 0.51, 0.33 y 0.29 Mb/s respectivamente, donde `infobulk` se toma por segundo completo, ligeramente por encima del objetivo. El servidor mantiene el límite basado en el número de solicitudes y ventana de tiempo, y el ancho de banda real varía según el tamaño de respuesta.

El rango de IDs de los tres primeros servicios es `[first, first + count)`:

- El valor de `first` debe ser al menos 1; el valor de `count` debe estar entre 1 y el límite correspondiente del servicio, y si supera el límite se truncará.
- No se devuelven videos inexistente o no públicos, ni se completan con registros posteriores. Al iniciar sesión como jugador o administrador, estos servicios solo devuelven videos públicos; `abstractbulk` no incluye el campo `ongoing_tournament`.
- La siguiente página usa `first += count`, donde `count` debe ser el valor real utilizado en esta solicitud, no más allá del límite. No se debe avanzar según el número de registros devueltos o el ID máximo devuelto, de lo contrario podría producirse una solicitud repetida o una omisión de intervalos.

La tarea de extracción debe tener previamente definidos los IDs de inicio y fin para esta ronda, y la última carga debe reducirse en `count` para evitar salir del rango de tareas. Estos interfaces no devuelven el total de la página, el ID máximo ni el cursor de actualización. Un array vacío solo indica que en este rango actualmente no hay grabaciones públicas disponibles; no debe considerarse como indicio de finalización de la escaneo.

Se recomienda realizar peticiones secuenciales: `abstractbulk` debe esperar al menos 2 segundos tras cada respuesta, `infobulk` y `detailbulk` al menos 1 segundo; `staticdetailbatch` puede programarse con intervalos de 0.25 segundos. En caso de recibir un código 429 o fallo de petición, se realizarán intentos limitados y se conservará el progreso actual del rango, sin considerar el fallo como resultado nulo. La unidad de `timems` es milisegundos; los indicadores vacíos (`null`) deben conservarse como valores desconocidos y no convertirse en 0.

### Extracción completa: infobulk y detailbulk

Al crear un conjunto de datos local por primera vez o al necesitar reconstruir completamente los datos, se deben leer por rangos de IDs consecutivos:

1. Dividir en intervalos de hasta 2000 IDs, obtener mediante `infobulk` los índices y resúmenes de las grabaciones y guardarlos por `id`.
2. Si se necesitan datos detallados como clics o estadísticas de situación, dividir en intervalos de hasta 500 IDs y completar los registros locales mediante `detailbulk`.
3. Registrar el progreso solo tras un éxito en cada lote; en caso de error, continuar desde el intervalo no completado.

Ejemplo de petición:

```http
GET /api/video/infobulk?first=1&count=2000
GET /api/video/infobulk?first=2001&count=2000

GET /api/video/detailbulk?first=1&count=500
GET /api/video/detailbulk?first=501&count=500
```

Si el conjunto de datos objetivo siempre requiere indicadores detallados, se puede crear directamente el conjunto usando `detailbulk` con un rango de 500 IDs, sin necesidad de obtener previamente el resumen de la misma carga. Los conjuntos de campos de diferentes interfaces y los nombres de campos de identificación dentro de las grabaciones no son idénticos; deben adaptarse según la especificación real del esquema local.

Al descargar una instantánea de datos públicos para el entorno de prueba local, se puede utilizar el `dangerzone.download_public_data` existente. Los puntos de entrada y el modo de retransmisión interrumpida se describen en [Instantánea de datos públicos local ](./management-commands.md#本地公开数据快照).

### Extracción incremental: abstractbulk y staticdetailbatch

Una vez exista un conjunto de datos local, se deben dividir los datos en dos partes: la información del sitio, que cambia con la aprobación, el enlace de identificación y otros procesos de negocio, y los campos de análisis, que normalmente son estables y no requieren descarga repetida en cada ronda.

1. Pedir mediante `abstractbulk` con un rango de hasta 10000 IDs, y actualizar localmente los campos `player`, `upload_time` y `state` por `id`.
2. Seleccionar entre los IDs devueltos en esta respuesta aquellos que no están registrados localmente o que faltan campos de análisis objetivo. Solo el resumen no indica que todos los campos de análisis estén completos.
3. Eliminar duplicados de los IDs pendientes de completar, y procesarlos en lotes de hasta 100, obteniendo mediante `/api/video/staticdetailbatch?ids=...` los campos de análisis y combinándolos localmente por `id`.
4. Para las grabaciones ya completamente analizadas, solo se actualizarán los datos de metadatos, sin realizar nuevas peticiones para campos de análisis.

Ejemplo de petición:

```http
GET /api/video/abstractbulk?first=1&count=10000
GET /api/video/abstractbulk?first=10001&count=10000

GET /api/video/staticdetailbatch?ids=42,105,8301
```

La respuesta de análisis en lote no garantiza el orden de las peticiones originales; es necesario usar el `id` para correlacionar. Los IDs ausentes o sin acceso no se devuelven; el estado público puede cambiar entre dos peticiones, por lo que las grabaciones sin datos de análisis se mantienen para reintentar posteriormente y no se marcan como completadas.

**La sincronización incremental aún requiere escanear rangos históricos de IDs.** Solo comenzar desde el ID máximo local, lo que impide detectar cambios de aprobación o de pertenencia en grabaciones antiguas, y también omite las competencias que antes no estaban públicas pero ahora sí lo están. `abstractbulk` no tiene un parámetro de filtrado para devolver solo cambios, por lo tanto, esta actualización incremental solo complementa los datos de análisis faltantes, no solo consulta IDs nuevos.

Para mantener el conjunto actual de grabaciones públicas, usar los IDs devueltos por `abstractbulk` en el rango exitoso de esta escaneo como referencia, y marcar como no visibles localmente aquellos que ya no aparezcan en este rango. El interfaz no puede distinguir si una grabación ha sido eliminada o simplemente no está pública; los rangos fallidos no permiten eliminar los registros.

Al modificar la definición o el cálculo de los campos de análisis, se debe reconstruir localmente el conjunto de datos afectado según la nueva definición, y no se puede actualizar solo los nuevos IDs para los resultados de análisis históricos.

### Descargar archivos de grabación

Ambos interfaces de archivo solo requieren el ID de la grabación, sin necesidad de incluir el tipo de software ni la extensión:

| Interfaces | Respuesta | Límite por IP |
| --- | --- | --- |
| `GET /api/video/preview?id=123`（Recomendado） | Los archivos actualmente almacenados; los videos comprimidos devuelven MSRC, que se descomprime en el cliente, mientras que los videos no comprimidos devuelven el archivo original | 20 veces por minuto |
| `GET /api/video/download/123` | El archivo original descomprimido del backend, que se puede guardar directamente | 5 veces por minuto |

**Se recomienda descargar mediante preview y luego usar [MSRC](https://github.com/putianyi889/MSRC) en el cliente para descomprimirlo** para reducir la cantidad de datos transferidos y el costo de descompresión del servidor. Procedimiento detallado:

1. Haz una solicitud a `/api/video/preview?id=123` y lee los bytes de respuesta y la cabecera `X-Replay-Container-Version`.
2. Si la versión del contenedor es `0`, la respuesta ya es el video original y no es necesario descomprimirlo; si es un número positivo, se utiliza el interfaz de descompresión de Python o JavaScript de MSRC para recuperar los bytes originales. El algoritmo y la versión específicos se identifican automáticamente por MSRC a partir de la cabecera del archivo, sin necesidad de especificar según el tipo de software o de realizar una selección manual.
3. Obtén el nombre del archivo desde `Content-Disposition`. El nombre del archivo en MSRC es el nombre original del archivo con la extensión `.msrc`; tras descomprimirlo, se elimina la extensión final `.msrc` y se guarda con el nombre original del archivo. Ambas cabeceras permiten lectura de origen cruzado.

Se recomienda descargar de forma secuencial; tras cada respuesta de preview, espera al menos 3 segundos. Solo se debe usar download cuando sea necesario que el servidor proporcione directamente el video original: se descomprime en la solicitud y siempre devuelve una versión del contenedor `0` y el nombre original del archivo, con un límite de tráfico más estricto, y se debe esperar al menos 12 segundos tras cada respuesta.

La estructura del resumen del video, los indicadores detallados, el tamaño original del archivo (`file_size`) y el hash original del contenido no cambian debido a la compresión de almacenamiento. Los analizadores y los reproductores del sitio guardan directamente el video original ya cargado y descompresionado mediante preview, sin realizar una llamada adicional a download. Los clientes que llaman directamente a preview deben manejar ambos estados de almacenamiento; los llamadores de download siempre reciben el video original. Los interfaces de descarga de paquetes completos o individuales de partidos han sido eliminados.
