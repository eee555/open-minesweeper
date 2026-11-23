---
title: "Expresiones de repetición - Open Minesweeper"
description: "Campos, operadores, funciones, diferencias y sumas de muestras para el reproductor nativo, los contadores de análisis y los eventos personalizados."
---

# Expresiones de repetición

Esta referencia abarca el reproductor nativo y los contadores y eventos personalizados en la página de análisis de repeticiones. No se aplica a reproductores de terceros. Los tres usan la sintaxis `expr-eval`, pero sus campos y requisitos de resultado varían.

## Tres contextos

| Funcionalidad | Reproductor de repeticiones | Contador de análisis | Evento personalizado de análisis |
| --- | --- | --- | --- |
| Ubicación | Contador personalizado en el diálogo del reproductor nativo | Contador numérico en la página de análisis; las pistas de datos utilizan sus resultados | Filas de eventos personalizados en la página de análisis |
| Entrada | Propiedades de la repetición en la posición actual de reproducción | Instantáneas de eventos nativos y datos de repetición estáticos | Los mismos campos que los contadores de análisis |
| Resultado final | Convertido a texto; se pueden concatenar números y cadenas | Debe ser un número único; se permiten `NaN` y el infinito positivo/negativo | Debe ser un valor booleano, número o cadena |
| Evaluación | Cuando se actualiza la posición de reproducción | En muestras seleccionadas por el modo de muestreo de cada fila | Muestreo continuo: el último evento nativo en cada milisegundo |
| Entre muestras | No utiliza interpolación de muestras del analizador | Interpolación lineal en el tiempo; fuera del rango de muestras, mantiene el punto final más cercano | Utiliza los estados de ocurrencia muestreados, no los valores de verdad interpolados |
| Formato de visualización | Uso de `toFixed`, `roundTo` o concatenación de cadenas dentro de la expresión | Entrada separada de formato `d3-format`, predeterminado `.3f` | Colores y estilos del marcador y la línea; sin formato numérico |
| Errores | Muestra el texto de error | Muestra el error en la celda de valor | Errores de análisis o tipos de resultado inválidos significan que el evento no ocurre |
| Función de diferencia `d` | No se admite | Se admite; los eventos previos siguen el modo de muestreo de la fila | Se admite; los eventos previos siguen el muestreo continuo |
| Suma `s` | No se admite | Se admite; utiliza los índices del arreglo de muestras de la fila | Se admite; utiliza los índices del muestreo continuo |

Los eventos personalizados usan la verdad nativa de JavaScript: `true`, números distintos de cero y cadenas no vacías indican ocurrencia; `false`, `0`, `-0`, `NaN` y cadenas vacías indican ausencia de ocurrencia. El infinito positivo o negativo indica ocurrencia. Las cadenas `"false"`, `"0"` y con solo espacios también indican ocurrencia. Otros tipos, incluyendo arrays y funciones, indican ausencia de ocurrencia.

El muestreo continuo incluye todos los tipos nativos de eventos y toma muestras cada milisegundo. Utiliza el último evento de ese milisegundo, o todos los campos del evento anterior más reciente cuando no hay evento, incluyendo `time`. La marca temporal de la muestra avanza, pero `time` mantiene el tiempo original del evento de origen. Los modos de botón de contador o de cambio de tablero filtran primero los eventos elegibles, luego conservan el último evento elegible en cada milisegundo sin rellenar los espacios vacíos. Las configuraciones de muestreo de fila de contador no afectan a los eventos personalizados.

La línea de tiempo y el tablero usan los mismos detalles al pasar el ratón sobre un evento: los pulsos muestran su tiempo y el resultado de la expresión numérico o de cadena, omitiendo los valores booleanos; los eventos sostenidos muestran su tiempo de inicio completo, tiempo de finalización y duración, incluso cuando el rango visible los recorta. Los tiempos se muestran en segundos con tres decimales.

La configuración del evento personalizado 'Tamaño del marcador del tablero' afecta únicamente a la capa del tablero. Los marcadores de la línea de tiempo permanecen en 8px y conservan la forma, color y opacidad del evento.

Nuevas configuraciones habilitan la capa de eventos personalizados con `pluck` seleccionado. Al pasar el ratón sobre un marcador de pulso, se muestra su tiempo y valor (omitidos los valores booleanos), o sobre una traza de evento sostenido para ver su tiempo de inicio completo, tiempo de finalización y duración, incluso cuando solo se muestra parte de la traza. Se conservan las configuraciones de capa guardadas.

