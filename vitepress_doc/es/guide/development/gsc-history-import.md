---
title: "Importación de repeticiones históricas de la GSC - Open Minesweeper"
description: "Flujo frontend y backend del proceso de importación de repeticiones históricas de la GSC, vinculación de identificadores, detección de duplicados, manejo del tiempo de subida y responsabilidades de cada API."
---

# Importación de repeticiones históricas de la GSC

Este artículo describe el proceso de importación de historial ya implementado, con énfasis en el caso de cuentas dentro de la plataforma que puedan proporcionar una repetición; en ausencia de repetición, se utiliza el CSV de resultados. El acceso se encuentra en `GSCAdminView` bajo "Importación de historial de resultados". Los campos de la interfaz y el esquema de respuesta se basan en la documentación automática de la API generada por Ninja.

## Alcance de la operación

- La interfaz de escritura histórica solo permite que los organizadores oficiales del evento o administradores del sitio realicen operaciones, requiriendo que el evento esté en estado `AWARDED` y tenga un `end_time`. Cada solicitud se verifica nuevamente, sin reutilizar el permiso de la solicitud previa. Para la lectura de información del evento y resultados se reutilizan interfaces públicas existentes, sin crear nuevas APIs de gestión de listas.
- Los permisos se controlan únicamente por los APIs: los APIs consultan y bloquean el evento dentro de una transacción, validan al operador y el estado del evento, y luego pasan los objetos autorizados del evento, usuario o participante a los servicios. Los servicios no reciben `actor`, no realizan consultas repetidas de permisos; el bloqueo se mantiene hasta que finalice la transacción de escritura.
- La interfaz de escritura de regrabado histórico no limita el número de operaciones para administradores de sitio ni para organizadores del evento; esto no modifica las restricciones de verificación de permisos, vinculación única de identificadores o límite de máximo 10 resultados por lote.
- El campo `order` representa la edición de GSC; `tournament_id` es el ID de la tabla padre `Tournament`; `participant_id` es el ID del participante. Ninguno de estos tres campos debe ser mezclado.
- La transmisión de identificadores no verifica límites de identificación real ni de número de videos, pero sí verifica la completitud, la seguridad del identificador y la pertenencia. No se puede forzar a convertir un video congelado o con identificador incompatibles en `OFFICIAL`.
- La interfaz de regrabado no recalcula automáticamente los resultados del evento, no actualiza las clasificaciones ni distribuye puntos, ni crea tareas de cálculo en segundo plano. Al crear un participante, se ejecuta normalmente la señal de guardado de mejor resultado, permitiendo usar resultados por defecto o manualmente para mejorar `gsc_best` y sincronizar el caché de clasificación. La vinculación de identificadores y el guardado del video aún activan los procesos de mantenimiento del estado del video, colas y clasificaciones. Al eliminar a un participante, se conservan las señales de descontado y actualización de mejor resultado.

## Flujo completo del regrabado de videos

Los nodos azules son APIs, los grises son procesos del frontend, los verdes son servicios o escrituras de datos y los amarillos son comandos manuales.

