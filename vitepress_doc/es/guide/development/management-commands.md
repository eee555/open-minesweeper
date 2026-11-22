# Comandos de gestión personalizados del backend

Este documento registra comandos personalizados de Django y puntos de entrada para la inicialización de datos locales. Se ejecutan en el directorio `back_end/saolei`. Los parámetros completos de los comandos se pueden ver con `--help`:

```bash
python manage.py <command> --help
```

## Creación de registro para cuentas homenaje

### `create_memorial_account`

Ubicación: `common/management/commands/create_memorial_account.py`.

El administrador debe verificar primero mediante el servidor, comandos existentes y shell la eliminación y limpieza de identidades antiguas, y luego especificar explícitamente el ID de UserProfile, el ID de UserMS y el nombre de usuario. Ambos números deben estar disponibles y menores que el máximo clave principal actual de sus respectivas tablas; no se agregan automáticamente, no se toman en posesión cuentas aisladas de UserMS, y se rechaza la creación si la tabla está vacía.

```bash
python manage.py create_memorial_account 42 70 legend --realname "传奇玩家" --country CN
```

Los IDs y datos son solo ejemplos y deben reemplazarse por valores verificados disponibles; además se admite `--firstname`, `--lastname`, `--signature`. El comando bloquea en transacción las filas con el máximo ID de las dos tablas, verifica disponibilidad y realiza solo la inserción, con rollback en caso de validación de modelo o conflicto de ocupación. Las nuevas cuentas no pueden iniciar sesión, no tienen permisos de administrador, usan contraseñas no válidas y tienen direcciones de correo independientes inactivas.

La limpieza de datos antiguos y el mantenimiento de información se realizan mediante herramientas existentes del administrador; la retransmisión de videos se realiza mediante `/superuser/memorial`. Las reglas de negocio se detallan en el repositorio `back_end/saolei/userprofile/README.md`.

## Primera migración y sincronización incremental de Open Minesweeper

### `sync_saolei_api`

Ubicación: `accountlink/management/commands/sync_saolei_api.py`. Utiliza la clave `saolei_api_key` del archivo `secrets.json` del servidor, y solo procesa cuentas de Open Minesweeper ya validadas y con asociación coherente. Esta primera fase se realiza mediante este comando; tras la migración se han abierto nuevos APIs de Ninja y sincronización manual desde el frontend, además se ha añadido una tarea diaria de sincronización automática. Los comandos del administrador no están afectados por el estado del usuario `auto_sync`; en las fases que implican importación de archivos se ignoran las marcas `import_rejected`, se intentan nuevamente todas las fuentes de lista blanca que no estén asociadas a videos de esta plataforma, constituyendo un canal de reintentos forzado tras un fallo de importación.

Antes de la implementación, se debe usar el comando existente `backfill_video_hashes` para completar los hashes de los archivos originales existentes, luego ejecutar `makemigrations accountlink --noinput` y verificar los resultados generados, y finalmente ejecutar `migrate`. Los archivos de migración no se siguen según la convención del repositorio; los números dependen de la historia existente del servidor. Se deben generar estructuras de migración que eliminen las antiguas `VideoSaolei`, creen una `SaoleiApiVideo` independiente y modifiquen los campos de la cuenta, conservando el vínculo de cuenta, los videos de esta plataforma, los registros extendidos y los archivos. Al ejecutar por primera vez, se puede especificar primero un ID de cuenta de Open Minesweeper para verificar los resultados, y luego procesar todos los vínculos asociados:

```bash
python manage.py sync_saolei_api --account-id 101 --full
python manage.py sync_saolei_api --all-linked --full
python manage.py sync_saolei_api --all-linked
python manage.py sync_saolei_api --all-linked --phase metadata
python manage.py sync_saolei_api --all-linked --phase videos --limit 100
```

`--account-id` se puede especificar múltiples veces; `--all-linked` indica todos los vínculos validados, y ambos deben seleccionarse exclusivamente. `--full` realiza un escaneo completo del directorio desde cero, sin borrar datos ni retroceder el cursor de éxito del jugador; eliminar esta opción para ejecuciones incrementales y continuación tras interrupción. `--page-size` tiene un valor predeterminado de 200, con valores comprendidos entre 1 y 1000.

`--phase` por defecto es `all`: primero completa la sincronización de los datos, directorios y detalles en lote del usuario seleccionado (`video_info` tiene como máximo 50 IDs por lote, actualización de metadatos), luego descarga e importa individualmente por ID de repetición. `--phase metadata` solo actualiza metadatos y no descarga archivos; `--phase videos` no solicita `stats`, `video_list` ni `video_info`, y descarga directamente por ID de repetición los fuentes pendientes de importación. `--limit` es el límite máximo de intentos por ronda de importación (incluyendo los fracasos), por defecto no hay límite; `--full` no puede usarse junto con `--phase videos`. En las fases de importación de archivos se requiere que los hashes originales de todos los videos existentes sean completos, pero no se requiere en la fase de metadatos.

La secuencia de comandos comparte un único cliente, con intervalos de 2.1 segundos para solicitudes de datos y 0.4 segundos para solicitudes de archivos; el control de velocidad de Redis se comparte con la página web, el calendario diario y los trabajadores de importación horaria, y aún así no se deben iniciar simultáneamente múltiples comandos de sincronización. Las páginas de directorio y `AccountSaolei.video_sync_cursor` se envían en transacción, y en caso de fallo no se avanza; los detalles y los archivos se recuperan de forma independiente para evitar pérdidas cuando el cursor se ha avanzado pero la recuperación posterior no se completa. La lista blanca de software es exacta: `Clone`, `Vienna`, `Arbiter`, `元扫雷`; los demás nombres solo se guardan en el directorio y se omiten; el upstream `status` no tiene límites de importación.

Los directorios se continúan en orden estricto de ID mayor que el cursor ya almacenado; `next_cursor` puede ser igual al último ID de esta página, sin incrementarse automáticamente. Al superar el valor `stats().max_video_id` de esta ronda, solo se envían los registros dentro del límite superior, y el cursor se almacena como máximo hasta ese límite; en la siguiente ronda, se podrá recuperar el video inmediatamente posterior al límite superior.

Al recibir directamente la verificación de archivos de esta página y rechazarlos (`file/type`, `file/incomplete`, `file/level`, `file/review`), se guarda el origen como `import_rejected=True`. El primer rechazo se cuenta como fallido; los incrementos posteriores y el `--full` se omiten, sin realizar solicitudes de detalles ni descarga de archivos, y se cuentan como omisiones. Al actualizar el directorio, se conserva la marca. Cuando se requiera reintentar manualmente, en el shell de Django se debe establecer el valor de `import_rejected` como `False` para el origen especificado y luego volver a ejecutar. Los fallos de red, de origen superior, de configuración, de enlace o de escritura aún pueden reintentarse; los videos con estado de congelado o pendiente de revisión que se guardan normalmente no reciben la marca de rechazo. Para implementar este cambio de campo, también es necesario ejecutar primero `makemigrations accountlink --noinput` y `migrate`.

Cuando hay coincidencia con el hash del archivo principal, se reutiliza el video de partida existente en esta página; en caso de conflicto de propietario, no se modifica la asignación ni la hora de subida. Si falla una operación individual, se conserva el progreso exitoso y se realiza un resumen, y el código de salida será distinto de cero; en caso de fallo de autenticación o límite de tráfico, se detiene inmediatamente sin intentos automáticos de reintentar. El progreso se muestra en la salida del comando y en los registros `accountlink`; los errores del cliente conservan el tipo de excepción y la causa específica, sin mostrar cabeceras de autenticación ni cuerpos de respuesta. Los datos del usuario solo incluyen ID, nombre y estado de bloqueo en sitios externos, sin sincronizar resultados ni listas de identificadores. Al implementar la funcionalidad de sincronización diaria, se genera y ejecuta automáticamente la migración de los campos configurados como activos por defecto en `auto_sync`, y luego se reinicia Web, worker y el APScheduler centralizado; no se vacía nuevamente las tablas de origen ni se realiza una importación completa.