## Campos admitidos

«Sí» significa que el nombre está disponible directamente como variable en la expresión; «—» significa que no lo está. Los nombres son sensibles a mayúsculas y minúsculas. Los valores dinámicos del analizador provienen de eventos muestreados; los valores estáticos describen todo el replay. El jugador lee sus getters actuales sin sustituir 0. Los nombres fuera de estas tablas, incluyendo `currentMs`, `current_time`, `timeMs` y `bvs`, no están soportados. Las claves de filas de contador y las claves de eventos no son variables en otras expresiones.

### Campos estáticos del tablero y del replay

| Campo | Significado y unidad | Reproductor de repeticiones | Contador de análisis | Evento personalizado |
| --- | --- | --- | --- | --- |
| `row` | Número de filas del tablero | Sí | Sí | Sí |
| `column` | Número de columnas del tablero | Sí | Sí | Sí |
| `mine_num` | Total de minas | Sí | Sí | Sí |
| `pix_size` | Tamaño original de la celda en píxeles, no el tamaño mostrado | Sí | Sí | Sí |
| `bbbv` | 3BV del tablero completo | Sí | Sí | Sí |
| `op` | Número total de aperturas del tablero | Sí | Sí | Sí |
| `isl` | Número de islas del tablero completo | Sí | Sí | Sí |
| `cell0` | Número de celdas vacías (en blanco) en todo el tablero | Sí | Sí | Sí |
| `cell1` | Número de celdas que muestran 1 en todo el tablero | Sí | Sí | Sí |
| `cell2` | Número de celdas que muestran 2 en todo el tablero | Sí | Sí | Sí |
| `cell3` | Número de celdas que muestran 3 en todo el tablero | Sí | Sí | Sí |
| `cell4` | Número de celdas que muestran 4 en todo el tablero | Sí | Sí | Sí |
| `cell5` | Número de celdas que muestran 5 en todo el tablero | Sí | Sí | Sí |
| `cell6` | Número de celdas que muestran 6 en todo el tablero | Sí | Sí | Sí |
| `cell7` | Número de celdas que muestran 7 en todo el tablero | Sí | Sí | Sí |
| `cell8` | Número de celdas que muestran 8 en todo el tablero | Sí | Sí | Sí |
| `zini` | Número estimado de operaciones de marcado con algoritmo greedy (ZiNi) | Sí | Sí | Sí |
| `hzini` | Número de operaciones después de abrir todas las aperturas primero, luego aplicar el algoritmo greedy (Human ZiNi) | Sí | Sí | Sí |
| `rtime` | Duración total del replay en segundos, no el progreso actual de reproducción | Sí | Sí | Sí |
| `level` | Código de nivel de dificultad del replay | Sí | Sí | Sí |
| `mode` | Código del modo de juego del replay | Sí | Sí | Sí |

Las variables `cell0` hasta `cell8` son nueve variables separadas. `cell0-8` no es un nombre de variable.

### Campos dinámicos y exclusivos del jugador