```dot
digraph gsc_history_flow {
    graph [layout=dot, rankdir=TB, bgcolor="transparent", nodesep=0.35, ranksep=0.65, splines=polyline];
    node [shape=box, style=filled, fillcolor="${#f1f5f9|#1f2937}", color="${#94a3b8|#64748b}", fontcolor="${#0f172a|#e5e7eb}", fontsize=12];
    edge [color="${#64748b|#94a3b8}", fontcolor="${#475569|#cbd5e1}", fontsize=10, arrowsize=0.7];

    info [label="Leer los datos del torneo\nget_GSC_tournament", fillcolor="${#dbeafe|#1e3a5f}"];
    participants [label="Consultar los resultados guardados\nget_results", fillcolor="${#dbeafe|#1e3a5f}"];
    files [label="Analizar los archivos en el cliente\nDeduplicar identificadores y seleccionar repeticiones"];
    times [label="Asignar las fechas de subida en el cliente\nOrdenar por fin de partida y calcular hacia atrás"];
    prepare [label="Obtener o crear el participante de la repetición\ncreate_history_participant", fillcolor="${#dbeafe|#1e3a5f}"];
    bind [label="Vincular los identificadores uno a uno\nbind_history_identifier\nEn caso de conflicto, omitir solo la vinculación", fillcolor="${#dbeafe|#1e3a5f}"];
    upload [label="Subir cada archivo en nombre del jugador\nupload_history_video", fillcolor="${#dbeafe|#1e3a5f}"];
    associate [label="Crear o reutilizar la repetición\nAñadirla expresamente a esta edición", fillcolor="${#dcfce7|#14532d}"];
    inspect [label="Actualizar la lista con los datos y resultados del torneo\nVerificar los resultados y conservar los archivos pendientes"];
    recalculate [label="Recalcular manualmente cada edición\nrefresh_tournament_scores", fillcolor="${#fef3c7|#713f12}"];
    results [label="Consultar los resultados públicos\nget_results", fillcolor="${#dbeafe|#1e3a5f}"];

    info -> participants [label="Obtener el ID y la fecha de fin del torneo"];
    participants -> files [label="Comprobar los participantes de esta edición"];
    files -> times [label="Conservar los archivos con identificadores seleccionados"];
    times -> prepare [label="order、user_id"];
    prepare -> bind [label="Devolver participant_id"];
    bind -> bind [label="Enviar una solicitud por identificador, en orden", style=dashed, constraint=false];
    bind -> upload [label="Tras procesar todos los identificadores"];
    upload -> associate [label="file y upload_time con zona horaria"];
    associate -> inspect [label="Devolver el ID de repetición y el estado de revisión"];
    inspect -> upload [label="Reintentar solo los archivos pendientes", style=dashed, constraint=false];
    inspect -> recalculate [label="Tras verificar, usar tournament_id"];
    recalculate -> results [label="Resultados del torneo actualizados"];
}
```

### Preparación y vinculación de identificadores

El componente `HistoryVideos.vue` analiza los videos en el navegador, muestra los identificadores de los jugadores desduplicados y permite al administrador seleccionar varios. Solo se suben los archivos correspondientes a los identificadores seleccionados; aquí se usa el identificador del jugador dentro del video, no el token del evento.

La función `create_history_participant` consulta y bloquea dentro de una transacción el evento y el usuario objetivo según la edición y el ID del usuario, completando la verificación de permisos y estado del evento; `prepare_gsc_history_videos` recibe estos dos objetos de modelo y devuelve los participantes existentes de este usuario con `manual_scores=false` para esta edición. Si no existen, los crea. Si ya hay una fuente de puntuación manual, se rechaza la operación sin cambiar automáticamente la fuente. Se reutiliza la información sin guardar el participante, sin modificar los resultados, clasificaciones, puntos, identificadores, token, ventana de participación ni relación con el video; tampoco se activan señales de creación o guardado de mejor resultado. No recibe lista de operadores ni de identificadores, ni realiza la vinculación. Al crear, se usa el resultado por defecto, la señal de creación no rellena automáticamente el historial de videos, pero sí crea por defecto un `TournamentUser` para el usuario en el sitio, y se intenta normalmente con el valor actual de `t37` para mejorar el mejor resultado.

Tras obtener el ID del participante, el frontend llama secuencialmente a `bind_history_identifier` según el orden seleccionado. Cada solicitud recibe solo un `identifier`. La API verifica nuevamente los permisos reales de competencia, el estado AWARDED y la fuente de la repetición del participante, luego pasa el objeto del participante a `bind_gsc_history_identifier`, donde el servicio registra el identificador y llama a `identifier.services.bind_identifier`. El enlace actualiza las repeticiones y clasificaciones existentes; no se pueden incluir varios identificadores en una misma solicitud:

