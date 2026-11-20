---
title: "Medallas - Open Minesweeper"
description: "Cómo obtener, ver y fijar medallas, entender los títulos de habilidad y resolver dudas sobre la aprobación de repeticiones, los premios históricos y los cambios de nivel."
---

# Medallas

Las medallas registran los objetivos que has alcanzado en este sitio. Un título es el nombre asociado a una medalla. **Las medallas elegibles se otorgan automáticamente. Luego puedes elegir hasta seis para fijarlas en tu perfil.**

## Inicio

1. Abre un perfil de jugador y selecciona **Medallas**.
2. Alternar entre **Todas las medallas** y **Medallas obtenidas**. Cada fila muestra el nivel actual, el objetivo siguiente y todos los umbrales. Navega horizontalmente por la pista de niveles y elige un nivel o **Detalles** para leer sus requisitos.
3. Inicia sesión, abre tu pestaña de Medallas y elige **Gestionar fijaciones**. Añade medallas y haz clic en **Guardar fijaciones**.

Todas las medallas incluyen objetivos no obtenidos públicos; las medallas obtenidas incluyen solo premios válidos actuales. Las medallas ocultas bloqueadas se excluyen. Para comenzar, completa tu nombre real, sube tus propias repeticiones y verifica que pasen la revisión.

## Obtención de medallas

### Títulos de principiante

- **Registrado**: tu cuenta tiene un nombre real y ya no es anónima.
- **Revisado**: al menos una de tus repeticiones ha pasado la revisión.
- **Principiante en Buscaminas**: has aprobado repeticiones en Principiante, Intermedio y Experto.
- **Principiante NF**: has aprobado repeticiones NF en todos los tres niveles.
- **Gran tour**: tienes al menos una repetición aprobada en cada uno de cuatro modos: Estándar, Velocidad NG, Hardcore NG y Suerte. Solo las repeticiones EVF distinguen los modos; todos los demás formatos se cuentan como Estándar. Cada modo se cuenta por separado; no necesitas los tres niveles de dificultad en cada modo, y cubrir tres niveles en un solo modo no cumple con este requisito.
- **Rastros antiguos**: el enlace de tu cuenta saolei.wang ha sido verificado. Consulta [Enlaces de cuenta](./account-links.md). El requisito actual es el enlace verificado; no es necesario importar otra repetición. La actualización del perfil y la sincronización de repeticiones están desactivadas durante la migración a saolei.wang.

Los requisitos de repetición de principiante siguen sus reglas individuales; no todos requieren el modo Estándar.

### Títulos de habilidad

Los títulos de habilidad siguen separadamente a Principiante, Intermedio y Experto:

- **Punto de ruptura** utiliza tu tiempo más rápido. Sub10 significa estrictamente menos de 10 segundos; 10.000 segundos no cumple.
- **Velocidad** utiliza tu mejor 3BV/s, la cantidad de trabajo en el tablero completado por segundo. Un nivel de 3 requiere al menos 3 3BV/s.
- **Maestría** utiliza tu mejor STNB, una medida del desempeño en un solo juego en lugar del número de juegos o del ranking.
- **Punto de ruptura NF, Velocidad NF y Maestría NF** utilizan las métricas correspondientes de las repeticiones NF.
- **NF Precisión y Precisión** utilizan la mayor thrp para ese estilo de juego. thrp es `3BV / effective clicks`; difiere de IOE, que utiliza los clics totales.
- **Precisión NF de tres niveles y Precisión de tres niveles** requieren que todos los tres niveles de dificultad cumplan con el umbral en el mismo estilo de juego. Tres niveles se refiere a niveles de dificultad, no a tres juegos, tres premios o una suma. Por ejemplo, Precisión NF de tres niveles · 0.9 requiere un thrp NF de al menos 0.9 en cada nivel, que puede provenir de repeticiones separadas.