| Campo | Significado y unidad | Reproductor de repeticiones | Contador de análisis | Evento personalizado |
| --- | --- | --- | --- | --- |
| `time` | Tiempo original del evento muestreado en segundos; puede ser negativo antes de que comience el temporizador del juego y difiere del progreso de reproducción de la página | — | Sí | Sí |
| `x` | Coordenada original en píxeles del último evento del ratón respecto al borde izquierdo del tablero; aumenta hacia la derecha | — | Sí | Sí |
| `y` | Coordenada original en píxeles del último evento del ratón respecto al borde superior del tablero; aumenta hacia abajo | — | Sí | Sí |
| `path` | Longitud acumulada del recorrido del ratón, manteniendo el valor de la biblioteca independientemente del tamaño de la casilla mostrada | Sí | Sí | Sí |
| `bbbv_solved` | 3BV resueltos hasta ahora | Sí | Sí | Sí |
| `left` | Clicks izquierdos acumulados | Sí | Sí | Sí |
| `right` | Clicks derechos acumulados | Sí | Sí | Sí |
| `double` | Dobles clics acumulados | Sí | Sí | Sí |
| `lce` | Clicks efectivos izquierdos acumulados | Sí | Sí | Sí |
| `rce` | Clicks efectivos derechos acumulados | Sí | Sí | Sí |
| `dce` | Dobles clics efectivos acumulados | Sí | Sí | Sí |
| `flag` | Cantidad de banderas colocadas | Sí | Sí | Sí |
| `op_solved` | Casillas abiertas hasta ahora | — | Sí | Sí |
| `isl_solved` | Islas resueltas hasta ahora | — | Sí | Sí |
| `mouse_state` | Código de estado del ratón; los analizadores usan el estado después del evento nativo | Sí | Sí | Sí |
| `bbbv_s` | 3BV por segundo | Sí | — | — |
| `ce` | Total de clics efectivos | Sí | — | — |
| `ce_s` | Clics efectivos por segundo | Sí | — | — |
| `cl` | Total de clics | Sí | — | — |
| `cl_s` | Clics por segundo | Sí | — | — |
| `left_s` | Clics izquierdos por segundo | Sí | — | — |
| `right_s` | Clics derechos por segundo | Sí | — | — |
| `double_s` | Dobles clics por segundo | Sí | — | — |
| `flag_s` | Tasa de colocación de banderas | Sí | — | — |
| `etime` | Tiempo estimado de finalización en segundos | Sí | — | — |
| `rtime_ms` | Duración total de la repetición en milisegundos | Sí | — | — |
| `rqp` | Métrica de velocidad RQP | Sí | — | — |
| `stnb` | Métrica de finalización y velocidad STNB | Sí | — | — |
| `corr` | Métrica de precisión operativa | Sí | — | — |
| `thrp` | Métrica de eficiencia de throughput | Sí | — | — |
| `ioe` | Índice de eficiencia | Sí | — | — |
| `pluck` | Métrica acumulada de Pluck | Sí | Sí | Sí |
| `current_event_id` | Índice actual del array de eventos nativos, no un valor de tiempo | Sí | — | — |
| `game_board_state` | Código de estado del tablero de juego | Sí | — | — |
| `video_start_time` | Desplazamiento de inicio de repetición en segundos | Sí | — | — |
| `video_end_time` | Coordenada de finalización de repetición en segundos | Sí | — | — |

El origen de `x` e `y` es la esquina superior izquierda del tablero; no cambian con el zoom ni con el tamaño mostrado. Los eventos sin ratón y los milisegundos sin eventos conservan la última posición; antes del primer evento del ratón, ambos campos son `NaN`. Las coordenadas fuera del tablero conservan los valores originales sin limitarlos ni sustituirlos. `x / pix_size` e `y / pix_size` dan coordenadas fraccionarias de casilla; `floor(x / pix_size)` y `floor(y / pix_size)` dan los índices de columna y fila desde 0. Antes de localizar una casilla, comprueba `x >= 0 and x < column * pix_size and y >= 0 and y < row * pix_size` para excluir posiciones fuera del tablero.

El analizador no expone directamente `bbbv_s`, `cl` o `ce`. Puedes combinar campos soportados, por ejemplo `bbbv_solved / time`, `left + right + double` o `lce + rce + dce`. Esas fórmulas no se garantizan que coincidan con los algoritmos de obtención del jugador en cada estado especial.

El analizador calcula el `pluck` por evento al cargar una repetición. Los valores brutos se conservan: los valores no disponibles pueden ser `NaN`, y el valor de fallo al tocar una mina es `Number.MAX_VALUE`, sin reemplazo por cero o infinito.

### Códigos de estado del ratón

| Valor | Estado | Significado |
| --- | --- | --- |
| 1 | `UpUp` | Ambos botones izquierdo y derecho liberados |
| 2 | `UpDown` | Se suelta el botón izquierdo y se presiona el derecho |
| 3 | `UpDownNotFlag` | Se suelta el botón izquierdo y se presiona el derecho sin colocar ni quitar una bandera |
| 4 | `DownUp` | Se presiona el botón izquierdo y se suelta el derecho |
| 5 | `Chording` | Se presionan ambos botones |
| 6 | `ChordingNotFlag` | Se presionan ambos botones después de presionar primero el derecho en una casilla que no puede ser clickeada con el botón derecho |
| 7 | `DownUpAfterChording` | Se suelta primero el botón derecho después de una apertura simultánea, mientras el botón izquierdo sigue presionado |
| 8 | `Undefined` | Estado no inicializado |