- Los identificadores nuevos se registran primero. Si el identificador está libre o ya pertenece al usuario de destino, se aplica el procedimiento habitual de vinculación. Las repeticiones de ese usuario con el identificador correspondiente también pueden pasar de `IDENTIFIER` a `OFFICIAL`.
- El marcador ya asignado a otro usuario devuelve `bound=false`, sin transferir la asignación, los demás marcadores continúan siendo procesados.
- Los identificadores que pueden vincularse pero que no son seguros hacen que la solicitud de vinculación falle y se deshaga, no se tratan como conflictos ignorables; los participantes previamente creados y los identificadores ya vinculados se conservan.

Se suben los archivos solo después de que todos los identificadores seleccionados devuelvan resultados de vinculación. Si la vinculación falla, se pausa y no se continúa con los siguientes identificadores ni se suben; al volver a intentarlo, se salta los identificadores ya recibidos (incluyendo conflictos de propiedad), y nunca se continúa desde un paso no completado. Si falla un archivo posterior, no se revierte el participante o la vinculación de identificadores ya enviados anteriormente. Durante la subida, se valida independientemente el identificador del archivo, y no se permite que un conflicto de propiedad en la fase de vinculación haga que el video participante se incluya en la puntuación.

### Tiempo de subida

El punto de tiempo predeterminado es la hora de finalización del evento devuelta por la interfaz de información del evento, y también se permite que el administrador lo modifique. El frontend solo ordena de forma estable ascendente por hora de finalización original de los archivos seleccionados, manteniendo el orden de selección en caso de horas iguales, y luego asigna:

```text
Último archivo:          upload_time[n] = fecha_de_referencia
Archivos anteriores:     upload_time[i] = upload_time[i+1] - timems[i+1]
```

`timems` en milisegundos. Cada archivo contiene la hora final calculada con zona horaria, el backend no realiza reordenamiento ni retrocede a la hora de finalización de la partida. Al repetir, se utiliza el tiempo asignado inicialmente, sin recálculo.

## Flujo interno del API de subida

El API realiza comprobaciones de permisos, estado del evento y origen del video dentro de una transacción, y entrega el objeto participant a `tournament.gsc.services.upload_gsc_history_video`. El servicio GSC verifica el tiempo de subida, busca primero por el hash de 96 dígitos del archivo original, y solo si no encuentra coincidencia, analiza y valida el identificador, y finalmente vincula con el evento histórico. Reutiliza `calculate_original_hash`, `find_identical_video`, los servicios existentes de identificadores y la herramienta `set_import_upload_time`, sin depender del módulo superior `common`. La incorporación de cuentas de homenaje se gestiona por separado en `common`, reutilizando las mismas capacidades básicas; los usuarios comunes que suben sus propios videos mantienen sus condiciones, cuotas y políticas de rechazo a archivos repetidos.