Estos títulos comparan tus resultados elegibles propios con umbrales fijos. Un resultado cualificado por cada métrica y nivel requerido es suficiente; no necesitas cinco resultados, una posición en la clasificación o un resultado mejor que otro jugador. Consulta [Datos](./minesweeper/stat.md) para más información sobre las métricas.

Para las medallas de habilidad en un solo nivel, una, dos y tres estrellas indican Principiante, Intermedio y Experto. Tres estrellas forman un triángulo con una arriba y dos abajo. Los colores indican los rangos de puntuación dentro de cada dificultad; los números muestran el umbral exacto. Los colores coincidentes entre dificultades no implican tiempos iguales ni posiciones en la clasificación. Tres Niveles de Precisión es un logro transdificultad y no recibe estrellas de Experto.

Abre **Personalizar colores de medallas** en una página de medalla o **Colores de medallas** en Configuración para cambiar los cinco colores de puntuación o sobrescribir un umbral individual. Los cambios afectan solo a tu vista y se guardan en este navegador. Se ofrecen opciones de reinicio y exportación/importación de JSON.

::: tip Ordinario, NF y FL
NF significa jugar sin banderas; FL significa jugar con banderas. El sitio determina el estilo según las acciones de clic derecho efectivas en la repetición. El Desarrollo Ordinario, la Velocidad y el Dominio aceptan cualquiera de los dos estilos, por lo que una repetición NF puede calificar para ambos títulos ordinarios y su versión NF.

Precisión mantiene los dos estilos separados: las repeticiones NF cuentan para la Precisión NF, mientras que las repeticiones FL cuentan para la Precisión. Una repetición no puede contar para ambos.
:::

### Otros títulos

**Socio Original** verifica si el ID de repetición más bajo que aún pertenece a ti en este sitio está por debajo de un umbral. Reconoce registros de repeticiones tempranas. No utiliza la fecha de registro de cuenta, la fecha de grabación del juego ni donaciones, y la repetición no necesita haber pasado por revisión.

Otros títulos dependen de lo que esté actualmente habilitado y de sus anotaciones. Una categoría ausente simplemente puede significar que no has ganado medallas en ella.

## ¿Qué repeticiones cuentan para títulos de habilidad?

Una repetición de habilidad debe:

1. **Pertenecer a tu cuenta.** Subir un archivo no es suficiente si su identificador de jugador no coincide. Consulta [Identificadores de jugador](./identifier.md).
2. **Haber pasado por revisión.** El éxito en la subida no significa aprobación. Las repeticiones pendientes o congeladas no se consideran resultados válidos de habilidad.
3. **Usar el modo Estándar en Principiante, Intermedio o Experto.** Otros modos, incluidos los sin adivinanzas, no cuentan para estos títulos.
4. **No estar oculto como repetición de torneo en curso.** Estos resultados se revisan nuevamente tras su publicación.
5. **Contener datos válidos para la métrica.** La Precisión requiere datos válidos de 3BV y clics; la Precisión NF excluye registros con menos clics efectivos que 3BV.

Estos títulos de habilidad actualmente no tienen un requisito adicional mínimo de 3BV. Diferentes repeticiones pueden proporcionar tus logros en tiempo, velocidad y eficiencia.

Las repeticiones antiguas pueden calificar una vez subidas y aptas. Los archivos almacenados solo en tu computadora, los resultados guardados solo en otra plataforma y los registros locales importados en la página desde un CSV no pueden otorgar directamente medallas.

## Fijar, reemplazar y ordenar medallas

1. Inicia sesión y abre **tu propio perfil → Medallas**. Las páginas de otros jugadores son de solo visualización.
2. Abre **Gestionar fijaciones**, luego usa **Añadir a fijaciones / Desfijar** en cada fila. Las vistas previas de niveles no modifican las fijaciones.
3. Selecciona hasta **seis**. Al llegar al límite, desmarca uno antes de añadir otro.
4. Haz clic en **Guardar fijaciones**, luego verifica la visualización en la zona de información de tu perfil.

Usa las flechas anterior/posterior en el editor de fijaciones para reordenar las medallas, luego guarda. **Cancelar cambios** restaura la selección guardada.