Nombres como `DownUp` no son constantes de expresión. Usa sus códigos numéricos, por ejemplo `mouse_state == 4`.

## Operadores y sintaxis

Todos los tres contextos soportan las siguientes operaciones, pero el resultado final del contador debe ser numérico. Los arrays, cadenas y valores booleanos pueden ser resultados intermedios. La tabla sigue aproximadamente el orden de precedencia de mayor a menor; usa paréntesis cuando no estés seguro.

| Operador o sintaxis | Significado y ejemplo | Reproductor de repeticiones | Contador de análisis | Evento personalizado |
| --- | --- | --- | --- | --- |
| `(...)` | Agrupación, por ejemplo `(left + right) / time` | Sí | Sí | Sí |
| `f(...)`, `a[i]`, `x.y` | Llamada a función, índice cero basado y acceso a propiedades, por ejemplo `[left, right][0]` o `[left, right].length`; no evita la lista blanca de variables | Sí | Sí | Sí |
| `[a, b, ...]`, `"text"`, `'text'` | Literales de array y cadena | Sí | Sí | Sí |
| `x!` | Factorial posfijo: `5!` es 120, no la negación lógica | Sí | Sí | Sí |
| `x ^ y` | Exponenciación: `2 ^ 3` es 8, no XOR | Sí | Sí | Sí |
| `+x`, `-x`, `not x` | Conversión numérica, negación y negación lógica; las funciones matemáticas unarias se enumeran a continuación | Sí | Sí | Sí |
| `*`, `/`, `%` | Multiplicación, división y módulo | Sí | Sí | Sí |
| `+`, `-` | Adición y sustracción numéricas; el operador `+` no es concatenación de cadenas | Sí | Sí | Sí |
| `x \|\| y` | Concatenación de cadenas, o concatenación de arrays cuando ambos operandos son arrays; no es la operación lógica OR | Sí | Sí | Sí |
| `==`, `!=`, `<`, `<=`, `>`, `>=` | Comparaciones, por ejemplo `left > right` | Sí | Sí | Sí |
| `x in a` | Miembro de array, por ejemplo `mouse_state in [4, 5, 7]` | Sí | Sí | Sí |
| `x and y` | AND lógico; omite el operando derecho si el izquierdo es falso | Sí | Sí | Sí |
| `x or y` | OR lógico; omite el operando derecho si el izquierdo es verdadero | Sí | Sí | Sí |
| `c ? a : b` | Expresión condicional; solo evalúa la rama seleccionada; se permite anidación | Sí | Sí | Sí |
| `a; b` | Evalúa secuencialmente y devuelve el último resultado; no es una declaración de variable | Sí | Sí | Sí |
| `x = value` | Asignación | No | No | No |
| `f(x) = expr` | Definición de función | No | No | No |
| `if (...) { ... }`, `&&`, `!x`, `**`, `===`, `=>` | Instrucciones o operadores de JavaScript o funciones de flecha; no pertenecen a esta gramática de expresiones | No | No | No |

Usa las palabras clave `and`, `or` y `not`. Los resultados lógicos son booleanos; usa `condition ? 1 : 0` para obtener un resultado numérico en un contador. Se admite notación científica como `1e-3`. Prefiere paréntesis alrededor de los argumentos de funciones unarias, por ejemplo `sin(time)^2`, para evitar ambigüedades de precedencia.

### Constantes

| Constante o expresión | Significado | Todos los tres contextos |
| --- | --- | --- |
| `PI` | Pi | Soportado |
| `E` | El número de Euler | Soportado |
| `true`, `false` | Booleanos | Soportados, pero no válidos como resultados finales del contador |
| `0 / 0` | Produce `NaN` | Soportados; se mantienen como números de contador, falso para eventos personalizados |
| `1 / 0`, `-1 / 0` | Produce infinito positivo/negativo | Soportados; se mantienen como números de contador, verdadero para eventos personalizados |
| `NaN`, `Infinity`, `Inf`, `null`, `undefined` | Estos nombres no son constantes integradas | No se admite |

## Funciones

La tabla lista funciones integradas, extensiones de aplicación y operadores unarios de función, junto con sus contextos soportados. `x`, `a` y `f` son lugares de argumento, no campos adicionales de repetición. Los ángulos están en radianes.