```dot
digraph gsc_history_upload {
    graph [layout=dot, rankdir=TB, bgcolor="transparent", nodesep=0.4, ranksep=0.5, splines=polyline];
    node [shape=box, style=filled, fillcolor="${#f1f5f9|#1f2937}", color="${#94a3b8|#64748b}", fontcolor="${#0f172a|#e5e7eb}", fontsize=12];
    edge [color="${#64748b|#94a3b8}", fontcolor="${#475569|#cbd5e1}", fontsize=10, arrowsize=0.7];

    request [label="upload_history_video\nUn archivo y una fecha de subida con zona horaria", fillcolor="${#dbeafe|#1e3a5f}"];
    guard [label="Comprobar permisos y estado en la transacción de la API\nExigir usuario registrado y participante con resultados de repeticiones", fillcolor="${#dbeafe|#1e3a5f}"];
    parse [label="MSVideoParser\nRechazar partidas sin terminar y conservar la revisión"];
    identifier [label="Comprobar la validez y la titularidad del identificador\nSi la repetición es válida pero el identificador no coincide, asignar IDENTIFIER"];
    duplicate [shape=diamond, label="Hash de 96 bits del archivo original\n¿Hay coincidencia en find_identical_video?"];
    owner [shape=diamond, label="¿Pertenece el archivo\nal usuario de destino?"];
    conflict [label="409: rechazar el conflicto de titularidad\nConservar la repetición y su fecha de subida", fillcolor="${#fee2e2|#7f1d1d}"];
    reuse [label="Reutilizar el VideoModel existente\nGuardar solo si la fecha solicitada es anterior", fillcolor="${#dcfce7|#14532d}"];
    create [label="create_from_parser\nPasar original_hash y upload_time", fillcolor="${#dcfce7|#14532d}"];
    save_time [label="set_import_upload_time\nSobrescribir auto_now_add tras crear"];
    link [label="tournament.videos.add(video)\nVincular al torneo histórico sin duplicar la relación M2M", fillcolor="${#dcfce7|#14532d}"];
    response [label="Devolver VideoBaseOut\nEl registro no implica estado OFFICIAL ni puntuación", fillcolor="${#dbeafe|#1e3a5f}"];

    request -> guard -> duplicate;
    duplicate -> owner [label="Existe"];
    duplicate -> parse [label="No existe"];
    parse -> identifier -> create;
    owner -> conflict [label="No"];
    owner -> reuse [label="Sí"];
    create -> save_time -> link;
    reuse -> link;
    link -> response;
}
```

- Si los primeros 96 dígitos del SHA-256 son iguales, se considera una repetición, sin realizar comparaciones de tamaño, puntuación ni bytes. Al detectar una coincidencia, se salta el análisis y la verificación de identificadores de archivos nuevos, se conserva el marcador `min(原上传时间, 请求上传时间)` para los usuarios repetidos, y se devuelve 409 para los archivos de otros usuarios; no se crea repetidamente una repetición. Cualquier operación de creación o guardado anticipado sigue el proceso normal de guardado.
- Se pasa el tiempo de origen al crear, para que `pre_save` realice un check-in automático, evitando que se ingrese por error en otro evento en curso; después de crear, se debe guardar explícitamente para sobrescribir `auto_now_add`.
- La asociación histórica de esta edición se establece explícitamente por el servicio de subida, sin requerir que el `arbiter_identifier` del servicio, el período de participación o el participante coincidan con el del archivo. No se modifican los tiempos originales de finalización dentro del video ni se cambia la propiedad del archivo.
- La completitud, los errores de identificación de inseguridad y otros errores de negocio se convierten en estados HTTP de error en la capa GSC API, evitando que el frontend interprete la respuesta HTTP 200 predeterminada como un éxito en la subida. Aún así, una respuesta de éxito con `state` podría no ser `OFFICIAL`.

## Responsabilidades del API

La siguiente tabla es un índice de roles de negocio, no sustituye los documentos automáticamente generados de solicitudes y respuestas. La interfaz de escritura histórica se encuentra en `tournament.gsc.api`; la lectura reutiliza directamente las APIs existentes de información de eventos y puntuaciones públicas, y la eliminación reutiliza `tournament.api`.