Tus fijaciones aparecen en la zona de información del perfil, normalmente a la izquierda en pantallas anchas y encima del contenido en pantallas estrechas. Permanecen visibles al cambiar entre Top, PB, Registro y otras pestañas. En lugares donde estén disponibles las herramientas de tooltip de nombre de jugador, como en clasificaciones, pasa el ratón sobre un nombre para ver sus fijaciones y luego sobre una medalla para leer su explicación.

::: tip Obtener y fijar son acciones separadas
Selecciona y guarda una medalla ganada para mostrarse entre tus banderas. Quitar una bandera no elimina el derecho de propiedad. Deseleccionar todo y guardar borra tus banderas, mientras que las medallas ganadas siguen visibles para otros en tu pestaña de medallas.

Las selecciones se mantienen pendientes hasta que se guarden. Si el guardado falla, revisa tu estado de inicio de sesión y conexión, vuelve a guardar y verifica la visualización.
:::

## Actualizaciones y otros cambios

Cada serie, dificultad y estilo de juego conserva el nivel más alto alcanzado actualmente. Si una mejora en el nivel de principiante pasa de Sub20 a Sub10, se convierte en Sub10 en lugar de añadir otra medalla Sub20. Una medalla ya banderada se actualiza con su nivel. Niveles distintos y títulos ordinarios frente a NF permanecen como medallas separadas.

Los premios automáticos dependen de resultados válidos actuales y de la información del perfil. Borrar, congelar, rechazar o reasignar una repetición, o cambiar detalles relevantes del perfil o enlaces de cuenta, desencadena una nueva verificación. Otros resultados elegibles podrían mantener el premio o permitir un nivel más bajo. Si ya no se cumplen los requisitos, la medalla puede ser desclasificada o retirada y desaparecer del área de banderas.

Las decisiones del administrador prevalecen sobre las medallas otorgadas o bloqueadas manualmente. Un nivel fijado manualmente no cambia automáticamente con resultados posteriores; si se debe restaurar la evaluación automática, contacta a un administrador. Las medallas globalmente desactivadas también se ocultan del display público.

## Preguntas comunes

### Subí un resultado calificado. ¿Dónde está mi medalla?

Revisa la propiedad, estado de aprobación, modo, nivel y métrica relevante en la pestaña de Repeticiones de tu perfil. El éxito de la subida y la aprobación son procesos separados. Los resultados sin adivinanzas y las repeticiones aún ocultas de torneos no cumplen con los requisitos para títulos de habilidad.

Los premios se actualizan mediante tareas en segundo plano, por lo que las subidas, aprobaciones o cambios de identificador pueden tardar en aparecer. Espera y recarga la página; no subas nuevamente la misma repetición solo para obtener una medalla. Si el problema persiste, informa a un administrador con tu ID de usuario, ID de repetición o enlace y el título esperado.

### Se están otorgando medallas históricas. ¿Qué debo hacer?

La primera visita programa una verificación de la información del perfil existente y de las repeticiones históricas. La página intenta actualizar automáticamente. Si el mensaje permanece, espera y haz clic en **Recargar**. Esto no significa que tus resultados anteriores hayan sido borrados, y no necesitas subir nuevamente las repeticiones antiguas.

### ¿Por qué una medalla ganada no aparece en mis banderas o en el tooltip del nombre?

Asegúrate de haberla seleccionado y de haber hecho clic en **Guardar banderas**. La pestaña de Medallas muestra medallas ganadas; la zona de banderas y los tooltips del nombre muestran solo las que has elegido para mostrar. Otras páginas abiertas podrían mostrar temporalmente resultados antiguos; recargalas después de un breve intervalo.

### ¿Por qué no hay un nivel siguiente?

Los títulos únicos no tienen ruta de mejora. Los títulos jerárquicos dejan de mostrar un nivel siguiente una vez que alcancen el máximo actual. El número en una medalla es su umbral alcanzado, que puede diferir de tu mejor resultado exacto.