Usa `toFixed` en el jugador para conservar los ceros finales. Devuelve texto; `roundTo` sigue devolviendo un número. Las nuevas expresiones por defecto usan tres decimales. Las expresiones guardadas se conservan; reemplaza las llamadas a `roundTo` solo para visualización con `toFixed` según sea necesario. Los contadores del analizador continúan usando su campo de formato separado, como `.3f`.

<!-- functions -->

| Función | Significado y ejemplo | Reproductor de repeticiones | Contador de análisis | Evento personalizado |
| --- | --- | --- | --- | --- |
| `abs(x)` | Valor absoluto, por ejemplo `abs(-3)` | Sí | Sí | Sí |
| `sign(x)` | Signo; los números negativos, cero o positivos normalmente producen -1, 0 o 1 | Sí | Sí | Sí |
| `ceil(x)` | Redondea hacia arriba | Sí | Sí | Sí |
| `floor(x)` | Redondea hacia abajo | Sí | Sí | Sí |
| `round(x)` | Redondea al entero más cercano usando las reglas de redondeo de JavaScript | Sí | Sí | Sí |
| `trunc(x)` | Elimina la parte fraccionaria hacia cero | Sí | Sí | Sí |
| `roundTo(x, n)` | Redondea a n decimales, por ejemplo `roundTo(time, 3)`; n negativo redondea a decenas, centenas, etc.; no rellena ceros finales | Sí | Sí | Sí |
| `toFixed(x, n)` | Devuelve texto con decimales fijos, por ejemplo `toFixed(3.4, 3)` devuelve `"3.400"`. Si n no se especifica, se usa 0; la precisión sigue las reglas de JavaScript `Number.toFixed` (0–100). Combina con `\|\|` | Sí | No; usa el campo de formato separado | No |
| `min(a, b, ...)` | Mínimo; también acepta un array, por ejemplo `min([left, right])` | Sí | Sí | Sí |
| `max(a, b, ...)` | Máximo; también acepta un array, por ejemplo `max([left, right])` | Sí | Sí | Sí |
| `sqrt(x)` | Raíz cuadrada | Sí | Sí | Sí |
| `cbrt(x)` | Raíz cúbica | Sí | Sí | Sí |
| `pow(x, y)` | Exponenciación, equivalente a `x ^ y` | Sí | Sí | Sí |
| `hypot(a, b, ...)` | Raíz cuadrada de la suma de los cuadrados de los argumentos | Sí | Sí | Sí |
| `pyt(a, b, ...)` | Alias de `hypot` | Sí | Sí | Sí |
| `exp(x)` | `E ^ x` | Sí | Sí | Sí |
| `expm1(x)` | `exp(x) - 1` | Sí | Sí | Sí |
| `ln(x)` | Logaritmo natural | Sí | Sí | Sí |
| `log(x)` | Alias de `ln`; no es de base 10 | Sí | Sí | Sí |
| `log2(x)` | Logaritmo en base 2 | Sí | Sí | Sí |
| `log10(x)` | Logaritmo en base 10 | Sí | Sí | Sí |
| `lg(x)` | Alias de `log10` | Sí | Sí | Sí |
| `log1p(x)` | `ln(1 + x)` | Sí | Sí | Sí |
| `sin(x)` | Seno | Sí | Sí | Sí |
| `cos(x)` | Coseno | Sí | Sí | Sí |
| `tan(x)` | Tangente | Sí | Sí | Sí |
| `asin(x)` | Arcoseno | Sí | Sí | Sí |
| `acos(x)` | Arcocoseno | Sí | Sí | Sí |
| `atan(x)` | Arcotangente | Sí | Sí | Sí |
| `atan2(y, x)` | Ángulo de dirección del vector (x, y); y viene primero | Sí | Sí | Sí |
| `sinh(x)` | Seno hiperbólico | Sí | Sí | Sí |
| `cosh(x)` | Coseno hiperbólico | Sí | Sí | Sí |
| `tanh(x)` | Tangente hiperbólica | Sí | Sí | Sí |
| `asinh(x)` | Arcoseno hiperbólico | Sí | Sí | Sí |
| `acosh(x)` | Arcocoseno hiperbólico | Sí | Sí | Sí |
| `atanh(x)` | Arcotangente hiperbólica | Sí | Sí | Sí |
| `gamma(x)` | Función gamma; para un entero positivo n, `gamma(n) = (n - 1)!` | Sí | Sí | Sí |
| `fac(x)` | Factorial, correspondiente a `x!`; para números no enteros se usa la extensión de Gamma | Sí | Sí | Sí |
| `random(n)` | Número aleatorio en [0, n); usa 1 si n no se especifica o es cero; no adecuado para análisis reproducible | Sí | Sí | Sí |
| `length(x)` | Longitud de cadena o arreglo | Sí | Sí | Sí |
| `indexOf(x, a)` | Índice cero inicial de la primera aparición de x en la cadena o arreglo a; -1 si no está presente | Sí | Sí | Sí |
| `join(sep, a)` | Une los elementos del arreglo en una cadena usando el separador sep | Sí | Sí | Sí |
| `map(f, a)` | Aplica una función a los elementos del arreglo y devuelve un arreglo, por ejemplo `map(abs, [-1, 2])` | Sí | Sí | Sí |
| `filter(f, a)` | Mantén los elementos cuyo resultado de la función sea verdadero; devuelve un arreglo, por ejemplo `filter(abs, [-1, 0, 2])` | Sí | Sí | Sí |
| `fold(f, initial, a)` | Reduce un arreglo a un único valor, por ejemplo `fold(pow, 2, [3, 2])` produce 64 | Sí | Sí | Sí |
| `if(c, a, b)` | Selecciona a o b según c, pero evalúa ambos argumentos primero; usa `c ? a : b` para cortocircuito | Sí | Sí | Sí |
| `not(x)` | Negación lógica, también escrita como `not x`; devuelve un booleano | Sí | Sí | Sí |
| `d(expr)` | Expresión numérica en la muestra actual menos su valor en la muestra anterior | — | Sí | Sí |
| `d(expr, n)` | Resta el valor n muestras antes; n debe ser un entero positivo | — | Sí | Sí |
| `s(expr)` | Suma desde el inicio del arreglo de muestras hasta la muestra actual incluida, con un acumulador inicial de 0 | — | Sí | Sí |
| `s(expr, n)` | Suma las últimas n muestras incluida la actual, sin rebasar el inicio del arreglo; n debe ser un entero positivo | — | Sí | Sí |