| API | Roles y resultados principales |
| --- | --- |
| `GET /api/tournament/gsc/admin-info?order=...`（`get_GSC_tournament`） | Obtiene el ID del evento padre, el rango de tiempo y el estado por edición; el frontend utiliza la hora de finalización como punto de tiempo predeterminado, y luego solicita las puntuaciones por ID de evento, combinándolas en una lista de gestión. |
| `POST /api/tournament/gsc/history/prepare`（`create_history_participant`） | Obtiene o crea el participante de origen del video, sin recibir lista de identificadores ni vincular identificadores. Si ya existen registros no manuales en esta edición, se devuelven tal como están; los orígenes manuales siguen generando conflictos, sin sobrescribir ni cambiar el origen. |
| `POST /api/tournament/gsc/history/participants/{participant_id}/identifier`（`bind_history_identifier`） | Cada vez que se registre y se asocie un identificador, se devuelve el `identifier` y el `bound`. Si hay conflicto de pertenencia, se devuelve `bound=false`; otros errores hacen que la solicitud falle; cada solicitud es un transacción independiente y se ejecuta en orden en el frontend. |
| `POST /api/tournament/gsc/history/participants/{participant_id}/videos`（`upload_history_video`） | Cada vez que se procese un archivo: se realiza un control de hash, si hay coincidencia se reutiliza, si no se analiza, se verifica el identificador y se crea; se guarda la hora de subida, se asocia con la competencia y se devuelve la repetición y el estado de revisión. Cada solicitud es una transacción independiente. |
| `POST /api/tournament/gsc/history/scores/users`（`import_history_user_scores`） | Para los participantes que tienen cuenta en la plataforma pero que carecen de repetición, se registran nueve resultados, se crea un participante con `manual_scores=true`, y no se calculan a partir de la repetición. |
| `POST /api/tournament/gsc/history/scores/anonymous`（`import_history_anonymous_scores`） | Se crea un participante de puntuación manual anónima con identificador de arbitro, sin inventar usuario en la plataforma ni vincularlo a una cuenta; comparte el puesto real con los participantes de la plataforma, pero no obtiene puntos de cuenta. |
| `POST /api/tournament/participant/{participant_id}/disqualify` | Solo los organizadores de competencias premiadas pueden solicitar la cancelación de calificaciones, independientemente de si hay o no repetición; si el administrador no es organizador, no tiene este permiso. El worker elimina al participante, revierte sus puntos y actualiza el mejor resultado, pero no elimina los archivos de repetición ni reorganiza a otros participantes. El frontend espera que la tarea se complete antes de actualizar la lista. |
| `GET /api/tournament/gsc/results?tournament_id=...`（`get_results`） | Punto de entrada para leer los resultados públicos de competencias premiadas, también se utiliza para gestionar la lista, complementar o eliminar y actualizar; ya incluye campos como `manual_scores` y `has_videos`. Solo lee los resultados guardados actualmente, sin desencadenar cálculos. |

Dos formatos CSV son analizados por el frontend, agrupados por `order`, y se envían en bloques de 1 a 10 registros JSON por solicitud, sin subir el archivo CSV original. Los participantes se identifican mediante `(order, user_id)` para usuarios de la plataforma y mediante `(order, arbiter_identifier)` para identificadores anónimos; no se mezclan ambos tipos de identidad. Si falla cualquier registro dentro de una solicitud, se deshace todo el lote, y los registros previamente exitosos se mantienen; el frontend envía las solicitudes en orden, y si falla una, no envía las siguientes.

Los CSV usan UTF-8 (permitiendo BOM) y encabezados, sin restricción en el orden de columnas; los strings de identidad conservan mayúsculas, minúsculas y espacios. Las nueve puntuaciones son enteros en milisegundos, sin verificar relaciones entre subcategorías ni la suma total; `t37` se calcula en la base de datos, el archivo no incluye clasificaciones ni puntos. Los encabezados se dividen en dos tipos, ejemplos en `front_end/cypress/fixtures/gsc/type2.csv` y `type3.csv`.

```csv
order,user_id,bt1st,bt20th,bt20sum,it1st,it12th,it12sum,et1st,et5th,et5sum
order,arbiter_identifier,bt1st,bt20th,bt20sum,it1st,it12th,it12sum,et1st,et5th,et5sum
```

Los usuarios de la plataforma deben existir, y los identificadores anónimos deben ser no vacíos. La misma identidad puede reutilizarse entre ediciones, pero si ya existe un participante en la misma edición o si hay una repetición de identidad en el mismo archivo, se rechaza; no se sobrescribe, no se cambia automáticamente la fuente de puntuación ni se eliminan participantes no listados en el archivo. Para corregir, se debe solicitar la cancelación de calificaciones por parte del organizador, esperar la eliminación exitosa y luego volver a añadir. El límite de 10 registros por lote es solo un límite de solicitud, no garantiza un tiempo de respuesta de 2 segundos en producción.

