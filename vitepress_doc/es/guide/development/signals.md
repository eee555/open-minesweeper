---
title: "Relación de activación de señales - Open Minesweeper"
description: "Detalles sobre la relación de activación de señales del backend de Open Minesweeper, incluyendo los flujos de señales pre_save y post_save para modelos como la repetición, el usuario y los torneos."
---

# Relación de activación de señales

`userprofile.signals.revoke_qq_login` recibe `QQConnectIdentity.pre_delete`, bloquea el `UserProfile` correspondiente dentro de la transacción y revoca de inmediato la vinculación de QQ en curso. El callback de vinculación utiliza el mismo bloqueo. Esperar hasta después del commit permitiría que un callback en curso volviera a crear la identidad eliminada. Esto se aplica a la desvinculación por el usuario, al borrado mediante un QuerySet y al borrado en cascada. Si se revierte la transacción, se conserva la identidad y es necesario autorizar de nuevo. El apodo y el avatar no se copian al perfil público y el token de acceso no se conserva.

`accountlink.signals.invalidate_github_authorizations_on_delete` recibe `AccountGitHub.pre_delete`, lee explícitamente y bloquea el correspondiente `UserProfile`, anula inmediatamente el estado actual de GitHub dentro de la transacción de eliminación antes de liberar el bloqueo de fila del usuario, sin usar `on_commit`, evitando que los callbacks reestablezcan la asociación después de la desvinculación y antes de que se ejecute el hook de commit. La asociación en la base de datos se mantiene durante el rollback, pero la autorización se vuelve inválida y el usuario debe reinitiarla. Este bloqueo de fila del usuario comparte el uso con el commit de OAuth y depende de la serialización de bloqueos de fila en MySQL en producción; SQLite no ofrece esta garantía. Los casos de desvinculación personal, desvinculación antigua general, desvinculación de administrador, eliminación mediante QuerySet y eliminación en cascada del usuario han pasado por este señal. Solo afecta a autorizaciones no completadas de GitHub, no revierte las autorizaciones de aplicaciones en el sitio de GitHub; los claves temporales se encuentran en [estructura de caché ](./cache.md#github-授权临时状态)].

Los registros antiguos de velocidad y las señales antiguas de `news_queue` han sido eliminados. Las noticias de la página principal ahora son gestionadas por el módulo independiente `news`: `speedranking` toma una instantánea antes y después de escribir en el ranking, `effranking` compara el registro personal con el puesto en el ranking y, si se cumplen las condiciones, llama a `news.services.emit` para enviar `news.events.news_event_detected`; la señal `news.signals.record_news_event` recibe el evento y lo almacena en el hash y el conjunto zset por categorías en `news/cache.py`, y si el almacenamiento falla, solo se registra en el log, sin afectar la actualización del ranking. Las operaciones de eliminación en bloque, reparaciones administrativas con `force=True`, reconstrucción del backend tras cambios de punto de referencia y reconstrucción completa no envían esta señal. Los nombres de las claves y las reglas de expiración se encuentran en [cache.md](./cache.md).

El modelo `msuser` mantiene el conteo de videos de competencia y no competitivos, así como el espacio de archivos y el límite de carga. El nuevo ranking de velocidad es gestionado por `speedranking` que recibe `VideoModel.post_save/post_delete`, y actualiza incrementalmente Redis o reemplaza los registros inválidos tras la confirmación de la transacción.

El `speedranking` reutiliza los valores capturados por `videomanager`. Monitorea al jugador, nivel, modo, estado, torneo en curso, BV, timems, right_ce, tiempo de carga; compara directamente los resultados cuando mejora, y solo reconstruye los indicadores cuando empeora, pierde el derecho o se elimina. Durante la migración de categorías, se trata tanto al jugador anterior como al nuevo, y se almacenan los valores de bvs e iqg en el campo generado de la base de datos; si cambia el BV o timems, se activan las evaluaciones de estos indicadores derivados. La vinculación o desvinculación, y la publicación en bloque de torneos no activan señales de guardado; es necesario llamar explícitamente a `add_videos_to_speed_ranks` o `remove_videos_from_speed_ranks`.

La entrada de velocidad coordina simultáneamente `speedranking.saolei`, `speedranking.pb` y `speedranking.top`: comparten el pipeline de lectura de registros del usuario y escritura de cambios principales, y cada uno evalúa independientemente la selección óptima y la reubicación. El PB se clasifica por nivel, 3BV, y tipo normal/NF, compara el código score en el caso de mejora; los IDs de los videos de miembros antiguos provienen del hash del usuario, y se determina el rango según el orden antes y después del cambio de miembro, y se actualiza solo en bloque el rango correspondiente tras la escritura, con extensiones hasta el final del ranking. El top conserva los cinco mejores registros; solo revisa los registros que ya estaban en los cinco primeros cuando se vuelven inválidos o empeoran, y se actualiza el punto de referencia tras la escritura, eliminando duplicados en el ranking si hay cambios pequeños. Los errores en actualizaciones individuales, actualizaciones en bloque, reparaciones administrativas, comandos de administración y reconstrucciones se registran con contexto y pila y se lanzan nuevamente, sin usar WATCH ni intentos repetidos.

Las consultas incrementales de selección óptima, reubicación y reconstrucción en masa de los registros personales mantienen su lógica original; solo se utilizan cuatro decimales de BV y tiempos de carga por minutos al generar el zset de Redis, y se verifica el rango de codificación de cada indicador individual o total. Si se supera el límite, solo se elimina el elemento correspondiente del zset, sin activar la reubicación de registros personales, y el hash conserva el mejor resultado original; el ranking general se evalúa de forma independiente por valor total.

Top: conjunto inicial de usuarios participantes en las dieciocho categorías unificadas, indexado en orden descendente mediante el promedio transformado. Después de la escritura conjunta, se actualiza primero la capacidad suave del usuario según los puntos de anclaje ya publicados; cuando cambian los valores de anclaje en tiempo real, se envía el evento `speedranking.top.events.soft_refresh_requested`, creado por `top.signals` para generar la tarea `task_refresh_soft_ranks`. Durante la ejecución de la tarea, si hay otra tarea READY en el mismo camino, se salta normalmente; en caso contrario, se obtiene acceso exclusivo en máquina, se realiza una fusión ponderada de nueve pasos y se publica de forma unificada. Los puntos de entrada HTTP relacionados obtienen acceso compartido antes de la transacción y sobrescriben el callback on_commit; durante la actualización, los nuevos pedidos HTTP de escritura devuelven un 503 por razones de negocio, y el sistema de negocio espera sin rechazarlos. Los detalles sobre interfaces, rutas de bloqueo y limitaciones de operación se encuentran en `back_end/saolei/speedranking/README.md`.

NF es una dimensión independiente, determinada por `VideoModel.right_ce == 0`, ya no se utiliza el modo `12`; si `right_ce` está vacío, no se considera NF. `UserMS` no mantiene contadores secundarios de NF ni del modo original. `videomanager` captura los cambios en `right_ce` y actualiza la cola; `customranking` no requiere información de NF y no monitorea este campo. Después de la conversión en lote del modo anterior, es necesario actualizar explícitamente las estadísticas y el caché; los pasos se describen en `back_end/saolei/msuser/refactor.md`.

`effranking.signals` procesa el guardado y la eliminación de repeticiones. Usa `_old_values` y `update_fields` para identificar las clasificaciones afectadas. Para Thrp comprueba los clics efectivos, el BV y la fecha de subida. Para NF IOE y la familia TPE comprueba los clics reales (`left/right/double`), el BV y el tiempo. Solo NF IOE exige `right_ce=0`.

Tras confirmar la transacción, las tres clasificaciones leen la repetición una sola vez y comparten los pipelines de lectura y escritura de Redis. Cada una selecciona y reemplaza sus récords por separado. En experto NF, Thrp reconstruye la lista de repeticiones con puntuación máxima o selecciona la mejor partida. En NF IOE, el tiempo desempata las puntuaciones máximas por nivel. Si la suma es máxima, solo cuenta el tiempo de experto. TPE, TPE2 y TPE3 seleccionan sus récords por separado y cada suma requiere un resultado de esa fórmula en intermedio y experto. Si se revierte la transacción, Redis conserva el estado anterior.

Al vincular o desvincular identificadores o al publicar un torneo, se llama explícitamente al servicio por lotes. Las excepciones se registran con su contexto y traza, y vuelven a lanzarse. Solo las mejoras de Thrp y NF IOE al añadir repeticiones individuales o en lote generan noticias en la sección `eff`. La familia TPE, los reemplazos por un resultado peor, las eliminaciones en lote, las reparaciones administrativas y las reconstrucciones completas no emiten esa señal. Los detalles están en `back_end/saolei/effranking/README.md`.

Al eliminar un video, `videomanager.signals.delete_video_expansion` limpia los registros extendidos dentro de la transacción actual; la eliminación desde la tabla extendida sigue la cascada de Django. `customranking` ya no mantiene una tabla de récords: las señales de guardado y eliminación registran callbacks `on_commit(..., robust=True)` que comparan Redis con la repetición actual y consultan reemplazos solo para récords invalidados. Los valores anteriores de jugador y nivel permiten mover categorías. Un rollback no publica cambios; los errores se registran sin bloquear otros callbacks, sin nuevos bloqueos ni reintentos. Los cambios masivos llaman a los servicios add/remove.

La cola de videos más recientes mantiene su estado actual: al eliminar un video, no se limpia el snapshot de `newest_queue`, y las consultas pueden devolver aún IDs eliminados; solo se mantiene mediante funciones de corte existentes y la funcionalidad de eliminación por parte del administrador.

El proceso de importación para cuentas de homenaje y la clasificación GSC se organizan de forma independiente, reutilizando el vínculo de identificadores existente, la comparación de archivos y `set_import_upload_time`, manteniendo la cadena de estadísticas, clasificaciones, medallas y marcadores de competencia; `is_memorial` y `is_active=False` no excluyen el conteo de videos válidos.

Al eliminar una repetición de torneo se borran el archivo y sus vínculos con los torneos. La señal de eliminación conserva los resultados ya liquidados, los puestos, los puntos y las mejores marcas históricas hasta que se solicite un recálculo explícito. El recálculo depende del torneo y del origen de los resultados: los torneos semanales y los resultados de la GSC basados en repeticiones dejan de contar la repetición eliminada. Los participantes de la GSC con `manual_scores=True` conservan la puntuación introducida, pero siguen participando en el recálculo de puestos y puntos. Cada nuevo tipo de torneo debe definir sus propias reglas de eliminación y recálculo. El propietario del sitio usa `POST /api/video/admin/delete` con un ID por solicitud. La API llama a `delete()` sobre la instancia dentro de una transacción, conserva estas señales, devuelve los ID de los torneos afectados y deja un aviso en el registro. El panel oculto pide confirmación antes de enviar las solicitudes en orden y se detiene al primer error. Todavía no se envía un mensaje privado a los organizadores. El plan está en `back_end/saolei/tournament/VIDEO_DELETION_PLAN.md`.

```automaton
flowchart LR
    video_pre_save[VideoModel pre_save]
    video_post_save[VideoModel post_save]
    video_pre_delete[VideoModel pre_delete]
    tournament_post_save[Tournament post_save]
    tournament_post_delete[Tournament post_delete]
    gsc_post_save[GSCTournament post_save]
    weekly_post_save[WeeklyTournament post_save]
    weekly_eff_post_save[WeeklyEffTournament post_save]
    participant_post_save[TournamentParticipant post_save]
    gsc_participant_post_save[GSCParticipant post_save]
    weekly_participant_post_save[WeeklyParticipant post_save]
    weekly_eff_participant_post_save[WeeklyEffParticipant post_save]
    weekly_eff_participant_post_delete[WeeklyEffParticipant post_delete]
    participant_post_delete[TournamentParticipant post_delete]
    gsc_participant_post_delete[GSCParticipant post_delete]
    weekly_participant_post_delete[WeeklyParticipant post_delete]

    video_pre_save --> capture_video_update[Capturar los valores anteriores]
    capture_video_update --> video_post_save
    video_pre_save --> checkin_video_before_create[Identificar repeticiones de torneo]
    checkin_video_before_create --> video_post_save

    video_post_save --> refresh_state_queue_on_video_save[Actualizar la cola de revisión]
    video_post_save --> update_video_count_on_video_save[Actualizar estadísticas y cuota de subida del jugador]
    video_post_save --> add_created_video_to_checked_tournaments[Vincular la repetición al torneo]
    video_post_save --> refresh_custom_pluck_rank_on_video_save[Actualizar la marca pLuck]
    video_post_save --> speedranking_save[Actualizar y completar marcas de velocidad tras la confirmación]
    video_post_delete[VideoModel post_delete] --> speedranking_delete[Completar las marcas de velocidad tras la confirmación]
    video_post_save --> effranking_save[Actualizar y completar marcas de eficiencia tras la confirmación]
    video_post_delete --> effranking_delete[Completar las marcas de eficiencia tras la confirmación]
    video_post_delete --> delete_video_expansion[Eliminar datos ampliados de la repetición]
    video_post_delete --> refresh_custom_pluck_rank_on_video_delete[Completar las marcas pLuck tras la confirmación]

    video_pre_delete --> update_video_count_on_video_delete[Restar la repetición de las estadísticas del jugador]
    profile_post_delete[UserProfile post_delete] --> delete_user_ms[Eliminar el perfil asociado de Buscaminas]
    profile_post_delete --> delete_derived_records[Limpiar resultados derivados de PB tras la confirmación]



    refresh_custom_pluck_rank_on_video_save --> pluck_redis[Actualizar Redis y reemplazar récords tras confirmar]
    refresh_custom_pluck_rank_on_video_delete --> pluck_redis
    minigame_post_delete[MiniGameBestScore post_delete] --> delete_cached_score[Eliminar el resultado de la clasificación del minijuego]

    add_created_video_to_checked_tournaments -. m2m_changed .-> no_video_signal[Ninguna]

    tournament_post_save --> update_cache_on_tournament_save[Actualizar la caché de torneos]
    gsc_post_save --> update_cache_on_tournament_save
    weekly_post_save --> update_cache_on_tournament_save
    weekly_eff_post_save --> update_cache_on_tournament_save
    tournament_post_delete --> update_cache_on_tournament_delete[Eliminar la caché del torneo]

    participant_post_save --> update_cache_on_participant_save[Actualizar la caché de inscripciones]
    gsc_participant_post_save --> update_cache_on_participant_save
    weekly_participant_post_save --> update_cache_on_participant_save
    weekly_eff_participant_post_save --> update_cache_on_participant_save
    weekly_eff_participant_post_save --> update_best_score_on_weekly_eff_participant_save[Actualizar la mejor marca histórica de eficiencia]
    weekly_eff_participant_post_delete --> update_best_score_on_weekly_eff_participant_delete[Recalcular la mejor marca histórica de eficiencia]
    gsc_participant_post_save --> update_best_score_on_gsc_participant_save[Actualizar la mejor marca histórica de la GSC]
    weekly_participant_post_save --> update_best_score_on_weekly_participant_save[Actualizar la mejor marca histórica del torneo semanal]
    gsc_participant_post_delete --> update_best_score_on_gsc_participant_delete[Recalcular la mejor marca histórica de la GSC]
    weekly_participant_post_delete --> update_best_score_on_weekly_participant_delete[Recalcular la mejor marca histórica del torneo semanal]
    participant_post_delete --> remove_participant_cache_on_delete[Eliminar la inscripción de la caché]
    participant_post_delete --> revoke_rank_score_on_participant_delete[Retirar los puntos concedidos por el torneo]
    update_cache_on_participant_save -->|Nueva inscripción salvo en una GSC ya premiada| add_existing_videos_to_participant_tournament[Vincular repeticiones existentes al torneo]

    add_existing_videos_to_participant_tournament -. m2m_changed .-> no_participant_signal[Ninguna]

    click video_pre_save "#signal-function-map" "Antes de guardar VideoModel"
    click video_post_save "#signal-function-map" "Después de guardar VideoModel"
    click delete_cached_score "#signal-function-map" "Tras la confirmación se elimina al jugador del ZSET del minijuego y del hash de detalles"
    click tournament_post_save "#signal-function-map" "Después de guardar Tournament"
    click tournament_post_delete "#signal-function-map" "Después de eliminar Tournament"
    click gsc_post_save "#signal-function-map" "Después de guardar GSCTournament"
    click weekly_post_save "#signal-function-map" "Después de guardar WeeklyTournament"
    click participant_post_save "#signal-function-map" "Después de guardar TournamentParticipant"
    click gsc_participant_post_save "#signal-function-map" "Después de guardar GSCParticipant"
    click weekly_participant_post_save "#signal-function-map" "Después de guardar WeeklyParticipant"
    click participant_post_delete "#signal-function-map" "Después de eliminar TournamentParticipant"
    click gsc_participant_post_delete "#signal-function-map" "Después de eliminar GSCParticipant"
    click weekly_participant_post_delete "#signal-function-map" "Después de eliminar WeeklyParticipant"

    click capture_video_update "#signal-function-map" "Registrar el estado anterior de la repetición para determinar qué actualizar tras guardarla"
    click checkin_video_before_create "#signal-function-map" "Antes de crear la repetición, consultar la caché de inscripciones para saber si corresponde a un torneo"
    click refresh_state_queue_on_video_save "#signal-function-map" "Sincronizar la cola de repeticiones ordinarias según el estado de la repetición"
    click update_video_count_on_video_save "#signal-function-map" "Un solo UPDATE ajusta el recuento, el espacio y los aumentos necesarios de cuota. Los cambios de titular usan un UPDATE condicional"
    click add_created_video_to_checked_tournaments "#signal-function-map" "Una vez creada la repetición, vincularla con los torneos correspondientes"
    click refresh_custom_pluck_rank_on_video_save "#signal-function-map" "Actualizar la clasificación pLuck personalizada después de guardar la repetición"
    click refresh_custom_pluck_rank_on_video_delete "#signal-function-map" "Tras confirmar la eliminación, elegir entre las repeticiones válidas restantes para completar la marca pLuck"
    click delete_video_expansion "#signal-function-map" "Eliminar los datos ampliados en la transacción de eliminación. La eliminación de su origen sigue usando la cascada existente"
    click update_video_count_on_video_delete "#signal-function-map" "Antes de eliminar la repetición, reducir el recuento y el espacio según su marca y sus vínculos de torneo"
    click profile_post_delete "#signal-function-map" "Eliminar el perfil asociado de Buscaminas después de borrar al usuario"
    click delete_user_ms "#signal-function-map" "Eliminar UserMS por su clave foránea en la misma transacción. Evitar limpieza duplicada si la cascada procede de UserMS"
    click delete_derived_records "#signal-function-map" "Tras confirmar, limpiar el hash de resultados derivados de PB y los miembros de todas sus clasificaciones"
    click pluck_redis "#signal-function-map" "Actualizar Redis mediante customranking.services.sync_video tras confirmar"
    click update_cache_on_tournament_save "#signal-function-map" "Sincronizar la caché de torneos NORMAL después de guardar el torneo"
    click update_cache_on_tournament_delete "#signal-function-map" "Al eliminar el torneo, eliminar también sus datos y sus inscripciones de la caché"
    click update_cache_on_participant_save "#signal-function-map" "Sincronizar la caché de inscripciones del usuario después de guardar la inscripción"
    click update_best_score_on_gsc_participant_save "#signal-function-map" "Actualizar la mejor marca histórica del usuario después de guardar su resultado en la GSC"
    click update_best_score_on_weekly_participant_save "#signal-function-map" "Actualizar la mejor marca histórica del usuario después de guardar su resultado semanal"
    click update_best_score_on_gsc_participant_delete "#signal-function-map" "Recalcular la mejor marca histórica del usuario después de eliminar su resultado en la GSC"
    click update_best_score_on_weekly_participant_delete "#signal-function-map" "Recalcular la mejor marca histórica del usuario después de eliminar su resultado semanal"
    click remove_participant_cache_on_delete "#signal-function-map" "Eliminar la inscripción del usuario de la caché, salvo si el participante no tiene cuenta en el sitio"
    click revoke_rank_score_on_participant_delete "#signal-function-map" "Tras eliminar la inscripción, retirar los puntos originales con la depreciación correspondiente a la fecha de fin del torneo. La base de datos se actualiza en la misma transacción y la clasificación tras su confirmación"
    click add_existing_videos_to_participant_tournament "#signal-function-map" "Buscar y vincular las repeticiones existentes del torneo después de crear la inscripción"
```

<a id="signal-function-map"></a>

`UserProfile.post_delete` llama a `userprofile.signals.delete_user_ms`, dentro del mismo transacción de eliminación, mediante `instance.userms_id` limpia las asociaciones `UserMS` y las elimina mediante la clave foránea existente; sobrescribe la eliminación de instancias, QuerySet y Admin. Cuando `origin` es una instancia o QuerySet de `UserMS`, se salta, ya que el recolector original se encarga de la eliminación, evitando la duplicación de señales. Se salta directamente si no hay asociaciones, y en caso de fallo en la limpieza se deshace la eliminación del usuario y los datos. Los datos aislados históricos se gestionan mediante [cleanup_orphan_userms](./management-commands.md#cleanup-orphan-userms).

Al ejecutar `UserProfile.post_delete`, también se activa `speedranking.pb_derived.signals.delete_derived_records` tras el commit, que elimina los campos y todos los miembros de los zset de los 132 subtableros derivados de los tres grandes rankings de PB del usuario; los receptores se registran en `speedranking.apps.ready`, sin añadir receptores para `VideoModel`. El caché original de PB aún no incluye limpieza al eliminar usuarios, lo cual constituye una brecha existente, y no se realiza ningún cambio implícito en el módulo derivado.

Al ejecutar `MiniGameBestScore.post_delete`, se llama a `minigame.signals.delete_cached_score`, que tras el commit elimina al jugador de la lista ZSET y del hash detallado, conservando la marca de inicialización; sobrescribe la eliminación por Admin, QuerySet y cascada del usuario, y en caso de error no modifica el caché. La creación y mejora de juegos pequeños se actualizan directamente por el servicio de envío mediante `on_commit`, sin necesidad de un señal de guardado adicional.

La importación histórica de GSC sigue usando las señales de creación por defecto de TournamentUser y de guardado de best, permitiendo mejoras por defecto o manualmente; los participantes anónimos no activan la actualización del caché de participación. Al crear GSC ya premiada, no se rellena automáticamente la grabación, y se asocia explícitamente por el servicio de transmisión; las inscripciones normales y las competencias semanales permanecen sin cambios. El orden de llamada y las reglas de puntuación manual en la interfaz de importación se describen en [Importación histórica de grabaciones de GSC](./gsc-history-import.md).

Los señales de guardado de Tournament/Participant en la competencia de eficiencia también se vinculan a la actualización del caché común y al receptor de completado de TournamentUser; se mantienen solo los receptores de eliminación del caché y retiro de puntos de la clase padre, evitando duplicación de retiros. Los señales `weekly_eff.signals` gestionan de forma independiente el mejor valor original en flotante y su correspondiente año/semana: se almacena en la base de datos dentro de la transacción actual, y se publica en Redis tras el commit; si no hay historial de resultados, se eliminan los tres campos juntos y se quita el miembro del zset de best. La cancelación de participación ya premiada se ejecuta mediante el mismo worker al eliminar el participante, activando estas señales, pero sin eliminar los archivos de grabación; los intentos de recuperación de registros ya eliminados no deducen puntos repetidamente.

La señal de guardado del mejor resultado en eficiencia solo consulta el resumen del usuario cuando hay datos en el campo de puntuación y la competencia ya ha sido premiada; en inscripciones normales, solo se completa el `TournamentUser` mediante la señal de creación común, sin realizar una consulta adicional de mejor resultado. Al eliminar un participante de una competencia de eficiencia, si el resumen del usuario está ausente, se crea primero una fila por defecto, y luego se reconstruye el mejor resultado a partir de los resultados ya premiados; la creación de fila no recupera los puntos históricos perdidos.

La importación de una repetición se configura previamente en `create_from_parser` estableciendo la fuente `upload_time` para usarla en el check-in de `pre_save`; tras crearla, se guarda explícitamente para sobrescribir `auto_now_add`. Para archivos existentes, solo se guarda si el tiempo actual es anterior. Ambos procesos siguen los señales de estado y clasificación, sin usar `QuerySet.update` para evitar efectos secundarios.

Solo modificar `upload_time` también activará la señal de guardado de repetición para actualizar los logros. Los trabajadores verifican antes de publicar el resumen los datos afectados tanto actuales como históricos, incluso si el rendimiento y el nivel no han cambiado, corrigiendo así la fecha de otorgamiento, los datos y los registros de etapas. Esto se aplica tanto si se modifica el tiempo de subida hacia adelante como hacia atrás. Los conjuntos de nuevos jugadores y los logros de tercer nivel conservan el ID completo de la repetición por parte, y cualquier cambio en una parte permite recalcular la fecha de primera finalización. Los logros otorgados manualmente no se sobrescriben.

| Nombre en el gráfico | Función |
| --- | --- |
| Eliminar el resultado de clasificación en juegos pequeños | `minigame.signals.delete_cached_score` |
| Capturar el valor anterior del campo | `capture_video_update` |
| Detección de repetición en competencias | `checkin_video_before_create` |
| Actualizar la cola de estado | `refresh_state_queue_on_video_save` |
| Actualizar el estadístico de video del usuario y el límite de subida | `update_video_count_on_video_save` |
| Eliminar el estadístico de video del usuario | `update_video_count_on_video_delete` |
| Eliminar los datos asociados de Buscaminas | `userprofile.signals.delete_user_ms` |
| Eliminar los resultados derivados de la marca personal (PB) tras la publicación | `speedranking.pb_derived.signals.delete_derived_records` → `services.remove_player` |
| Asignar la repetición de competencia al evento | `add_created_video_to_checked_tournaments` |
| Actualizar el registro de pluck | `refresh_custom_pluck_rank_on_video_save` |
| Completar el registro de pluck tras la publicación | `refresh_custom_pluck_rank_on_video_delete` |
| Limpiar los registros extendidos de la repetición | `videomanager.signals.delete_video_expansion` |
| Actualizar el registro de eficiencia y completar posiciones necesarias tras la publicación | `effranking.signals.refresh_ranks_on_video_save` |
| Completar el registro de eficiencia tras la publicación | `effranking.signals.refresh_ranks_on_video_delete` |
| Actualizar Redis y reemplazar récords pLuck tras confirmar | `customranking.services.sync_video` |
| Actualizar el caché del evento | `update_cache_on_tournament_save` |
| Eliminar el caché del evento | `update_cache_on_tournament_delete` |
| Actualizar el caché de los participantes | `update_cache_on_participant_save` |
| Actualizar el historial mejor de la Copa de la Oveja de Oro | `update_best_score_on_gsc_participant_save` |
| Actualizar el historial mejor de la semana | `update_best_score_on_weekly_participant_save` |
| Recalcular el historial mejor de la Copa de la Oveja de Oro | `update_best_score_on_gsc_participant_delete` |
| Recalcular el historial mejor de la semana | `update_best_score_on_weekly_participant_delete` |
| Actualizar el historial mejor de la competencia de eficiencia | `weekly_eff.signals.update_best_score_on_weekly_eff_participant_save` |
| Recalcular el historial mejor de la competencia de eficiencia | `weekly_eff.signals.update_best_score_on_weekly_eff_participant_delete` |
| Eliminar el caché de los participantes | `remove_participant_cache_on_delete` |
| Revocar los puntos de competencia ya publicados | `revoke_rank_score_on_participant_delete` |
| Registrar una repetición de competencia | `add_existing_videos_to_participant_tournament` |

Las repeticiones se cuentan por separado fuera de torneos (`video_num_total`), en torneos (`video_num_tournament`) y en total (`video_num_all`). Los tamaños correspondientes se guardan en `video_size_total`, `video_size_tournament` y `video_size_all`. Se suman los bytes realmente almacenados de `stored_file_size` y, si el valor es nulo, se usa el tamaño original `file_size`. La base de datos calcula automáticamente ambos totales mediante `GeneratedField`.

Al crear, después de la verificación en `pre_save` del evento, se clasifica según `ongoing_tournament`. Al guardar, se reutiliza el valor anterior capturado por `videomanager`, se procesa `stored_file_size`, se vuelve al valor `file_size` en caso de necesidad y se actualiza la pertenencia del jugador, y se consulta inmediatamente si la repetición actual tiene marcación de evento o asociación con uno. Al comprimir manualmente se usa `QuerySet.update()` para cambiar el archivo, y dentro de la misma transacción se envía `videomanager.events.video_storage_changed`; `msuser.signals.update_video_size_on_storage_change` ajusta el espacio según la pertenencia actual, se incluye o se deshace junto con la operación, sin activar la agregación de todos los videos del usuario. Al eliminar, se lee el tamaño almacenado y la pertenencia actual en `pre_delete` para evitar eliminar en cascada antes de quitar la asociación con el evento.

Los campos estadísticos en la rama `if/else` usan codificación literal; actualizados mediante `F()`. El número, el espacio y el límite de subida pendiente se combinan en una sola operación `UserMS UPDATE`; la transferencia de pertenencia se realiza mediante `CASE WHEN`, reduciendo simultáneamente el saldo del jugador original y aumentando el del nuevo jugador, permitiendo solo aumentos para el nuevo jugador. No se emiten notificaciones de estadísticas de usuario `UPDATE` cuando no haya cambios en estadísticas ni en límites. Los dos totales se generan de forma sincronizada en la base de datos.

Las reglas de coincidencia y asociación para la entrada de datos se mantienen sin cambios. La adición o eliminación de asociación con eventos, la limpieza o la eliminación del evento no ajustan inmediatamente las estadísticas; tampoco el hecho de que un evento se haga público cambia directamente las estadísticas. Después de eso, cualquier modificación en cantidad, tamaño o pertenencia se procesa según la pertenencia actual del evento, permitiendo que las estadísticas tengan desviaciones temporales, que se corriguen en conjunto mediante `refresh_video_counts` para una recalculación completa, sin guardar marcas históricas de clasificación. La recalculación utiliza `EXISTS` para verificar la relación de evento, combinando la marcación del evento y cualquier asociación con eventos, y en cada transacción solo se escribe en el estadístico del usuario, evitando acumulaciones duplicadas por la misma repetición con múltiples eventos. Los importes masivos o actualizaciones que evitan señales también se completan mediante comandos de recalculación. Las reglas de cálculo del límite de subida se mantienen sin cambios, y se escriben en `update_video_count_on_video_save` al momento de la publicación del video.

Los señales de guardado de `Tournament`, `GSCTournament` y `WeeklyTournament` se asignan al mismo receptor `update_cache_on_tournament_save`. Las señales de guardado de `TournamentParticipant`, `GSCParticipant` y `WeeklyParticipant` se asignan al mismo receptor `update_cache_on_participant_save`. La señal de eliminación de caché solo conserva el receptor de la clase padre; al eliminar instancias de subclases en herencia múltiple, también se dispara la eliminación de la tabla padre. El mejor resultado histórico depende del campo de puntuación de la subclase participant, por lo que se maneja de forma independiente mediante las señales de guardado y eliminación de `GSCParticipant` y `WeeklyParticipant`: al guardar, se compara solo el participante actual con el mejor anterior; al eliminar, se recalcula el mejor histórico del usuario. La señal de actualización del mejor resultado modifica el campo agregado en la tabla `TournamentUser`, y debe mantenerse coherente con los cambios en los participantes, por lo que no se utiliza `transaction.on_commit`.

`revoke_rank_score_on_participant_delete` solo escucha a la clase padre `TournamentParticipant.post_delete`, y se ejecuta una vez para la eliminación de instancias, QuerySet y ligas, sin vincularse repetidamente a subclases. Los participantes anónimos y `rank_score=0` se saltean. Para otros registros, se bloquean los existentes `TournamentUser` dentro de la transacción de eliminación, se llama a `add_score(-rank_score, tournament.end_time, category=...)` para revocar los puntos ya enviados; los puntos actuales se descomponen según el tiempo de finalización de la competición hasta el valor de `last_updated` que el usuario mantiene, y las puntuaciones históricas se restan de las clasificaciones GSC/Clásico de la semana, eliminando el valor original no descontado. El sistema de deducción en la base de datos no utiliza `on_commit`, y el rollback se realiza junto con la eliminación; solo el ranking de puntos en Redis se actualiza tras la confirmación, manteniendo el punto anual existente. Se conserva TournamentUser, sin reordenar automáticamente a los demás participantes; para reordenar y corregir sus puntuaciones se ejecuta `refresh_tournament_scores`. Si hay puntos enviados pero falta TournamentUser, se trata de un error de integridad de datos, no se salta en silencio ni se crea un usuario con puntuación cero.

Las definiciones de medallas las proporciona `medal/definitions.py` de forma estática, sin señales de pérdida de tabla de configuración ni de caché de directorio. `medal.signals.enqueue_medal_refresh_on_video` monitorea el guardado y la eliminación de `VideoModel`, y tras la confirmación de transacción, agrega al jugador actual en `task_refresh_player_medals` y registra el id de la repetición encontrada. Al deshacerse, cuando los resultados empeoran, al cambiar de jugador o al eliminar, se lleva consigo el nivel afectado. Al guardar, si la repetición ya tiene registrado un antiguo `player_id`, también se agrega el antiguo jugador. `medal.signals.enqueue_medal_refresh_on_profile` revisa el campo de modelo real `_realname`, y si se guarda la información y cambia el nombre real, se agrega a una actualización completa. `medal.signals.enqueue_medal_refresh_on_saolei_link` agrega a una actualización completa cuando se vincula o se desvincula en la plataforma Saolei.wang; en otras plataformas no se agrega. Para operaciones masivas de vinculación o desvinculación, se agrega a una actualización incremental con el id de la repetición de esta serie; al desvincular, se lleva consigo el nivel afectado y se vence la colección de nuevos jugadores, igual que en una anulación individual de repetición. Si la serie supera `medal.utils.REFRESH_VIDEO_ID_LIMIT` elementos, involucra a varios jugadores, no proporciona el id de la repetición, no declara explícitamente `lost_qualification` (`True` o `False`), o declara la pérdida de calificación sin adjuntar `lost_levels`, se agrega a una actualización completa. Los receptores no evalúan directamente las medallas ni hacen referencia a ellas en `userprofile` o `accountlink`.

La función `medal.signals.invalidate_summary_on_evidence_delete` escucha la señal `pre_delete` de `VideoModel` y `TournamentParticipant`. Antes de que `SET_NULL` borre las referencias a las pruebas de concesión, consulta qué jugadores están afectados, los bloquea en orden de clave primaria y elimina los registros `PlayerMedalSummary` correspondientes dentro de la misma transacción. La clave `medal:display:v4:{user_id}` solo se elimina después de la confirmación de la transacción. Si la eliminación se revierte, se conservan tanto el resumen como la clave de estado. En la próxima lectura se actualiza el resumen para reflejar las referencias a pruebas que han quedado nulas. El proceso de evaluación en segundo plano sigue gestionando el progreso natural y el derecho a las medallas. Eliminar la clave de visualización no modifica `MedalScan`. La siguiente actualización de repeticiones procesa de forma incremental los niveles y las pruebas afectados. Si falta la clave de visualización, se consultan los resúmenes o las concesiones por lotes para reponerla, sin volver a recorrer las repeticiones históricas.

Los marcadores `QuerySet.update()`, `post_save`, etc., se copian intactos; cada uno representa código literal. Los puntos de entrada de negocio envían los afectados `player_ids` a través de `videomanager.events.videos_bulk_changed`, opcionalmente incluyendo el nombre único del jugador `video_ids`, si el video de partida ha perdido el derecho `lost_qualification` y su dificultad `lost_levels`; el receptor de medallas realiza deduplicación y registra un callback independiente para cada jugador `transaction.on_commit(..., robust=True)`; el rollback de transacciones no se agrega a la cola, si el registro de jugador único falla en entrar a la cola se registra un error en el log, pero no interrumpe a otros jugadores ni la actualización del caché. La publicación en bloque de la última cola de competencia y las clasificaciones individuales utilizan callbacks robustos independientes, sin dependencia mutua entre el caché y el registro de medallas; estos callbacks no se reintentan automáticamente. La función de entrada se serializa en MySQL mediante una cadena denominada 'ID del jugador + nombre de la base de datos' `GET_LOCK`, se libera tras el commit de la transacción de entrada, no bloquea la fila del jugador, por lo que no espera a que se ejecute la evaluación de medallas; el bloqueo por nombre solo se compite entre los lados de entrada, se mantiene normalmente durante milisegundos; si el tiempo de espera del bloqueo supera `medal.utils.QUEUE_LOCK_TIMEOUT` segundos, se deja de esperar, se registra una advertencia y se ingresa normalmente, posiblemente generando tareas duplicadas en múltiples clasificaciones, que se ejecutan de forma serial bajo bloqueo en la fila del jugador, sin cambios en el resultado. Si el resultado de liberación no es exitoso, se registra una advertencia y se cierra la conexión para evitar que los bloqueos de sesión dejados en conexiones persistentes ralentizen futuras entradas. En bases de datos distintas a MySQL, no se usan bloqueos por nombre, sino que se bloquea la fila del jugador mediante la transacción de entrada. La transacción de entrada es `durable`; si se llama desde una transacción externa, se produce un error directo, dentro de una transacción de negocio debe pasar por `transaction.on_commit` para entrar. En la base de datos, se decide si ya existe una tarea mediante el camino de la tarea, el estado `READY` y los parámetros del jugador, sin leer el JSON completo de la cola. La prioridad de las nuevas inserciones `task_refresh_player_medals` es 1, y solo se puede ejecutar después de 3 segundos; si ya existe una tarea `READY`, se combinan los parámetros sin retrasar la tarea anterior; en caso de errores, el tiempo de inicio se ajusta al límite máximo de retraso de 3 segundos. Durante la consulta de combinación, si la tarea ya fue tomada por un worker, se programa una nueva tarea para gestionar el cambio. La prioridad de la tarea reenviada sigue siendo 0 y se puede ejecutar inmediatamente tras su creación. El callback `on_commit()` sigue ejecutándose de forma sincrónica, por lo que no se puede considerar que no haya costo de entrada en la solicitud.

## Transformación del almacenamiento de grabaciones

Las nuevas subidas y importaciones intentan comprimir y verificar en `VideoModel.create_from_parser`. Si el proceso es exitoso, se guarda y se archiva; si falla, se guarda el archivo original y se registra el formato de compresión como `0`. La creación de grabaciones sigue desencadenando los eventos existentes de competencia, estadísticas, clasificaciones y medallas. El valor original de `file_size` y el resultado de la interpretación se mantienen sin cambios.

`compress_video_files` ejecuta `QuerySet.update()` usando como condiciones el identificador principal, la ruta original y el formato de compresión original, sin llamar al método `save()` del modelo ni desencadenar señales de guardado. El servicio de conversión verifica después de su confirmación si hay referencias en la base de datos a los archivos antiguos y los elimina. El tamaño original, el hash, el estado de revisión y la información de competencia permanecen sin cambios. La transformación del almacenamiento no recalcula clasificaciones ni el número de grabaciones, ni depende de las señales de guardado de django-cleanup para cambiar los caminos.