<!-- /functions -->

Los argumentos de función para `map`, `filter` y `fold` pueden usar built-ins compatibles, no funciones de flecha de JavaScript ni definiciones de nuevas funciones. No existen funciones generales `String`, `Number`, `isNaN`, `isFinite` ni `Math.*`. Utiliza `+` para la conversión numérica, `"" || value` para la concatenación de texto y `value != value` para probar por `NaN`, reemplazando el valor por un campo o expresión real. `d` y `s` requieren llamadas directas y no pueden utilizarse como callbacks de funciones de array.

### Reglas de diferencia

| Regla | Explicación |
| --- | --- |
| Operando | Un campo o expresión numérica, por ejemplo `d(left)`, `d(left + right)` o `d(bbbv_solved) / d(time)` |
| Paso predeterminado | `d(expr)` es igual a `d(expr, 1)`; cuenta las muestras conservadas, no milisegundos ni el conteo nativo de eventos |
| Expresión de paso | n se evalúa en la muestra actual, por ejemplo `d(left, time > 1 ? 2 : 1)`; pasos no positivos o no enteros son errores |
| Predecesores ausentes | Devuelve `NaN`; los contadores los mantienen, los eventos personalizados los tratan como ausencia |
| Anidamiento | `d(d(left))` y `d(d(left, 2), 3)` funcionan; sus primeras dos y cinco muestras respectivamente son `NaN` |
| Sin normalización automática | No divide por el paso ni por el tiempo transcurrido; divide explícitamente por `d(time)` para obtener una tasa |
| Orden de evaluación | Filtrar y eliminar duplicados de muestras en milisegundos, luego evaluar diferencias; la interpolación y formato de contadores ocurren después |
| Ramificaciones condicionales | Saltar una llamada de diferencia no cambia cuál muestra es el predecesor |

### Reglas de suma

