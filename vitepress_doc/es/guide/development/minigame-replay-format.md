---
title: "Formato de datos de repetición de minijuego v1 - Open Minesweeper"
description: "Compresión del tablero, codificación de eventos de ratón, toque y especiales, y reglas de migración de frontend y backend desde el formato de repetición de minijuego v0 al v1"
---

# Formato de datos de repetición de minijuego v1

Estado: implementado. El sitio web y la edición offline guardan las nuevas grabaciones como v1 y pueden leer grabaciones de v0. Las actualizaciones de IndexedDB ocurren automáticamente; la historia del backend ha completado su migración de compresión

Esta especificación define el payload JSON v1 utilizado para reproducción y persistencia, y su contenedor 7z. Los formatos de descarga independientes y las extensiones de archivo aún no están definidos. El texto JSON utiliza UTF-8. El orden de las propiedades y los espacios en blanco no afectan el significado; el orden de los campos de tupla y el orden de los eventos deben conservarse

## 1. Payload y registro externo

El registro externo continúa proporcionando el juego, el modo, la puntuación y el tiempo de finalización. La repetición no los duplica:

| Información | IndexedDB | Backend |
| --- | --- | --- |
| Juego y modo | `game`, `mode` | Determinado por `ranking_key` |
| Duración total, en milisegundos enteros | `scoreMs` | `score` |
| Tiempo de finalización | `playedAt`, en milisegundos de Unix | `achieved_at`, en tiempo del servidor |
| Repetición para todos los juegos | `replay`, un `ArrayBuffer` de 7z | `replay_archive` BinaryField, bytes de 7z |
| Rondas de casillas faltantes | `rounds` en el JSON descomprimido | `rounds` en el JSON descomprimido |
| Versión del formato de repetición | `version` en el JSON descomprimido | `version` en el JSON descomprimido |

Las dimensiones del tablero provienen del modo encerrado. No infieras dimensiones a partir de la cadena comprimida o del array de preguntas. Todas las coordenadas del tablero utilizan índices de celda cero basados en `[row, column]`; los eventos del ratón siguen usando coordenadas en píxeles `x, y`.

Solo se guardan ejecuciones exitosas. Las ejecuciones fallidas o incompletas que se reinician no se suben ni se guardan en el historial local. La reproducción en tiempo real puede usar la misma representación de eventos para ejecuciones fallidas

### Contenedor de almacenamiento

Cada grabación es un archivo independiente, no cifrado, de formato 7z que contiene exactamente un archivo regular llamado `replay.json`, cuyo contenido es el JSON UTF-8 definido aquí. Usa LZMA2; los escritores actuales usan nivel 1 y un diccionario de 1 MiB, sin compresión entre grabaciones. La versión del JSON `version` sigue identificando el formato del payload; el envoltorio 7z no cambia su significado

