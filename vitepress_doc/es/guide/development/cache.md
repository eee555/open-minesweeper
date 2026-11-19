---
title: "Estructura del caché - Open Minesweeper"
description: "Explicación detallada de la estructura de caché de Open Minesweeper con Redis/Django, incluyendo cola de repeticiones, clasificación de jugadores y caché de partidas, así como las estructuras de datos y los flujos de lectura y escritura."
---

# Estructura del caché

Este documento registra la estructura actual de Redis/Django cache utilizada en el proyecto, así como los flujos de lectura y escritura entre el caché, la base de datos y las API. La estructura de los campos de la base de datos se basa en los archivos `models.py` de cada aplicación; aquí solo se describen las estructuras de datos reales almacenadas en el caché.

## Estado temporal del acceso con QQ

`userprofile/qqconnect/cache.py` utiliza la caché predeterminada de Django. Todas las claves llevan el prefijo `userprofile:qq:` y caducan al cabo de 600 segundos. `flow:{state}` guarda el modo, el appid, el HMAC de la sesión y el ID del usuario que vincula la cuenta. `active:{session_hmac}` y `user:{user_id}` identifican la autorización vigente. `used:{state}` marca el estado como consumido o revocado. Las claves de sesión originales quedan fuera de estos valores.

`pending:{session_hmac}` guarda temporalmente el appid y OpenID confirmados, el unionid opcional, el apodo y el avatar hasta que el usuario anónimo confirme el registro. No contiene tokens, códigos ni secretos. `registered:{state}` evita confirmaciones duplicadas. Cancelar o reiniciar elimina el registro pendiente, que también caduca automáticamente. Solo se crea la cuenta tras la confirmación. El bloqueo de la fila del usuario serializa la vinculación y la desvinculación. Eliminar la identidad revoca de inmediato la autorización en curso.

## Estado temporal de autorización de GitHub {#github-授权临时状态}

Open Minesweeper utiliza el caché predeterminado de Django (actualmente en Redis DB 1), con un tiempo de vida (TTL) de 600 segundos para todas las claves, sin almacenar tokens de acceso ni datos públicos. La clave `accountlink:github:flow:{state}` almacena el ID del usuario, el huella HMAC de la sesión y el verificador PKCE; `accountlink:github:active:{user_id}` almacena el estado más reciente del usuario, siendo reemplazado por un nuevo flujo al autorizar nuevamente. La clave `accountlink:github:used:{state}` se marca como `True` mediante `cache.add` de forma atómica para evitar que varios trabajadores procesen el mismo callback. Solo los requests que coincidan con el usuario y la sesión pueden ocupar el estado. Al revocar, el estado se marca como `revoked` y se elimina la información del flujo, pero no se elimina el puntero activo; este puntero expira naturalmente o es reemplazado por la siguiente autorización, evitando eliminar por error nuevas autorizaciones creadas en paralelo. Al eliminar una cuenta vinculada, se revoca inmediatamente con un bloqueo de fila en la fila del usuario, sin posponer hasta `on_commit`, asegurando que no se pueda restaurar la asociación si se recibe un callback posterior. El rollback conserva la asociación en la base de datos, pero no restaura el caché de autorización; el usuario debe volver a iniciar el proceso de autorización. La operación de cancelación de cuenta sin vinculación también se revoca inmediatamente. La interfaz de cancelación del frontend valida el estado, el usuario y la sesión, sin afectar a las autorizaciones más recientes. La limpieza del caché solo hace que las autorizaciones no completadas se vuelvan inválidas; el usuario puede volver a iniciar la autorización, sin afectar las asociaciones ya validadas en la base de datos.

## Credenciales de confirmación de vinculación con Saolei.wang

Acuerdo de enlace con Saolei.wang v2 utiliza el caché predeterminado de Django (actualmente la base de datos Redis 1) para almacenar credenciales temporales de confirmación, con clave `accountlink:saolei:bind:{token}`, tiempo de vida (TTL) de 24 horas. El valor es `{confirmer_id, uid, username, sync}`: representa respectivamente el ID del confirmador de esta página, el uid de Saolei.wang, el nombre de usuario de Saolei.wang en el momento de la confirmación y el interruptor de sincronización. Se escribe solo tras el éxito de la transacción de enlace; `/api/accountlink/saolei/bind/status` solo acepta las credenciales propias de este token, requiriendo que el uid de Saolei.wang sea idéntico y que el valor actual de `AccountSaolei.parent_id` siga siendo igual a `confirmer_id`. Si Saolei.wang cancela la solicitud desde su lado, se devuelve directamente pending; los enlaces históricos, los anteriores tras cambio de enlace y las solicitudes ya validadas sin credenciales no se consideran como confirmación actual. Limpiar el caché no afecta los enlaces ya existentes en la base de datos, pero las solicitudes no validadas deben reconfirmarse en la página de autorización de Open Minesweeper para generar nuevas credenciales.

## Datos de repetición y cuentas