| Regla | Explicación |
| --- | --- |
| Operando | Un campo o expresión numérica; convierte una condición booleana con `condition ? 1 : 0` |
| Rango predeterminado | `s(expr)` suma desde el índice 0 hasta el índice actual del arreglo de muestras. El acumulador empieza en 0; si la primera muestra es `NaN`, devuelve 0 |
| Ventana | `s(expr, n)` incluye los índices desde `max(0, i - n + 1)` hasta el índice actual i; `s(expr, 1)` devuelve la muestra actual, o 0 si es `NaN` |
| Parámetro de ventana | n se evalúa en la muestra actual, por ejemplo `s(left, time > 1 ? 10 : 2)`; los valores no enteros o no positivos son errores |
| Muestreo | Utiliza los índices tras filtrar, eliminar duplicados y rellenar huecos, sin ponderar por fotogramas, eventos nativos o tiempo. En muestreo continuo, `s(condition ? 1 : 0)` cuenta las muestras de milisegundos que cumplen la condición |
| Anidamiento y navegación | Admite `s(s(left))`, `d(s(left))` y `s(d(left), 2)`. Retroceder o saltar una llamada en una condición externa no cambia su rango |
| Valores NaN | Omite los resultados `NaN`; devuelve 0 si todas las muestras son `NaN`. Estas muestras siguen ocupando índices y no se añaden muestras anteriores a la ventana |
| Infinitos | No omite los infinitos positivos ni negativos. El `NaN` producido al sumar infinitos opuestos se conserva como resultado acumulado. Los infinitos fuera de la ventana no la afectan |
| Combinación con diferencias | `s(d(left))` omite los valores `NaN` iniciales y suma los incrementos válidos; recuperar el valor original también requiere añadir el valor de la primera muestra |

Para los valores muestreados `[1, 3, 8]`, `s(expr)` produce `[1, 4, 12]` y `s(expr, 2)` produce `[1, 4, 11]`. Las sumas de contadores se evalúan antes de interpolar y formatear; los eventos personalizados usan las mismas reglas.

## Contadores predeterminados

Al primer uso, los contadores utilizan muestreo continuo y el formato de visualización `.3f`:

| clave | Expresión | Gráfico predeterminado |
| --- | --- | --- |
| `Bvs` | `d(bbbv_solved, 1000) / d(time, 1000)` | Gráfico 1 |
| `Ces` | `d(lce+rce+dce, 1000)/d(time, 1000)` | Gráfico 1 |
| `Mov` | `d(path, 1000) / d(time, 1000) / 16` | Gráfico 2 |

Aquí, 1000 conteos de muestras continuas en milisegundos; el denominador utiliza la diferencia del evento original en `time`. Los primeros 1000 muestras son `NaN`, y una diferencia de tiempo cero también puede producir valores no finitos. El valor en minúscula `bvs` ya no es un contador predeterminado. Se conservan las configuraciones de contador y gráfico guardadas.

## Eventos personalizados predeterminados

Al primer uso, los siguientes eventos se incluyen:

| clave | Tipo | Expresión |
| --- | --- | --- |
| `left` | Sostenido | `mouse_state in [4, 5, 6, 7]` |
| `right` | Sostenido | `mouse_state in [2, 3, 5, 6]` |
| `pluck` | Pulso | `d(pluck)` |

El pulso `pluck` ocurre cuando el valor acumulado cambia desde el millisecond anterior. Un valor no cambiado o una diferencia `NaN` no produce pulso. Se conservan los eventos personalizados guardados previamente.

## Ejemplos

| Contexto | Expresión | Resultado |
| --- | --- | --- |
| Reproductor de repeticiones | `toFixed(bbbv_s, 3) \|\| "@" \|\| bbbv_solved \|\| "/" \|\| bbbv` | Combinar una tasa con tres decimales, resuelto BV y BV total como texto |
| Contador de análisis | `time > 0 ? bbbv_solved / time : 0` | 3BV/s acumulados; el formato separado puede ser `.3f` |
| Contador de análisis | `d(bbbv_solved) / d(time)` | 3BV/s entre muestras; la primera muestra es `NaN` |
| Evento de pulso personalizado | `d(left) > 0` | Un pulso cuando aumentan los clics izquierdos acumulados |
| Evento personalizado sostenido | `mouse_state in [4, 5, 6, 7]` | Segmentos continuos donde se presiona el botón izquierdo |
| Evento personalizado | `mouse_state == 4 and d(left) > 0` | Requiere tanto un estado del ratón como un aumento de clic |

Referencia de sintaxis: [expr-eval](https://github.com/silentmatt/expr-eval). Formato de visualización separado para contadores: [d3-format](https://d3js.org/d3-format); el formato no es una función de expresión