El frontend utiliza [7z-wasm](https://github.com/use-strict/7z-wasm) y almacena un `ArrayBuffer` crudo en IndexedDB, sin conversión a Base64. El paquete offline incluye el Wasm de compresión y no requiere carga de red. El backend utiliza [py7zr](https://py7zr.readthedocs.io/en/latest/api.html) y almacena los bytes del mismo contenedor en BinaryField, fuera de Redis

La API de envío aún acepta una cadena JSON v1 en el formato. El backend la comprime al crear o mejorar una puntuación. Lee los datos almacenados en este orden: extrae 7z → analiza JSON UTF-8 → identifica `version` → descompone el tablero y los eventos.

### Detección de versión

Lee `version` desde la ubicación especificada anteriormente para identificar el formato de repetición. No adivines la versión desde la forma del tablero o del array de eventos:

| `version` | Interpretación |
| --- | --- |
| Propiedad ausente o entero `0` | v0, el formato anterior: matrices bidimensionales de tablero y objetos de eventos de ratón; el objetivo de casillas faltantes es el único `10` del tablero |
| Entero `1` | El formato v1 definido aquí |
| Cualquier otro entero no negativo | Versión no soportada; informa sobre ella y detén la interpretación sin caer en v0 |

Cuando esté presente, el valor debe ser un entero no negativo. Valores como `null`, cadenas o booleanos son errores de formato, no ausencia de propiedad. Identifica los datos existentes sin `version` como v0, luego valida los campos requeridos de v0. Las nuevas escrituras deben almacenar explícitamente `version: 1`.

### Entrenamiento con clic izquierdo y bandera-apertura simultánea

```ts
interface TrainingRecordingV1 {
    version: 1;
    cellSize: number | null;
    initialBoard: string | [row: number, column: number, mineDirection: number][];
    events: [dt: number, x: number, y: number, action: number][];
    specialEvents: [dt: number, index: number, type: number][];
}
```

| Campo | Convención |
| --- | --- |
| `version` | Entero fijo `1`, que identifica este formato de repetición; lee los datos antiguos sin esta propiedad como v0 |
| `cellSize` | Longitud en píxeles CSS de una celda de referencia, un entero positivo o `null`; en nuevos registros se fija en el evento que inicia el cronómetro; la migración v0 escribe `null`, que los lectores interpretan usando el valor fijo `32` |
| `initialBoard` | Una cadena de minas en Base64 para entrenamiento con clic izquierdo, o un array de preguntas que contenga para cada pregunta su centro y dirección de la mina para entrenamiento con bandera-apertura simultánea; véase la Sección 2; el juego que contiene determina cuál representación se aplica |
| `events` | Eventos ordinarios del ratón desde el inicio hasta el final del cronómetro, en orden de procesamiento; cada tupla contiene exactamente cuatro enteros, según lo definido en la Sección 3 |
| `specialEvents` | Eventos especiales como pérdida de enfoque o cancelación, que contienen un delta de tiempo, un índice de inserción y un tipo; almacena un array vacío cuando no existen; véase la Sección 3.5 |

La versión del formato, la versión de la base de datos IndexedDB y la versión de las reglas en las claves de clasificación se mantienen separadamente. IndexedDB ahora tiene versión `3`, que soporta actualizaciones desde datos v0 en versión de base de datos `1` y datos JSON v1 en versión de base de datos `2` hasta almacenamiento 7z. Las reglas y claves de clasificación permanecen sin cambios. Cambios futuros en los campos de tupla, unidades, codificación o significado de valores existentes de enumeración requieren una nueva versión del formato, en lugar de modificar la interpretación de v1.

### Entrenamiento de multi-touch

El envoltorio `game: 'multi-touch'` o `multi-touch-*` en clasificación selecciona esta estructura. Es independiente de los registros de ratón y no modifica los cuatro-tuplas existentes de v1. El entrenamiento multi-touch no tiene formato v0.

Los juegos exitosos de multi-touch se comprimen en este formato y se guardan en IndexedDB. Las subidas manuales envían el mismo JSON, que el backend comprime en BinaryField. Las repeticiones no se almacenan en Redis.

```ts
interface TouchRecordingV1 {
    version: 1;
    cellSize: number | null;
    initialBoard: string;
    events: [dt: number, dx: number, dy: number, contact: number, action: number][];
}
```

`cellSize` y la cadena Base64 `initialBoard` tienen el mismo significado que en el entrenamiento con clic izquierdo. Todos los contactos comparten un flujo de eventos ordenado. Los tiempos y coordenadas en píxeles son deltas respecto al **elemento anterior del array**, incluso cuando pertenecen a otro contacto; el primer elemento es relativo a cero y tiene coordenadas absolutas. Mantén los deltas firmados sin ZigZag. `contact` no está codificado como delta: asigna un nuevo ID consecutivo comenzando en `0` para cada toque inicial, incluyendo cuando el navegador reutiliza un `pointerId`.

| `action` | Significado |
| --- | --- |
| `0` | Abajo: crea el contacto y intenta abrir su celda |
| `1` | Mover: actualiza solo la posición de ese contacto |
| `2` | Arriba: elimina el contacto sin abrir una celda |
| `3` | Cancelar: elimina el contacto sin abrir una celda |

Mover, arriba y cancelar deben referirse a un contacto activo. La cancelación global, como pérdida de enfoque o ocultación de la página, escribe un evento `3` por cada contacto activo, por lo que no se necesita un array de `specialEvents`. El cronómetro comienza en el primer evento de toque inicial. Preserva el orden del array para tiempos iguales. El registro se detiene al finalizar, por lo que los contactos pueden seguir activos al final. Reconstructe independientemente la trayectoria y el marcador de posición actual de cada contacto, aplicando solo los eventos de toque inicial al tablero del juego. No renderices previsualizaciones de celdas presionadas.

Ejemplo: dos dedos bajan, el primero se mueve, luego el segundo se levanta:

```json
[[0,16,16,0,0],[10,32,0,1,0],[5,-30,2,0,1],[5,30,-2,1,2]]
```

Agregar este juego no cambia el esquema ni la versión de IndexedDB. Los registros de ratón existentes y los que faltan de celdas no necesitan migración.

El modo experto siempre utiliza un tablero de 16×30 y las coordenadas del evento. En la visualización vertical, el tablero y las trazas se intercambian y las coordenadas de entrada se invierten. La orientación es una configuración local del usuario, excluida de las repeticiones, y no afecta la clave de clasificación. Cambiar la orientación conserva el contenido actual del juego y de la repetición.

### Entrenamiento de casilla faltante

El entrenamiento de casillas ausentes no registra eventos del ratón. Cada ronda almacena una cadena de minas, las coordenadas objetivo y el tiempo:

```ts
interface MissingCellRecordingV1 {
    version: 1;
    rounds: { board: string; target: [row: number, column: number]; timeMs: number }[];
}
```

`rounds` sigue el orden de juego y contiene exactamente 10 entradas para una ejecución exitosa. `board` codifica solo minas. `target` identifica por separado la única casilla segura no abierta y no debe apuntar a una mina; los números visibles se recalculan a partir de las minas. `timeMs` es la duración del turno en milisegundos no negativos, y la suma de todas las duraciones de turno equivale a la puntuación total contenida. No existe un rastro dependiente del tamaño de la casilla, por lo que las grabaciones de casillas faltantes no almacenan `cellSize`. Comprime todo el objeto `{version, rounds}` en el campo `replay` de la entrada de IndexedDB.

### Entrenamiento de reacción

Seleccionado por el contenedor `game: 'reaction'`, con teclas de modo `reaction-{b|i|e}-{25|50}-v1`. Principiante/Intermedio/Avanzado usan líneas horizontales de 5/10/20 casillas y objetivos de 10/20/40 reacciones. Juegos exitosos guardan historial local; el sitio soporta subidas manuales y reproducción de repeticiones públicas. La API existente comprime el mismo JSON en almacenamiento BinaryField. Los metadatos de clasificación usan `density` para la probabilidad; los modos locales conservan `probability`.

```ts
interface ReactionRecordingV1 {
    version: 1;
    draws: (0 | 1)[];
    sides: (0 | 1)[];
    clicks: [downDelta: number, upDelta: number][];
}
```

- `draws` almacena los resultados aleatorios reales en orden: `1` para una mina, `0` para una celda segura. La celda segura después de una mina saltada y la mina final después de una celda segura como penúltima son forzadas y no consumen entrada. Mantén el último resultado si el controlador toma muestras antes de comprobar el objetivo de reacción.
- `sides` tiene una entrada por línea iniciada: `0` para el extremo izquierdo, `1` para el derecho. Las reglas y los resultados aleatorios determinan las posiciones siguientes. La línea inicialmente vacía y la fila fija de minas no necesitan carga de tablero.
- `clicks` almacena solo pares de presiones y liberaciones progresivas, incluyendo el primer clic de cada línea. El primer par es `[0, first hold duration]`; los pares siguientes son `[previous saved release to current press, current press to release]`, en milisegundos no negativos. Con `Q(t) = round(t - first valid release)`, la primera presión es `-Q(first press)` y los valores siguientes son las diferencias entre los tiempos correspondientes de `Q`. No redondees los intervalos independientemente.

No hay coordenadas, eventos del ratón, fuentes de entrada, contactos, `cellSize` ni rutas. Los clics en casillas abiertas o en la fila de banderas, las cancelaciones y otras entradas ineficaces se omiten; su tiempo transcurrido permanece en el delta del siguiente clic consecutivo. El timing también continúa entre líneas. La puntuación es `max(1, last release - first release)`; resta el primer mantenimiento al timeline acumulado para obtener el tiempo de juego.

Reconstruir tableros y instantáneas injectando `draws` y siguiendo `sides` y los clics sucesivos, sin volver a tomar muestras. La reproducción debe alcanzar exactamente el objetivo y consumir todos los dibujos y lados iniciales. Las posiciones de presión se deducen a partir de las reglas para las vistas previas de casillas presionadas y no representan los caminos reales del ratón. Las muestras de análisis utilizan clics sucesivos dentro de cada línea; se excluye el primer clic de cada línea. Usar el mismo contenedor 7z sin modificar esquema ni versión de IndexedDB. El entrenamiento de reacción no tiene formato v0.

Por ejemplo, los tiempos de presión y liberación avanzados de `100/130`, `200/220` y `500/530ms`, con un clic omitido e ineficaz en `300/320ms`, se codifican como:

```json
[[0, 30], [70, 20], [280, 30]]
```

Los tiempos acumulados de liberación son `30, 120, 430ms`, lo que da un puntaje de `430 - 30 = 400ms`. Una presión cancelada no puede emparejarse con una operación posterior en liberación. Omitir operaciones ineficaces nunca cambia la referencia de delta desde la liberación anterior guardada.

## 2. Codificación del tablero

### 2.1 Minas en Base64 para clic izquierdo y celda ausente

Cada casilla ocupa un bit: `1` para una mina y `0` para una casilla sin mina. Usa el alfabeto estándar de Base64 de [RFC 4648 Sección 4](https://www.rfc-editor.org/rfc/rfc4648.html#section-4), indexado desde `0..63`:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
```

Partiendo de la esquina superior izquierda, recorre las filas de arriba a abajo y las casillas de izquierda a derecha, pasando directamente a la siguiente fila. Cada grupo de 6 casillas forma un carácter, con las casillas anteriores ocupando bits más significativos:

```text
i = row * columns + column
characterIndex = floor(i / 6)
bitPosition = 5 - i % 6

value[j] = sum(mine[6 * j + k] * 2 ** (5 - k), k = 0..5)
board[j] = alphabet[value[j]]
```

Si el grupo final contiene menos de 6 casillas, rellena sus bits bajos con `0`; estos bits de relleno no representan casillas. La longitud de la cadena es exactamente `ceil(rows * columns / 6)`. No almacenes caracteres de relleno `=`, espacios ni saltos de línea. Los bits de relleno finales deben ser `0`.

| Nivel | Filas × columnas | Cantidad de casillas | Longitud de la cadena de minas |
| --- | --- | --- | --- |
| Para principiantes | `8 × 8` | `64` | `11` |
| Intermedio | `16 × 16` | `256` | `43` |
| Experto | `16 × 30` | `480` | `80` |

Por ejemplo, los bits de mina `1, 0, 1, 0, 0, 1` forman el binario `101001`, cuyo valor es `41`, correspondiente al carácter `p`. Seis casillas consecutivas sin mina producen `A`; seis casillas consecutivas con mina producen `/`.

Las implementaciones pueden empaquetar los bits ordenados por filas en bytes, con el bit de mayor significado primero, y reutilizar un codec de Base64 existente. Todos los tamaños actuales del tablero contienen un múltiplo de 8 casillas, por lo que eliminar los caracteres `=` del encoding produce esta representación. Restaura temporalmente `=` cuando un decodificador requiera relleno; el valor persistente permanece sin relleno.

### 2.2 Arreglo de preguntas con bandera y apertura simultánea

`initialBoard` es un arreglo de preguntas, con exactamente tres enteros por elemento:

```text
[row, column, mineDirection]
```

`row, column` son los índices de casilla del número central `1`, no coordenadas en píxeles. Añade el desplazamiento de dirección al centro para localizar la mina. Los códigos de dirección siguen el recorrido existente de vecinos por filas, omitiendo el centro:

| `mineDirection` | Dirección | Desplazamiento en fila | Desplazamiento en columna |
| --- | --- | --- | --- |
| `0` | Superior-izquierda | `-1` | `-1` |
| `1` | Arriba | `-1` | `0` |
| `2` | Superior-derecha | `-1` | `1` |
| `3` | Izquierda | `0` | `-1` |
| `4` | Derecha | `0` | `1` |
| `5` | Inferior-izquierda | `1` | `-1` |
| `6` | Abajo | `1` | `0` |
| `7` | Inferior-derecha | `1` | `1` |

Por ejemplo, `[3, 5, 2]` coloca el centro de la pregunta en fila `3`, columna `5`, con la mina en `(2, 6)`. Cada pregunta tiene exactamente una mina y su número siempre es `1`, por lo que ni el número ni las otras casillas seguras se almacenan por separado. En nivel principiante hay exactamente 4 elementos y en nivel intermedio hay 15. Cada región 3×3 completa de una pregunta debe estar dentro del tablero y no debe superponerse con otra pregunta.

Los autores ordenan las preguntas por el centro's `row`, luego por el `column`, en orden ascendente para dar a cada diseño una representación consistente. El orden del array no indica el orden de resolución del jugador.

### 2.3 Coordenadas del objetivo de casilla ausente

Cada ronda de `board` utiliza el codificado de minas del Sección 2.1, con un separado `target: [row, column]`. El objetivo debe estar dentro del tablero y su bit de mina debe ser `0`. El orden y duración de la ronda pertenecen únicamente al array encerrante `rounds`, no al string de minas.

### 2.4 Reconstrucción de los tableros en tiempo real

La capa de almacenamiento utiliza las representaciones compactas descritas anteriormente. El decodificación restaura las matrices bidimensionales del tablero principal existente del proyecto:

| Valor | Clic izquierdo en `initialBoard` | Bandera y apertura simultánea en `initialBoard` | Ronda de casilla ausente en `board` |
| --- | --- | --- | --- |
| `0` | No utilizada | Área en blanco fuera de las preguntas | Casilla en blanco abierta |
| `1..8` | No utilizada | Solo `1`, el centro de la pregunta | Casilla adyacente con conteo de minas abierta |
| `10` | Casilla segura aún no clickeada | Casilla vecina segura aún no abierta | El único objetivo seguro no abierto |
| `16` | Minas visibles | Minas visibles | Mina oculta, convertida a `10` para mostrar durante la revisión |

Para el entrenamiento con clic izquierdo, restaura `16` y `10` a partir de los bits de mina. Para el entrenamiento con bandera y apertura simultánea, llena el tablero con `0`, luego restaura cada centro como `1`, su mina como `16` y sus vecinos restantes como `10`. Para el entrenamiento con casillas faltantes, calcula el número de minas adyacentes en las casillas seguras, luego asigna a las minas el valor `16` y al objetivo el valor `10`. Al mostrar una ronda con casilla faltante, convierte los valores de mina de `16` a `10` cubiertos y resalta las coordenadas del objetivo almacenadas por separado.

El tablero inicial conserva todas las posiciones de las minas, no un semilla aleatoria ni los conteos de minas adyacentes. Las banderas, banderas incorrectas, minas explotadas y tableros tras operaciones se reconstruyen según las reglas del juego. Los instantáneos por operación, los conteos restantes y los resultados de análisis no se almacenan.

## 3. Tuplas de eventos del ratón

```text
[dt, x, y, action]
```

| Índice | Campo | Primero evento | Eventos posteriores |
| --- | --- | --- | --- |
| `0` | `dt` | Entero en milisegundos desde el inicio del cronómetro hasta este evento, normalmente `0` para nuevas grabaciones | Entero no negativo en milisegundos desde el evento anterior ordinario |
| `1` | `x` | Coordenada horizontal absoluta respecto al rincón superior izquierdo del tablero, en píxeles enteros; puede ser negativa | Entero con signo que representa el desplazamiento horizontal desde el evento anterior ordinario |
| `2` | `y` | Coordenada vertical absoluta respecto al rincón superior izquierdo del tablero, en píxeles enteros; puede ser negativa | Entero con signo que representa el desplazamiento vertical desde el evento anterior ordinario |
| `3` | `action` | Código del evento de entrada | Igual |

Los desplazamientos siempre se refieren al elemento anterior en el array de eventos ordinarios, incluyendo movimientos y eventos de botón ineficaces, en lugar de la última operación efectiva del juego. Los eventos especiales se almacenan por separado y no participan en los desplazamientos de tiempo o coordenadas ordinarios. `dt = 0` está permitido. Los eventos dentro del mismo milisegundo mantienen el orden del array y no deben deduplicarse ni reordenarse por tiempo.

### 3.1 Tiempo

Usa el reloj monótono del juego en milisegundos; el tiempo Unix no participa. Redondea los tiempos acumulados antes de calcular los desplazamientos:

```text
t[i] = max(0, round(now[i] - startedAt))
dt[0] = t[0]
dt[i] = t[i] - t[i - 1]       // i > 0
```

Para valores no negativos, `round` significa `floor(value + 0.5)`. Ni el frontend ni el backend pueden redondear cada intervalo por separado. Los valores antiguos de `timeMs` ya están redondeados, por lo que la migración los resta directamente.

- El entrenamiento con clic izquierdo comienza cuando la primera liberación del botón izquierdo desencadena una operación. Esa liberación se registra en `t = 0`; su presión anterior y movimientos de observación se omiten, por lo que el primer clic no tiene una presión pareja dentro de la grabación cronometrada.
- El entrenamiento con bandera y apertura simultánea comienza con la primera colocación efectiva de bandera. Esa presión del botón derecho se registra en `t = 0`.
- Después de que comience el cronómetro, los movimientos, presiones y liberaciones se almacenan en `events`; las cancelaciones y los reinicios se almacenan en `specialEvents`. Se incluyen operaciones ineficaces del juego. El evento final debe incluirse, sin añadir eventos después de que termine la ejecución.
- Se permiten arrays vacíos y significan que no hay entrada para reproducir. Normalmente, las grabaciones nuevas completadas deben contener los eventos necesarios para iniciar y finalizar. La migración no debe eliminar un registro histórico simplemente porque su array de eventos esté vacío.

Cada array acumula independientemente sus propios valores de `dt` para recuperar los tiempos relativos al mismo origen de cronometraje. La duración total proviene del puntaje que lo contiene. Conserva el mínimo puntaje exitoso existente de `1ms`; no reemplace forzosamente la duración total con la marca del último evento.

### 3.2 Coordenadas en píxeles y tamaño de casilla

El rincón superior izquierdo del contenido del tablero es `(0, 0)`. `x` aumenta hacia la derecha y `y` hacia abajo. Las coordenadas son píxeles lógicos de CSS en el tamaño de la celda de referencia. Excluyen contadores, bordes y desplazamientos de página, y no se multiplican por `devicePixelRatio`.

`cellSize: null` significa que el tamaño original del registro es desconocido. Utiliza el valor de referencia fijo `32`, independiente del tamaño actual de la casilla en las configuraciones. La propiedad sigue siendo obligatoria; la ausencia de la propiedad u otro valor inválido no se trata como `null`. Todas las fórmulas siguientes utilizan el valor de referencia efectivo:

```text
referenceCellSize = cellSize === null ? 32 : cellSize
```

Sea el tamaño de la celda mostrado en el evento `displayCellSize`, y la posición lógica del puntero sobre ese tablero mostrado `displayX, displayY`:

```text
x[i] = floor(displayX / displayCellSize * referenceCellSize)
y[i] = floor(displayY / displayCellSize * referenceCellSize)
```

Si se aplica escalado CSS, primero mapa el rectángulo real mostrado del tablero a píxeles lógicos. Utiliza el mismo `referenceCellSize` durante toda la ejecución. Cambiar el tamaño de la casilla durante el juego no reinicia la ejecución ni modifica los metadatos; los eventos posteriores se mapean al sistema de referencia original. Usa coordenadas enteras antes de aplicar deltas, evitando que un clic cerca del borde derecho de una casilla se convierta en su vecina.

No limites las coordenadas al tablero: se mantienen coordenadas negativas y posiciones fuera de su anchura o altura. La repetición determina los impactos según si las coordenadas están dentro del tablero y no conserva información de ocultación del navegador ni de corte por desplazamiento.

Durante la reproducción, restaura las coordenadas en píxeles, luego conviértelas a unidades de celda esperadas por el renderizador existente:

```text
column = x / referenceCellSize
row = y / referenceCellSize
```

Las operaciones del juego utilizan `floor(column)` y `floor(row)` como índices de casilla. La representación puede redimensionarse al tamaño actual de la casilla mostrada; la reproducción no necesita restaurar el tamaño de visualización del registro. La cuantización de píxeles descarta fracciones menores a un píxel de referencia sin modificar la casilla que contiene.

### 3.3 Deltas de coordenadas

Escribe directamente el `x, y` del primer evento. Los eventos siguientes almacenan el `dx, dy` en relación con el evento ordinario anterior como enteros JSON firmados, sin conversión ZigZag.

```text
storedX[0] = x[0]
storedY[0] = y[0]

storedX[i] = x[i] - x[i - 1]       // i > 0
storedY[i] = y[i] - y[i - 1]

x[0] = storedX[0]
y[0] = storedY[0]
x[i] = x[i - 1] + storedX[i]       // i > 0
y[i] = y[i - 1] + storedY[i]
```

Una coordenada estacionaria tiene delta `0`; moverse a la izquierda o hacia arriba genera un delta negativo en el eje correspondiente. Los valores almacenados, las coordenadas reconstruidas, los timestamps acumulados y los intermediarios de cálculo deben mantenerse dentro del rango de enteros seguros de JavaScript.

### 3.4 Códigos de eventos de entrada

| `action` | Evento de entrada | Nombre existente |
| --- | --- | --- |
| `0` | Movimiento del ratón | `mv` |
| `1` | Presión del botón izquierdo | `lc` |
| `2` | Libertad del botón izquierdo | `lr` |
| `3` | Presión del botón derecho | `rc` |
| `4` | Libertad del botón derecho | `rr` |

El adaptador de entrada continúa convirtiendo la entrada táctil en eventos de botón izquierdo; no se añade código específico para toques. La cancelación y los reinicios usan el array especial, en lugar de códigos de eventos ordinarios.

### 3.5 Eventos especiales y índices de inserción

Cada elemento `specialEvents` contiene exactamente tres enteros no negativos:

```text
[dt, index, type]
```

| Campo | Significado |
| --- | --- |
| `dt` | Entero en milisegundos desde el evento especial anterior; para el primer elemento, desde el inicio del cronómetro; no es relativo a eventos ordinarios |
| `index` | Índice de inserción cero en el array de eventos ordinario, dentro de `0..events.length` |
| `type` | Tipo especial de evento; v1 define solo `0`, lo que significa cancelar y restablecer el estado de entrada |

`index = i` significa ejecutar antes de `events[i]`. `index = 0` se ejecuta antes del primer evento ordinario; `index = events.length` se ejecuta después del último. Los índices siempre se refieren al array original de `events` y no aumentan cuando se insertan otros eventos especiales. Varios eventos especiales pueden compartir un mismo índice de inserción; ejecútalos en orden `specialEvents` sin deduplicación.

Registra los eventos especiales en orden de ocurrencia, con valores de `index` no decrecientes. Sea el timestamp acumulado de un evento especial `s`, su índice de inserción `i` y los timestamps de eventos ordinarios `t`. Si existe un evento ordinario anterior, se requiere `t[i - 1] <= s`; si existe un evento ordinario posterior, se requiere `s <= t[i]`. Dentro de un mismo milisegundo, el orden de inserción y el orden del array determinan el orden de ejecución. No se fusionen los arrays únicamente por timestamp.

La pérdida de enfoque, una página oculta, la cancelación de toque y el estado inconsistente del botón usan el tipo `0`. Al ejecutarlo, se reinicia el autómata, se eliminan las previsiones de presión y los tiempos de presión no emparejados, y no se dispara ningún clic izquierdo, colocación de bandera o operación de apertura simultánea. Los eventos especiales no almacenan coordenadas: se mantiene la posición del evento ordinario anterior sin modificar la referencia de delta para eventos ordinarios. No existe una posición de puntero antes del primer evento ordinario. El motivo específico de reinicio no se almacena por separado.

### 3.6 Estado derivado y eventos iniciales

El estado del botón, la intención de operación y las previsiones de presión no se persisten. Se reconstruyen a partir del existente `ClassicMouseAutomaton`, las coordenadas de los eventos y el tablero actual. Durante la reproducción, se procesan los eventos ordinarios a través del autómata primero, y luego se envían las intenciones resultantes a las reglas del juego si las coordenadas están dentro del tablero. Las operaciones ineficaces permanecen en la secuencia de eventos.

- El primer evento ordinario de clic izquierdo de entrenamiento es el `lr` que inicia el conteo. Se inicializa el autómata manteniendo el botón izquierdo presionado antes de procesarlo. Esto solo proporciona el estado inicial conocido; no genera un `lc` cronometrado, por lo que el primer clic permanece excluido de las estadísticas de duración de presión.
- El entrenamiento de colocación de bandera y apertura simultánea comienza desde el estado inicial del autómata. Su primer evento ordinario es el `rc` que inicia el conteo, generando una operación de bandera según las reglas normales.
- Después de un reinicio, se procesan los eventos ordinarios siguientes desde el estado inicial. Los eventos fuera del tablero actualizan aún el estado del botón, pero no generan operaciones en el tablero ni previsiones de presión.

Las previsiones siguen las reglas compartidas existentes: una prevención de botón único excluye solo celdas marcadas; una prevención de apertura simultánea cubre el centro y las 3×3 celdas circundantes, manteniendo las celdas marcadas elevadas. Se utiliza el estado completo del autómata para distinguir un botón sostenido ordinario de un botón aún sostenido tras la activación de una apertura simultánea.

## 4. Ejemplos de codificación compartida entre interfaz y backend

Estos son fragmentos de eventos, no ejecuciones completas exitosas. `cellSize = 32`; las coordenadas se decodifican en píxeles de referencia.

### Clic izquierdo, movimiento y cancelación

| Índice | Tiempo acumulado | Coordenadas `(x, y)` | Entrada | Estado / intención / prevención | Tupla almacenada |
| --- | --- | --- | --- | --- | --- |
| `0` | `0` | `(16, 16)` | `lr` | `uu` / `left` / none | `[0, 16, 16, 2]` |
| `1` | `10` | `(48, 16)` | `lc` | `du` / none / single cell | `[10, 32, 0, 1]` |
| `2` | `25` | `(45, 18)` | `mv` | `du` / none / single cell | `[15, -3, 2, 0]` |
| `3` | `25` | `(45, 18)` | `lr` | `uu` / `left` / none | `[0, 0, 0, 2]` |

Si la cancelación ocurre en `30ms`, almacénala por separado:

```json
{"specialEvents": [[30, 4, 0]]}
```

Aquí `4` es la posición de inserción al final del array de eventos ordinarios. Si en cambio la cancelación ocurre en `25ms` después del movimiento pero antes de la liberación, almacénela así:

```json
{"specialEvents": [[25, 3, 0]]}
```

Procesa el evento ordinario `2`, luego reinicia, luego procesa el evento ordinario `3`. El `lr` después del reinicio no genera una operación de clic izquierdo. Los deltas de tiempo y coordenadas ordinarios permanecen sin cambios en cualquiera de los casos. La columna de estado / intención / prevención solo ilustra resultados derivados y no forma parte de los campos almacenados.

### Colocación de bandera seguida de una apertura simultánea

| Índice | Tiempo acumulado | Coordenadas `(x, y)` | Entrada | Estado / intención / prevención | Tupla almacenada |
| --- | --- | --- | --- | --- | --- |
| `0` | `0` | `(16, 16)` | `rc` | `ud` / `right` / none | `[0, 16, 16, 3]` |
| `1` | `10` | `(16, 16)` | `rr` | `uu` / none / none | `[10, 0, 0, 4]` |
| `2` | `30` | `(48, 48)` | `lc` | `du` / none / single cell | `[20, 32, 32, 1]` |
| `3` | `40` | `(48, 48)` | `rc` | `dd` / none / 3×3 | `[10, 0, 0, 3]` |
| `4` | `50` | `(48, 48)` | `lr` | `ud` / `chord` / none | `[10, 0, 0, 2]` |

Si el acorde finaliza correctamente una pregunta, sus tres tiempos estadísticos son `0ms`, `30ms` y `50ms`. El segmento inferior del gráfico apilado es de `30ms` y el superior de `20ms`. Los acordes fallidos o ineficaces permanecen en la secuencia de eventos pero no generan estadísticas de acorde exitoso.

## 5. Decodificación y reproducción

1. Determina el juego y el modo a partir del registro contenedor. Identifica el formato mediante `version`; lee una propiedad ausente como v0 y conviértela usando la Sección 6 antes de decodificarla como v1.
2. Para las repeticiones de ratón, acumula los deltas de tiempo de cada array de forma independiente, restaura las coordenadas ordinarias de los eventos, luego los fusiona usando índices especiales de inserción. Para las repeticiones de múltiples toques, acumula el flujo único de eventos y rastrea cada contacto. Utiliza los índices de secuencia decodificados para instantáneas en tiempo de ejecución y posiciones dentro de un milisegundo; no modifiques los índices de inserción persistidos.
3. Decodifica `initialBoard` en una matriz bidimensional usando la Sección 2, luego crea el controlador del juego. Para las repeticiones de ratón, proporciona el estado inicial de la Sección 3.6, procesa entradas ordinarias y reinicios especiales en orden, deriva intenciones de operación y aplica las reglas del juego. Las repeticiones de múltiples toques intentan abrir celdas únicamente en eventos de presión. Reutiliza el automata existente y las reglas de clic izquierdo / bandera y acorde sin introducir `ms-toollib`. Para celdas de entrenamiento ausentes, decodifica separadamente las minas de cada ronda y restaura el tablero usando sus coordenadas objetivo.
4. Reconstruye todos los instantáneos del tablero, los conteos restantes y los tiempos exitosos de los acordes una sola vez. Mantiene este dato derivado únicamente en memoria.
5. Calcula la velocidad del ratón, la velocidad de clic y las duraciones de presión a partir de la traza decodificada y los tiempos. Utiliza la puntuación del contenedor como punto final de reproducción.

Después de identificar la versión, los errores de formato incluyen campos obligatorios faltantes para esa versión, valores inválidos de enum, deltas de tiempo negativos, valores no enteros en campos enteros y sobrecarga de enteros seguros. También incluyen índices de inserción especiales fuera de rango o decrecientes, orden de eventos o marcas de tiempo contradictorios, longitud, caracteres o bits de relleno inválidos en la cadena de minas, coordenadas fuera de rango, un objetivo sobre una mina, o un diseño de bandera y apertura simultánea que no pueda reconstruirse. Los lectores informan el error y detienen el análisis de ese registro en lugar de asignar valores faltantes a cero. La ausencia de `version` significa v0 según la Sección 1, mientras que `cellSize: null` utiliza el valor de referencia `32` según la Sección 3.2. No interpretes un desconocido `version` como el formato antiguo. Estas comprobaciones apoyan la lectura de datos y la migración; no añaden autenticidad de puntuación, legalidad del juego ni validación anti-trampa.

## 6. Migración de v0 a v1

### 6.1 Reglas compartidas de conversión

Los registros de clic izquierdo y bandera-acorde de v0 contienen `{initialBoard, events}`, con un tablero bidimensional y objetos de evento que incluyen `timeMs`, `row`, `column`, `action`, `state`, `pressed`, `trigger` y `cancelled`. Los registros de celdas ausentes de v0 contienen `{rounds}`, con cada ronda representada como `{board: number[][], timeMs}`. Una ausencia de `version` o un valor entero explícito `0` se valida y convierte como v0. Los arrays vacíos de eventos de ratón también deben convertirse.

Convierte los tableros usando el juego y el modo del contenedor:

- Clic izquierdo: codifica cada `16` en el antiguo `initialBoard` como bit de mina `1` y cada celda segura como `0`, produciendo una cadena en Base64.
- Bandera y acorde: encuentra cada número `1` en el antiguo `initialBoard`, extrae su centro y el único `16` entre sus ocho vecinos, y convierte el desplazamiento de mina a un código de dirección. Ordena por coordenadas del centro para formar el array de pregunta.
- Casilla faltante: para cada antiguo `board`, codifica `16` como bit de mina `1` y todas las demás casillas como `0`. Extrae el único `10` como `target` y conserva su `timeMs`. Los números ya no se almacenan; al decodificar, se recalculan a partir de las minas.

Las coordenadas antiguas del ratón usan unidades de casilla y no incluyen el tamaño de la casilla en la grabación, por lo que su tamaño original en píxeles no puede recuperarse. Los registros de clic izquierdo y bandera con apertura simultánea migrados almacenan `cellSize: null` y usan el valor predeterminado de referencia `32` para convertir las coordenadas antiguas de casilla a píxeles. Separa los eventos ordinarios y de cancelación en su orden original, luego calcula los deltas de forma independiente.

```text
normal = old.events.filter(event => !event.cancelled)
x[i] = floor(normal[i].column * 32)
y[i] = floor(normal[i].row * 32)
dt[0] = normal[0].timeMs
dt[i] = normal[i].timeMs - normal[i - 1].timeMs
```

Almacena los eventos ordinarios con deltas de coordenadas firmadas y códigos de `action` del Sección 3. Convierte las entradas antiguas con `cancelled: true` en eventos especiales del tipo `0`. Su índice de inserción es el número de eventos ordinarios conservados antes de alcanzarlos en la secuencia antigua. El `dt` de un evento especial es relativo solo al evento especial anterior; el primero utiliza el `timeMs` original. No calcules los deltas de todos los eventos antiguos y luego elimines los eventos de cancelación, ya que eso pierde los intervalos transcurridos.

Los valores antiguos de `state`, `pressed` y `trigger` ya no se almacenan; se reconstruyen a partir del autómata y las coordenadas al leerlos. No se mantiene información separada sobre el impacto en el DOM. El contenido del tablero y el orden combinado de entradas permanecen iguales; solo cambia su representación.

`cellSize: null` conserva el hecho de que el tamaño original es desconocido. El valor de 32 píxeles es solo una referencia compartida para el decodificación, no una afirmación de que la grabación se hizo a 32 píxeles. La migración conserva las posiciones de las casillas mientras descarta las fracciones de casilla menores a `1/32` de una casilla; la reproducción puede escalar aún así a cualquier tamaño de pantalla.

Agrega `version: 1` solo después de que se haya convertido completamente el tablero y los eventos, o todos los ciclos de casillas faltantes. No escribas registros parcialmente convertidos. Las migraciones repetidas dejan sin cambios los registros válidos de v1. Conserva y reporta versiones desconocidas y datos corruptos.

### 6.2 IndexedDB del frontend

Reutiliza la biblioteca existente `idb` y actualiza `saolei-minigame` a la versión `3`, soportando v0 en la versión de la base de datos `1` y v1 en JSON en la versión `2`. Inicializa el compresor antes de abrir la transacción de actualización. Recorre `results` dentro de la transacción, lee y convierte el payload de cada juego, y escribe el `ArrayBuffer` 7z en el campo común `replay`. Mueve los niveles superiores `rounds` y `version` de las entradas antiguas de casillas faltantes al payload comprimido. Conserva `id`, `playedAt`, `scoreMs`, `game`, `mode`, y ambos índices de `playedAt` y `scoreMs`.

Las instalaciones recientes crean esquema nuevo directamente. Si no se puede convertir un replay, registra una advertencia, comprime el JSON original completo en 7z, preserva la entrada y todos los campos originales del payload, y continúa migrando otros registros. No añadas `version: 1`; las lecturas posteriores siguen aplicando la validación normal y reportan errores de análisis. Haz clic izquierdo y marca con bandera y apertura simultánea conserva el objeto original `replay`; la casilla ausente conserva el original `rounds` y cualquier `version` existente. Si falla la compresión o una operación de base de datos, aborta la transacción y conserva los datos antiguos en lugar de eliminar la base de datos o borrar el historial. Las páginas antiguas continúan cerrando sus conexiones al cambiar de versión para evitar bloquear la actualización. Usa el mecanismo [upgradeneeded de IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IDBOpenDBRequest/upgradeneeded_event).

Cuando es necesario convertir registros antiguos, el sitio web y la edición offline muestran «Optimizando el formato de repetición. Por favor, no cierre esta página.» con el progreso completado / total. El cuadro se cierra después de que se comita la transacción de actualización o se revierta en caso de error. Permite que el navegador dibuje el aviso antes de la compresión, manteniendo las peticiones a la base de datos activas mientras se espera, para que la transacción de actualización no termine prematuramente. Las bases de datos vacías o ya actualizadas no muestran el aviso.

### 6.3 Almacenamiento del backend

La historia del backend ha finalizado la conversión a la versión 1 y al formato de compresión 7z. Las repeticiones se almacenan únicamente en el campo `replay_archive` de tipo BinaryField. El antiguo campo `replay` de tipo JSONField, el comando de migración de una sola vez y su código de conversión han sido eliminados. Los archivos de migración permanecen ignorados por Git; el script de despliegue genera y aplica la migración de esquema que elimina el antiguo campo, preservando las repeticiones binarias, los jugadores, las clasificaciones, las puntuaciones, los tiempos de logro y las claves primarias. Para despliegue manual, ejecuta estos comandos desde `back_end/saolei`:

```bash
python manage.py makemigrations
python manage.py migrate
```

La API de envío aún acepta una cadena de objeto JSON y la comprime al crear o mejorar una puntuación. Las repeticiones no se almacenan en Redis; la migración de esquema no requiere reconstruir los cachés de clasificación. Los datos antiguos del frontend IndexedDB continúan actualizándose según lo descrito en la Sección 6.2, manteniendo la compatibilidad de lectura v0.