El análisis de archivos se ejecuta mediante un subproceso independiente, cada uno con un límite de 60 segundos; un fallo nativo o tiempo de espera se considera `rust/panic` y se continúa con el siguiente, sin establecer una marca permanente de rechazo. `accountlink` registra el ID de la repetición, el ID de cuenta y la URL relativa del archivo antes del análisis; `utils.parser` registra el código de salida anómalo y el diagnóstico final; la siguiente sincronización reintentará estos fallos. El aislamiento utiliza la biblioteca estándar de Python [`subprocess.run`](https://docs.python.org/3.12/library/subprocess.html#subprocess.run)], sin copiar la conexión de base de datos del worker.

## Clasificación de obras

### `refresh_media_rankings`

Ubicación: `media/management/commands/refresh_media_rankings.py`. Comando manual de baja frecuencia, usado para avanzar el punto de referencia de popularidad, reconstruir desde cero los cuatro rankings de obras en zset y realizar inspecciones de solo lectura; **no se incluye en el flujo de despliegue ni en `start.sh` / `stop.sh`**. Los comandos anteriores `rebuild_media_rankings` y `check_media_rankings` se han integrado en este comando. Las tareas mensuales de `refresh_media_hot_reference` en APScheduler y las tareas de sincronización del fondo de media ya han sido eliminadas.

```bash
python manage.py refresh_media_rankings --check
python manage.py refresh_media_rankings --check --max-examples 20
python manage.py refresh_media_rankings --rebuild-only
python manage.py refresh_media_rankings --reference 2026-12-01T00:00:00+00:00
python manage.py refresh_media_rankings --batch-size 500
```

`--check` Solo lectura: aplica `decay(T_db, T_r)` a cada `hot_value` de obras `verified` para calcular su puntuación esperada y acumular la puntuación por autor, comparándola luego con los cuatro zset (tolerancia relativa o absoluta de `1e-6`). Si coincide, muestra `matches the database` y finaliza normalmente; si hay miembros adicionales, faltantes, puntuaciones desajustadas o ausencia de `T_r`, lanza un `CommandError` con código de salida no nulo indicando ejemplos de desfase y sugerencias de corrección, para permitir alertas externas basadas en el código de salida. El banco de datos siempre es el valor oficial; las revisiones ya no muestran FAILED ni el número de tareas de sincronización acumuladas (no hay tareas de fondo para media), y no es necesario evitar los ventanales de actualización mensual.

`--rebuild-only` No actualiza `T`, solo reconstruye los cuatro zset de forma completa a partir del valor actual de `T_r`, para corregir desfases causados por competencia o fallos en Redis; en caso de base vacía, elimina los cuatro zset antiguos. Si no se incluye `--check` ni `--rebuild-only`, primero se ejecuta `--reference` (por defecto en el momento actual, formato ISO 8601 UTC, no antes que `T_db` actual) dentro de una transacción del banco de datos usando `F()` para multiplicar todos los `hot_value` por `decay(T_db_old, T_new)` y escribirlos en el nuevo `T_db`, luego se reconstruye completamente y se publica `T_r`. Repetir la ejecución con el mismo `--reference` no realizará una escala repetida del banco de datos. `--batch-size` (por defecto 1000, debe ser positivo) y `--max-examples` (por defecto 10, debe ser positivo) controlan respectivamente el tamaño de lote de reconstrucción y el número de ejemplos de revisión.

Reconstrucción completa solo toma `status='verified'`, escribe en la clave temporal `media:rebuild:<uuid>:*`, y finalmente en un `MULTI/EXEC` se combinan los cuatro zset oficiales mediante `rename` y `SET media:hot:anchor`; en caso de error, se borra la clave temporal y se mantiene la clasificación anterior. El comando **no tiene bloqueo ni impide la escritura de solicitudes**: durante su ejecución, los incrementos en las claves oficiales podrían ser temporalmente cubiertos por `rename`, lo que causa un desplazamiento breve, ya confirmado como aceptable; el banco de datos siempre es correcto, y se puede recuperar al volver a ejecutar o al siguiente acceso a la ruta de escritura. Si falla la publicación en Redis, el comando lanza `CommandError`, indicando que `T_db` ya es el valor oficial, y se puede volver a ejecutar el comando sin interrumpir el servicio.

El umbral de popularidad `T` aún requiere avance, ya que evita que `1 / decay(T, now)` crezca exponencialmente a largo plazo hasta que ocurra un desbordamiento de punto flotante; con double se puede establecer al menos anualmente, por lo que basta con realizar una vez al año `--reference` manualmente. `T_r` se inicializa con `T_db` usando `SET NX` al primer llamado de `get_hot_reference()` (lectura de la lista de autores o sincronización del caché de ruta de solicitud), y cuando la base esté vacía, los cuatro zset estarán vacíos, lo cual es correcto; el proceso de despliegue no requiere reconstrucción completa.

### Detección de fallos

El banco de datos es la fuente de verdad, Redis es el índice de clasificación. Si ocurre un error en la sincronización del caché de la ruta de petición, solo se registra un mensaje de error `media` en `logs/media.log`, sin revertir el banco de datos, sin generar tareas FAILED, ni tareas de reinicio ni acumulación. El método de detección es `refresh_media_rankings --check`: expone mediante código de salida no nulo los desfases entre los cuatro zset y el banco de datos (incluyendo ausencia de `T_r`), se recomienda integrar alertas externas periódicas; el método de corrección es `--rebuild-only` (solo corrige desfases) o un avance raro de referencia con `--reference`.

Las obras aprobadas aparecen en orden de fecha de publicación pero no en el ranking de popularidad en tiempo real o en acumulación de votos: primero ejecuta `--check`; si se muestra `missing member`, indica que los cuatro zset aún no están sincronizados, ejecuta `--rebuild-only` para solucionarlo. Los rankings de popularidad en tiempo real y acumulación de votos se leen directamente de los zset de Redis, mientras que el orden por fecha de publicación se consulta directamente en el banco de datos; las obras con `likes` o `hot_value` igual a 0 aún aparecerán en el ranking pero al final, y si el número de obras supera una página, se debe navegar a la siguiente. Hacer clic en la cabecera vuelve a cargar la lista, o se puede usar el botón de actualización en la parte superior de la tabla para cargarla manualmente.

## Reembolso de medallas

### Actualización de reglas estáticas

Las reglas y umbrales de las medallas están definidas en `medal/definitions.py` y `medal/utils.py`, y se publican mediante revisión de código. El progreso del jugador, la asignación, el uso, la cobertura manual y los registros de auditoría se mantienen en la base de datos. Las medallas no definidas o desactivadas conservan sus datos históricos; el directorio público solo muestra las definiciones activas. El directorio de reglas ahora lee directamente las definiciones del código.

Las bases de datos existentes se actualizan siguiendo los siguientes pasos.

1. Pausa el servicio posterior y las tareas de medallas, realiza una copia de seguridad de la base de datos y exporta `medal_medaldefinition`. Compara la configuración original con las reglas del código. Se establecen fijamente los requisitos de los cuatro modos: 00, 05, 06 y 10. Los conjuntos de modos personalizados en la configuración anterior ya no se aplican.
2. Ejecuta `python manage.py makemigrations medal --name static_definitions` basado en el historial de migraciones existente en el servidor. Revisa las operaciones generadas, asegurándote de que primero se elimine el foreign key `PlayerProgress.definition`, y luego se elimine el modelo `MedalDefinition`. El número de migración depende del historial existente del servidor.
3. Usa `python manage.py migrate medal --plan` para verificar el plan de migración, y luego ejecuta `python manage.py migrate medal`. Los foreign keys antiguos tienen comportamiento de eliminación en cadena, por lo que eliminar directamente las definiciones de medallas mediante ORM eliminará también el progreso asociado.
4. Verifica el progreso del jugador, las asignaciones, el uso, la cobertura manual y los registros de auditoría antes y después de la migración, asegurándote de que el número de registros, los identificadores principales y el contenido sean consistentes. Las asignaciones existentes mantienen el `definition_code` anterior, y el progreso utiliza el `code` anterior.
5. Inicia el nuevo servicio y los trabajadores de fondo, y sigue el procedimiento `--all` descrito a continuación para previsualizar, dividir en lotes y verificar. La migración completa y el recálculo se ejecutan manualmente durante la implementación.

En nuevas instalaciones, se genera una migración inicial basada en el modelo actual. La tabla de definiciones de medallas ya ha sido eliminada del modelo. Si es necesario retroceder tras la actualización, se debe restaurar usando la copia de seguridad y la configuración exportada antes de la actualización, y se debe revisar nuevamente los foreign keys, el estado del jugador y el caché.

### `enqueue_medal_backfill`

Ubicación: `medal/management/commands/enqueue_medal_backfill.py`

Por defecto, se agrega a la cola el jugador sin `MedalScan` para la tarea `task_backfill_player_medals`; el parámetro `--all` incluye a los jugadores ya escaneados, útil para recálculos históricos tras cambios en las reglas. Si un jugador ya tiene una tarea `READY` para reembolso, se reutiliza la tarea existente y no se inserta nuevamente. La prioridad de la tarea es 0, menor que las actualizaciones diarias de carga.

El comando solo consulta a los jugadores y crea tareas, no escanea repeticiones ni reconstruye Redis. Los trabajadores ejecutan completamente `evaluate_player`, actualizan todas las medallas automáticas y el resumen del jugador, y conservan las decisiones de cobertura manual. El final de la cola no implica que el recálculo esté completo; se debe revisar el estado de finalización o fallo de las tareas de fondo y los resultados reales del jugador.

| Parámetros | Uso |
| --- | --- |
| `--all` | Incluye a los jugadores ya marcados como escaneados; se requiere esta opción al cambiar las reglas en línea. |
| `--dry-run` | Solo muestra el número de candidatos y el límite superior de los IDs, sin crear tareas. |
| `--batch-size 200` | Número de IDs de jugadores leídos por cada lectura, paginado por clave principal, sin usar OFFSET; no representa un límite de velocidad de ejecución de tareas. |
| `--limit 500` | Número máximo de jugadores que se procesan en esta iteración (incluyendo jugadores que ya tienen tareas pendientes), para dividir el proceso en lotes. |
| `--after-id ID` | Solo procesa a jugadores con ID mayor que este valor, útil para continuar desde donde se dejó. |
| `--through-id ID` | Límite superior del ID del jugador; si no se especifica, se fija al máximo ID al momento de iniciar el comando. |

```bash
# Por defecto, solo se procesan los jugadores que aún no se han evaluado.
python manage.py enqueue_medal_backfill

# Después de cambiar las reglas, obtener primero una vista previa de todos los jugadores y encolar por lotes pequeños.
python manage.py enqueue_medal_backfill --all --dry-run
python manage.py enqueue_medal_backfill --all --limit 500 --batch-size 100

# Tras completar y verificar el lote, continuar con last_user_id y through_id del registro.
python manage.py enqueue_medal_backfill --all --after-id LAST_USER_ID --through-id THROUGH_ID --limit 500 --batch-size 100
```

Al fallar, el comando informa del ID del último jugador procesado con éxito, y puede reintentarse con las mismas opciones de filtrado; las tareas READY ya existentes se eliminan. Repetir la evaluación completa no genera duplicados de medallas, pero si un jugador ya completó la tarea y vuelve a entrar en cola, sí genera carga de consulta. Monitorea en batches el acumulado de trabajadores y la carga de la base de datos, sin cargar de forma indefinida a todos los jugadores productores; incluso al repetir solo tareas fallidas, el rango debe seleccionarse según el estado real.

Al cambiar del modo antiguo de 'recorrido rápido' al modo cuatro, es necesario cubrir a los jugadores ya escaneados. Después de implementar las reglas estáticas y migrar la estructura de la base de datos, se debe reenviar mediante el proceso anterior `--all`; simplemente refrescar la página, limpiar Redis o ejecutar comandos por defecto no garantizan que los jugadores antiguos sean reevaluados. Se determina el tiempo inicial de reunión según el primer video aprobado en cada modo, y se prohibirá manualmente la distribución, sin que se agregue automáticamente al equipo.

## Ranking de juegos pequeños

El comando `minigame/management/commands/rebuild_minigame_ranks.py` reconstruye el ZSET, el hash detallado y la marca de inicialización a partir de los mejores resultados almacenados en la base de datos; también inicializa las listas vacías. No modifica la base de datos, permitiendo pequeñas desviaciones temporales cuando se ejecuta simultáneamente con envíos.

```bash
python manage.py rebuild_minigame_ranks
python manage.py rebuild_minigame_ranks --ranking-key left-click-b-50-v1
```

Primera implementación, ejecuta primero `python manage.py migrate`. El caché también puede inicializarse según necesidad al realizar la primera consulta; durante fallos en Redis, las consultas se degradan a la base de datos.

## Actualización del caché de repetición

### `compact_video_cache`

Simplificar la muestra repetida de campos de hash para los cuatro plucks personalizados de `newest_queue` y eliminar los marcadores `freeze_queue`, `review_queue` ya no mantenidos. No escanear el espacio de claves de Redis ni reconstruir el último conjunto de miembros; los miembros modificados o eliminados de forma concurrente no serán cubiertos por valores antiguos ni reintroducidos.

```bash
python manage.py compact_video_cache --dry-run
python manage.py compact_video_cache
```

Primero despliega el nuevo frontend y backend y asegúrate de que los procesos antiguos hayan terminado, luego ejecuta el compresor. El comando puede ejecutarse repetidamente, muestra la cantidad de cambios y la estimación de memoria; la correspondencia entre interfaces y campos de almacenamiento se encuentra en el `front_end/src/services/videoService.md` del repositorio.

## dangerzone.init_local_test (script independiente) {#本地公开数据快照}

### `dangerzone.init_local_test`（script independiente）

La descarga y la inicialización se encuentran respectivamente en `dangerzone/download_public_data.py`, `dangerzone/init_local_test.py`; utiliza `python -m` para iniciar.

**La inicialización borrará la base de datos local y la base de datos Redis correspondiente a `saolei_website`.** Utiliza una base de datos local independiente y Redis para ejecutarla; antes de ejecutarla, detén los trabajadores, tareas programadas y otros procesos de escritura. Se requiere que no existan marcadores `.production`, `DEBUG=True`, `E2E_TEST=True`; tanto la base de datos como Redis deben tener direcciones de bucle; antes de importar se verificará la integridad del snapshot y las relaciones de referencia.

```bash
# Descargar los metadatos públicos. Se puede reanudar una descarga interrumpida.
python -m dangerzone.download_public_data
# Si detailbulk no está disponible, completar la instantánea con los detalles existentes y la lista pública de repeticiones.
python -m dangerzone.download_public_data --skip-details
python manage.py migrate
# Leer la instantánea, vaciar la base de datos, importar los datos y crear el torneo semanal clásico del día.
python -m dangerzone.init_local_test
# Importar sin crear un torneo semanal.
python -m dangerzone.init_local_test --no-weekly
```

El directorio predeterminado de instantáneas es `tmp/public-data`. Para descargar usa `--output-dir`, para importar usa `--snapshot-dir` para especificar otro directorio. La descarga solicita solo el API público, y tras cada respuesta se espera al menos 1.25 segundos; `--interval` puede aumentar este intervalo. Las instantáneas completadas no refrescan los datos existentes; para obtener nuevos datos es necesario cambiar de directorio; las instantáneas antiguas pueden completarse mediante la ejecución nuevamente del punto de entrada de descarga para recuperar los identificadores de usuario.

Importar IDs de usuarios/repeticiones, atributos públicos y pertenencias de identificadores de usuarios, y reconstruir automáticamente el contador de repeticiones, el límite de subida, la clasificación de velocidad (incluyendo NF, sin adivinar normal), el ranking de eficiencia Thrp, el caché de registros pluck y la cola de estados de repeticiones. `--no-weekly` solo salta la creación de competiciones semanales, sin afectar la reconstrucción.

- Administrador: ID `2`, contraseña `admin123456`; cuenta común: ID `48`, contraseña `user123456`. El nombre de usuario conserva los datos de producción; se puede especificar otra contraseña mediante `--admin-password` / `--user-password`.
- Otros usuarios desactivan el acceso mediante contraseña; solo el ID `2` tiene permisos de administrador local, con correo unificado en `user-{id}@example.invalid`.
- Las instantáneas no incluyen la contraseña original, el correo electrónico, los archivos de repetición, los archivos de perfil ni las asociaciones de competiciones. Las repeticiones se pueden usar para pruebas en listas y clasificaciones, pero no se pueden reproducir localmente ni reanalizar; el contador de repeticiones no excluye las repeticiones de competiciones públicas sin asociación.
- `--skip-details` Prioriza los detalles existentes, los demás videos usan los datos de la lista. Los indicadores faltantes se mantienen como NULL, los identificadores dentro del video pueden estar vacíos; se conserva el `right_ce` proporcionado por la lista para la evaluación de NF, sin inferencias basadas en el modo anterior.
- `--metadata-index` Salta la repetición de análisis en la lista de repeticiones, solo para pruebas que no dependen de Pluck, no puede usarse junto con `--skip-details`.

Descarga de opciones, formatos de instantáneas y limitaciones de compatibilidad unificadas en el `back_end/saolei/dangerzone/readme.md` del repositorio.

## Reconstrucción de caché

### `rebuild_eff_ranks`

Ubicación: `effranking/management/commands/rebuild_eff_ranks.py`

Reconstruye la clasificación de eficiencia a partir de la base de datos de repeticiones. `--ranking-name` soporta `thrp` (predeterminado, incluye la lista de puntuaciones máximas en niveles avanzados), `nf_ioe` y `tpe`; `--batch-size` tiene un valor predeterminado de 1000 y debe ser un número positivo. Después de añadir una nueva clasificación grande, se debe ejecutar explícitamente para incluir las repeticiones históricas en el caché, sin necesidad de migrar datos de registros personales.

`--ranking-name tpe` reconstruye los seis récords personales y los nueve conjuntos ordenados de TPE, TPE2 y TPE3. Ejecuta el comando una vez al desplegar las nuevas fórmulas para incorporar las repeticiones históricas. No requiere una migración de la base de datos.

```bash
python manage.py rebuild_eff_ranks
python manage.py rebuild_eff_ranks --ranking-name nf_ioe
python manage.py rebuild_eff_ranks --ranking-name tpe
```

Ejecuta al crear una clasificación por primera vez o tras pérdida del caché. La API no vuelve a consultar la base de datos. Antes de ejecutar, se debe suspender la subida, revisión, modificación, eliminación, marcación de vinculación/desvinculación y publicación de competencias. El comando construye primero una clasificación temporal, la reemplaza de forma atómica si es exitosa, y mantiene la anterior si falla. Ver las reglas en `back_end/saolei/effranking/README.md`.

### `rebuild_speed_ranks`

Ubicación: `speedranking/management/commands/rebuild_speed_ranks.py`

Reconstruye el ranking de velocidad a partir del modelo `VideoModel`, agrupado por jugador. `--ranking-name` puede ser `saolei` o `saolei_nf`, si no se especifica se reconstruyen ambos; `--batch-size` tiene un valor predeterminado de 1000 y debe ser un número positivo.

```bash
python manage.py rebuild_speed_ranks
python manage.py rebuild_speed_ranks --ranking-name saolei_nf --batch-size 1000
```

Ejecuta al crear una clasificación por primera vez o tras pérdida del caché. La API no vuelve automáticamente a la fuente. Antes de ejecutar, se debe suspender la subida, modificación, eliminación, marcación de vinculación/desvinculación y publicación de competencias. El comando construye primero una clasificación temporal, la reemplaza de forma atómica si es exitosa, y mantiene la anterior si falla. Se requieren especificaciones de codificación y actualización en `back_end/saolei/speedranking/README.md`.

### `rebuild_strict_ng_ranks`

Ubicación: `speedranking/management/commands/rebuild_strict_ng_ranks.py`

Reconstruir el ranking de velocidad de predicción fuerte desde `VideoModel`, solo acepta repeticiones del modo fuerte de predicción, 3BV no vacío y 3BV básico ≥ 2; para intermedio y avanzado no hay límite. `--ranking-name` puede ser opcional `strict_ng` o `strict_ng_nf`, si se omite se reconstruirán ambos; `--batch-size` predeterminado en 1000, debe ser un número positivo.

```bash
python manage.py rebuild_strict_ng_ranks
python manage.py rebuild_strict_ng_ranks --ranking-name strict_ng_nf --batch-size 1000
```

Independiente de `rebuild_speed_ranks`, no borra el caché del otro; también construye primero una clasificación temporal, reemplaza cada gran clasificación de forma atómica si es exitosa y luego elimina la clave temporal. Antes de ejecutar, se debe suspender la subida, modificación, eliminación, marcación de vinculación/desvinculación y publicación de competencias. Ver las reglas en `back_end/saolei/speedranking/README.md`. La inicialización de instantáneas locales `init_local_test` llama a este comando tras importar datos, sin necesidad de reconstruir manualmente el ranking de estricto sin adivinanzas.

### `rebuild_pb_ranks`

Ubicación: `speedranking/management/commands/rebuild_pb_ranks.py`

Reconstruye el ranking de PB (normal/NF), el ranking de usuarios y el número de participantes en las clasificaciones pequeñas a partir de la base de datos de repeticiones. `--batch-size` tiene un valor predeterminado de 100 y debe ser un número positivo.

```bash
python manage.py rebuild_pb_ranks
```

Ejecuta al crear una clasificación por primera vez o tras pérdida del caché. La API no vuelve a la fuente. Antes de ejecutar, se debe suspender la lectura y escritura relacionadas con PB, incluyendo subida, revisión, vinculación/desvinculación, eliminación y publicación de competencias. El comando borra directamente el espacio de nombres de PB y lo reconstruye, posiblemente dejando parte del caché si falla; tras corregir errores, se debe volver a ejecutar. Una vez que se actualicen completamente el ranking principal y los rankings de las pequeñas clasificaciones, se llama una vez al final al reemplazo completo de los rankings derivados de PB, por lo que no es necesario ejecutar nuevamente `rebuild_pb_derived_ranks`.

### `rebuild_pb_derived_ranks`

Ubicación: `speedranking/management/commands/rebuild_pb_derived_ranks.py`

Recalcula de forma completa los tres grandes rankings: colección, fuerza y tiempo típico, a partir de los hashes de usuarios existentes en `speedranking:pb:player:*`, sin volver a escanear la tabla de repeticiones. `--batch-size` tiene un valor predeterminado de 100 y debe ser un número positivo.

```bash
python manage.py rebuild_pb_derived_ranks
```

Reconstruye toda la clasificación si cambia la tabla de frecuencias de BV, los límites de los tramos o las probabilidades. También permite reparar datos derivados ausentes o incoherentes en la caché. Si cambian los límites de los tramos, actualiza también la copia estática `derivedSegments` en `services/pbDerivedService.ts`. La configuración del servidor y la del cliente están en el código: no hay versión ni suma de comprobación que avise de cambios o discrepancias. El comando vacía primero `speedranking:pb_derived:*` y luego escribe por lotes. La primera versión no implementa el cambio mediante escritura doble. Antes de ejecutarlo, pausa las escrituras de PB (subidas, revisiones, vinculación o desvinculación, eliminaciones y publicación de torneos) y las lecturas relacionadas. Si falla, se registra la excepción y se interrumpe la ejecución, lo que puede dejar la caché incompleta. Corrige el error y vuelve a ejecutarlo. Reconstruye primero la clasificación PB original y después la derivada: `rebuild_pb_derived_ranks` no crea la original si falta. Las actualizaciones ordinarias aplican diferencias directamente a los resultados. Si falta el hash o la categoría es incoherente, se recalculan todos los resultados del usuario para esa operación. Los usuarios sin cambios en sus PB no se reparan automáticamente. Tras cambiar los tramos o las frecuencias, los resultados existentes conservan el criterio anterior. Una pérdida de caché o un cambio de configuración requiere una reconstrucción completa o una reparación individual. Para reparar un usuario, usa la opción de clasificaciones derivadas de PB (`PB 衍生榜`) en la herramienta de reconstrucción de clasificaciones del panel de administración. La operación corresponde a `POST /api/speedranking/pb_derived/admin/rebuild_player`.

### `rebuild_top_ranks`

Ubicación: `speedranking/management/commands/rebuild_top_ranks.py`

Reconstruye la clasificación original de los top, los puntos de referencia y las clasificaciones derivadas de capacidad o LSF a partir de la base de datos de repeticiones. `--batch-size` tiene un valor predeterminado de 100 y debe ser un número positivo.

```bash
python manage.py rebuild_top_ranks
```

Se ejecuta al crear la clasificación por primera vez o tras pérdida de caché; las consultas no se vuelven a obtener automáticamente. El comando construye una clasificación temporal y la publica de forma atómica; en caso de error, se conserva la clasificación anterior. Un cierre forzado puede dejar datos temporales. Durante la reconstrucción, se espera que se completen las escrituras en tránsito; los nuevos requests HTTP devuelven 503, las escrituras en segundo plano esperan, y la clasificación anterior sigue siendo accesible.

Todos los procesos deben compartir un archivo de bloqueo escribible `TOP_RANKING_LOCK_PATH` (por defecto `BASE_DIR/runtime/top-lock.sqlite3`); no se debe eliminar un archivo de bloqueo activo; incluso los scripts personalizados deben cumplir con las reglas de acceso. Las convenciones sobre caché y bloqueo se describen en `back_end/saolei/speedranking/README.md`.

### `rebuild_top_soft_ranks`

Ubicación: `speedranking/management/commands/rebuild_top_soft_ranks.py`

Reconstruye el índice de capacidad o LSF a partir de la clasificación original de los top existente y del punto de referencia en tiempo real, sin corregir la clasificación original. Usa los mismos mecanismos de acceso exclusivo y lógica de publicación temporal que `rebuild_top_ranks`, y en caso de error se conserva la versión anterior. Se usa `rebuild_top_ranks` al crear la clasificación por primera vez o cuando la clasificación original está dañada.

```bash
python manage.py rebuild_top_soft_ranks
```

### `rebuild_tournament_cache`

Ubicación: `tournament/management/commands/rebuild_tournament_cache.py`

Borrar y reconstruir `tournament:normal` y `tournament:normal:participants`, incluyendo el estado de `NORMAL` para la Copa de la Oveja de Oro, el campeonato de velocidad, el campeonato de eficiencia y sus relaciones de participación. Durante la ejecución, se suspenderán la inscripción y el registro de estados de competición para evitar que la reconstrucción completa sobrescriba las actualizaciones incrementales.

```bash
python manage.py rebuild_tournament_cache
```

### `rebuild_tournament_user_cache`

Ubicación: `tournament/management/commands/rebuild_tournament_user_cache.py`

Reconstruye todos los cachés de clasificación de `TournamentUser` en Redis. Los puntos actuales se convierten uniformemente a 00:00 UTC del 1 de enero del año actual, y los demás campos se escriben según los valores de la base de datos, sin modificar la base de datos. Durante la ejecución se suspenden las escrituras de ajuste de puntos y otras clasificaciones; si solo se necesita corregir el orden de puntos actuales, se usa `rebuild_tournament_current_score_cache`.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--batch-size` | `1000` | Número de filas de caché procesadas por lote |

```bash
python manage.py rebuild_tournament_user_cache
```

### `rebuild_tournament_current_score_cache`

Ubicación: `tournament/management/commands/rebuild_tournament_current_score_cache.py`

Recalcula la clasificación de puntos actuales a partir de `TournamentUser.score_current` y `last_updated`, usando como punto de referencia 00:00 UTC del 1 de enero del año actual. No modifica la base de datos ni otras clasificaciones, ni reparte puntos nuevamente.

Durante la reconstrucción se suspenden las tareas de ajuste de puntos y corrección de puntos históricos. El comando reemplaza atómicamente la clasificación y el punto de referencia dentro de la misma transacción de Redis; al ejecutarse repetidamente, no se acumulan pérdidas.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--batch-size` | `1000` | Número de usuarios leídos por lote, debe ser un número entero positivo |

```bash
python manage.py rebuild_tournament_current_score_cache
```

### `rebuild_custom_pluck_cache`

Ubicación: `customranking/management/commands/rebuild_custom_pluck_cache.py`

Reconstruye la clasificación pLuck directamente desde `VideoModel`, seleccionando la mejor repetición por jugador y configuración, sin una tabla adicional de récords. Borra primero las claves seleccionadas y escribe por lotes: pausa las escrituras relacionadas durante la reconstrucción y repite el comando si falla. Un despliegue normal conserva los datos existentes de Redis y no requiere ejecutar este comando.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--level` | Ninguno | Reconstruye solo el nivel personalizado indicado. Si se omite, reconstruye todas las configuraciones. |
| `--batch-size` | `1000` | Número de registros que se escriben en Redis por lote |

Los valores aceptados por `--level` se definen en `CUSTOM_PLUCK_CONFIGS`, en `config/customranking.py`. También se muestran con `--help`.

```bash
python manage.py rebuild_custom_pluck_cache
python manage.py rebuild_custom_pluck_cache --level c16_30_150
```

## Actualización de datos

### `compress_video_files`

Ubicación: `videomanager/management/commands/compress_video_files.py`

Convierte manualmente repeticiones históricas o archivos antiguos al formato MSRC indicado en `videomanager.config.TARGET_COMPRESSION_FORMAT`, actualmente `(1, 1, 2)`. Las nuevas subidas e importaciones guardan preferentemente el archivo comprimido. Si falla la validación, se guarda el original y se marca el fallo. Para reintentarlo, usa `--retry-failed`. Se omiten las repeticiones que ya usan el formato de destino. No hay ninguna tarea de compresión periódica. Ejecuta el comando únicamente cuando tanto el cliente como el servidor sean compatibles con MSRC.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--start` | `0` | ID inicial de repetición, inclusive |
| `--end` | Sin límite | ID final de repetición, exclusivo |
| `--batch-size` | `100` | Número de registros candidatos que se leen por lote. Debe ser un entero positivo. |
| `--dry-run` | Desactivado | Solo muestra los ID candidatos y sus rutas relativas, sin leer ni escribir archivos. |
| `--retry-failed` | Desactivado | Reintenta solo los registros fallidos. Cada registro se intenta como máximo una vez por ejecución. |

```bash
python manage.py compress_video_files --dry-run
python manage.py compress_video_files --start 1000 --end 1100
python manage.py compress_video_files --retry-failed
```

Por defecto, se omiten los archivos con el formato de destino y los marcados como fallidos. Para cada registro se leen los bytes originales y se comprueban el tamaño, el hash existente, el formato comprimido y la recuperación exacta del original al descomprimir. Solo después de guardar el archivo completo se actualiza la base de datos, siempre que la ruta y el formato originales sigan siendo los mismos. La diferencia de espacio ocupado en `UserMS` se actualiza en la misma transacción. Tras confirmar, se comprueban las referencias a la ruta anterior y se limpia de inmediato. Una reproducción o descarga que falle durante el cambio se puede reintentar. El comando muestra el total y el progreso de cada registro. No vuelve a analizar las repeticiones ni dispara las señales de guardado habituales, y conserva el tamaño original, el hash y las clasificaciones.

Si falta un archivo o está dañado, se conservan el registro y su formato, se marca el fallo y se continúa. Los errores de configuración de dependencias, espacio en disco, almacenamiento de solo lectura, permisos o base de datos detienen la ejecución. Las conversiones ya completadas se conservan. Usa `--retry-failed` para reintentar los archivos fallidos: cambiar el formato de destino no borra la marca de fallo. Si se desconoce el resultado de la confirmación de la base de datos, se conservan los archivos para comprobarlos. Los fallos de limpieza se anotan en el log.

### `backfill_video_hashes`

Ubicación: `videomanager/management/commands/backfill_video_hashes.py`

Después del despliegue, aplica primero las migraciones y ejecuta manualmente este comando para rellenar `original_hash` en todas las repeticiones cuyo valor sea NULL o una cadena vacía. Guarda los primeros 96 bits del SHA-256 del archivo original como 24 caracteres hexadecimales en minúscula. Incluye repeticiones de cualquier estado y de torneos. Conserva los hashes existentes. Lee un archivo a la vez, sin analizar la partida, y guarda el hash mediante una actualización condicional. No dispara señales de guardado ni actualizaciones de clasificaciones o cachés, ni modifica la subida o la detección de duplicados.

Al comenzar, se cuenta el número de registros pendientes y se fija el ID máximo de repetición. Los registros se leen por lotes en orden de ID y cada archivo se procesa por bloques, sin cargar todas las repeticiones ni un archivo completo en memoria. Se muestran el número procesado y el total, el porcentaje, los éxitos, los fallos, los omitidos y el ID actual, también al inicio y al final. Si otro proceso elimina o completa registros durante la ejecución, el número procesado puede quedar por debajo del total inicial. Las subidas e importaciones ya calculan el hash antes de analizar el archivo y lo guardan con la nueva repetición. Tras activar la nueva detección de duplicados en producción, ejecuta de nuevo el comando para completar los hashes que hayan quedado vacíos mientras se usaba el código anterior.

Si falta el archivo, se informa del ID de la repetición, se deja el hash vacío y se continúa. Los demás errores de lectura, escritura o base de datos detienen el comando. Los resultados ya guardados se conservan y la operación se puede repetir. Al escribir, se comprueba que la ruta no haya cambiado y que el hash siga vacío para no sobrescribir el resultado de otro proceso. Para los archivos MSRC se restaura primero el contenido original mediante la capa común de archivos y se calcula su hash. Los archivos originales se siguen procesando por bloques.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--start` | `0` | ID inicial de repetición, inclusive. Debe ser mayor o igual que cero. |
| `--end` | Sin límite | ID final de repetición, exclusivo. No puede ser menor que `start` |
| `--batch-size` | `1000` | Número de registros leídos por lote, debe ser un entero positivo |
| `--step` | `100` | Frecuencia con la que se muestra el progreso al procesar, debe ser un entero positivo |

```bash
python manage.py backfill_video_hashes
python manage.py backfill_video_hashes --start 10000 --end 20000 --step 10
```

### `refresh_videos`

Ubicación: `videomanager/management/commands/refresh_videos.py`

Reinterpreta y guarda cada video en orden de ID, activando señales de instancia. Procesa por defecto todos los videos, sin restricciones por estado, modo, nivel o marca de competencia. Cada video se bloquea y se envía de forma independiente; durante el proceso de interpretación, se bloquea cualquier otra escritura sobre el mismo video.

Si se detecta un error de interpretación, se informa del ID y se salta; otros errores detienen el comando, deshacen la escritura en la base de datos de la línea actual, pero no se deshacen los datos ya procesados o almacenados en Redis. Este comando no reemplaza la reconstrucción completa de la clasificación; para recalcular el número de videos, se debe usar `refresh_video_counts`.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--start` | `0` | ID inicial de repetición, inclusive. Debe ser mayor o igual que cero. |
| `--end` | Sin límite | ID final de repetición, exclusivo. No puede ser menor que `start` |
| `--step` | `100` | Frecuencia con la que se muestra el progreso al procesar videos, debe ser un entero positivo |

Intervalo en `[start, end)`, puede especificarse solo un límite; `step` se cuenta según el número real de videos procesados.

```bash
python manage.py refresh_videos
python manage.py refresh_videos --start 10000 --end 20000 --step 50
```

### `refresh_video_counts`

Ubicación: `msuser/management/commands/refresh_video_counts.py`

Refresca el número total de partidas y repeticiones de `UserMS`, así como el espacio de archivos: `video_num_total`, `video_num_tournament`, `video_size_total`, `video_size_tournament`. El espacio se calcula sumando el almacenamiento real de `VideoModel.stored_file_size`, con valores nulos devolviéndose al valor original de `file_size`, en bytes; los campos totales `video_num_all` y `video_size_all` se calculan automáticamente por la base de datos `GeneratedField`. No modifica el límite de subida, los registros personales ni Redis. Después de cambiar la estadística de espacio de despliegue de tamaño original a tamaño almacenado, ejecuta este comando para corregir las estadísticas existentes.

Los videos de competencia en curso y los videos asociados a cualquier competencia (incluso los finalizados) se cuentan como competencia; los demás se cuentan como no competencia; no se filtran por estado de revisión. Se verifica mediante `EXISTS` si hay asociación con una competencia para evitar que un mismo video se cuente varias veces; si un usuario no tiene videos, todos sus indicadores básicos se establecen en cero, incluyendo a los `UserMS` sin perfil personal asociado.

Los ajustes de asociación se realizan sin modificar inmediatamente las estadísticas; posteriormente, las eliminaciones, cambios de tamaño o de pertenencia se ajustan según la categoría de competencia actual del video, permitiendo un desfase temporal, y se corrige mediante este comando. El comando agrupa directamente los videos actuales, no mantiene marcas históricas de clasificación ni actualiza las filas de los videos; las estadísticas por usuario se escriben en una sola transacción, y si falla, se deshace solo la parte actual; las partes ya completadas no se deshacen. Después de la migración, se debe ejecutar este comando para rellenar las nuevas estadísticas. Durante su ejecución, se suspenden las escrituras relacionadas con videos, competencias o pertenencia de jugadores para evitar que las estadísticas se sobrescriban.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--batch-size` | `1000` | Número de usuarios procesados por lote, debe ser un entero positivo |

```bash
python manage.py refresh_video_counts
```

### `refresh_tournament_scores`

Ubicación: `tournament/management/commands/refresh_tournament_scores.py`

Recalcula los resultados, clasificaciones, puntos y los mejores resultados históricos de los participantes en competencias específicas sin necesidad de trabajadores en segundo plano. Solo acepta competencias GSC, carreras clásicas de puntos o carreras de eficiencia con premios otorgados y con fecha de finalización.

El comando recalcula los resultados basándose en videos válidos, corrige los puntos acumulados según la diferencia entre los nuevos y antiguos puntos, y sincroniza con Redis; no se acumulan puntos repetidamente ni se retrocede la última fecha de cálculo. Durante su ejecución, se evita modificar los videos o participantes de la competencia, y se suspenden los cálculos de puntos para los usuarios relacionados. La escritura en la base de datos ocurre en una sola transacción, y si falla, se deshace; Redis no se deshace con la base de datos, por lo que tras un fallo se debe volver a ejecutar para restaurar la coherencia.

Las reglas de cálculo se diferencian según el tipo de competencia y la fuente de los resultados. Para las carreras de puntos clásicas y GSC, solo se consideran los resultados de videos existentes que cumplan con las condiciones de puntuación; los resultados de videos eliminados se consideran nulos y se reemplazan por los resultados de los videos restantes o por el valor predeterminado del formato. En GSC con `manual_scores=true`, se aplican los 9 resultados manuales configurados por el participante, no se recalculan de videos parciales o vacíos, pero sí participan en la clasificación general y en la actualización de puntos; los resultados de los videos solo se consideran si cumplen con los criterios de modo, nivel y 3BV para videos OFFICIAL. Los participantes anónimos compiten en la clasificación conjunta pero no obtienen puntos.

Borrado normal de repetición sin recalculo inmediato ni eliminación de puntos; solo se aplican las reglas mencionadas al ejecutar explícitamente este comando. La señal de eliminación de registros de participación retira los puntos del propio jugador. Este comando se utiliza para corregir los puestos y puntos restantes. El orden de operaciones tras la incorporación de repeticiones históricas se ve en [GSC complemento de repetición histórica](./gsc-history-import.md#重试与人工重算). Al añadir una nueva categoría o sistema de competición, se debe proporcionar la implementación propia de borrado y recálculo, y luego integrar el comando; no se puede asumir que se reutilicen las reglas de origen de los resultados de otra categoría.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `tournament_id` | Obligatorio | ID de la competición, no el número de edición ni de semana del GSC |
| `--batch-size` | `1000` | Tamaño de la escritura en lote, debe ser un número entero positivo |

```bash
python manage.py refresh_tournament_scores 123
```

### `refresh_tournament_user_stats`

Ubicación: `tournament/management/commands/refresh_tournament_user_stats.py`

Completa los participantes faltantes en competiciones ya premiadas con `TournamentUser`, actualiza el puntaje histórico total, los puntos por categorías (GSC, velocidad, eficiencia), el mejor historial y sincroniza con Redis; se reconstruyen los campos anuales y semanales del mejor rendimiento de eficiencia, sin codificación en punto flotante. No modifica el puntaje en tiempo real `score_current`. Se debe evitar ejecutar este comando durante tareas de cierre o cancelación de participantes.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--batch-size` | `1000` | Tamaño del lote para operaciones en lote: creación, actualización y escritura en caché |

```bash
python manage.py refresh_tournament_user_stats
```

## Limpieza de datos

### `cleanup_orphan_userms` {#cleanup-orphan-userms}

Ubicación: `msuser/management/commands/cleanup_orphan_userms.py`

Elimina los `UserMS` aislados sin asociación con `UserProfile`, y elimina de forma cascada los identificadores de estos registros mediante la relación existente. Se determina la aislamiento mediante la asociación real, no se compara el valor de las claves primarias de las dos tablas; todos los registros asociados a usuarios se conservan, incluyendo cuentas desactivadas.

```bash
python manage.py cleanup_orphan_userms --dry-run
python manage.py cleanup_orphan_userms --batch-size 1000
```

`--dry-run` solo cuenta; `--batch-size` por defecto 1000, debe ser un número positivo; `--database` por defecto `default`, se puede especificar el alias de la base de datos configurada. La salida solo cuenta la cantidad de `UserMS`, no incluye los identificadores de eliminación cascada, y al ejecutar repetidamente sin datos pendientes por limpiar, muestra 0.

Elimina realmente por lotes basándose en la clave principal, con transacciones independientes por lote: primero bloquea las filas candidatas `UserMS`, luego vuelve a verificar la asociación del usuario, conservando los datos asociados que ya estaban vinculados en la consulta de candidatos. En caso de error, se deshace el lote actual, pero se mantienen los lotes ya completados. El comando no escanea ni modifica Redis, ni reconstruye el ranking del usuario. La eliminación de cuentas nuevas ya ha sido limpiada automáticamente por `UserProfile.post_delete` de sus asociaciones `UserMS`; este comando se encarga de los datos aislados provenientes de historial o fuentes distintas.

Durante la ejecución, pausa el proceso de escritura que primero crea `UserMS` y luego asocia cuentas; los nuevos registros aún no completados también cumplen con las condiciones de aislamiento, por lo que el comando no puede diferenciarlos de los residuos históricos.

## Limpieza de caché

### `delete_legacy_speedranking_cache`

Ubicación: `common/management/commands/delete_legacy_speedranking_cache.py`

Limpiar el Redis `saolei_website` de las clasificaciones antiguas y `news_queue`, sin modificar la base de datos u otros cachés. Las claves de los registros antiguos son `player_{stat}_{mode}_{用户ID或ids}`, los indicadores están limitados a `timems/bvs/stnb/ioe/path` y los modos a `std/nf/ng/dg`. Asegúrate de que el código de escritura antiguo esté desactivado antes de ejecutarlo.

```bash
python manage.py delete_legacy_speedranking_cache --dry-run
python manage.py delete_legacy_speedranking_cache
```

`--dry-run` solo lista las claves coincidentes y cuenta su cantidad.

### `delete_newest_queue`

Ubicación: `videomanager/management/commands/delete_newest_queue.py`

Recorta la cola más reciente de Redis, lee los hashes y los ordena por tiempo de subida en Python, conserva las 1000 últimas, y en caso de fechas iguales conserva el ID más alto. Ya no se eliminan por límite de 7 días; si hay menos de 1000, se conservan todas. Al escribir no se recorta, se permite superar el límite temporalmente, y se recorta de forma unificada cada día a las 01:08 por tareas de fondo; también se puede ejecutar este comando para limpiar inmediatamente.

```bash
python manage.py delete_newest_queue
```

## Tareas de fondo y tareas programadas

### `db_worker_robust`

Ubicación: `common/management/commands/db_worker_robust.py`

Inicie el worker `django-tasks-db`, utilizando el archivo pid y la detección de procesos para evitar el arranque duplicado. El proceso en ejecución y su proceso padre no se cuentan como otro worker. Solo se marcarán como `FAILED` las tareas `RUNNING` residuales cuando no se detecte un worker existente, y luego se iniciará el worker; no se recuperarán tareas ni se reiniciará el proceso durante la ejecución.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--queue-name` | Cola predeterminada de tareas | Cola a procesar; múltiples colas separadas por comas, `*` indica todas |
| `--interval` | `2` | Intervalo de consulta del worker, en segundos |
| `--backend` | backend de tareas predeterminado | backend de tareas utilizado |
| `--batch` | `False` | modo de procesamiento pasado al `db_worker` |
| `--no-startup-delay` | deshabilitado | deshabilitar el retraso de inicio de `db_worker` |
| `--max-tasks` | Ninguno | número máximo de tareas procesadas |
| `--worker-id` | generado automáticamente | sobrescribir el ID del worker generado automáticamente |
| `--pidfile` | `logs/db_worker_robust.pid` | ruta del archivo pid para evitar el inicio repetido |

```bash
python manage.py db_worker_robust
python manage.py db_worker_robust --queue-name default --interval 2
```

### `refresh_monitor_snapshot` {#refresh-monitor-snapshot}

Ubicación: `monitor/management/commands/refresh_monitor_snapshot.py`

Muestra inmediatamente la repetición, las tareas, las estadísticas de disco y memoria, y genera un JSON para el monitoreo atómico, que será leído por `GET /api/monitor/summary`. En el entorno de desarrollo se escribe por defecto en `BASE_DIR/runtime/monitor.json`; en el entorno de producción se escribe por defecto en `runtime/monitor.json`, al mismo nivel que `STATIC_ROOT`, y puede ser sobrescrito mediante `MONITOR_SNAPSHOT_PATH`. Se puede ejecutar manualmente al realizar el primer despliegue o durante la depuración local; las actualizaciones diarias se ejecutan mediante la tarea APScheduler descrita a continuación. Si falla un elemento, se conserva el ejemplo original y la hora, mientras que los demás continúan actualizándose; la estructura específica se encuentra en [instantáneo de monitoreo del servidor ](./cache.md#服务器监控快照).

```bash
python manage.py refresh_monitor_snapshot
```

En entornos de producción se debe implementar la configuración de ruta exacta especificada en `default.conf`, y ejecutar `nginx -t` y reload. El `alias` de Nginx debe coincidir con la ruta real de salida de la muestra; al cambiar el directorio de salida, se debe ajustar también la configuración. Los trabajadores de Nginx deben tener permisos para leer archivos y recorrer los directorios superiores. Si la muestra o la escritura fallan, revise `logs/apscheduler.log`; los archivos antiguos no caducan automáticamente y debe verificar los tiempos de muestreo de cada elemento.

### `runapscheduler`

Ubicación: `common/management/commands/runapscheduler.py`

ejecutar en un solo proceso en segundo plano los tareas registradas en `common/apscheduler.py`:

| tarea | frecuencia | Descripción |
| --- | --- | --- |
| `refresh_monitor_snapshot` | al iniciar y cada 5 minutos | generar un JSON de monitoreo uniforme; ejecución en un solo instante, si se pierde varias veces en el cronograma, se ejecuta en conjunto |
| `sync_saolei_metadata_daily` | a las 03:30 todos los días (zona horaria del scheduler, actualmente UTC) | APScheduler sincroniza directamente los datos del perfil de los usuarios activos y los directorios incrementales, con un máximo de 50 IDs por lote para recuperar detalles y URLs; no descarga archivos, no crea tareas de Django |
| `import_saolei_hourly` | cada hora exacta | agrega una tarea de bajo nivel en Django, descarga secuencialmente los videos pendientes de los usuarios activos por orden ascendente de `remote_id`, con un máximo de 100 intentos por ronda (incluyendo los fallidos); cualquier fallo se marca y se pasa a `sync_saolei_api` para reintentar; no se agrega nuevamente si la ronda anterior no se completó |
| `delete_old_job_executions` | a las 00:03 todos los días | elimina registros de ejecución de APScheduler mayores de 7 días |
| `delete_newest_queue` | a las 01:08 todos los días | mantiene los últimos 1000 registros por fecha de subida, permite superar temporalmente el límite entre dos limpiezas |
| `delete_overdue_emailverifyrecord` | lunes a las 01:03 cada semana | elimina los códigos de verificación de correo más de una hora antiguos |
| `delete_overdue_captcha` | lunes a las 01:05 cada semana | elimina los códigos de verificación gráficos vencidos |
| `delete_overdue_tasks` | lunes a las 01:10 (zona horaria de `settings.TIME_ZONE`, actualmente UTC) | elimina en lotes los registros de tareas exitosas según el periodo de retención definido en `config/common.py`, sin límite en la cantidad total eliminada |
| `refresh_tournament_score_reference` | el 1 de enero a las 00:00 UTC cada año | realiza un cálculo atómico de los puntos actuales en el conjunto zset y los actualiza en el punto de referencia del nuevo año; el sistema de base de datos permanece sin cambios |

La tarea de punto anual también se ejecuta una vez al iniciar el scheduler, para verificar la idempotencia y completar actualizaciones perdidas por interrupciones o errores durante el cambio de año; dentro del mismo año, no se reduce repetidamente.

Los videos congelados ya no se eliminan automáticamente por fecha. Al iniciar el scheduler, se eliminan las tareas de `delete_freezed_video` que quedaron en la base de datos; después de actualizar el código, se debe reiniciar el scheduler para que los procesos antiguos dejen de ejecutar esta tarea.

La limpieza de tareas de fondo y la interfaz de administrador `POST /api/common/tasks/cleanup` comparten el mismo servicio; la interfaz elimina como máximo 200 registros por tipo, y las tareas programadas eliminan de forma cíclica en lotes de 200 todos los registros que cumplen con los criterios. Las tareas fallidas, pendientes, en ejecución y sin configuración se conservan.

El periodo de retención se basa en `config/common.py`. Para la tarea de actualización de LSF `speedranking.top.tasks.task_refresh_soft_ranks`, los registros exitosos (incluyendo los que se saltan normalmente tras la fusión) se conservan durante 7 días y se eliminan en la próxima limpieza semanal.

| Parámetros | Valor predeterminado | Descripción |
| --- | --- | --- |
| `--pidfile` | `logs/apscheduler.pid` | Path del archivo pid para evitar el inicio repetido del proceso de APScheduler |

```bash
python manage.py runapscheduler
```

Solo ejecuta un proceso de APScheduler. Después de modificar el registro de tareas o la configuración de limpieza, reinicia el comando `runapscheduler` para que los cambios tengan efecto.

### Inicio en producción y registro de logs

El script `start.sh` inicia dos servicios mediante `nohup bash run_background.sh` tras migrar la base de datos. Al finalizar, no se reinicia automáticamente. Las variables de entorno son las siguientes:

| Servicios | Interruptor (establecer en `0` para omitir) | Retraso de inicio (en segundos) | Valor de nice | Intervalo de consulta (en segundos) | Registro de logs |
| --- | --- | --- | --- | --- | --- |
| APScheduler | `START_APSCHEDULER`, valor predeterminado `1` | `APSCHEDULER_START_DELAY`, valor predeterminado `10` | `APSCHEDULER_NICE`, valor predeterminado `10` | — | `logs/apscheduler.log` |
| worker | `START_DB_WORKER`, valor predeterminado `1` | `DB_WORKER_START_DELAY`, valor predeterminado `20` | `DB_WORKER_NICE`, valor predeterminado `10` | `DB_WORKER_INTERVAL`, valor predeterminado `2` | `logs/db_worker.log` |

Antes de volver a desplegar, ejecuta `stop.sh`. Primero envía `SIGTERM` al lanzador (`run_background.sh`) y a los procesos activos `db_worker_robust` / `runapscheduler`. Tras un período de gracia de `${STOP_GRACE_SECONDS:-5}` segundos, envía `SIGKILL` y usa `pgrep` para verificar y enumerar los procesos restantes. Si queda alguno, termina con un código distinto de cero. El lanzador espera 10 o 20 segundos antes del arranque. Si solo se detienen los procesos hijos de Python, un lanzador antiguo que siga en `sleep` podría iniciar el código anterior tras el despliegue. Si `db_worker_robust` detecta otro proceso db_worker, termina de inmediato y el trabajador antiguo sigue consumiendo las tareas nuevas. Si desconoce una tarea nueva, la incompatibilidad de firmas puede dejarla en estado FAILED. Usa `STOP_DRY_RUN=1 bash stop.sh` para ver los comandos sin ejecutarlos.

### Diagnóstico del cierre de procesos en segundo plano

El script `run_background.sh` registra el tiempo de inicio, el PID del launcher/Python, el estado de finalización y la señal recibida. El código de salida `137/KILL` no puede probar por sí solo un problema de uso de memoria (OOM), ya que el worker también podría salir con código `0` tras recibir `SIGTERM`; es necesario analizar los registros previos. Si el launcher también es eliminado, los registros de finalización podrían estar incompletos.

Los registros de la aplicación también pueden escribirse en `logs/root.log` y en los registros de cada aplicación; si los registros de servicio están vacíos, también debe revisarse estos archivos y los registros del sistema.

```bash
tail -n 100 logs/apscheduler.log
tail -n 100 logs/db_worker.log
sudo journalctl -k --since today --no-pager | grep -Ei 'oom|out of memory|killed process|segfault'
sudo journalctl -u systemd-logind --since today --no-pager
```
