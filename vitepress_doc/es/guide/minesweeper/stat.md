---
title: "Datos de Buscaminas - Open Minesweeper"
description: "Explicación detallada de las métricas de datos de Buscaminas, incluyendo 3BV, ZiNi, bvs, rqp, ioe y stnb para datos de partida individual, así como sistemas históricos como el sistema LSF."
---

# Datos de Buscaminas

Los datos de Buscaminas son las métricas utilizadas para evaluar la complejidad del tablero y el rendimiento del jugador. Las métricas existentes se pueden dividir aproximadamente en datos de partida individual y datos históricos.

- Los **datos de partida individual** son los datos de un solo juego. Los datos de partida individual se dividen aún más en datos básicos y datos derivados.
  - [Datos básicos](#basic-data) son datos que no dependen de ningún otro dato. Los datos básicos se dividen además en datos de tablero y datos de entrada.
    - [Datos del tablero](#board-data) se determinan según la colocación de las minas y incluyen [bv, op, is](#bv-op-is), [zini](#zini) y [cellx](#cellx).
    - [Los datos de entrada](#input-data) se determinan a partir de las operaciones del ratón que realiza el jugador y incluyen [tiempo](#time), [ruta](#path-cpath-epath), [cl, ce](#cl-ce) y [bvdone, opdone](#bvdone-opdone).
  - [Datos derivados](#derived-data) se calculan a partir de varios datos básicos con el fin de evaluar la calidad de un juego.
    - basados en bv y tiempo: [bvs, rqp, qg, ios, rv](#bvs-rqp-qg-ios-rv).
    - para evaluar la velocidad de clic: [ces, cls](#ces-cls).
    - para evaluar la eficiencia de las operaciones: [corr, thrp, ioe](#corr-thrp-ioe).
    - para evaluar la eficiencia en el manejo de aperturas: [cpo, coo](#cpo-coo).
    - basados en la ruta: [mov, sao, iome](#mov-sao-iome).
    - basados en zini: [zinis, znt, zne](#zinis-znt-zne).
    - basado en la finalización: [finalización, estimación, stnb](#completion-estime-stnb).
    - basado en casillas: [números, obg](#numbers-obg).

  `time`, `bvs` y `stnb` son los tres métricas más ampliamente aceptadas para evaluar la fuerza en carreras, y se llaman los **tres parámetros principales**.
- Los **datos históricos** se derivan de todos los datos de partida individual de un jugador fijo durante toda su carrera en Buscaminas. Actualmente, los tipos más populares de datos históricos son el sistema LSF, el sistema de marcas personales (PB) y el sistema de línea del jugador.
  - El sistema [LSF ](#the-lsf-system) es un estándar que clasifica el nivel de un jugador basándose en los datos de los mejores jugadores del país.
  - El PB es el mejor resultado histórico de un jugador en un bv específico. La potencia de combate, el tiempo típico, el stnb típico, el sistema de medallas y el mecanismo de enfrentamientos se pueden derivar a partir de los PBs.
  - La línea del jugador es el conjunto de las mejores repeticiones de un jugador que no se superan entre sí. Los niveles gruesos, los niveles finos y el mecanismo de eliminación mutua se pueden derivar de las líneas del jugador.

_______
# Datos Básicos {#basic-data}
Los datos básicos son datos específicos de cada repetición que no dependen de otros datos. Al subdividirlos aún más, los datos básicos pueden dividirse nuevamente en propiedades del tablero en sí (datos de tablero) y datos de entrada del jugador.

Las propiedades del tablero incluyen [bv, op, is](#bv-op-is), [las diversas zini](#zini) y [cellx](#cellx). Los datos de entrada del jugador incluyen [las diversas cl y ce](#cl-ce), [path](#path-cpath-epath) y [time](#time). Estrictamente hablando, la colocación de minas es la propiedad más básica del tablero en sí, y cada clic y la trayectoria del ratón son los datos de entrada más básicos del jugador, pero estos son demasiado tediosos para resumir y generalmente no se discuten.

## Datos de Tablero {#board-data}

#### `bv`, `op`, `is`
`bv` es abreviatura de `3BV`, `3BV` es abreviatura de `BBBV` y `BBBV` es abreviatura de `Bechtel's Board Benchmark Value`. `bv` es el parámetro más clásico para medir la complejidad del tablero.

`op` es abreviatura de `Opening`; en chino es `空`.

`is` es abreviatura de `Island`; en chino es `岛`. Para evitar confusión con la palabra inglesa «is», a veces se escribe `isl`.

El artículo de [la columna de Wudi](https://zhuanlan.zhihu.com/p/27185883) explica en detalle qué significa `bv`, `op` y `is` y qué papel juegan en la dificultad del tablero, por lo que no se repite aquí.

### `zini`
Si `bv` mide el límite inferior del número de operaciones NF necesarias para resolver un tablero, `zini` mide el límite inferior del número de operaciones FL. El concepto y los algoritmos de `zini` fueron propuestos en 2009 por [Elmar Zimmermann](https://minesweepergame.com/profile.php?pid=322) y [Christoph Nikolaus](https://minesweepergame.com/profile.php?pid=173) en el [foro internacional](https://minesweepergame.com/forum//viewtopic.php?f=15&t=70), y se nombran según sus apellidos. Como encontrar la solución óptima de FL para un tablero es un problema NP, es decir, no puede calcularse con un costo bajo, en su lugar buscaron algoritmos de aproximación rápidos. Propusieron tres algoritmos greedy.

La idea básica greedy es encontrar la operación con mayor ganancia en cada paso. Dado que todas las posiciones de minas son conocidas, cada casilla en un estado dado del tablero tiene exactamente una operación que produzca ganancia:
- Coloca banderas alrededor de esta casilla y realiza una apertura simultánea; la ganancia es `bv opened by the chord - number of flags - 1`. Si la casilla aún no está abierta, entonces teniendo en cuenta la operación necesaria para abrir la casilla, la ganancia se reduce en 1. Las casillas ya abiertas y las banderas ya colocadas no se cuentan. Realizar una apertura simultánea directamente es equivalente a un conteo de banderas de 0.

A partir del comienzo del juego, calcula la ganancia de cada casilla no con mina en cada paso. Si alguna casilla tiene ganancia no negativa, elige la casilla con mayor ganancia y realiza la operación correspondiente; si todas las casillas tienen ganancia negativa, finaliza el resto del `bv` con clics izquierdos. El número de operaciones utilizadas para finalizar el juego de esta manera es su `zini`. Los tres algoritmos `zini` solo difieren en detalles.

`gzini` significa "ZiNi Greedy": cuando varias casillas comparten la mayor ganancia, siempre elige la más arriba y luego la más a la izquierda. `rzini` significa "ZiNi Aleatorio": cuando varias casillas comparten la mayor ganancia, elige una al azar. El barrido aleatorio se repite hasta que n partidas consecutivas no establezcan un nuevo récord con el menor número de operaciones. `hzini` significa "ZiNi Humano": primero abre todas las `op` con clics izquierdos y luego actúa como `gzini`.

Obviamente `rzini` aún contiene elementos de azar y es inestable, por lo que generalmente no se utiliza como métrica. `gzini` y `hzini` no están ordenados, ni son invictos. Los jugadores ya han superado tanto `gzini` como `hzini` en niveles principiante e intermedio (es decir, finalizando con menos operaciones), pero nadie ha logrado esto en el nivel experto aún. Ambos, Minesweeper Arbiter y Metasweeper, reportan `gzini` y `hzini`.

En los últimos años han aparecido otras variantes de algoritmos zini, la más destacada siendo [Pttazini (ZiNi de PTTACGfans)](https://github.com/PTTACGfans/Minesweeper-ZiNi-Calculator).

### cellx
cellx es el número de casillas que muestran el dígito x. x varía desde 0 hasta 8.

## Datos de entrada {#input-data}

### `time`
`time` es el tiempo empleado para finalizar un juego y es la métrica más importante en Buscaminas.

Históricamente han existido dos tipos de `time`. Uno comienza a contar desde 1 segundo y pertenece a Minesweeper Clone. El otro comienza desde 0 segundos y pertenece a Minesweeper Arbiter. La cuenta oficial actual comienza desde 0 segundos, pero como el primer Winmine comenzó desde 1 segundo, algunos conceptos siguen la convención de 1 segundo.
- Saolei.wang muestra datos cronometrados desde 1 segundo.
- (Muy importante, de lectura obligatoria para los internos y curiosidades extrañas para los externos) Tradicionalmente, los conceptos de segundos y sub se definen bajo la premisa de que el cronómetro comienza desde 1 segundo. Por ejemplo, un tiempo intermedio de 10 segundos significa que, con el cronómetro que comienza desde 1 segundo, la parte entera es 10, lo que corresponde a `rtime` entre 9.00 y 9.99. Sub40 experto significa segundos expertos sub40, es decir, segundos expertos <= 39, es decir, `rtime<=38.99`.

Sin importar qué convenio de cronometraje se use, `rtime` (Tiempo Real) es inambiguo y siempre significa el tiempo contado desde 0 segundos. El `time` mencionado en el resto de esta página siempre significa `rtime`.

### `path`, `cpath`, `epath`
El `path` es la distancia que recorre el cursor al finalizar un juego. La unidad de `path` es píxeles o celdas, donde 1 celda = 16 píxeles.

El `cpath`, abreviado como Ruta de Click, solo considera la distancia entre las posiciones donde ocurren los eventos de clic y ignora la pérdida por trayectorias curvas del ratón.

El `epath`, abreviado como Ruta Efectiva, solo considera la distancia entre los centros de las celdas de los eventos de clic efectivos y ignora la diferencia sobre dónde dentro de una celda se hizo el clic.

### `cl`, `ce`
El `cl` significa "Clics" y representa el número de clics del ratón. El `ce` significa "Clics Eficientes" y representa el número de clics efectivos. Desglosados por tipo de clic, también existen `lcl`, `rcl`, `dcl`, `lce`, `rce` y `dce`, donde el prefijo `l` significa Izquierdo (botón izquierdo), el prefijo `r` significa Derecho (botón derecho) y el prefijo `d` significa Dobles (apertura simultánea).

La diferencia entre `cl` y `ce` es los clics inefectivos. Las razones de los clics inefectivos con el botón izquierdo, derecho y ambos son:
- clic izquierdo que cae sobre un número o una bandera; cancelación de un clic izquierdo; hacer clic en una celda recién abierta durante una secuencia continua debido a una reacción lenta.
- clic derecho que cae sobre un número; colocar una bandera incorrectamente; cancelar una bandera incorrecta; cancelar incorrectamente una bandera; volver a colocar una bandera tras cancelarla incorrectamente.
- apertura simultánea que falla; cancelación de una apertura simultánea; una apertura simultánea de prueba que falla.

La principal discrepancia entre los estándares es sobre los clics derechos inefectivos. El Arbiter de Buscaminas considera que `ce` incluye todas las operaciones que modifican el tablero, por lo que tanto los errores de bandera como la cancelación de banderas se cuentan como clics efectivos. Open Minesweeper y Metasweeper son más estrictos y requieren que una operación sea correcta para considerarse como `ce`.

### `bvdone`, `opdone`
bvdone significa bv completado y opdone significa op completado.

### `luck`, `pluck`
Ambos parámetros se basan en una máquina de probabilidades. Para cada operación que abre una celda, la máquina calcula la probabilidad de seguridad (0-1) desde el estado actual del tablero; multiplicando las probabilidades de seguridad de todas las operaciones se obtiene `luck`, que representa el porcentaje teórico de victoria de un juego. `pluck` se define como `-log10(luck)`.

________________
# Datos derivados {#derived-data}

### `bvs`, `rqp`, `qg`, `ios`, `rv`
El `bvs` significa "bv por segundo"; la fórmula es `bvs=bv/time`, lo que significa el número de `bv` resueltos por segundo, y mayor es mejor. `bvs` es la métrica de velocidad más clásica, solo segundo en importancia al `time`. En general, un `bv` más pequeño da un mejor `time`, mientras que un `bv` más grande da un mejor `bvs`, por lo que se necesitan otros parámetros para equilibrarlos.

`rqp` es abreviatura de "Rapport Qualité Prix"; la fórmula es `rqp=(time+1)/bvs`. La razón de sumar 1 al tiempo es que la convención de cronometraje era aún de base 1 cuando se creó este parámetro. Si se ignora ese segundo de 1 segundo cuando `time` es grande, `rqp` es aproximadamente igual a `time^2/bv`. `rqp` valora en gran medida el papel de `time`, pero se desvía cuando `time` es pequeño, y el desvío ya es grave cuando `time<60`

`qg` es abreviatura de "Quality Grade", un parámetro de fuerza definido por [Guo Jinyang](https://openms.top/#/player/48) a partir de una gran cantidad de datos; la fórmula es `qg=time^1.7/bv`. En comparación con `rqp`, `qg` tiene la ventaja de enfatizar más el `bvs` y eliminar la desviación en tiempos bajos.

`ios` es abreviatura de "Index of Speed"; la fórmula es `ios=log(bv)/log(time)`.

`rv` es abreviatura de "Rirun Value"; la fórmula es `rv=sqrt(yybv*rqp+0.25)-0.5`. Aquí `yybv` es el `bv` usado para el pensamiento deseado, por ejemplo 100 para experto y 30 para intermedio.

### `ces`, `cls`
Similar a `bvs`, `ces=ce/time` y `cls=cl/time`. Estos dos parámetros representan la velocidad de operación del jugador; `cls` se centra en la tasa general de operaciones, mientras que `ces` representa la tasa de operaciones conscientes.

### `corr`, `thrp`, `ioe`
`corr` es abreviatura de "Correctness"; la fórmula es `corr=ce/cl`. Como los clics ineficaces en la mayoría de los casos no son causados por errores de puntero (un jugador que erra mucho difícilmente termina un juego), `corr` puede reflejar, en cierta medida, cuánta reflexión se invierte en las operaciones. Las aperturas sin pensamiento y los combos que ignoran completamente el potencial `op` reducen `corr`.

`thrp` es abreviatura de "ThroughPut"; la fórmula es `thrp=bv/ce`. Para FL, `thrp` refleja la eficiencia general en banderas y aperturas simultáneas. Para NF, `thrp` refleja la eficiencia general en la apertura y ruptura de casillas.

`ioe` es abreviatura de "Index of Efficiency"; la fórmula es `ioe=bv/cl`. `ioe` refleja la eficiencia general de las operaciones.

Obviamente también tenemos las siguientes relaciones:
- `corr=ces/cls`
- `thrp=bvs/ces`
- `ioe=bvs/cls`
- `ioe=corr*thrp`

Para NF, la única forma de mejorar la eficiencia operativa es aumentar la conciencia sobre `op`; para NF, los significados de `ioe`, `thrp` y `corr` son muy similares, y un valor más alto indica una mayor conciencia en la apertura y ruptura. Para FL, `corr` refleja principalmente la precisión operativa y la tasa de éxito en las aperturas simultáneas, mientras que `thrp` refleja la eficiencia de la estrategia de optimización. Como las aperturas razonables generan ganancia, los jugadores de FL no deben exagerar en `corr`.

### `cpo`, `coo`
Para NF, un bajo `thrp` en un solo juego puede deberse no solo a una insuficiente conciencia en la apertura y ruptura, sino también a un mal tablero. En otras palabras, cuánto más `op` tenga un tablero, más bajo será el `thrp`. Para contrarrestar la influencia de las fluctuaciones en `op` sobre `thrp`, se inventaron dos parámetros.

`cpo` es abreviatura de "avg Ce wasted Per Opening"; la fórmula es `cpo=(ce-bv)/op`. `coo` es abreviatura de "avg Ce cost On each Opening"; la fórmula es `coo=cpo+1`.

### `mov`, `sao`, `iome`
`mov` es abreviatura de "Movement"; la fórmula es `mov=path/time`, que refleja la velocidad general del ratón.

`iome` es abreviatura de "Index of Movement Efficiency"; la fórmula es `iome=bv/path`, que refleja la estrategia de resolución. Un bajo `iome` indica una tendencia a resolver `bv` cerca, mientras que un alto `iome` indica una tendencia a buscar soluciones óptimas en un área amplia.

`sao` es abreviatura de "风骚度" (flair); la fórmula es `sao=mov*ces`, que refleja la intensidad general de las operaciones.

### `zinis`, `znt`, `zne`
En el marco que utiliza `bv` como medida de complejidad del tablero, `bvs` representa la velocidad y `thrp` y `ioe` representan la eficiencia. `bvs`, `thrp` y `ioe` corresponden a `zinis`, `znt` y `zne` en el marco que utiliza `zini` como medida de complejidad del tablero:
- `zinis=zini/s`
- `znt=zini/ce`
- `zne=zini/cl`

Para diferentes algoritmos de `zini`, simplemente cambia el prefijo correspondiente de `zini`, por ejemplo `gzinis`, `rznt`, `hzne` y así sucesivamente.

### `completion`, `estime`, `stnb`
`completion` significa completitud; la fórmula es `completion=bvdone/bv`.

`estime` es abreviatura de "Estimated Time", que significa tiempo estimado; la fórmula es `estime=time/completion`

El valor `stnb` se refiere a "cómo impresionante es un cuerpo" (cuán impresionante es un cuerpo) y mide cuán impresionante es un cuerpo; la fórmula es `stnb=sqrt(completion)*constant/qg`. Los valores constantes para principiante, intermedio y experto son `36, 162, 435`; el propósito de la constante es hacer que `stnb` sea aproximadamente igual en los tres niveles a un mismo nivel de habilidad. Es precisamente por esta constante que `stnb` es más popular que `qg` y forma parte de uno de los tres parámetros más importantes.

> La constante también puede calcularse como `73.5*mode^2-94.5*mode+57`. Esto se aplica a contadores personalizados que no soportan lógica de ramificación.
> Antes de 2023-09-13, los valores constantes eran `47.299, 153.73, 435.001`, y la fórmula para calcular la constante era `87.420*(mode^2)-155.829*mode+115.708`.

### `numbers`, `obg`
El valor `numbers` es la suma de todos los números en el tablero; la fórmula es `numbers=0*cell0+1*cell1+2*cell2+3*cell3+4*cell4+5*cell5+6*cell6+7*cell7+8*cell8`.

El valor `obg` mide la reacción del jugador ante `bv`; la fórmula es `obg=10000*bvs/numbers`, donde 10000 se utiliza simplemente para evitar que el valor sea demasiado pequeño.

__________
# El Sistema LSF {#the-lsf-system}

Las clasificaciones de la cima y LSF utilizan los cinco mejores resultados, los anclajes y la fuerza relativa para evaluar a los jugadores. Consulta [Clasificaciones de la cima y LSF](../top-lsf.md) para conocer las reglas actuales y el sistema de niveles.

________
# Referencias
1. [Guo Jinyang, "Una breve discusión sobre los parámetros de fuerza" (Discusión breve sobre los parámetros de fuerza), Saolei.wang](http://www.saolei.wang/BBS/Title.asp?Id=9786)
2. [Lin Jinfan, "Diccionario de métricas técnicas de Buscaminas" (Análisis del diccionario de métricas técnicas de Buscaminas), Saolei.wang](http://www.saolei.wang/BBS/Title.asp?Id=12924)
3. [Guo Jinyang, "Métricas técnicas avanzadas de Buscaminas" (Métricas técnicas avanzadas de Buscaminas), Saolei.wang](http://www.saolei.wang/BBS/Title.asp?Id=12918)
4. [Zhou Ke, "Análisis breve de 3BV y ZiNi" (Análisis breve de 3BV y ZiNi), Saolei.wang](http://saolei.wang/BBS/Title.asp?Id=6946)
5. [Zhao Shuang, "Terminología de Buscaminas, segunda edición" (Terminología de Buscaminas (segunda edición)), Saolei.wang](http://saolei.wang/BBS/Title.asp?Id=6919)
6. [Elmar Zimmermann, "Nuevo estándar: 3bv para marcadores", Autoridad en Buscaminas](https://minesweepergame.com/forum//viewtopic.php?f=15&t=70)