La primera migración a Saolei.wang se ejecuta de forma secuencial mediante el comando [sync_saolei_api](./management-commands.md#sync-saolei-api). Después de la migración, se abre la sincronización manual por páginas y por elementos en el frontend; los cuentas con `AccountSaolei.auto_sync=True` (por defecto activadas) se sincronizan diariamente mediante APScheduler, actualizando hasta 50 elementos por lote, y cada hora se intenta importar hasta 100 elementos mediante una tarea de Django por ID de repetición. No se utiliza un caché especial de Redis para el progreso o tareas; el directorio y el cursor `AccountSaolei.video_sync_cursor` se comiten en la misma transacción de base de datos, y `video_update_time` solo marca que el directorio ha sido escaneado, no que todos los detalles o archivos hayan sido importados; el cursor no espera la importación de detalles o archivos, y se obtienen de forma independiente si no se completan. Los campos de historial de puntuaciones, popularidad, número de réplicas de nivel tres y punteros de tareas se eliminan junto con las cuentas antiguas, ya no se mantienen valores históricos correspondientes. Aunque se eliminan los tiempos de subida anteriores de réplicas creadas en esta plataforma y archivos duplicados, se mantienen los señales antiguas y se actualizan los cachés de clasificación; no se limpia el caché de répicas de esta plataforma para reconstruir el directorio de origen.

Los claves `saolei:throttle:data` y `saolei:throttle:download` son puntos de control superior compartidos entre páginas, workers y comandos, almacenan solo el valor constante `1`, se ocupan de forma atómica mediante Redis `SET NX PX`, y caducan automáticamente después de 2100ms y 400ms respectivamente. No almacenan datos de usuario ni claves. Los clientes compiten por el mismo límite, con un máximo de 6 segundos de espera; no se deben borrar manualmente mientras estén en uso.

El servicio `SaoleiApiVideo` no almacena direcciones de archivos de video ni tiene una caché separada de URLs: el upstream ya no devuelve `fileUrl`, y la importación utiliza directamente `remote_id` para solicitar `https://saolei.wang/video/download/{id}`, y el nombre del archivo se obtiene del campo `Content-Disposition` de la respuesta de descarga. Solo se mantienen los metadatos de directorios y detalles en lotes; si un detalle está faltante, se conserva la información previa. En fases de importación automática y comandos de videos, no se hacen solicitudes repetidas de detalles; al importar manualmente una entrada desde el frontend, se obtiene primero el detalle más reciente de esa entrada.

El estado `SaoleiApiVideo.import_rejected` persiste en la base de datos los resultados de rechazo directo de verificación de archivos de esta página, sin usar caché. Se escribe de forma independiente tras el rollback de la transacción de importación; en fases posteriores de sincronización, se salta la solicitud de detalles y descarga del archivo, y el refresco del directorio así como el modo `--full` no eliminan este marcador. Cuando se requiere un reintentar manualmente, el administrador debe eliminarlo desde el shell de Django; en caso de fallos no relacionados con archivos (red, upstream, otros), no se establece el marcador, y se continúa intentando la importación desde la fuente local no completada.

Los campos de análisis de video ahora se almacenan en IndexedDB del frontend por ID. Las consultas normales devuelven el ID y los campos dinámicos del sitio, y se completan en lote; cuando cambian las definiciones de campos, se incrementa la versión de `CACHE_STORE_DEFINITIONS['video-info'].version` junto con la actualización del frontend, y se vacía toda la tabla de video al cargar una nueva versión del frontend. Los interfaces y cambios en Redis no requieren el envío de versión. La tabla de campos antes y después de los cambios se encuentra en el repositorio `front_end/src/services/videoService.md`. Después de la implementación, se debe ejecutar [compact_video_cache](./management-commands.md#compact-video-cache) para comprimir los datos existentes.

La lógica de lectura y escritura de los antiguos rankings de velocidad y noticias se ha eliminado. Se puede ejecutar `python manage.py delete_legacy_speedranking_cache` para eliminar los hashes de registros personales, los conjuntos de rankings y la cola `news_queue`. Se soporta el modo `--dry-run` para una vista previa, el rango exacto se encuentra en [la documentación de comandos de gestión](./management-commands.md#delete-legacy-speedranking-cache).

El número de videos y el espacio de archivos de `UserMS` se almacenan en la base de datos, sin clasificación por nivel, modo o NF, ni se involucra la limpieza de Redis. Al crear se clasifica por `ongoing_tournament`; durante el cálculo completo, los videos asociados a `ongoing_tournament=True` o a cualquier competencia se cuentan como parte de la métrica de competencia, incluyendo videos públicos y finalizados. Si un video está asociado a múltiples competencias, se cuenta solo una vez. El espacio se calcula sumando el tamaño real almacenado en `VideoModel.stored_file_size`, con valores nulos devolviendo el tamaño original `file_size`, en bytes; para videos comprimidos, se cuenta el tamaño comprimido.

| Métrica | Campo de cantidad | Campo de espacio de archivo |
| --- | --- | --- |
| Videos no de competencia | `video_num_total` | `video_size_total` |
| Videos de competencia | `video_num_tournament` | `video_size_tournament` |
| Todos los videos | `video_num_all` | `video_size_all` |

Los dos campos `*_all` son persistentes `GeneratedField`, calculados por la base de datos como la suma de los valores de partida y no partida, y no se escriben directamente. El límite de subida `video_num_limit` se mantiene independientemente, y la verificación del límite continúa utilizando el número no de partida `video_num_total`.

Al eliminar un `UserProfile`, el señal `userprofile.signals.delete_user_ms` elimina de forma interna el `UserMS` asociado mediante el `userms_id` real, y su `Identifier` se elimina por cascada de clave externa. Ambos, instancia y QuerySet, se aplican correctamente; la cascada iniciada desde `UserMS` utiliza el recolector original de eliminación para evitar la limpieza duplicada. Los `UserMS` históricos sin usuarios asociados pueden ser limpiados en bloques mediante el comando [cleanup_orphan_userms](./management-commands.md#cleanup-orphan-userms); este comando no modifica Redis, y los registros ya asociados se conservan.

Los cuentos commemorativos no tienen caché especial; los datos antiguos y los residuos de Redis se eliminan mediante herramientas existentes del administrador en el servidor, especialmente no se debe olvidar la eliminación del snapshot de `newest_queue` tras borrar grabaciones normales. Los nombres y las imágenes públicos siguen el ciclo de actualización existente y no se fuerzan a vencer al iniciar el sitio; la columna `is_memorial` en la fila de caché tiene valor predeterminado false, y otros navegadores pueden mostrar temporalmente el nombre antiguo antes de la actualización normal. Las reglas de registro y de complemento de grabaciones se encuentran en `back_end/saolei/userprofile/README.md`.

La página de base de datos de usuarios `/database/users` lee directamente la base de datos mediante `GET /api/userprofile/query`, sin usar el caché IndexedDB de perfiles de usuarios: los cambios en el conteo de grabaciones no actualizan `UserProfile.date_updated`. Las consultas se centran en `common.services`, y cada página no vacía realiza tres consultas: conteo, usuarios y estadísticas, así como el ID verificado actual de la página. Se utiliza un índice compuesto `AccountLinkQueue(platform, identifier)` para consultas precisas por ID de plataforma, y un índice de clave externa para lecturas en bloques tras paginación. El uso de la interfaz se describe en el repositorio `back_end/saolei/userprofile/README.md`.

La autenticación del jugador se cambia a una tabla de aristas dirigidas `UserVerifyEdge`: la restricción única `(from_user, to_user)` evita aristas repetidas en la misma dirección, y los dos índices de claves externas permiten buscar aristas de entrada y salida, permitiendo múltiples aristas de entrada, salida y ciclos. La estructura del grafo y el estado de los nodos se leen directamente de la base de datos, sin almacenar en Redis; las tres clases de escrituras (autenticación normal activa, configuración de administrador de `verified`, y actualización completa por parte del administrador) se completan en una sola transacción de base de datos, y el caché de datos públicos sigue el ciclo normal de expiración según `infoupdated`; la respuesta personal proporciona identificación real y `verified`, y el frontend `UserProfile.canSubmitReplays` calcula inmediatamente según el ID de usuario válido, identificación real o autenticación, sin almacenar el estado de acceso. Los interfaces de subida y de competencia siguen validando el acceso real por separado. Redis solo almacena dos claves de corto tiempo (prefijo `userprofile:verification:`): el estado de sesión del administrador y un bloqueo de escritura en serie. La sesión se recupera automáticamente al vencerse, se libera inmediatamente al finalizar o al enviar un lote, y desaparece al reiniciar Redis, con el servicio tratado como inactivo; el bloqueo tiene TTL y se libera automáticamente si el proceso se cierra anormalmente. La lectura del estado de sesión es una operación de lectura sin bloqueo; los datos expirados o dañados se consideran directamente como «no activado», y no se eliminan en el camino de lectura (de lo contrario podría eliminar una sesión creada después de la lectura), dejando el resto para la limpieza por TTL; la eliminación activa se realiza solo en los procesos de finalización o envío que posean el bloqueo de escritura. Las reglas se describen en el repositorio `back_end/saolei/userprofile/PLAYER_VERIFICATION_PLAN.md`.

La lógica de complemento y el comportamiento de recálculo retrasado se mantiene igual: los cambios en la asociación de competencias no ajustan inmediatamente las estadísticas. Las eliminaciones, cambios de tamaño de archivo y cambios de pertenencia del jugador se clasifican según la competencia actual de la grabación, permitiendo desviaciones respecto al criterio original, y se corriguen mediante [refresh_video_counts](./management-commands.md#refresh-video-counts) en un recálculo completo; no se guardan campos históricos de clasificación. Después de la migración, se debe ejecutar el comando de recálculo para completar las estadísticas históricas.

Los valores de cantidad, espacio de archivo y el límite de subida a aumentar se combinan en una sola actualización `UserMS UPDATE`; los cambios de pertenencia se gestionan mediante una sola instrucción `CASE WHEN UPDATE` que afecta a dos jugadores. Al cambiar manualmente el tamaño almacenado de `stored_file_size`, se envía inmediatamente un evento `video_storage_changed`, se consulta solo la competencia actual de la grabación y se actualiza el criterio según la diferencia de tamaño de almacenamiento, sin recalcular todas las grabaciones del usuario ni modificar el tamaño original `file_size`. Todos los campos estadísticos usan nombres fijos y ramas `if/else`, sin concatenación dinámica. Después de implementar esta modificación del criterio estadístico, se debe ejecutar una vez `refresh_video_counts` para corregir las estadísticas existentes.

La página de monitoreo del mundo anterior y la recolección de CPU/network IO han sido eliminadas; ya no se leen ni se escriben muestras históricas. Los antiguos endpoints `/monitor/io_cpus/` y `/monitor/capacity/` no se restaurarán. Después de desplegar y detener los procesos antiguos de recolección, se puede limpiar de forma directa los cinco claves heredadas en la base de datos Redis `saolei_website` mediante nombres fijos, sin necesidad de recorrer otras claves.

```bash
redis-cli -n 0 DEL io_s_old io_r_old io_s_spds io_r_spds cpus
```

La extracción del sitio antiguo de Saolei.wang y la lista de fuentes antiguas, así como las consultas de estadísticas, han sido desactivadas; se mantiene la asociación de cuentas. En la primera fase, solo los comandos de administración usarán la nueva estructura de fuentes para sincronizar directorios e importar archivos; las tareas antiguas no accederán a sitios externos ni escribirán datos de negocio. El acceso específico se encuentra en el repositorio `back_end/saolei/accountlink/README.md`.

## Clasificación de obras

El repositorio de GitHub utiliza `Media.format='g_r'`, y `suffix` almacena la cadena de identificador numérico del repositorio. Se continúa utilizando los cuatro ZSET originales, así como los procesos de revisión y alimentación, sin añadir cachés, tareas ni planificadores. `MediaOut` devuelve `format` y `suffix`, ya no devuelve `url` ni `embed_url`: los enlaces comunes y las direcciones de incorporación de Bilibili se generan en el frontend, y la página principal de GitHub se consulta directamente por el navegador según necesidad, sin almacenarse en caché persistente en este sitio.

Página de obras con calor real time / clasificación por acumulación de alimentación y página de clasificaciones del tablero 'Obras' utiliza cinco claves Redis fijas (base de datos `saolei_website`): `media:rank:hot`, `media:rank:likes` son zset de dimensión obra, `media:rank:user:hot`, `media:rank:user:likes` son zset de dimensión autor acumulados, `media:hot:anchor` almacena el umbral de calor en el lado de Redis `T_r` (ISO 8601 UTC). Los cuatro zset no tienen TTL, solo `verified` indica que una obra ha entrado en la clasificación; `pending` permite alimentar obras pero solo escribe en la base de datos, y cuando es aprobada se completa con el valor actual de la base de datos. La página de obras se ordena por fecha de publicación (originalmente el tablero 'Últimas') y se consulta directamente en la base de datos; las obras pendientes de revisión no tienen acceso en la página de obras, solo se ven en la página personal y en el panel de administración. Las cinco claves fijas ya están incluidas en el conjunto fijo de estadísticas de memoria del monitoreo del servidor, **no hay claves de bloqueo temporales**.

La popularidad utiliza dos referencias (ver explicación de mantenimiento en `back_end/saolei/media/README.md`): `T_db` es el valor unificado completo de `Media.hot_value_updated_at`, y todos los datos de la base de datos de `hot_value` se basan en él; `T_r` contiene `media:hot:anchor`, y las puntuaciones de calor de los cuatro zset se basan en él. Ambos sistemas son internamente coherentes, no requieren ser iguales, y difieren por un factor común `decay(T_db, T_r)`, manteniendo el mismo orden. Cuando `T_r` esté ausente, la primera lectura o escritura se inicializa con `T_db` usando `SET NX`; `likes` no disminuye. La respuesta de paginación de obras devuelve `T_db`, y los campos de las obras y la popularidad en tiempo real se basan en la base de datos; la respuesta de la lista de autores devuelve `T_r` y el valor original del zset, que se calcula en el frontend según `0.99 ** ((now - T_r) / 1 天)`; no se pueden mezclar los puntos de referencia de ambos casos.

**Las escrituras se completan durante la solicitud**. Dar rubíes (solo a obras `verified`), aprobar una obra, enviarla o eliminarla definitivamente como propietario del sitio llama a `services.sync_media_scores()` después de confirmar la transacción. Se vuelve a consultar la base de datos para obtener las puntuaciones absolutas de todas las obras `verified` de ese autor. Después, `cache.set_media_scores()` actualiza los cuatro conjuntos ordenados con un único `pipeline(transaction=True)` explícito (usa `ZREM` si la obra ya no existe). El cliente Redis usado durante la solicitud tiene un tiempo de espera de 1 segundo (`MEDIA_SOCKET_TIMEOUT`, frente a los 5 segundos de la conexión de caché en producción) para respetar el límite de 2 segundos de la pasarela de las API ordinarias. Los errores de Redis se registran en el log de errores de `media`. No se deshace la transacción ya confirmada, no se encolan tareas y no se reintenta la escritura. Las discrepancias restantes se corrigen con el comando de administración periódico. `MULTI/EXEC` no revierte los cambios: una excepción no garantiza que la escritura no se haya realizado. Se escriben valores absolutos con `ZADD`, en lugar de incrementarlos con `ZINCRBY`, para evitar acumular puntos dos veces si las respuestas se retrasan, llegan desordenadas o se pierden. No se usan `media:cache:lock`, `WATCH`, `ZUNIONSTORE`, señales de modelo ni callbacks de `on_commit`.

Hay que adelantar `T` de vez en cuando para que el crecimiento exponencial de `1 / decay(T, now)` no provoque un desbordamiento de coma flotante. Ya no hay una tarea mensual: se eliminaron la tarea `refresh_media_hot_reference` de APScheduler, la sincronización de contenidos en segundo plano, la configuración de limpieza de tareas y el servicio de reinicio de tareas. Ejecuta manualmente [refresh_media_rankings](./management-commands.md#refresh-media-rankings) a intervalos largos. Con `--reference`, una transacción de base de datos usa `F()` para multiplicar todos los valores de `hot_value` por `decay(T_db_old, T_new)` y guardar el nuevo `T_db`. Después se recalculan los cuatro conjuntos ordenados y se publican de forma atómica junto con `T_r`. La opción `--rebuild-only` solo corrige desviaciones. La opción `--check` realiza una comprobación de solo lectura: calcula las puntuaciones esperadas a partir de la base de datos con `decay(T_db, T_r)` y devuelve un código de salida distinto de cero si detecta una desviación o falta `T_r`. Puede incorporarse a una comprobación periódica externa. El comando se ejecuta fuera del despliegue, sin adquirir bloqueos ni impedir las escrituras de las solicitudes. Durante su ejecución, `rename` puede sobrescribir actualizaciones incrementales de las claves activas y causar una desviación temporal. Los datos de la base siguen siendo correctos y basta con repetir el comando para recuperar la coherencia.

La rechazo solo ocurre en `pending`, nunca entra en la clasificación, no es necesario retroceder. La reconstrucción completa solo lee la línea `verified`, escribe en la clave temporal `media:rebuild:*` y, en una sola ejecución de `MULTI/EXEC`, actualiza los cuatro conjuntos formales `rename` y publica `T_r`; en caso de error, se mantiene la clasificación anterior y se lanza `CommandError`, indicando que `T_db` ya es el valor oficial, se debe volver a ejecutar el comando. Cuando hay retraso en el caché, se realiza manualmente la acción de `--rebuild-only` para restaurarlo.

## Snapshot de monitoreo del servidor {#服务器监控快照}

La solicitud `GET /api/monitor/summary` devuelve una vez `{videosummary, tasksummary, diskusage, memoryusage}`, y la página del servidor frontal la solicita solo una vez, luego la distribuye entre las tarjetas. Cuando se inicia el trabajo `refresh_monitor_snapshot` de APScheduler, se ejecuta inmediatamente, y posteriormente cada 5 minutos se reutiliza la función de recolección de `monitor/services.py` para publicar el JSON de monitoreo. En entornos de desarrollo se escribe por defecto en `BASE_DIR/runtime/monitor.json`; en entornos de producción se escribe en `runtime/monitor.json` al mismo nivel que `STATIC_ROOT`, separado del directorio de código fuente. En producción, Nginx proporciona directamente el archivo; en entornos locales, el interfaz Ninja solo lee el archivo y no realiza recolección en las solicitudes. Si el archivo no existe, se devuelve un código 503.

Los tres primeros ítems mantienen los campos estadísticos originales, añadiendo la marca UTC `sampled_at`; `memoryusage` incluye tanto `memory` como `redis`, cada uno conservando su momento de muestreo. Los ítems que fallan en la primera recolección se establecen como `null`; los bloques de memoria siguen usando la estructura `unavailable` descrita a continuación. Si un ítem falla posteriormente, se conserva su resultado anterior exitoso y su hora original, mientras que los demás se actualizan normalmente. Los dos bloques de memoria también conservan independientemente sus muestras anteriores. Al leer el momento de muestreo se puede determinar si el cronograma se detuvo o falló continuamente, lo que indica que los datos han expirado.

Antes de la publicación, se valida según `monitor/schema.py`, se escribe un archivo temporal completo en el mismo directorio, y luego se usa `os.replace` para reemplazarlo de forma atómica; si falla, no se daña el archivo oficial. Nginx establece el tipo JSON, `Cache-Control: no-cache` y `open_file_cache off` para el camino preciso, evitando que se continúe usando el descriptor de archivo antiguo tras el reemplazo; el límite de solicitudes se maneja por Nginx. El directorio debe ser accesible, y el archivo se publica con permisos 0644, asegurando que los workers de Nginx puedan leerlo. Si cambia la ruta de despliegue, se debe actualizar también `default.conf`; se puede sobrescribir la ruta de muestreo y lectura mediante `MONITOR_SNAPSHOT_PATH`.

La muestra y el `alias` de Nginx deben apuntar al mismo archivo. Si se actualiza solo el código sin sincronizar la configuración real de Nginx o si ambos usan rutas diferentes, incluso si el registro de muestreo indica éxito, las solicitudes podrían devolver 503. `start.sh` despliega `default.conf` y recarga Nginx; al desplegar manualmente, se debe sincronizar la configuración, ejecutar `nginx -t` para verificar que sea correcta y luego recargar.

Los cuatro interfaces independientes de monitoreo antiguos y el caché de resultados de Redis se han eliminado; los claves de resultados antiguos caducarán automáticamente con un TTL de 300 segundos. En la página de tareas del administrador se utiliza una solicitud independiente a `GET /api/common/tasks/summary`, accesible solo para administradores, que consulta directamente la base de datos sin leer el snapshot; eliminar tareas, reiniciar o limpiar no desencadenan el cálculo completo de los datos de monitoreo. En primeras instalaciones o durante pruebas locales, se puede ejecutar [refresh_monitor_snapshot](./management-commands.md#refresh-monitor-snapshot) para generar manualmente los archivos, luego reiniciar APScheduler, verificar y volver a cargar Nginx.

### Métricas de recolección en memoria

Cada bloque incluye `status`, fecha UTC `sampled_at`, código de error fijo `reason`, un entero no negativo `total_bytes` y una clasificación fija `groups`. Los procesos se agrupan por uWSGI (incluyendo master/workers), el proyecto APScheduler, Redis, MySQL, db_worker y otros procesos. En Linux se recopila uniformemente PSS; en otras plataformas se usa RSS; el RSS puede contabilizar repetidamente páginas compartidas. El total solo cubre la memoria residencial de los procesos; la memoria total o disponible del host se almacena en `memory.host` y no está incluida en el total general del gráfico. Para el proceso del servicio Redis local se agrupa por nombre del proceso o nombre del ejecutable; cuando las configuraciones de conexión a Redis o MySQL son remotas o conocidas por aislamiento en contenedores, el bloque de procesos devuelve un rango insuficiente.

La clasificación de Redis solo lee las claves de base de datos DB 0 determinadas directamente por el código de negocio, sin ejecutar `SCAN`, `scan_iter`, `KEYS` ni enumeración de miembros de los rankings:

| Clasificación | Origen de la clave |
| --- | --- |
| Clasificación de marcas personales (PB) | `PBRankingCache.counts_key`; se construyen claves de pequeños rankings mediante `HKEYS` de un hash verificado; se generan claves de hash de usuarios tomando los IDs en orden de la clave principal de `UserProfile`, en lotes de hasta 1.000 IDs por lote. Las clasificaciones derivadas de PB también se generan mediante `PBDerivedCache().keys()` enumerando 3 hashes de puntuaciones y 132 claves de pequeños rankings, todas incluidas en la clasificación `pb_rankings`. Si falta metadatos, no se detectan claves ni se desencadena reconstrucción. |
| Otras clasificaciones | `SpeedRankingCache(name, stats=RANK_STATS).keys` para Saolei.wang y Sin azar estricto (dos clasificaciones por modalidad, 36 claves en total), `TopRankingCache().keys`, `ThrpRankingCache().keys`, `NFIOERankingCache().keys`, `TPERankingCache().keys`, `MiniGameRankingCache().keys`, `MEDIA_CACHE_KEYS` (cinco claves de estadísticas de medios), las claves de clasificación y detalle de las cuatro configuraciones personalizadas de pluck, la clave de clasificación de jugadores en torneos y la clave de tiempo de puntuación. En total se cuentan 197 claves. |
| Última repetición | `newest_cache.key`（`newest_queue`）。 |
| Otros | La diferencia entre `INFO memory.used_memory` y las tres categorías anteriores; incluye métricas de otros negocios, sesiones, caché compartido de base de datos en el mismo instante (DB 1), claves aisladas/históricas/temporales y gasto de Redis, sin enumerar DB 1. |

Todos los claves conocidas se eliminan duplicados y se ejecutan en lotes de hasta 100 claves con `pipeline(transaction=False)` usando `MEMORY USAGE ... SAMPLES 5`; las claves que no existen se consideran 0. Este resultado es una estimación, `redis.estimated=true`, `redis.samples=5`; el total corresponde al valor de `used_memory` del instante, distinto del RSS/PSS de los procesos. Si la suma de las categorías supera el total del instante, no se publica la distribución. Se comparten 5 segundos de presupuesto de recolección colaborativa entre dos bloques, además se limita a un máximo de 5.000 procesos y 50.000 claves; los sockets o consultas bloqueadas siguen siendo controladas por sus propios tiempos de espera, por lo que 5 segundos no es un límite rígido.

Los PIDs que terminan durante la recolección de procesos se omiten; si un proceso vivo tiene permisos insuficientes, el bloque completo no está disponible y se registra el número en `memory.unreadable_processes`, no se considera cero. El tiempo, el total y la clasificación de bloques inactivos son `null`, mientras que el otro bloque puede tener éxito independientemente; si ya hay muestras exitosas, el emisor conserva el valor y el tiempo anteriores. Los registros del recolector solo incluyen razones de seguridad, tiempo y cantidad, sin registrar PIDs, líneas de comando, nombres de clave o valores de negocio. Antes de poner en producción, se debe verificar con usuarios reales de APScheduler los permisos de Linux en `/proc` y realizar revisiones aleatorias del tiempo de recolección, resultados de Redis y tiempos de actualización de archivos. Cuando un pedido HTTP falla, el frontend continúa mostrando el resultado de la última ejecución exitosa de la página actual.

## Vista general

### Juegos pequeños `minigame`

Cada lista de whitelist utiliza el ZSET `minigame:rank:v1:{ranking_key}` (ID de jugador → número entero original en milisegundos), el Hash `minigame:detail:v1:{ranking_key}` (ID de jugador → `{score, achieved_at}` en formato JSON) y la cadena `minigame:ready:v1:{ranking_key}` (valor `1` indica que la lista ha sido inicializada completamente). Los 29 rankings tienen un total de 87 claves fijas, todas sin TTL, y se incluyen en el conteo de memoria del servidor. Los nuevos rankings para la práctica de reacción añaden seis listas, reutilizando la misma estructura de claves, lógica de inicialización y reconstrucción.

Las peticiones por categorías devuelven una vez las columnas de botón izquierdo o múltiples dedos (9 columnas), marcado doble (2 columnas) o sin mina (3 columnas), ordenadas por cualquier columna dentro del grupo. Al estar inicializado, se leen dos veces con pipeline las marcas, el número de jugadores, la posición de los jugadores en la página y los detalles de todas las columnas, sin consultar el registro de puntuaciones. Las listas vacías también guardan la marca de inicialización; una sola subida no establece la marca. Cuando no está inicializado, se carga la lista completa desde la base de datos; en caso de fallo en Redis, toda la petición se vuelve a cargar desde la base de datos.

En la página de juegos pequeños, el panel de clasificaciones solo lee los primeros 20 jugadores de la página seleccionada y la posición del usuario conectado, reutiliza las claves mencionadas anteriormente, sin inicializar otros rankings del grupo ni añadir nuevas claves de caché. Las respuestas que incluyen la posición personal no pueden compartirse en caché; los detalles del interfaz se describen en el README del backend.

Al crear un nuevo registro o mejorar estrictamente un resultado, se escribe el ZSET y el Hash mediante `on_commit`. Al eliminar un resultado, se elimina el miembro y se conserva la marca de inicialización. Los administradores al eliminar un registro o una repetición en 'Registros de juegos pequeños' también usan esta señal, sin afectar el caché de otras configuraciones. Se aceptan sobrescripciones accidentales por paralelismo o reconstrucción; se puede restaurar el caché ejecutando `manage.py rebuild_minigame_ranks [--ranking-key key]`, sin modificar los resultados en la base de datos. La interfaz completa y los criterios de decisión se describen en `back_end/saolei/minigame/README.md`.

El archivo comprimido 7z del mejor resultado se almacena solo en el campo BinaryField `MiniGameBestScore.replay_archive`, sin entrar en Redis. Durante la reconstrucción del caché o la sincronización con la base de datos de clasificaciones, se excluye el campo de archivo de repetición mediante `defer('replay_archive')`.

### Nombre del usuario y privacidad

La columna del nombre en el frontend `user-info` es directamente compatible con la marca de ocultamiento `hidden`, sin necesidad de ajustar la versión de la base de datos ni de verificar el intervalo. Una vez que se guardan los datos, `invalidateUserInfo(id)` elimina el caché local del usuario y notifica a los `PlayerName` ya montados para que releer el nombre público; las respuestas emitidas antes de la expiración no se escriben con valores antiguos. Si falla la eliminación del caché, no afecta las configuraciones ya guardadas, se salta el caché anterior del usuario y se reinicia el tiempo de verificación para intentarlo nuevamente. Los cambios en la calificación o en el estado de ocultamiento actualizan `date_updated`, mientras que otros navegadores siguen actualizando normalmente mediante el proceso existente `infoupdated`. El ranking en Redis sigue solo referenciando el ID del usuario. El proceso de caché se describe en el repositorio `front_end/src/services/userService.md`; los acuerdos sobre autorización, visualización y migración se detallan en `back_end/saolei/userprofile/README.md`.

El script de inicialización local independiente `dangerzone/init_local_test.py` vaciará el banco de datos local `saolei_website` de Redis (incluyendo sesiones) y reconstruirá el ranking de velocidad (listas normales de NF en Saolei.wang, listas normales de NF en fuerte sin pistas, listas PB normales de NF, listas PB derivadas de los tres grandes, los dieciocho ítems top y los puntos de referencia), el ranking de eficiencia Thrp, el caché de registros de pluck y la cola de estado de las repeticiones. La lista de PB derivada se reconstruirá al final de `rebuild_pb_ranks` sin escanear de forma independiente la tabla de repeticiones. Se inicia en el directorio `back_end/saolei` usando `python -m dangerzone.init_local_test`. Solo se permite la configuración de pruebas locales y se rechaza cualquier entorno con la marca `.production`; no se registra el comando de gestión `import_public_data`. Más detalles y limitaciones de datos ausentes en [Snapshot de datos públicos locales ](./management-commands.md#本地公开数据快照).]

### Gestión de identidades

La página de identificación de la base de datos solo permite a los usuarios normales consultar identificadores con `safe=True`; los administradores pueden consultar todos los identificadores y acceder al campo `safe`. Los administradores establecen el estado de seguridad mediante `POST /api/identifier/safe` y asignan un usuario mediante `POST /api/identifier/bind`. El valor `id=0` indica desasociación y conservación del registro de identificador. Los identificadores ya asociados deben desasociarse antes de establecerse como no seguros.

La asignación y desasignación usan `identifier.services`, sincronizando actualizaciones en la lista de identificadores del usuario, el estado de revisión de las repeticiones, la cola de repeticiones más recientes y la clasificación. Los métodos antiguos de administrador para añadir, eliminar o desasociar identificadores, así como para aprobarlos, han sido reemplazados por los dos APIs Ninja mencionados anteriormente; el acceso para los usuarios normales a gestionar sus propios identificadores se mantiene sin cambios.

### Nueva clasificación de velocidad `speedranking`

Saolei.wang regula las reglas de uso con el hash `speedranking:{ranking_name}:records` para guardar los registros personales, utiliza el zset `speedranking:{ranking_name}:{stat}` para guardar los índices de clasificación con el id del jugador como miembro, gestionado por `speedranking.saolei.cache.SpeedRankingCache`. PB es una excepción general: cada `(普通/NF, level, bv)` tiene un zset, y cada usuario tiene un hash que incluye el tiempo, el id de la repetición y el rank, gestionado por `speedranking.pb.cache.PBRankingCache`.

La capa de caché compartida proporciona conexiones y pipelines; los servicios de Saolei.wang, PB y top se encuentran en subdirectorios correspondientes. Una actualización o cada segmento de procesamiento lee conjuntamente los registros de usuarios, toma decisiones independientes y escribe conjuntamente; las consultas de PB sobre puntuaciones antiguas, la actualización de las pequeñas clasificaciones y la actualización del punto de referencia del top dependen de fases posteriores basadas en resultados previos. Los casos que requieran complementación se resuelven según las reglas de cada clasificación.

El top está gestionado por `speedranking.top.cache.TopRankingCache`, y contiene los cinco primeros detalles de usuario, dieciocho índices originales, nueve índices de habilidad suave/LSF y el punto de referencia. La estructura de caché, la publicación en segundo plano y el acceso en entornos locales, así como el snapshot inicial del frontend, se definen de forma uniforme en `back_end/saolei/speedranking/README.md`. Durante la implementación o actualización, se debe ejecutar el comando [de reconstrucción del top](./management-commands.md#rebuild-top-ranks) y no se debe mezclar con el código antiguo de puntuaciones.

Los acuerdos sobre codificación de clasificación, precisión, rango numérico, actualización de registros y actualización de caché se mantienen unificadamente en el archivo `back_end/saolei/speedranking/README.md` del repositorio, sin repetirlos aquí. El uso del comando de reconstrucción se describe en [los comandos de gestión](./management-commands.md#rebuild-speed-ranks).

Los interfaces de solo lectura de PB no se actualizan automáticamente; el procedimiento de inicialización y reparación se describe en el comando [de reconstrucción de PB](./management-commands.md#rebuild-pb-ranks). La página de clasificación de PB en el frontend ya está implementada; el tiempo de carga paginado se obtiene directamente a partir de la decodificación del score del zset, sin necesidad de agregar campos de consulta o hash.

PB también utiliza el hash `speedranking:pb:counts` para resumir el número de participantes en cada subclasificación, que puede ser leído de forma única mediante `GET /api/speedranking/pb/counts`, y se actualiza de forma sincronizada con el cambio de puesto; el frontend lo utiliza para mostrar el número de participantes en la cuadrícula. Los registros existentes se completan mediante el comando de reconstrucción de PB. Los campos específicos y acuerdos sobre clasificaciones vacías se detallan en el README de la aplicación.

Las clasificaciones derivadas de PB se gestionan con `speedranking.pb_derived.cache.PBDerivedCache`. Tres hashes `speedranking:pb_derived:{collection|skill|typical_time}:records` guardan todos los resultados derivados de cada usuario. Cada uno de los 132 conjuntos ordenados `speedranking:pb_derived:{ranking}:{field}` mantiene un índice de usuarios para ese criterio. El cliente y el servidor definen sus tramos por separado en el código, sin número de versión ni clave de versión en Redis. Las clasificaciones derivadas comparten con la clasificación PB original la misma secuencia de lecturas y escrituras en pipeline de `sync_video` / `_update_videos`, tanto para operaciones individuales como por lotes. De las tres consultas HMGET, la fuerza por tramo del hash `skill` es imprescindible para calcular el tiempo típico por tramo y su variación. Si falta, se recalculan todos los resultados afectados por esa operación. En las actualizaciones habituales se parte de los resultados anteriores y solo se suma o resta la contribución de los grupos de PB modificados. Las tres columnas de colección y la fuerza por tramo o nivel se actualizan linealmente con `ΔW = p_l[v] * ΔBvs`. Para el tiempo típico se deduce `W_I` de la fuerza del tramo, se recalcula su tiempo y se añade la diferencia al total. Solo se escriben los hashes y los conjuntos ordenados que han cambiado, sin almacenar valores intermedios ni recalcular las 132 métricas. Se acepta el error acumulado por sumas y restas en doble precisión, salvo cuando la contribución del tramo vuelve a cero: hay que fijarla exactamente en cero, restablecer el tiempo típico a `999.999` segundos y aplicar la diferencia al total. De lo contrario, dividir por el residuo de coma flotante (`H_I / 浮点残差`) produce cifras enormes que contaminan los totales posteriores. Si solo cambian el ID de la repetición o la fecha de subida y se conservan el BV y el tiempo, los índices no se actualizan. Si falta el hash de resultados o no coincide la categoría, se hace un recálculo completo para ese cambio. Los usuarios cuyos PB no cambian no se reparan automáticamente. Actualizar los puestos de PB, las instantáneas de noticias o los valores de referencia de la clasificación top no desencadena otro recálculo de los resultados derivados. Las API de lectura no recorren la base de datos ni reconstruyen la caché. Si cambian los tramos o la tabla de frecuencias, los resultados conservan el criterio anterior hasta que se reconstruya toda la clasificación con `rebuild_pb_derived_ranks`. Las entradas ausentes se recuperan mediante una reparación individual del administrador o una reconstrucción completa. Consulta las fórmulas y las claves en `back_end/saolei/speedranking/pb_derived/README.md`.

En la pestaña 'Reconstrucción de registros de clasificación' de la página de administrador, se puede reparar el caché individualmente por gran lista, pequeña lista o ID de usuario; el método correspondiente es `POST /api/speedranking/admin/rebuild_record`; los detalles sobre el alcance específico y los acuerdos de concurrencia se describen en el README anterior.

### Ranking de eficiencia `effranking`

Thrp utiliza un hash de récords personales y cinco conjuntos ordenados. NF IOE tiene su propio hash y cuatro conjuntos ordenados. TPE, TPE2 y TPE3 comparten un hash y nueve conjuntos ordenados. La tabla siguiente describe las claves. Las reglas de codificación, selección de récords y delimitación de las transacciones se detallan en `back_end/saolei/effranking/README.md`. Tras el primer despliegue o la pérdida de la caché, ejecuta [rebuild_eff_ranks](./management-commands.md#rebuild-eff-ranks) para la clasificación afectada. Las consultas no reconstruyen la caché.

La inicialización del snapshot público local se reconstruye explícitamente para estos tres grandes rankings de eficiencia.

```dot
digraph cache {
    graph [
        layout=neato,
        model=subset,
        overlap=prism,
        splines=true,
        outputorder=edgesfirst,
        bgcolor="transparent",
        start=7
    ];

    node [
        shape=box,
        style="rounded,filled",
        fillcolor="${#f8fafc|#1f2937}",
        color="${#94a3b8|#64748b}",
        fontcolor="${#0f172a|#e5e7eb}",
        fontsize=12
    ];

    edge [
        color="${#64748b|#94a3b8}",
        fontcolor="${#475569|#cbd5e1}",
        fontsize=9,
        arrowsize=0.7
    ];

    // Aumentar el tamaño mínimo de los nodos con más conexiones reduce los solapamientos en neato.

    subgraph api_nodes {
        get_account_links [label="/api/accountlink/{user_id}"];
        create_account_link [label="/api/accountlink/create/"];
        delete_link [label="/api/accountlink/delete/"];
        update_link [label="/api/accountlink/update/"];
        view_saolei_get_import_list [label="/accountlink/saolei/videolist/get/"];
        view_saolei_get_import_summary [label="/accountlink/saolei/videoimport/stat/"];
        task_summary [label="/api/common/tasks/summary (staff)"];
        monitor_summary [label="/api/monitor/summary (Nginx)"];
        video_upload [label="/api/common/uploadvideo"];
        pluck_rank [label="/api/customranking/pluck"];
        minigame_score [label="POST /api/minigame/{ranking_key}/score"];
        minigame_rank [label="/api/minigame/{game}/rank\n/api/minigame/{game}/player/{id}"];
        player_pluck_records [label="/api/customranking/pluck/player"]
        add_identifier [label="/identifier/add/"];
        del_identifier [label="/identifier/del/"];
        get_tournament_list [label="/api/tournament/get_list"];
        get_tournament [label="/api/tournament/get"];
        set_tournament [label="/api/tournament/set"];
        cancel_tournament [label="/api/tournament/cancel"];
        get_participant_list [label="/api/tournament/participants"];
        reset_participant [label="POST /api/tournament/participant/{id}/reset"];
        disqualify_participant [label="POST /api/tournament/participant/{id}/disqualify"];
        get_disqualification_task [label="GET /api/tournament/disqualification-task/{id}"];
        get_participant_videos [label="/api/tournament/get_videos/participant"];
        reveal_video [label="POST /api/tournament/video/{video_id}/reveal"];
        get_tournament_news [label="/api/tournament/get_news"];
        get_gsc_results [label="/api/tournament/gsc/results"];
        create_gsc_participant [label="/api/tournament/gsc/participant"];
        register_gsc_participant_identifier [label="/api/tournament/gsc/participant/identifier"];
        get_weekly_results [label="/api/tournament/weekly/results"];
        create_weekly_participant [label="/api/tournament/weekly/participant"];
        get_weekly_eff_results [label="/api/tournament/weekly-eff/results"];
        create_weekly_eff_participant [label="/api/tournament/weekly-eff/participant"];
        get_user_info [label="/api/userprofile/info/{user_id}"];
        get_user_info_bulk [label="/api/userprofile/infobulk"];
        get_user_info_updated [label="/api/userprofile/infoupdated"];
        get_user_identifier [label="/api/userprofile/identifier"];
        get_user_avatar [label="/api/userprofile/avatar/{user_id}"];
        get_user_videos [label="/api/userprofile/videolist"];
        update_user_profile [label="/api/userprofile/update_profile"];
        update_user_avatar [label="/api/userprofile/update_avatar"];
        user_login [label="/userprofile/login/"];
        user_retrieve [label="/userprofile/retrieve/"];
        user_register [label="/userprofile/register/"];
        check_collision [label="/userprofile/checkcollision/"];
        refresh_captcha [label="/userprofile/refresh_captcha/"];
        get_email_captcha [label="/userprofile/get_email_captcha/"];
        get_review_queue [label="/api/video/review_queue"];
        get_video_info_bulk [label="/api/video/infobulk"];
        get_video_detail_bulk [label="/api/video/detailbulk"];
        get_static_video_detail_batch [label="/api/video/staticdetailbatch"];
        get_video_abstract_bulk [label="/api/video/abstractbulk"];
        video_preview [label="/api/video/preview"];
        video_download [label="/api/video/download/{video_id}"];
        video_query [label="/api/video/query"];
        video_query_by_id [label="/api/video/query_by_id"];
        newest_queue [label="/api/video/newest_queue"];
    }

    subgraph db_nodes {
        node [shape=cylinder, fillcolor="${#e0f2fe|#0f172a}"];
        captcha_db [label="CaptchaStore"];
        task_db [label="DBTaskResult", width=2.0, height=0.8];
        accountlinkqueue_db [label="AccountLinkQueue\nplatform accounts"];
        accountlinkplatform_db [label="AccountSaolei\nAccountMinesweeperGames\nAccountBilibili\nAccountWorldOfMinesweeper\nAccountQQ", width=3.0, height=1.4];
        videosaolei_db [label="VideoSaolei"];
        custom_pluck_db [label="CustomPluckRecord"];
        minigame_db [label="MiniGameBestScore"];
        identifier_db [label="Identifier"];
        userms_db [label="UserMS", width=3, height=3, fontsize=30];
        tournament_db [label="Tournament\nGSCTournament\nWeeklyTournament", width=2.5, height=1.1];
        participant_db [label="TournamentParticipant\nGSCParticipant\nWeeklyParticipant", width=2.8, height=1.1];
        tournament_user_db [label="TournamentUser", width=2.2, height=0.8];
        userprofile_db [label="UserProfile", width=4, height=4, fontsize=40];
        email_otp_db [label="EmailVerifyRecord"]
        video_db [label="VideoModel\nExpandVideoModel", width=4, height=4, fontsize=30];
    }

    subgraph cache_nodes {
        node [shape=box, fillcolor="${#dcfce7|#14532d}"];
        pluck_rank_cache [label="customranking:pluck:{level}:rank\nzset"];
        pluck_detail_cache [label="customranking:pluck:{level}:detail\nhash"];
        minigame_cache [label="minigame:{rank|detail|ready}:v1:{ranking_key}\nzset / hash / string"];
        newest_cache [label="newest_queue\nhash"];
        tournament_cache [label="tournament:normal\nhash\nsubclass + data", width=2.6, height=1.0];
        participant_cache [label="tournament:normal:participants\nhash", width=3.2, height=0.9];
        tournament_user_rank_cache [label="tournament:user:{field}\nzset\nmember = user_id", width=3.4, height=1.0];
        tournament_user_score_time_cache [label="tournament:user:score_current:last_updated\nstring\nReferencia anual: 1 de enero UTC", width=4.2, height=1.0];
    }

    minigame_score -> minigame_db [label="Guardar la mejor puntuación y la repetición en JSON"];
    minigame_db -> minigame_cache [label="Actualizar o eliminar en on_commit, o reconstruir"];
    minigame_cache -> minigame_rank [label="Lectura por lotes y grupos"];
    minigame_db -> minigame_rank [label="Alternativa si falla Redis"];

    subgraph file_nodes {
        node [shape=folder, fillcolor="${#e0f2fe|#0f172a}"];
        video_files [label="video files"];
        avatar_files [label="avatar files"];
        monitor_snapshot [label="runtime/monitor.json"];
    }

    monitor_sampler [label="APScheduler refresh_monitor_snapshot\nstartup + every 5 minutes"];

    subgraph signal_nodes {
        node [
            shape=box,
            fillcolor="${#fef3c7|#713f12}",
            color="${#f59e0b|#d97706}"
        ];
        capture_video_update [label="capture_video_update"];
        refresh_state_queue_on_video_save [label="refresh_state_queue_on_video_save"];
        delete_video_expansion [label="delete_video_expansion"];
        update_video_count_on_video_save [label="update_video_count_on_video_save"];
        update_video_count_on_video_delete [label="update_video_count_on_video_delete"];
        refresh_custom_pluck_rank_on_video_save [label="refresh_custom_pluck_rank_on_video_save"];
        refresh_custom_pluck_rank_on_video_delete [label="refresh_custom_pluck_rank_on_video_delete"];
        update_custom_pluck_cache_on_record_save [label="update_custom_pluck_cache_on_record_save"];
        update_custom_pluck_cache_on_record_delete [label="update_custom_pluck_cache_on_record_delete"];
        checkin_video_before_create [label="checkin_video_before_create"];
        add_created_video_to_checked_tournaments [label="add_created_video_to_checked_tournaments"];
        update_cache_on_tournament_delete [label="update_cache_on_tournament_delete"];
        update_cache_on_tournament_save [label="update_cache_on_tournament_save"];
        update_cache_on_participant_save [label="update_cache_on_participant_save"];
        update_best_score_on_gsc_participant_save [label="update_best_score_on_gsc_participant_save", width=3.4, height=0.8];
        update_best_score_on_weekly_participant_save [label="update_best_score_on_weekly_participant_save", width=3.7, height=0.8];
        update_best_score_on_gsc_participant_delete [label="update_best_score_on_gsc_participant_delete", width=3.5, height=0.8];
        update_best_score_on_weekly_participant_delete [label="update_best_score_on_weekly_participant_delete", width=3.8, height=0.8];
        update_best_score_on_weekly_eff_participant_save [label="update_best_score_on_weekly_eff_participant_save", width=3.9, height=0.8];
        update_best_score_on_weekly_eff_participant_delete [label="update_best_score_on_weekly_eff_participant_delete", width=4.0, height=0.8];
        remove_participant_cache_on_delete [label="remove_participant_cache_on_delete"];
        revoke_rank_score_on_participant_delete [label="revoke_rank_score_on_participant_delete", width=3.4, height=0.8];
    }

    subgraph task_nodes {
        node [
            shape=box,
            fillcolor="${#ede9fe|#4c1d95}",
            color="${#8b5cf6|#a78bfa}"
        ];
        task_gsc_finish [label="task_gsc_finish"];
        task_gsc_refresh_best [label="task_gsc_refresh_best"];
        task_award_tournament [label="task_award_tournament"];
        task_weekly_finish [label="task_weekly_finish"];
        task_weekly_refresh_best [label="task_weekly_refresh_best"];
        task_weekly_eff_finish [label="task_weekly_eff_finish\nend_time + 1 hour"];
        task_weekly_eff_refresh_best [label="task_weekly_eff_refresh_best"];
        task_disqualify_participant [label="task_disqualify_participant"];
        refresh_tournament_score_reference [label="APScheduler\nrefresh_tournament_score_reference"];
        rebuild_tournament_current_score_cache [label="manage.py\nrebuild_tournament_current_score_cache"];
    }

    // accountlink API
    accountlinkqueue_db -> get_account_links;
    accountlinkplatform_db -> get_account_links;
    create_account_link -> accountlinkqueue_db;
    accountlinkqueue_db -> delete_link;
    delete_link -> accountlinkqueue_db;
    delete_link -> accountlinkplatform_db;
    accountlinkplatform_db -> update_link;
    update_link -> accountlinkplatform_db;
    userprofile_db -> view_saolei_get_import_list;
    accountlinkplatform_db -> view_saolei_get_import_list;
    videosaolei_db -> view_saolei_get_import_list;
    task_db -> view_saolei_get_import_list;
    accountlinkplatform_db -> view_saolei_get_import_summary;
    videosaolei_db -> view_saolei_get_import_summary;
    task_db -> view_saolei_get_import_summary;

    // monitor API
    task_db -> task_summary;
    task_db -> monitor_sampler;
    video_db -> monitor_sampler;
    userprofile_db -> monitor_sampler [label="PB user IDs"];
    newest_cache -> monitor_sampler [label="MEMORY USAGE"];
    monitor_sampler -> monitor_snapshot -> monitor_summary;

    // common API
    video_upload -> video_db [label="create after is_completed check"];
    video_upload -> video_files [label="write after is_completed check"];

    // customranking API
    pluck_rank_cache -> pluck_rank
    pluck_detail_cache -> pluck_rank
    pluck_rank_cache -> player_pluck_records
    pluck_detail_cache -> player_pluck_records

    //identifier API
    userms_db -> add_identifier;
    video_db -> add_identifier;
    add_identifier -> identifier_db;
    add_identifier -> userms_db;
    add_identifier -> custom_pluck_db;
    userms_db -> del_identifier;
    video_db -> del_identifier;
    del_identifier -> identifier_db;
    del_identifier -> userms_db;
    del_identifier -> custom_pluck_db;


    // tournament API
    tournament_db -> get_tournament_list;
    tournament_cache -> get_tournament_list;
    tournament_db -> get_tournament;
    userprofile_db -> set_tournament;
    tournament_db -> set_tournament;
    set_tournament -> tournament_db;
    userprofile_db -> cancel_tournament;
    tournament_db -> cancel_tournament;
    cancel_tournament -> tournament_db;
    tournament_db -> get_participant_list;
    participant_db -> get_participant_list;
    identifier_db -> get_participant_list;
    video_db -> get_participant_list [label="EXISTS has_videos"];
    participant_db -> reset_participant [label="read personal end_time"];
    tournament_db -> reset_participant [label="host/state read (join)"];
    video_db -> reset_participant [label="any video EXISTS"];
    reset_participant -> participant_db [label="delete expired registration"];
    participant_db -> disqualify_participant [label="read"];
    tournament_db -> disqualify_participant [label="host/AWARDED read"];
    disqualify_participant -> task_db [label="enqueue"];
    disqualify_participant -> task_disqualify_participant [label="enqueue"];
    task_db -> get_disqualification_task [label="read scoped task"];
    tournament_db -> get_disqualification_task [label="host read"];
    participant_db -> task_disqualify_participant [label="read/delete"];
    tournament_db -> task_disqualify_participant [label="FK state read"];
    task_disqualify_participant -> participant_db [label="delete; triggers best/refund signals"];
    userprofile_db -> get_participant_videos;
    tournament_db -> get_participant_videos;
    participant_db -> get_participant_videos;
    video_db -> get_participant_videos;
    video_db -> reveal_video [label="read / lock / owner check"];
    reveal_video -> video_db [label="save ongoing_tournament=False"];
    tournament_cache -> get_tournament_news;

    // tournament gsc API
    tournament_db -> get_gsc_results;
    participant_db -> get_gsc_results;
    identifier_db -> get_gsc_results [label="select_related"];
    video_db -> get_gsc_results [label="EXISTS has_videos"];
    tournament_db -> create_gsc_participant;
    userprofile_db -> create_gsc_participant;
    create_gsc_participant -> participant_db;
    userprofile_db -> register_gsc_participant_identifier;
    tournament_db -> register_gsc_participant_identifier;
    participant_db -> register_gsc_participant_identifier;
    identifier_db -> register_gsc_participant_identifier;
    register_gsc_participant_identifier -> identifier_db;
    register_gsc_participant_identifier -> participant_db;
    register_gsc_participant_identifier -> userms_db;
    register_gsc_participant_identifier -> video_db;

    // tournament weekly API
    tournament_db -> get_weekly_results;
    participant_db -> get_weekly_results;
    tournament_db -> create_weekly_participant;
    userprofile_db -> create_weekly_participant;
    create_weekly_participant -> participant_db;
    tournament_db -> get_weekly_eff_results;
    participant_db -> get_weekly_eff_results;
    tournament_db -> create_weekly_eff_participant;
    userprofile_db -> create_weekly_eff_participant;
    create_weekly_eff_participant -> participant_db;

    // userprofile API
    userprofile_db -> get_user_info;
    userprofile_db -> get_user_info_bulk;
    userprofile_db -> get_user_info_updated;
    userprofile_db -> get_user_identifier;
    userms_db -> get_user_identifier;
    userprofile_db -> get_user_avatar;
    avatar_files -> get_user_avatar;
    userprofile_db -> get_user_videos;
    video_db -> get_user_videos;
    userprofile_db -> update_user_profile;
    userms_db -> update_user_profile;
    update_user_profile -> userprofile_db;
    userprofile_db -> update_user_avatar;
    userms_db -> update_user_avatar;
    update_user_avatar -> userprofile_db;
    update_user_avatar -> avatar_files;
    captcha_db -> user_login;
    userprofile_db -> user_login;
    userms_db -> user_login;
    video_db -> user_login;
    email_otp_db -> user_retrieve;
    userms_db -> user_retrieve;
    video_db -> user_retrieve;
    userprofile_db -> user_retrieve;
    user_retrieve -> userprofile_db;
    user_retrieve -> email_otp_db;
    email_otp_db -> user_register;
    userms_db -> user_register;
    video_db -> user_register;
    userprofile_db -> user_register;
    user_register -> userprofile_db;
    user_register -> email_otp_db;
    userprofile_db -> check_collision;
    refresh_captcha -> captcha_db;
    captcha_db -> refresh_captcha;
    captcha_db -> get_email_captcha;
    get_email_captcha -> captcha_db;

    // tournament finish tasks
    task_db -> task_gsc_finish [label="status/read"];
    tournament_db -> task_gsc_finish [label="read/write"];
    participant_db -> task_gsc_finish [label="read/write/delete"];
    video_db -> task_gsc_finish [label="score: OFFICIAL only; reveal: read/write"];
    tournament_user_db -> task_gsc_finish [label="ensure_tournament_users: read"];
    task_gsc_finish -> participant_db [label="score/rank"];
    task_gsc_finish -> tournament_db [label="state write"];
    task_gsc_finish -> tournament_user_db [label="ensure_tournament_users: create missing"];
    task_gsc_finish -> newest_cache [label="restore queues"];
    task_gsc_finish -> freeze_cache [label="restore queues"];
    task_gsc_finish -> review_cache [label="restore queues"];
    task_gsc_finish -> pluck_rank_cache [label="restore pluck"];
    task_gsc_finish -> pluck_detail_cache [label="restore pluck"];
    task_gsc_finish -> task_award_tournament [label="enqueue"];
    task_gsc_finish -> task_gsc_refresh_best [label="enqueue"];

    task_db -> task_award_tournament [label="status/read"];
    tournament_db -> task_award_tournament [label="read"];
    participant_db -> task_award_tournament [label="read/write rank_score"];
    tournament_user_db -> task_award_tournament [label="read/write score"];
    task_award_tournament -> tournament_user_db [label="ensure_tournament_users / award_tournament_rank_scores"];
    task_award_tournament -> tournament_user_rank_cache [label="write score zsets"];
    tournament_user_score_time_cache -> task_award_tournament [label="read reference time"];
    tournament_user_rank_cache -> task_award_tournament [label="EXISTS only if reference missing"];
    task_award_tournament -> tournament_user_score_time_cache [label="init only when empty"];
    tournament_user_score_time_cache -> refresh_tournament_score_reference [label="read old anchor"];
    tournament_user_rank_cache -> refresh_tournament_score_reference [label="ZUNIONSTORE score_current"];
    refresh_tournament_score_reference -> tournament_user_rank_cache [label="annual rescale"];
    refresh_tournament_score_reference -> tournament_user_score_time_cache [label="set annual anchor"];
    tournament_user_db -> rebuild_tournament_current_score_cache [label="read score_current / last_updated"];
    rebuild_tournament_current_score_cache -> tournament_user_rank_cache [label="atomic rebuild score_current only"];
    rebuild_tournament_current_score_cache -> tournament_user_score_time_cache [label="set annual anchor"];

    task_db -> task_gsc_refresh_best [label="status/read"];
    tournament_db -> task_gsc_refresh_best [label="read"];
    participant_db -> task_gsc_refresh_best [label="read"];
    tournament_user_db -> task_gsc_refresh_best [label="read/write best"];
    task_gsc_refresh_best -> tournament_user_db [label="ensure_tournament_users / refresh_gsc_best_scores"];
    task_gsc_refresh_best -> tournament_user_rank_cache [label="write best zset"];

    task_db -> task_weekly_finish [label="status/read"];
    tournament_db -> task_weekly_finish [label="read/write"];
    participant_db -> task_weekly_finish [label="read/write/delete"];
    video_db -> task_weekly_finish [label="score: OFFICIAL only; reveal: read/write"];
    tournament_user_db -> task_weekly_finish [label="ensure_tournament_users: read"];
    task_weekly_finish -> participant_db [label="score/rank"];
    task_weekly_finish -> tournament_db [label="state write"];
    task_weekly_finish -> tournament_user_db [label="ensure_tournament_users: create missing"];
    task_weekly_finish -> newest_cache [label="restore queues"];
    task_weekly_finish -> freeze_cache [label="restore queues"];
    task_weekly_finish -> review_cache [label="restore queues"];
    task_weekly_finish -> pluck_rank_cache [label="restore pluck"];
    task_weekly_finish -> pluck_detail_cache [label="restore pluck"];
    task_weekly_finish -> task_award_tournament [label="enqueue"];
    task_weekly_finish -> task_weekly_refresh_best [label="enqueue"];

    task_db -> task_weekly_refresh_best [label="status/read"];
    tournament_db -> task_weekly_refresh_best [label="read"];
    participant_db -> task_weekly_refresh_best [label="read"];
    tournament_user_db -> task_weekly_refresh_best [label="read/write best"];
    task_weekly_refresh_best -> tournament_user_db [label="ensure_tournament_users / refresh_weekly_best_scores"];
    task_weekly_refresh_best -> tournament_user_rank_cache [label="write best zset"];

    tournament_db -> task_weekly_eff_finish [label="read/state write"];
    participant_db -> task_weekly_eff_finish [label="read/delete empty"];
    video_db -> task_weekly_eff_finish [label="OFFICIAL STD query time/IOE; reveal"];
    tournament_user_db -> task_weekly_eff_finish [label="ensure users"];
    task_weekly_eff_finish -> participant_db [label="float scores/ranks"];
    task_weekly_eff_finish -> tournament_db [label="AWARDED"];
    task_weekly_eff_finish -> newest_cache [label="reveal queues"];
    task_weekly_eff_finish -> task_award_tournament [label="enqueue"];
    task_weekly_eff_finish -> task_weekly_eff_refresh_best [label="enqueue"];
    participant_db -> task_weekly_eff_refresh_best [label="read"];
    tournament_db -> task_weekly_eff_refresh_best [label="FK year/week"];
    tournament_user_db -> task_weekly_eff_refresh_best [label="read"];
    task_weekly_eff_refresh_best -> tournament_user_db [label="write float best/year/week"];
    task_weekly_eff_refresh_best -> tournament_user_rank_cache [label="on_commit raw float ZADD/ZREM"];

    // videomanager API
    video_db -> get_review_queue;
    video_db -> get_video_info_bulk;
    video_db -> get_video_detail_bulk;
    video_db -> get_static_video_detail_batch;
    video_db -> get_video_abstract_bulk;
    video_db -> video_preview;
    userprofile_db -> video_preview;
    video_files -> video_preview;
    video_db -> video_download;
    userprofile_db -> video_download;
    video_files -> video_download;
    userprofile_db -> video_query;
    video_db -> video_query;
    userprofile_db -> video_query_by_id;
    video_db -> video_query_by_id;
    newest_cache -> newest_queue;

    // videomanager signals
    video_db -> capture_video_update [label="pre_save"];
    video_db -> capture_video_update [label="read"];
    video_db -> refresh_state_queue_on_video_save [label="post_save"];
    video_db -> refresh_state_queue_on_video_save [label="O2O read"];
    userprofile_db -> refresh_state_queue_on_video_save [label="FK read"];
    refresh_state_queue_on_video_save -> newest_cache [label="write/delete"];
    video_db -> delete_video_expansion [label="post_delete"];
    delete_video_expansion -> video_db [label="delete expansion in transaction"];

    // msuser signals
    video_db -> update_video_count_on_video_save [label="post_save"];
    tournament_db -> update_video_count_on_video_save [label="membership read on size/owner change"];
    userprofile_db -> update_video_count_on_video_save [label="FK read"];
    userms_db -> update_video_count_on_video_save [label="O2O read"];
    update_video_count_on_video_save -> userms_db [label="one UPDATE: statistics + limit"];

    video_db -> update_video_count_on_video_delete [label="pre_delete"];
    tournament_db -> update_video_count_on_video_delete [label="m2m exists"];
    userprofile_db -> update_video_count_on_video_delete [label="FK read"];
    userms_db -> update_video_count_on_video_delete [label="O2O read"];
    update_video_count_on_video_delete -> userms_db [label="write"];





    // customranking signals
    video_db -> refresh_custom_pluck_rank_on_video_save [label="post_save"];
    video_db -> refresh_custom_pluck_rank_on_video_save [label="read best"];
    userprofile_db -> refresh_custom_pluck_rank_on_video_save [label="FK read"];
    custom_pluck_db -> refresh_custom_pluck_rank_on_video_save [label="read"];
    refresh_custom_pluck_rank_on_video_save -> custom_pluck_db [label="write/delete"];
    video_db -> refresh_custom_pluck_rank_on_video_delete [label="post_delete / on_commit read remaining"];
    refresh_custom_pluck_rank_on_video_delete -> custom_pluck_db [label="on_commit backfill/write/delete"];
    refresh_custom_pluck_rank_on_video_delete -> pluck_rank_cache [label="on_commit write/delete"];
    refresh_custom_pluck_rank_on_video_delete -> pluck_detail_cache [label="on_commit write/delete"];

    custom_pluck_db -> update_custom_pluck_cache_on_record_save [label="post_save"];
    video_db -> update_custom_pluck_cache_on_record_save [label="FK read"];
    update_custom_pluck_cache_on_record_save -> pluck_rank_cache [label="write"];
    update_custom_pluck_cache_on_record_save -> pluck_detail_cache [label="write"];

    custom_pluck_db -> update_custom_pluck_cache_on_record_delete [label="post_delete"];
    custom_pluck_db -> update_custom_pluck_cache_on_record_delete [label="on_commit read current"];
    update_custom_pluck_cache_on_record_delete -> pluck_rank_cache [label="on_commit write/delete"];
    update_custom_pluck_cache_on_record_delete -> pluck_detail_cache [label="on_commit write/delete"];

    // tournament signals
    video_db -> checkin_video_before_create [label="pre_save"];
    video_db -> checkin_video_before_create [label="O2O read"];
    participant_cache -> checkin_video_before_create [label="read"];
    tournament_db -> checkin_video_before_create [label="query read"];
    checkin_video_before_create -> video_db [label="write field"];

    video_db -> add_created_video_to_checked_tournaments [label="post_save"];
    add_created_video_to_checked_tournaments -> tournament_db [label="m2m write"];

    tournament_db -> update_cache_on_tournament_delete [label="post_delete"];
    update_cache_on_tournament_delete -> tournament_cache [label="delete"];
    participant_cache -> update_cache_on_tournament_delete [label="scan/read"];
    update_cache_on_tournament_delete -> participant_cache [label="write/delete"];

    tournament_db -> update_cache_on_tournament_save [label="post_save"];
    tournament_db -> update_cache_on_tournament_save [label="subclass read"];
    update_cache_on_tournament_save -> tournament_cache [label="write/delete"];
    participant_cache -> update_cache_on_tournament_save [label="scan/read"];
    update_cache_on_tournament_save -> participant_cache [label="write/delete"];

    participant_db -> update_cache_on_participant_save [label="post_save"];
    participant_cache -> update_cache_on_participant_save [label="read"];
    tournament_db -> update_cache_on_participant_save [label="FK/m2m read"];
    identifier_db -> update_cache_on_participant_save [label="FK read"];
    video_db -> update_cache_on_participant_save [label="query read"];
    update_cache_on_participant_save -> participant_cache [label="write/delete"];
    update_cache_on_participant_save -> tournament_db [label="m2m write"];

    participant_db -> update_best_score_on_gsc_participant_save [label="post_save"];
    tournament_db -> update_best_score_on_gsc_participant_save [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_gsc_participant_save [label="read/create"];
    update_best_score_on_gsc_participant_save -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_weekly_participant_save [label="post_save"];
    tournament_db -> update_best_score_on_weekly_participant_save [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_weekly_participant_save [label="read/create"];
    update_best_score_on_weekly_participant_save -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_gsc_participant_delete [label="post_delete"];
    participant_db -> update_best_score_on_gsc_participant_delete [label="query best"];
    tournament_db -> update_best_score_on_gsc_participant_delete [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_gsc_participant_delete [label="read"];
    update_best_score_on_gsc_participant_delete -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_weekly_participant_delete [label="post_delete"];
    participant_db -> update_best_score_on_weekly_participant_delete [label="query best"];
    tournament_db -> update_best_score_on_weekly_participant_delete [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_weekly_participant_delete [label="read"];
    update_best_score_on_weekly_participant_delete -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_weekly_eff_participant_save [label="post_save"];
    tournament_db -> update_best_score_on_weekly_eff_participant_save [label="FK state; AWARDED: subclass year/week"];
    tournament_user_db -> update_best_score_on_weekly_eff_participant_save [label="AWARDED: read/create"];
    update_best_score_on_weekly_eff_participant_save -> tournament_user_db [label="write best/year/week"];
    update_best_score_on_weekly_eff_participant_save -> tournament_user_rank_cache [label="on_commit float best"];
    participant_db -> update_best_score_on_weekly_eff_participant_delete [label="post_delete"];
    participant_db -> update_best_score_on_weekly_eff_participant_delete [label="query remaining best"];
    tournament_db -> update_best_score_on_weekly_eff_participant_delete [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_weekly_eff_participant_delete [label="read/create"];
    update_best_score_on_weekly_eff_participant_delete -> tournament_user_db [label="create if missing; write/clear best and edition"];
    update_best_score_on_weekly_eff_participant_delete -> tournament_user_rank_cache [label="on_commit float best"];

    participant_db -> remove_participant_cache_on_delete [label="post_delete"];
    participant_cache -> remove_participant_cache_on_delete [label="read"];
    remove_participant_cache_on_delete -> participant_cache [label="write/delete"];

    participant_db -> revoke_rank_score_on_participant_delete [label="post_delete"];
    tournament_db -> revoke_rank_score_on_participant_delete [label="FK read end_time/subclass"];
    tournament_user_db -> revoke_rank_score_on_participant_delete [label="SELECT FOR UPDATE"];
    revoke_rank_score_on_participant_delete -> tournament_user_db [label="write decayed refund/totals"];
    tournament_user_score_time_cache -> revoke_rank_score_on_participant_delete [label="on_commit read anchor"];
    tournament_user_rank_cache -> revoke_rank_score_on_participant_delete [label="on_commit EXISTS if anchor missing"];
    revoke_rank_score_on_participant_delete -> tournament_user_rank_cache [label="on_commit write/remove score zsets"];
    revoke_rank_score_on_participant_delete -> tournament_user_score_time_cache [label="on_commit init only when empty"];
}
```

<a id="cache-data-structure"></a>

## Estructura de datos del caché

Cola reciente de repeticiones claramente mantiene el significado de snapshot independiente: eliminar `VideoModel` no elimina el elemento `newest_queue`, la interfaz de lectura tampoco consulta la base de datos para filtrar, por lo que podría devolver un ID de repetición eliminado. Los elementos se recortan solo según el límite establecido o son eliminados por el administrador.

Los campos de HSET en la inscripción siguen dividiéndose por usuario; los métodos `update_participant`, `remove_participant` y la limpieza al final de la competición usan el mismo camino de lectura y escritura `WATCH / MULTI / EXEC`. La escaneo de limpieza solo enumera usuarios, y al modificar se vuelve a leer la lista actual para evitar sobrescribir una nueva inscripción en otra competencia; al mismo tiempo, se monitorea el HSET de competencias normales para evitar que los callbacks de guardado tardíos reintegren inscripciones tras la eliminación de la competencia del caché. Los callbacks de eliminación incluyen el ID de inscripción anterior, y no eliminan inscripciones recién creadas en la misma competencia. Aquí no se añade ningún nuevo key de bloqueo de Redis.

Se cancela la calificación mediante un API solo accesible por organizadores, donde la tarea `task_disqualify_participant` se ejecuta en el mismo trabajador secuencial para eliminar el registro y actualizar los puntos/mejores resultados; el aceptar el API no implica que la tarea haya sido exitosa. El reinicio de la competencia solo permite a organizadores o administradores realizarlo cuando el cuadro personal haya finalizado y no exista ninguna repetición de la partida, y se completa dentro de la solicitud, sin compartir un estado con la cancelación de calificación.

La finalización, el cálculo de puntos, los mejores resultados y la cancelación de calificación se ejecutan en un solo trabajador de forma secuencial; los cálculos manuales y la reconstrucción del caché deben evitarse durante estas operaciones de escritura. La cancelación solo elimina el registro correspondiente y revierte los puntos personales, sin reordenar a otros participantes; las tareas posteriores consultan nuevamente los registros existentes, y las cancelaciones repetidas no se deducen múltiples veces. Al aumentar el número de trabajadores o permitir mantenimiento manual en paralelo, se debe reevaluar la coherencia entre los puntos y los mejores resultados entre competencias.

Las tareas finales de los tres tipos de competencia se ejecutan primero en el original `end_time + 1 小时`, manteniendo NORMAL y el caché de inscripción durante este periodo; al reiniciar GSC se respetará este límite inferior. Aquí se bufferan solo las subidas ya en proceso antes de la fecha límite, sin extender los períodos de competencia o de inscripción individual ni modificar el tiempo de degradación de puntos. Un guardado anómalo que dure más de una hora puede seguir intersectándose; al finalizar el periodo individual de inscripción, se reinicia la inscripción sin esperar a las subidas en tránsito, y en esta ocasión no se incrementa el contador de subidas en tránsito ni se aplica bloqueo de cierre.

Después de eliminar un video personalizado, se reemplaza en la transacción el registro `CustomPluckRecord` y el elemento correspondiente en Redis desde los registros restantes válidos; al sincronizar el caché tras la eliminación, se vuelve a leer el estado actual de la base de datos tras la confirmación de la transacción, y en caso de rollback, no se publican estas dos actualizaciones.

La eliminación normal de un video de competencia no realiza inmediatamente un cálculo de nuevo, manteniendo temporalmente los resultados ya calculados, clasificaciones, puntos y mejor resultado histórico. El cálculo explícito se maneja según el tipo de competencia y la fuente de los resultados: para competencias de check-in y videos de GSC, se excluyen los videos eliminados; para fuentes manuales de GSC, se conservan los resultados ingresados, pero ambos tipos participan en el ranking general y en la actualización de puntos. Cada nuevo tipo de competencia debe definir sus propias reglas para eliminación, recálculo y mantenimiento de los mejores resultados. El API del administrador ya devuelve el ID de la competencia afectada y registra una advertencia en el log; la página oculta ya muestra advertencias y confirmaciones de eliminación; aún no se ha implementado la notificación privada a los organizadores, ver el plan en el repositorio `back_end/saolei/tournament/VIDEO_DELETION_PLAN.md`.

El método `POST /api/video/admin/delete` solo está permitido para superusuarios, con verificación de sesión CSRF; el cuerpo de la solicitud en formato JSON es `{"id": 123}`, eliminando un video por solicitud. La función `videomanager.services.delete_video_by_id` llama al método `delete()` dentro de una transacción de base de datos, desencadenando señales de limpieza de extensiones, actualización del conteo de videos y actualización de clasificaciones, sin eliminar directamente el elemento de la cola en Redis. Durante la reconstrucción de clasificaciones, el acceso HTTP devuelve 503 antes de cualquier eliminación; el acceso compartido interno del servicio cubre tanto la confirmación de la base de datos como las llamadas de eliminación. La solicitud GET en la misma ruta solo verifica el superusuario y inicializa el cookie/token CSRF, y la respuesta está prohibida para caché.

La página oculta `/#/superuser/delete-videos` utiliza solo el idioma chino y no se incluye en el menú ni en las pestañas de administrador. La página acepta una lista de IDs tras confirmación de permisos del backend, realiza validación de duplicados y espera una respuesta por eliminación individual, mostrando el estado de eliminación, inexistencia y competencias afectadas. Cada solicitud se procesa de forma independiente; errores, timeouts o interrupción manual bloquean los siguientes procesos, sin intentos automáticos de reintentar ni recuperación de los elementos ya exitosamente eliminados. Aunque cada solicitud se procesa de forma sincrónica, no se considera el `on_commit` como una tarea en segundo plano.

| app perteneciente | clave | Tipos de Redis | Estructuras de datos |
| --- | --- | --- | --- |
| `minigame` | `minigame:rank:v1:{ranking_key}` | zset | `member = player_id` con puntuación en milisegundos como entero original. |
| `minigame` | `minigame:detail:v1:{ranking_key}` | hash | `field = player_id` con valor `{score, achieved_at}` en formato JSON. |
| `minigame` | `minigame:ready:v1:{ranking_key}` | string | `1` indica que la lista oficial ha sido inicializada; se mantiene también una lista vacía sin tiempo de expiración (TTL). |
| `videomanager` | `newest_queue` | hash | `field = video_id`；JSON solo incluye `state`, `time`, `player_id`. La interfaz de última repetición lee directamente el snapshot de hash y lo convierte en un array de metadatos, sin consultar la base de datos; el queue solo almacena repeticiones públicas, por lo que el valor de `ongoing_tournament` es `false`. Los campos de análisis se completan con el caché del navegador de grabación; la tarea de fondo conserva diariamente a las 01:08 las últimas 1000 entradas según `time`, manteniendo la con el ID más alto en caso de igualdad de tiempo, y ya no caduca por días. No se recorta al escribir, permitiendo temporalmente superar el límite; el recorte se realiza mediante ordenación en Python y eliminación normal en Redis, usando la misma lógica que las órdenes de gestión. `freeze_queue` y `review_queue` ya no se mantienen, y las claves residuales se eliminan mediante el comando de actualización. |
| `effranking` | `effranking:thrp:records` | hash | `field = player_id`；registro completo de jugador en JSON. Los valores comunes `b/i/e` son `null` o `{value, video_id, upload_time}`; `e_nf` es `null` o `{value, video_ids}`, incluyendo todas las grabaciones completadas en caso de puntuación máxima, de lo contrario solo la mejor partida. La suma no se almacena repetidamente. |
| `effranking` | `effranking:thrp:{stat}` | zset | `stat = b/i/e/sum/e_nf`；`member = player_id`. Los valores originales de las cuatro categorías con seis decimales y los tiempos de cumplimiento por minutos; el NF avanzado utiliza el negativo de Thrp, y tras alcanzar la puntuación máxima se usa el negativo del número de partidas completadas. Se lee en orden ascendente, no se utiliza para restaurar puntuaciones. |
| `effranking` | `effranking:nf_ioe:records` | hash | `field = player_id`；registro completo de `b/i/e`, cada uno como `null` o `{value, video_id, timems}`; la suma se calcula a partir del valor original y no se almacena repetidamente. |
| `effranking` | `effranking:nf_ioe:{stat}` | zset | `stat = b/i/e/sum`；`member = player_id`；la puntuación se toma como el negativo del valor de puntuación de negocio, para comparar el tiempo en cada categoría al alcanzar la puntuación máxima, y para la suma total solo se compara el tiempo en niveles avanzados. |
| `effranking` | `effranking:tpe:records` | hash | `field = player_id`. Para cada uno de los seis campos (`i/i2/i3/e/e2/e3`) se guarda `null` o `{value, video_id}`. `value` es el resultado en segundos de la fórmula correspondiente, sin redondear. Las tres sumas se calculan a partir de esos campos. |
| `effranking` | `effranking:tpe:{stat}` | zset | `stat = i/i2/i3/e/e2/e3/sum/sum2/sum3`, `member = player_id`. La puntuación es el valor de la fórmula correspondiente y se ordena de menor a mayor, sin codificar desempates. Cada suma requiere récords de esa fórmula en los niveles intermedio y experto. El cero es válido. |
| `customranking` | `customranking:pluck:{level}:rank` | zset | `member = player_id`；`score = pluck`，cuando `pluck == 0` se active, usa `timems - MAX_TIMEMS` para reducir 0 riesgos de colisión. |
| `customranking` | `customranking:pluck:{level}:detail` | hash | `field = player_id`；JSON incluye `video_id`, `timems`, `upload_time`. El modo mostrado y el 3BV se completan con el caché de grabación del navegador; el conjunto ordenado (zset) mantiene el código original. |
| `tournament` | `tournament:normal` | hash | `field = tournament_id`；`value = CachedTournament JSON`，incluye `id`、`state`、`subclass`、`host_id`、`start_time`、`end_time`、`data`。GSC data es `order`、`token`；competición de velocidad es `year`、`week`、`tournament_format`；competición de eficiencia es `year`、`week`, sin formato. |
| `tournament` | `tournament:normal:participants` | hash | `field = user_id`；`value = list[CachedNormalParticipant] JSON`，cada uno incluye `id`、`token`、`arbiter_identifier`、`tournament`、`start_time`、`end_time`. |
| `tournament` | `tournament:user:score_current` | zset | `member = user_id`；`score = score_current × tournament_score_decay_factor(last_updated, 缓存时间基准)`；Todos los miembros usan el mismo marco de tiempo. No se escriben en la base de datos `score_current = 0`. |
| `tournament` | `tournament:user:score_current:last_updated` | string | fecha y hora con zona horaria; el punto de referencia anual para el conjunto de puntuaciones actual, normalmente el 1 de enero de 00:00 UTC. Se actualiza mediante una tarea de APScheduler anual; las asignaciones de puntuaciones normales no avanzan. Si la tarea de programación se retrasa, se continúa usando el punto de referencia anterior. |
| `tournament` | `tournament:user:score_total` / `gsc_total` / `gsc_best` / `weekly_total` / `weekly_classic_total` / `weekly_classic_best` / `weekly_eff_total` / `weekly_eff_best` | zset | `member = user_id`；la puntuación es el valor correspondiente del campo, el total predeterminado es 0 y no se incluye en la clasificación, el mejor de GSC/competencia de velocidad es un valor entero de señal, el mejor de eficiencia es NULL y no se incluye en la clasificación. El mejor de eficiencia almacena directamente el valor original en punto flotante, sin codificar año o semana. |
| `article` | `articles` | lista | cadena de título de artículo, proveniente de los archivos de artículos en `assets/article` o en el directorio estático. |
| `news` | `news:events:v1` | hash | `field = 事件 id`；value es un JSON de evento, contiene `id`, `category`, `occurred_at` (milisegundos), `player_id` y `payload`. El campo hash no tiene TTL; los elementos vencidos y en exceso son reciclados explícitamente por la parte que los escribe. |
| `news` | `news:idx:all:v1` | zset | `member = 事件 id`, score es un marcador de tiempo en milisegundos; la categoría «Todos» se lee en orden inverso. |
| `news` | `news:idx:cat:{category}:v1` | zset | índice por categoría, sincronizado con el índice general; categorías: `pb`, `lsf`, `eff`. |

Las noticias se generan a partir de los cambios de la actualización actual de las clasificaciones. No se reconstruyen en bloque ni se guarda un historial permanente. Por defecto, un registro solo se elimina si queda fuera de los 200 más recientes y tiene más de siete días. Se conservan todos los registros de los últimos siete días, aunque sean más de 200, y los 200 más recientes, aunque tengan más de siete días. Antes de cada escritura se obtienen de `news:idx:all:v1` los ID que están después de los primeros 200 y que superan el TTL. En el mismo pipeline se eliminan del hash y de todos los índices, se guarda el evento nuevo y se renueva el TTL de cada clave. Las aplicaciones que generan eventos son `speedranking` y `effranking`. Antes de escribir, `speedranking` obtiene la instantánea anterior del jugador. Obtiene la nueva después de escribir el índice de fuerza y antes de actualizar los valores de referencia. Para `pb` se publican las mejoras de marcas que terminan entre las diez primeras después de recalcular los puestos de PB. Para `lsf` solo se publica si cambia el valor real de LSF y el nuevo puesto está entre los primeros 36. Las actualizaciones por lotes generan un evento por cada cambio, con el ID de la repetición que lo causó. Las eliminaciones no generan noticias, ni tampoco `soft_refresh_requested` al cambiar los valores de referencia o la reconstrucción global de la fuerza en segundo plano.

Al añadir repeticiones, de una en una o en lote, `effranking` publica noticias en la sección `eff` cuando mejora un resultado de Thrp o NF IOE. La familia TPE no genera noticias. La mejora se determina comparando las puntuaciones antes y después de la escritura. La posición anterior se lee antes de escribir y la nueva se obtiene con `ZRANK` en el mismo pipeline de escritura. Los reemplazos por un resultado peor, las eliminaciones en lote, las reparaciones administrativas y las reconstrucciones completas tampoco generan noticias. La sección sobre las noticias de portada de `back_end/saolei/effranking/README.md` detalla los datos publicados, los requisitos para las sumas y las reglas de presentación.

`TournamentUser` es un resumen consolidado de las puntuaciones de los torneos con persistencia, utilizando Redis con 9 conjuntos ordenados; total en orden descendente, y tres categorías de mejores puntuaciones en orden ascendente. Cuando un usuario del sitio crea un participante de cualquier tipo de competencia soportado, se crea de forma interna en la transacción actual del banco de datos el marcador `TournamentUser`; al eliminar la inscripción, no se elimina la tabla de resumen del usuario. Los usuarios anónimos tienen un banco de datos nulo, la API devuelve user_id=0 y no se incluyen en la clasificación de puntuaciones. Se mantienen los marcadores originales `weekly_classic_total` y `weekly_classic_best`; el frontend solo simplifica la presentación repetida.

Antes de finalizar, se completan los resúmenes de usuarios, se eliminan los participantes sin video, se actualizan los resultados y los puestos, se marcan como AWARDED, se publican los videos en grupo y se añaden a una cola para tareas independientes de puntos y mejores. La tarea de finalización no se ejecuta antes de una hora después de la hora original de finalización; los intervalos de tiempo individuales y la disminución de puntos siguen usando la hora original de finalización. El worker ejecuta tareas de forma secuencial en un solo proceso; las dos tareas siguientes no tienen dependencia de orden; los cálculos manuales y la reconstrucción de caché se evitan que se superpongan. Los puntos se corrigieron según la diferencia entre los nuevos y antiguos valores de rank_score, se escriben en grupo y, tras la confirmación, se actualizan en grupo los conjuntos zset.

En las competencias de eficiencia, solo se cuentan los videos oficiales y en modo estándar de nivel medio y alto. Se seleccionan 2 altos y 5 medios usando el valor flotante original `timems * cl / (1000 * bv)`, con límites estrictos de 240 y 60 como valores máximos y valores por defecto. Los mejores de eficiencia y sus campos anuales y semanales se escriben en la base de datos, y en ausencia de resultados se establece como NULL; los mejores de GSC y de velocidad se mantienen con su codificación entera original y el valor de sentinela MAX_TOURNAMENT_BEST. Cada tipo de señal solo compara el resultado actual; al eliminar una señal, se reconstruye el mejor a partir de los participantes ya premiados. La actualización del mejor en la base de datos se realiza al finalizar la transacción actual; la publicación en Redis de los resultados de eficiencia se retrasa hasta después de la confirmación; las operaciones de pago en grupo no desencadenan señales de guardado, y utilizan tareas independientes de mejores. Los registros siguen usando el logger de competición.

El comando `refresh_tournament_user_stats` reconstruye los totales y mejores de tres categorías (incluyendo los mejores de eficiencia anuales y semanales), sin modificar el score_current; `rebuild_tournament_user_cache` reconstruye todos los conjuntos zset de puntos. `refresh_tournament_scores` soporta tres tipos de competencias ya premiadas, recalcula los puntos a partir de los videos existentes según las reglas de cada tipo de competencia, corrige las diferencias de puntos y los mejores; no recupera los registros eliminados de inscripción.

El relleno histórico de GSC no crea caché ni incluye la interfaz de gestión en el gráfico de API pública. Al crear participantes, se ejecutan por defecto las operaciones de creación de TournamentUser y actualización de best; los jugadores anónimos no registran puntos de usuario en el zset. La vinculación de identificadores, la creación o subida anticipada de videos se mantienen mediante las colas originales de señales y clasificaciones, y el bloqueo HTTP de entrada cubre las transacciones y los callbacks de solicitud de vinculación, preparación y subida. El campo `has_videos` utiliza una subconsulta EXISTS relacionada, y el identificador de resultado GSC usa `select_related('arbiter_identifier')`, sin leer individualmente la tabla de usuarios. El proceso completo se describe en [Relleno histórico de videos de GSC](./gsc-history-import.md).

Al eliminar un participante, `revoke_rank_score_on_participant_delete` bloquea y actualiza TournamentUser dentro de la transacción de eliminación, y tras el commit solo actualiza el zset de puntos afectados; los miembros con puntos reducidos a cero se eliminan, pero el punto anual permanece inalterado. Durante el rollback de la base de datos, no se emite el caché de descalificación. Las reglas de descuento y clasificación se detallan en [Relación de señales de activación](./signals.md#signal-function-map).

Al publicar en bloque un torneo `reveal_videos_for_tournament` actualiza primero en transacción el marcado de publicación de videos, y solo después actualiza el último ranking, el ranking de velocidad, los registros custom pluck, sus cachés en Redis y el ranking de eficiencia con los IDs fijos de este lote. Cada actualización utiliza un callback independiente `transaction.on_commit(..., robust=True)`; en caso de rollback, no se publica el caché, y si un elemento falla tras el commit, Django registra el error en el log, sin revocar el estado de publicación ni bloquear otros callbacks de caché o medallas. Los callbacks de entrada masiva de medallas también aíslan excepciones, y la actualización del caché no depende del éxito de la entrada. Actualmente no se intenta automáticamente reintentar los callbacks fallidos; las tareas de caché o medallas afectadas deben recuperarse mediante los puntos de reconstrucción o recálculo existentes.

Puntos actuales zset usan un punto de referencia anual fijo. `update_tournament_users` lee el punto de referencia de caché, calcula solo para los usuarios de esta cohorte, sin considerar el avance de los usuarios `last_updated` ni el descenso general de otros miembros. Al escribirse por primera vez en caché, se inicializa en 00:00 UTC del 1 de enero del año actual. El cálculo utiliza `tournament_score_decay_factor(last_updated, 锚点)`; las diferencias de tiempo negativas se manejan automáticamente mediante exponentes negativos; por lo tanto, cuando se calculan nuevos puntos dentro del año, se amplifican al inicio del año, pero todos los miembros comparten el mismo punto de referencia, por lo que el orden es equivalente al puntaje en tiempo real. La lectura del punto de referencia y la escritura en esta cohorte usan redis-py `transaction` (`WATCH` / `MULTI` / `EXEC`); al actualizar en paralelo el punto de referencia anual, se realiza un intento de recuperación. La base de datos mantiene los valores individuales de los usuarios `score_current` / `last_updated`, y la API devuelve estos valores originales; el frontend los muestra con una reducción según `globalNow`; el punto de referencia unificado solo afecta al orden en Redis. Actualizar otros campos como total o mejor no cambia el punto de referencia actual de los puntos.

La función `common.apscheduler.refresh_tournament_score_reference` se ejecuta a las 00:00 UTC del 1 de enero cada año, llamando a `TournamentCache.refresh_tournament_score_reference`, que utiliza `ZUNIONSTORE` con pesos para calcular el zset de puntos actuales en relación con el nuevo punto de referencia, y establece simultáneamente el nuevo punto de referencia dentro de la misma transacción de Redis; los demás rankings y la base de datos permanecen sin cambios. La ejecución repetida en el mismo año no tiene efecto secundario. Se ejecuta también al iniciar el scheduler, para completar la transición entre años; si no se ha completado, el cálculo se basa en el punto de referencia anterior, sin mezclar años. La lectura del punto anterior, el cálculo global y la asignación del nuevo punto se realizan mediante `WATCH` / `MULTI` / `EXEC`, manteniendo coherencia con la escritura de cálculo.

La función `rebuild_tournament_current_score_cache` recalcula y reemplaza de forma atómica el zset de puntos actuales y el punto de referencia desde la base de datos usando el punto de referencia del comienzo del año, sin modificar los otros 8 rankings ni la base de datos. En caso de escritura concurrente en el caché, se desencadena un reintentar; antes del commit, se puede leer aún la lista anterior. Durante el cálculo, se suspenden el cálculo de puntos y las correcciones históricas; `rebuild_tournament_user_cache` limpia y reconstruye en lotes todos los 9 zset y el punto de referencia, suspendiendo así otras escrituras en rankings. Si el zset de puntos actuales no está vacío pero no tiene punto de referencia, se produce un error y se reconstruye explícitamente, sin recurrir a un fallback en la base de datos.

Actualización del caché de clasificaciones por lote se agrupa por campos: cada zset realiza una vez al máximo una operación de múltiples miembros `ZADD` y una vez al máximo una operación de múltiples miembros `ZREM`, escribiendo miembros con puntuaciones no predeterminadas y eliminando miembros con puntuaciones predeterminadas, sin ejecutar comandos individuales para cada usuario. La reconstrucción del caché lee por lotes según `batch_size`.

La función `ensure_tournament_users` elimina duplicados basándose en los `user_id` no vacíos de los participantes y ejecuta `get_or_create`, sin sobrescribir registros existentes; la puntuación predeterminada es 0, la mejor puntuación en GSC/competencia es `MAX_TOURNAMENT_BEST` y la mejor puntuación en eficiencia es NULL, por lo que la creación de registros no escribe en el zset de clasificaciones. Este paso es compatible con datos históricos anteriores que solo tenían participantes, sin registro de `TournamentUser` y sin asignación de puntuaciones, y no se encarga de recuperar puntuaciones históricas perdidas. Los nuevos participantes siguen siendo correctamente asociados mediante la señal de creación. En competencias de eficiencia, la mejor puntuación se verifica primero si está otorgada, luego se lee la agregación y las subclases dirigidas; en inscripciones comunes, no se realiza consulta repetida ni se crea agregación. Al eliminar, si la agregación está ausente, se crea una fila por defecto y se recalcula la mejor puntuación histórica restante. El camino de eliminación para GSC/competencia sigue dependiendo de la entrada de tarea para completarla. Cada tarea registra el número de registros creados, sin necesidad de comandos adicionales de gestión.

El campo `GSCParticipant.t37` es un campo generado persistido en la base de datos y se ha creado el índice `gsc_t37_idx` para servir a las consultas de clasificación en GSC y de historial de mejores puntuaciones. La señal de guardado utiliza el valor temporal de `t37` en la instancia actual del participante para comparar incrementos de mejor puntuación, por lo que no se realiza una consulta adicional para leer el campo generado.

## Catálogo de medallas

Las reglas de las medallas se proporcionan por `medal/definitions.py` y por umbral estático en el código, no se almacenan en la configuración de la base de datos ni se utilizan cachés en Redis. Las búsquedas por código y ordenación se realizan completamente dentro del proceso; la visibilidad relacionada con el usuario se lee de los registros de otorgamiento.

El resumen del jugador se almacena en MySQL en la tabla `medal_playermedalsummary`, una fila por jugador, con el ID del jugador como clave primaria. El JSON solo incluye hechos públicos válidos, valores de progreso, orden de uso y estado de primera escaneo; las definiciones, condiciones de ocultamiento y puntuación se obtienen de las reglas estáticas actuales. Cuando el resumen ya está creado, `player_summary()` devuelve el resultado mediante una sola consulta que une las tablas de jugador y resumen. Este conteo no incluye accesos a autenticación, sesiones, Redis ni intermediarios.

La evaluación en segundo plano, las otorgaciones individuales, las decisiones manuales y el servicio de uso de medallas actualizan simultáneamente los registros de negocio y el resumen del jugador bajo el mismo bloqueo de jugador y la misma transacción de base de datos; si el contenido es idéntico, no se sobrescribe el resumen. Al leer por primera vez a un jugador anterior, se completa desde la tabla existente de medallas, sin escanear las repeticiones. Antes de eliminar el registro de video o de participación en competencia, se elimina la asociación del resumen bajo el mismo bloqueo de jugador y la misma transacción de eliminación. Después de que se comite la transacción, se elimina el registro `medal:display:v4:{user_id}` del jugador; en caso de rollback, tanto el resumen como la clave permanecen. La próxima vez que se lea, se completa el resumen desde el registro con el foráneo nulo. Los scripts que mantienen la tabla original de medallas deben usar la entrada del servicio o eliminar el resumen afectado bajo el mismo bloqueo de jugador y transacción; los puntos de entrada existentes para recálculo por parte de administradores también sincronizarán la reconstrucción del resumen.

La consulta de estado de video utiliza el índice compuesto `video_state_player_level_idx(state, player_id, level)`, y el foráneo del jugador se mantiene mediante un índice independiente `player_id`. Si se utiliza InnoDB nativo y se verifica el foráneo con un índice compuesto que incluya `state`, las actualizaciones de vinculación o desvinculación del estado de video podrían esperar el bloqueo del jugador mantenido por la evaluación de medallas. Colocar `state` en la primera posición evita este tipo de competencia, véase [Descripción de los bloqueos de índices de foráneos en MySQL](https://bugs.mysql.com/bug.php?id=94148). Durante la implementación, se ejecutan normalmente `makemigrations` y `migrate`, y Django reemplaza los índices compuestos antiguos y crea los índices de foráneo según sea necesario.

La repetición o el cambio de tiempo de subida de video desencadena una actualización; antes de publicar el resumen, se corrigen la fecha de otorgamiento, la evidencia y los registros de fase. El resumen se actualiza en la misma transacción, y la clave de estado se reconstruye con la nueva fecha del banco de datos tras la confirmación. Los logros ya obtenidos también se ajustan por cambios de tiempo, sin necesidad de mejora en el rendimiento ni cambio de nivel. Los registros de nuevos jugadores y los logros de tercer nivel incluyen evidencia detallada por categoría; cualquier cambio en una categoría permite recalcular el tiempo de finalización.

El panel frontal y la página de logros comparten servicios para reutilizar resúmenes guardados por el jugador y solicitudes en curso. En caso de escaneo inicial incompleto, se realiza un número limitado de consultas; al cambiar de jugador o al desactivar la página, se cancela la suscripción del componente, y ninguna solicitud anterior puede sobrescribir la nueva. Al guardar el logro, se vuelve inválido el resumen relacionado y se notifica a los suscriptores activos para que actualicen. Al pasar el ratón sobre un nombre, se lee la información en `medal:display:v4:{user_id}`; el caché del navegador solo dura durante la sesión actual de la página.

Después de que una subida de video normal sea exitosa, se inicia en el mismo navegador una verificación de estado limitado compartida. Los intervalos de espera se suceden en 1, 2, 3, 5, 8, 13, 20 y 30 segundos, con un máximo de 8 intentos; se combinan subidas consecutivas, sin reiniciar el contador, y no se procesan simultáneamente los pedidos lentos. El método `GET /api/medal/refresh-status` solo permite a usuarios autenticados consultar su propio estado, utiliza una verificación de existencia (EXISTS) para comprobar si la tarea de actualización o reenvío está en estado READY/RUNNING, no devuelve parámetros de tarea, no la agrega a la cola ni realiza consultas sobre videos. Cada solicitud de estado tiene un tiempo de espera de 5 segundos; si falla o se agotan los intentos, se detiene, y al subir correctamente la próxima vez se reinicia. Si el proceso de cola en el fondo se detiene o se retrasa más allá del límite de espera, no se garantiza la sincronización automática en esta ronda.

Cuando una tarea ya no esté pendiente, el frontend vuelve inválido el resumen correspondiente al jugador, y la página activa de logros y la sección de logros compartan una nueva solicitud de resumen; al mismo tiempo, se elimina el caché de suspensión de nombres. Los nombres que ya han sido mostrados antes se relecturan, los demás se mantienen para la próxima visualización. Las solicitudes anteriores que estén en proceso antes de la subida no se escriben en el caché. Si no hay suscriptores activos de resumen, solo se vuelve inválido el resumen, y se leerá de nuevo al entrar de nuevo. La clave de Redis sigue siendo actualizada por tareas del fondo tras la entrega, el frontend no recalcula ni fuerza la reconstrucción de Redis. Esta notificación solo afecta a la página del navegador que inició la subida; otros navegadores no reciben notificaciones.

Los administradores deciden manualmente guardar en `medal_medaloverride`, y se registran los registros de operación en `medal_medaloverridelog`. Las reglas de revocación solo se guardan en la base de datos; el caché de visualización elimina los otorgamientos revocados, sin guardar marcas de bloqueo ni razones. Al enviar la página de administración, se vuelve inválido el resumen del jugador objetivo en el mismo navegador, mientras que los cachés de otros jugadores permanecen sin cambios. Para restaurar automáticamente se requiere volver a cargar tras completar la tarea del fondo; las páginas ya abiertas en otros navegadores no recibirán notificaciones. Ver las reglas de prioridad detalladas en [Decisión de logros por parte del administrador](./medal-overrides.md).

## Estado del logro

El tipo de logro, dirección, juego y uso de la serie se definen mediante códigos cortos de `config.text_choices.Medal_TextChoices`, y el frontend los encuentra en `utils/medal_const.ts`; el nombre, la descripción y el mensaje se buscan directamente en el diccionario de traducciones del frontend, mientras que el directorio de imágenes y el código del logro permanecen sin cambios. El valor de la serie no supera dos caracteres, y los demás valores de enumeración son caracteres individuales. Los miembros de la enumeración se usan directamente, sin crear alias de valor igual en `medal/utils.py`.

La clave lógica es `medal:display:v4:{user_id}`, con un TTL de 300 segundos, y solo sirve para la solicitud `GET /api/medal/players/state` de visualización. Redis no almacena el estado de cálculo; el ID mínimo de video original del titular, los niveles y modos no completados para el nivel inicial, el nivel natural de habilidad, y las sobrescripciones manuales se obtienen directamente del estado de la base de datos leído en esta sesión. Solo se verifica si el proceso de `MedalScan` ha iniciado; si falta la clave o hay fallo en Redis, no se desencadena una evaluación completa.

El valor contiene solo registros cortos ya otorgados por el jugador, en orden con la lista de logros, y con tiempos en segundos Unix. Si no lleva logros, es `{"grants":[]}`:

```json
{"grants":[{"code":"ability.time.b","stage":20000,"timestamp":1761123456,"scope":"","tournament":null,"rank":null}]}
```

- El campo `code` es la definición, `stage` es el nivel actual, `timestamp` es `granted_at`.
- El campo `scope` es `scope_key`, para logros comunes está vacío; para `tournament` y `rank` proviene del otorgamiento en competencia.
- No guardar `value`, `levels`, `modes`, `locked`, ID de repetición, umbral, puntuación o razón humana. Los elementos no archivados y los eliminados no se escriben.
- Cuando no se encuentren minas tras la búsqueda se puede almacenar `{"grants":[]}`; los jugadores no escaneados no tienen el botón de visualización.

El cálculo en segundo plano realiza una carga de definiciones válidas, progreso del jugador, todos los otorgamientos y las coberturas humanas. Las repeticiones comunes se leen en bloques por clave principal, y se comparan con las posiciones naturales del sistema y los conjuntos de principiantes. Si el tiempo de ejecución pasa de 48 segundos a 46 segundos, no se modifica la evidencia de otorgamiento; al reenviar una repetición anterior o modificar el tiempo, se corrige según necesidad la fecha de otorgamiento, la evidencia y el registro de etapas. Solo se recalcula la evidencia para los niveles afectados; al escanear por primera vez, al realizar un refresco explícito completo o al modificar en bloque existente, se evalúa completamente al jugador. Si el progreso del antiguo sistema de base de datos faltaba conjuntos, se realiza una consulta histórica para completarlo.

El resumen se actualiza dentro de una transacción comercial. Solo se publica cuando cambia la lista de prendas, los registros públicos breves o el estado de escaneo; si cambian los conjuntos internos o los resultados permanecen iguales, no se publica. Al publicar, se obtiene nuevamente el bloqueo del mismo jugador, se lee la versión más reciente del resumen, y durante el periodo de bloqueo se escribe en bloque en Redis; los llamados anteriores y la relleno de caché también siguen este bloqueo para evitar que las versiones antiguas cubran los resultados nuevos. Los rollback comerciales no se publican. Al eliminar la evidencia en una transacción, se elimina la clave; al volver a actualizar, se sigue usando `MedalScan` para incrementar el valor.

La interfaz de estado lee primero en bloque en Redis. Si el ID está ausente, se lee junto con el resumen dentro del bloqueo del jugador: si el resumen está completo, se realiza una sola consulta SELECT; si hay partes del resumen ausentes, se realiza una consulta adicional de otorgamiento en bloque para completar la exhibición; no se consulta historial de repetición. Si el jugador no ha escaneado o no existe, se devuelve una lista vacía, y no se inicia el escaneo en esta interfaz; la primera entrega se realiza mediante la interfaz de detalles y se agrega a [enqueue_medal_backfill](./management-commands.md#enqueue-medal-backfill). Si hay coincidencia en caché, no se ejecutan consultas SQL de negocio.

Los errores de conexión y lectura/escritura en Redis se registran en el log. Los cálculos y los resúmenes de la base de datos no se deshacen. La interfaz de estado devuelve los resultados de la base de datos. Si la publicación falla, se intenta eliminar el valor anterior; en la siguiente solicitud se rellena nuevamente. Si al eliminar en Redis no se puede acceder, el valor anterior se conserva hasta que expire el TTL restante. Este intento de recuperación depende de la lectura siguiente sin coincidencia en caché, sin crear una cola independiente de publicación.

Dentro de la misma pestaña del navegador, tras un pedido exitoso de otorgamiento, revocación o restauración automática por parte del administrador, o tras guardar prendas o subir sincronización, se comparte `refreshPlayerMedals` para que el resumen y el caché del nombre de suspensión del jugador objetivo se vuelvan inválidos. Los mensajes de suspensión abiertos se leen nuevamente en bloque mediante notificación de versión; los que no están abiertos se mantienen hasta la próxima suspensión; los pedidos de administración fallidos no limpian el caché ni agregan un control de tiempo periódico.

## Entrada de escritura y reconstrucción

| Caché | Entrada principal de escritura | Entrada de reconstrucción / limpieza |
| --- | --- | --- |
| Cola de estado de repetición | `videomanager.signals.refresh_state_queue_on_video_save` | La función `videomanager.cache.add_videos_to_state_queues_bulk` puede agregar en bloque a las colas comunes según el estado. |
| Eficiencia Thrp / NF IOE / TPE clasificación | Los señales `effranking.signals` y los servicios en bloque, se actualizan tras la entrega | La orden `rebuild_eff_ranks --ranking-name thrp/nf_ioe/tpe` especifica la reconstrucción de grandes clasificaciones; el administrador corrige el ítem correspondiente de la gran clasificación mediante `admin/rebuild_record`, y la suma se recalcula solo desde el hash individual. |
| Clasificación personalizada de pluck | Se guarda al actualizar `update_custom_pluck_top_cache`; al eliminar una repetición se llama `refresh_custom_pluck_rank` para rellenar, y al eliminar un registro se llama `sync_custom_pluck_top_cache` para sincronizar el estado actual | La orden `manage.py rebuild_custom_pluck_cache` reconstruye completamente desde `CustomPluckRecord`, sin crear registros faltantes en la base de datos. |
| Competencia NORMAL | `TournamentCache.update_tournament` | `manage.py rebuild_tournament_cache` Consulta explícita `NORMAL` GSC, competencias de velocidad y registros de eficiencia y reconstrucción. |
| Relación de participación en competencia NORMAL | `TournamentCache.update_participant` / `remove_participant` | La orden `manage.py rebuild_tournament_cache` reconstruye agrupando por `user_id`. |
| Clasificación de puntos de competencia | Los métodos `TournamentCache.update_tournament_user` / `update_tournament_users`; el actualizador de APScheduler actualiza los puntos anuales como punto de referencia | `manage.py rebuild_tournament_user_cache` reconstruye todos los 9 zset; `manage.py rebuild_tournament_current_score_cache` recalcula de forma atómica el zset de puntuaciones actuales y el punto anual de referencia. |
| resumen común | corresponde a la operación interna `cache.set` del API | vence automáticamente al final de su TTL. |
| Catálogo de medallas | reglas de código estático | no hay caché por directorio, tablas definidas en base de datos ni escrituras de inicialización; las reglas se actualizan con cada publicación del código. |
| Estado del logro | al cambiar la lista de recompensas, los otorgamientos públicos o el estado de escaneo, se lee el resumen más reciente al enviar y se escribe `medal:display:v4:{user_id}` | se rellenan por lotes según necesidad los campos faltantes para la visualización, sin escanear las repeticiones; se elimina la clave cuando se borra el resumen. `manage.py enqueue_medal_backfill` incluye por defecto a los jugadores no escaneados en la cola, y con `--all` también incluye a los ya escaneados. |
| tabla de contenidos | `article.views.update_list` | los administradores pueden llamar manualmente a `update_list` para actualizar completamente. |

## lectura según acuerdos

- la lista de competencias NORMAL es de solo lectura en `tournament:normal`, no cae a la base de datos en caso de ausencia en caché; si el caché y la base de datos no están sincronizados, se considera un error en la ruta de escritura.
- el caché de la cola de repeticiones no almacena los videos de competencias; `VideoQueueCache.add` / `add_bulk` omiten los videos con `ongoing_tournament=True`.
- al hacer checkin de participantes, se lee primero `tournament:normal:participants`, y luego se consulta el objeto de la competencia por ID, para establecer la relación muchos-a-muchos en los videos de registro.
- `customranking:pluck:{level}:rank` solo almacena los datos necesarios para el orden; los campos de visualización provienen del hash `detail` del mismo nivel.

## almacenamiento físico de los videos

la compresión solo modifica los campos de almacenamiento como `file`, `original_filename`, `stored_file_size`, `compression_format`, `compression_failed`; los valores originales de `file_size`, `original_hash` y los resultados de análisis permanecen sin cambios, no se actualiza la versión del caché del video en el frontend, ni se almacena el contenedor comprimido en IndexedDB.

el resumen del disco del servidor y el espacio de archivo de `UserMS` suman `stored_file_size`; los videos originales no completados se devuelven a `file_size`. Al subir o importar nuevos videos, se intenta comprimir y verificar antes de crear el video; si se logra, se guarda el archivo comprimido, si no, se guarda el archivo original y se registra `compression_format=0`, `stored_file_size=file_size` y la marca de error; en ambos casos se sigue el mismo proceso de creación; los archivos históricos se convierten manualmente por parte del administrador mediante `compress_video_files`, y se sincroniza la diferencia de espacio del usuario durante la transacción de cambio de archivo, sin registrar tareas de compresión de APScheduler.

preview Solo con el ID numérico devuelve el archivo almacenado actualmente; el cliente lo descomprime según la versión del contenedor; download Recupera los bytes originales del video en la solicitud, reutiliza el tamaño de salida y límites de memoria de `original_file`, no crea archivos temporales, no almacena el resultado descomprimido ni modifica el archivo almacenado. Cada IP está limitada por `20/m` y `5/m` para ambos; en producción, el preview y la descarga de archivos no comprimidos siguen el camino de `X-Accel-Redirect`, mientras que la descarga de archivos comprimidos se envía directamente desde Django mediante una respuesta en bytes de memoria descomprimidos.

la lista blanca de CORS, las solicitudes preflight y las cabeceras de respuesta públicas se configuran unificadamente en `default.conf`, se evalúan según el valor original de `$request_uri`, por lo tanto, tras `X-Accel-Redirect` se mantiene el alcance de dominio cruzado original del API. Los medios internos heredan las cabeceras CORS del servidor HTTPS y recuperan `X-Replay-Container-Version` desde las variables superiores. En entornos DEBUG y Cypress se gestionan mediante el middleware CORS de Django. Se valida primero, se recarga la configuración completa de Nginx, y luego se actualiza el backend de producción, evitando que durante la transición se pierdan las cabeceras de dominio cruzado.