## Reintentos y cálculos manuales {#重试与人工重算}

El frontend registra separadamente el ID del participante, los identificadores ya procesados y los resultados de subida por archivo. Si la asociación falla, se pausa y, en los reintentos, no se procesa nuevamente un identificador ya tratado; una vez completados todos los identificadores, la subida de repetición se realiza según el archivo, y si un archivo falla, se continúa con otros archivos; se reintentan solo los archivos que no han tenido éxito y se conserva la hora original de subida. Si el tiempo de preparación de la solicitud vence, se puede reintentar directamente; los participantes con origen de repetición ya enviados se devuelven tal como están, sin crear uno nuevo. Al refrescar la página, se debe seleccionar nuevamente el archivo; el interfaz de preparación puede reutilizar los registros de origen de repetición ya existentes; los orígenes manuales no pueden ser gestionados así. Si el tiempo de asociación vence, se puede reintentar con el mismo identificador; si ya pertenece al propio usuario, se mantiene la asociación original y no se transfiere un identificador ajeno.

Durante mantenimiento, se hace una copia de seguridad de los datos, se suspenden las tareas de cálculo, mantenimiento del mejor resultado y actualización de puntos anuales, se completan las correcciones y se verifica todo, y luego se ejecuta en `back_end/saolei` por edición.

```bash
python manage.py refresh_tournament_scores <tournament_id>
```

Aquí se utiliza el ID de competición del tablero proporcionado por la lista de gestión, no el `order`. El comando rellena secuencialmente dentro de una transacción los datos de `TournamentUser`, recalcula los resultados de las repeticiones, actualiza todos los rankings, corrige los puntos según la diferencia entre los nuevos y antiguos `rank_score`, reconstruye los mejores resultados personales y actualiza el caché de clasificaciones. Los puntos de las repeticiones solo se aceptan para `OFFICIAL`, STD (incluyendo NF), nivel estándar de tres niveles y las condiciones correspondientes de 3BV o tiempo; los resultados manuales conservan las nueve calificaciones introducidas, y los jugadores anónimos ocupan posiciones pero no se registran en los puntos de cuenta.

Los `manual_scores` de GSC se configuran por jugador, y en una misma competición se pueden mezclar ambas fuentes. Borrar una repetición no implica inmediatamente recalcular; al ejecutar este comando posteriormente, los resultados de las repeticiones eliminadas se consideran nulos y se reemplazan por valores de las repeticiones restantes o por valores por defecto. Los resultados manuales conservan las nueve calificaciones introducidas por la organización, pero las posiciones y puntos pueden cambiar según la reordenación general de la competición; no se puede cambiar automáticamente a fuente manual solo por la ausencia de una repetición.

Los registros reinsertados tras su eliminación también deben recalcularse por cada edición para corregir los rankings y puntos de los demás jugadores. Al eliminar los puntos propios, se calcula la descomposición usando el tiempo de finalización original de la competición; no se puede sustituir el valor anterior de `rank_score` por el nuevo registro tras la eliminación para omitir la reducción de puntos. El final normal de una tarea no es una entrada alternativa para el mantenimiento histórico.

Implementación relacionada: `tournament/gsc/api.py`, `tournament/gsc/services.py`, `tournament/management/commands/refresh_tournament_scores.py`; interfaz del frontend: `components/GSCAdmin/HistoryImport.vue`, `HistoryVideos.vue`, `HistoryScores.vue` y `history.ts`.

Más detalles sobre señales y mantenimiento se encuentran en [la relación de activación de señales](./signals.md), [la estructura del caché](./cache.md) y [los comandos de gestión](./management-commands.md#refresh-tournament-scores).
