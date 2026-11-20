---
title: "Formato evf - Open Minesweeper"
description: "Especificación completa del formato abierto evf para repeticiones de Buscaminas, que abarca los objetivos de diseño, comparación con alternativas, símbolos de operación, terminología y disposiciones de campo para las versiones v0 hasta v4."
---

# evf: El segundo formato abierto para repeticiones de Buscaminas en la historia

* La especificación completa y las versiones históricas están disponibles en: https://github.com/eee555/ms_toollib/blob/main/evf%E6%A0%87%E5%87%86.md
* En caso de conflicto entre versiones en diferentes idiomas, prevalecerá la versión en chino.

Ambos formatos AVF y RMV para repeticiones de Buscaminas han alcanzado estabilidad técnica, permitiendo a clones especializados como Arbiter y Viennasweeper grabar y reproducir sus propias repeticiones. Sin embargo, este modelo centrado en el software es cerrado, impidiendo que nuevos programas generen estos formatos. Según [thefinerminer](https://minesweepergame.com/forum/viewtopic.php?f=26&t=1330), actualmente, debido a la salida de desarrolladores, el análisis de estos archivos depende del reverse engineering, lo que los hace inseguros y restrictivos para que los desarrolladores conviertan entre formatos. Para superar este problema, por un lado, Freesweeper puede reproducir múltiples formatos de video en una sola aplicación por primera vez. Por otro lado, Freesweeper puede convertir otros formatos de video al formato [rawvf](https://github.com/thefinerminer/minesweeper-rawvf) (el primer formato abierto para video de Buscaminas). La capacidad de reproducir múltiples formatos y convertirlos en un formato unificado es sin duda la dirección futura del desarrollo. Sin embargo, rawvf se centra principalmente en problemas de legibilidad humana, similar a información de depuración de un parser, lo que no solo dificulta satisfacer las preferencias de todos, sino que también ocupa innecesariamente espacio en disco, en contraste con las prácticas generales de ingeniería.

Además, los formatos existentes tienen los siguientes defectos: (1) Precisión insuficiente. Con los avances en hardware, la precisión temporal puede alcanzar niveles milisegundos. (2) Falta de soporte para la codificación UTF-8, que permite idiomas globales. (3) No permite grabar la pantalla antes del inicio del juego, como marcar minas antes de comenzar, moverse después del primer clic izquierdo o mantener el tiempo. (4) Solo se dispone de identificadores de usuario sin identificadores dedicados para carreras, lo que dificulta el análisis. (5) Falta de identificadores únicos, lo que impide distinguir entre usuarios con el mismo nombre. (6) No hay indicador de si el juego ha terminado, requiriendo analizar todo el juego para determinar si ha terminado. (7) Tamaño fijo de las casillas de 16 píxeles en el tablero.

Para resolver estos problemas, esta especificación propone el formato evf (formato de video de Buscaminas de eee555).

Con las siguientes características:
- Fácil codificación y decodificación para computadoras. A diferencia del formato RAWVF, los desarrolladores niegan que se pueda equilibrar la legibilidad para computadoras y para humanos.
- evf es un formato de video completamente independiente, no vinculado a ningún software ni a ningún parser de video.
- Sigue el principio de Kerckhoffs, utilizando un checksum en lugar de obfuscación.
- En comparación con el formato actualmente más popular `avf`, `evf` ofrece alta precisión, manteniendo la precisión hasta el milisegundo.
- Los datos enteros se almacenan en formato big-endian.
- Las cadenas generadas directamente en videos se codifican en utf-8, lo que permite codificar cualquier idioma, carácter o símbolo. Para videos transcodificados, se proporcionan métodos posibles de codificación.
- Tamaño ajustable de las casillas, que se adapta al tamaño real de la pantalla.
- La grabación comienza desde el primer clic izquierdo o derecho que afecte al juego antes de que comience.
- Viene con un documento claro y sin ambigüedades (este documento) y soporte confiable del proyecto, sin detalles ocultos ni backdoors.

Aunque tiene las siguientes limitaciones:
- Aplicable únicamente a un video.
- No es adecuado para repeticiones donde los ajustes del juego o los modos cambian durante el juego, como cambiar signos de pregunta, pasar de estándar a recursivo, modificar el tamaño de las casillas, etc.
- No es adecuado para repeticiones que carezcan de detalles de operación. Por ejemplo, en este formato, "l" indica el presionado o soltado del botón izquierdo, no ambos; el último es un presionado o soltado instantáneo, que no puede registrarse en este formato.
- Solo aplica a repeticiones de juegos de Buscaminas con disposición cuadrada en 2D y minas clásicas, no es adecuado para Buscaminas cuántico, con minas positivas y negativas, múltiples minas en una casilla, Buscaminas con casillas poligonales, Buscaminas en 3D, etc.
- Solo aplica a repeticiones de juegos de Buscaminas en modo de un jugador, no es adecuado para variantes multijugador.
- El tamaño en píxeles de las casillas varía entre 5 y 255, el rango de filas entre 1 y 255, y el rango de columnas entre 1 y 255. El producto de fila por tamaño en píxeles debe ser menor o igual a 32767, y el producto de columna por tamaño en píxeles debe ser menor o igual a 32767. Es adecuado para repeticiones que duren hasta 136 años.

### Objetivos de diseño/decisiones

El formato evf no es una innovación revolucionaria, sino un suplemento necesario y adecuado basado en reglas tradicionales. Además de los beneficios evidentes de mayor seguridad, más tipos de modo, transparencia y precisión, la importancia profunda de usar evf incluye:
1. Mejorar la propiedad del usuario sobre sus datos. Los formatos de video tradicionales solo contienen identificadores, mientras que AVF incluye también el país, pero no se sabe si contienen otra información que garantice la propiedad del usuario sobre sus datos. Sin embargo, los identificadores de usuario y los identificadores únicos del formato evf ayudan a los usuarios a asegurar la unicidad de sus identificadores. Además, evf registra el UUID del dispositivo del usuario, maximizando la dificultad de falsificar identidades.
2. Descentralización. Los archivos de video en formato evf son independientes de sitios web, software y jugadores. A diferencia de plataformas centralizadas como WOM, incluso si el sitio web cierra, la legalidad de los archivos evf permanece sin afectar. Los usuarios pueden subirlos a otros sitios web una vez que se establezcan nuevos.

### Comparación con alternativas
- En comparación con AVF: AVF es ampliamente utilizado, pero no es de código abierto, y su diseño es anticuado y obsoleto. No hay razón para usar AVF en nuevas réplicas.
- En comparación con [RMV](https://github.com/ralokt/rmv_spec): RMV exige la presencia de eventos de tablero y no tiene un UUID, pero su tamaño de archivo es ligeramente mayor que el de EVF. RMV sigue siendo mantenido y tiene ciertas características. Si realmente cumple con tus necesidades, puedes considerarlo.
- En comparación con [RAWVF](https://github.com/thefinerminer/minesweeper-rawvf): EVF es legible por máquinas, mientras que RAWVF es legible por humanos. Ningún jugador necesita convertir a RAWVF para reproducirlo, por lo que no hay razón para usar videos en RAWVF.

### Cadena de herramientas
El diseño del formato evf está respaldado por un sólido fondo de proyecto y por una completa cadena de herramientas de soporte. [Metasweeper](https://github.com/eee555/Metasweeper) es uno de los clones para obtener réplicas en formato evf; [ms-toollib](https://github.com/eee555/ms_toollib) ayuda a los desarrolladores a leer y analizar réplicas en evf y a convertir otros formatos a evf; [Flop New Player](https://github.com/eee555/flop-player) ayuda a los sitios de clasificación a reproducir réplicas en evf; además, [Open Minesweeper](https://openms.top) acepta réplicas en evf subidas por usuarios para clasificaciones globales.

Agradecimientos: 13688 (pruebas), ralokt (sugerencias), 9952 (sugerencias), 36 (sugerencias)

### Símbolos de tipo de operación definidos en esta especificación:
- mv: movimiento del ratón
- lc: presión de clic izquierdo
- lr: liberación de clic izquierdo
- rc: presión de clic derecho
- rr: liberación de clic derecho
- mc (no recomendado): presión de clic central (equivalente a doble clic)
- mr (no recomendado): liberación de clic central (equivalente a liberación de doble clic)
- pf (no recomendado): marcar minas antes de comenzar el juego. Algunas versiones no registran el proceso antes de comenzar el juego (es decir, antes del primer clic válido de liberación izquierdo), sino que registran directamente qué minas están marcadas. Esta operación no puede ser equivalente a "rc" + "rr" porque implica cómo contar los clics derechos. Por ejemplo, antes de comenzar el juego, si marcas una mina, luego repites marcar y desmarcar otra mina antes de comenzar el juego con un clic izquierdo, ¿cómo se cuenta el número de clics derechos durante todo el juego? En ms_toollib, el marcado pf registra right+1, flag+1, pero no es necesariamente preciso.
- cc (no recomendado): el archivo registra una presión de doble clic, pero no está claro qué botón se presionó, requiriendo que la máquina de estados finita del ratón en el analizador determine qué botón estaba activo en ese momento.
- l (no recomendado): presión o liberación de clic izquierdo, requiriendo que la máquina de estados finita del ratón en el analizador determine si es un clic o liberación.
- r (no recomendado): presión o liberación de clic derecho, requiriendo que la máquina de estados finita del ratón en el analizador determine si es un clic o liberación.
- m (no recomendado): presión o liberación de clic central, requiriendo que la máquina de estados finita del ratón en el analizador determine si es un clic o liberación.

### Términos definidos en esta especificación
- Resoluble, irresoluble: En esta especificación, "irresoluble" se refiere a la existencia de cualquier matriz pequeña irresoluble bajo el marco teórico de ["partición", "segmentación"](https://github.com/eee555/ms_toollib/blob/main/base/src/lib.rs#L10-L11), también conocido como irresolubilidad local. El opuesto es el estado "resoluble".
- Sin adivinaciones: El tablero "sin adivinaciones" debe cumplir las siguientes condiciones: (1) Después del primer clic, el tablero del juego sigue siendo resoluble. (2) Suponiendo que el tablero del juego es resoluble tras el nth clic, el tablero debe seguir siendo resoluble o ya haber ganado cuando se haga clic en cualquier posición no con mina posteriormente. (3) Al resolver el tablero del juego, no es necesario introducir el número total de minas como restricción.
- Sin adivinaciones estándar: Además de las condiciones de "sin adivinaciones", el tablero de "sin adivinaciones estándar" debe cumplir la condición de que: (1) La posición del primer clic es seleccionada por el jugador y debe garantizar que no sea una mina. (2) Cualquier tablero debe generarse mediante el método de filtrado, es decir, el algoritmo debe plantar minas de forma uniforme sin verificar, luego filtrar los tableros que cumplan con las restricciones.
- Sin adivinaciones estrictas: El algoritmo garantiza que el tablero del juego siempre sea resoluble durante la plantación de minas. Durante el juego, si el jugador hace clic en una posición que podría ser una mina, incluso si no lo es, el juego se pierde inmediatamente. Ejemplos de esta regla incluyen juegos móviles como Chocolate Sweeper
- "Juego débil sin adivinaciones": Aunque el algoritmo no garantiza que el tablero del juego siempre sea resoluble, sí puede determinar siempre si el tablero es irresoluble. Durante el juego, si el jugador encuentra un tablero irresoluble, el siguiente clic, independientemente de dónde sea, no provocará una pérdida. Sin embargo, si el jugador encuentra un tablero resoluble pero no hace clic en una posición no con mina, el juego terminará en pérdida. Ejemplos de esta regla incluyen [Kaboom](https://pwmarcz.pl/kaboom/).
- "Clásico sin adivinaciones": El algoritmo garantiza que el tablero del juego siempre sea resoluble. Durante el juego, incluso si el jugador hace clic en una posición que podría ser una mina, siempre que no lo sea, el juego continúa. Ejemplo de esta regla incluye [Simon Tatham's Mines](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/js/mines.html). Como el algoritmo no es un método de filtrado, no se considera "clásico sin adivinaciones".
- "Modo bendición": El algoritmo no garantiza que el tablero del juego siempre sea resoluble. Sin embargo, sí puede determinar siempre si el tablero es irresoluble. Durante el juego, incluso si el jugador encuentra un tablero irresoluble, el siguiente clic no provocará una pérdida. Ejemplo de esta regla incluye Freesweeper.
- "Sin adivinaciones pero adivinables": Aunque el algoritmo garantiza que siempre existe una solución en el tablero del juego, es posible adivinar dónde están las minas incluso cuando el tablero ya está determinado. Además, si una adivinación es incorrecta, y existe una probabilidad de que la casilla no sea una mina, el tablero se ajustará automáticamente para asegurar que dicha casilla realmente no sea una mina. Además, en los pasos siguientes, el tablero se ajustará continuamente para garantizar que no se requieran adivinaciones.
- "Modo de suerte": El algoritmo no garantiza que siempre exista una solución en el tablero del juego desde el inicio. Los jugadores pueden adivinar dónde están las minas según su deseo. Además, si una adivinación es incorrecta, y existe una probabilidad de que la casilla no sea una mina, el tablero se ajustará automáticamente para asegurar que dicha casilla realmente no sea una mina.

Los diferentes modos y sus nombres se pueden resumir como se muestra en el siguiente diagrama.
![](/evf-standard/mode_en.svg)

### v0.4 (Usado por Metasweeper 3.2.1)

Descripción del formato:

1. Longitud fija de 1 byte: Número de versión. En esta versión, es '\4'.
2. Longitud fija de 1 byte: Resumen. En escenarios de alta confianza, sirve para reducir la complejidad de la interpretación.
    - Longitud fija de 1 bit (2e7): Si la repetición ha finalizado. `1` indica que ha finalizado. El software atestigua que el juego ha terminado, es decir, que no se han tocado minas y que ningún valor (como el tiempo) ha sobrepasado su límite. No se garantizan otras condiciones.
    - Longitud fija de 1 bit (2e6): Si la repetición es oficial. `1` indica que es oficial. El software verifica que el juego es oficial y definitivamente completado, incluyendo que no se ha aplicado filtrado de 3BV por software, no se han usado funciones auxiliares, se ha jugado en modo estándar y no ha habido sobrepaso de valores. No necesariamente cumple con las restricciones adicionales de 3BV de los sitios de clasificación. (Este indicador es útil para sitios de clasificación de Buscaminas que solo soportan el modo estándar.)
    - Longitud fija de 1 bit (2e5): Si la repetición se completa de forma justa. `1` indica una conclusión justa. El software garantiza que el juego se finaliza de forma justa, definitivamente completado, por ejemplo, sin filtrado de 3BV por software, sin uso de funciones auxiliares y sin sobrecarga de valores. La diferencia entre un juego justamente completado y uno oficial es que solo el modo estándar puede ser oficial, mientras que modos como upk y no-guess pueden ser justamente completados pero no oficiales. Si es oficial, debe ser justamente completado. (Este indicador es beneficioso para los sitios de clasificación de Buscaminas que soportan múltiples modos.)
    - Longitud fija de 1 bit (2e4): Indica si se está realizando un barrido sin banderas (NF). Un valor de 1 significa que se está usando NF, equivalente a right_eff == 0; 0 en caso contrario.
    - Fijación de longitud 1 bit (2e3): Bandera de video transcodificado. `0` significa que este video no ha sido transcodificado; `1` significa que el video ha sido transcodificado, por ejemplo, un video evf obtenido al transcodificar un video avf o evf utilizando Meta Minesweeper.
    - Los bits restantes están reservados y todos establecidos en 0; pueden añadirse según las necesidades de los desarrolladores de sitios de clasificación y aplicaciones de estadísticas de puntuaciones.
3. Longitud fija de 1 byte: Configuraciones del juego. Estas configuraciones están diseñadas para ofrecer una conveniencia (o inconveniencia) adecuada al jugador, mientras que en general no afectan la formalidad ni la justicia de la puntuación.
    - Longitud fija de 1 bit (2e7): Indica si se desactivan los signos de interrogación. Un valor de 1 significa que están desactivados.
    - Longitud fija de 1 bit (2e6): El puntero del ratón no puede salir del borde. Un valor de 1 significa que no puede salir.
    - Longitud fija de 1 bit (2e5): Indica si está habilitada la reinicio automático al tocar una mina. Un valor de 1 significa que está habilitada.
    - Los bits restantes están reservados y establecidos en 0; pueden añadirse según las necesidades de los desarrolladores de clonadores.
4. Longitud fija de 1 byte, uint8: Número de filas, que varía entre 1 y 255, y filas × tamaño de casilla <= 32767.
5. Longitud fija de 1 byte, uint8: Número de columnas, que varía entre 1 y 255, y columnas × tamaño de casilla <= 32767.
6. Longitud fija de 2 bytes, uint16: Número de minas.
7. Longitud fija de 1 byte, uint8: Tamaño de casilla, que varía entre 5 y 255, y filas × tamaño de casilla <= 32767, columnas × tamaño de casilla <= 32767.
8. Longitud fija de 2 bytes, uint16: Modo de juego (símbolos y significados: 0->estándar, 1->upk; 2->cheat; 3->Densidad (de Viennasweeper), 4->win7, 5->Clásico sin adivinar, 6->Estricto sin adivinar, 7->Débil sin adivinar, 8->Modo bendición, 9->Sin adivinar y adivinable, 10->Modo suerte, 11->Apertura simultánea recursiva (recursiva estándar), 12->Recursiva con bandera, 13->Apertura simultánea con bandera recursiva, 14->Apertura simultánea sin adivinar recursiva, 15->Bandera sin adivinar recursiva, 16->Apertura simultánea con bandera sin adivinar recursiva, 65535 -> sin regla, el resto están reservados y pueden añadirse según las necesidades de nuevos desarrolladores de clonadores).
9. Longitud fija de 2 bytes, uint16: Valor de 3BV.
10. Longitud fija de 4 bytes, uint32: Tiempo real (rtime), en milisegundos.
11. Longitud fija de 2 bytes: Nombre o código de país o región. Usa el código de país o región en mayúsculas de dos letras del estándar ISO 3166-1:2020, permitiendo al reproductor de video mostrar correctamente la bandera del país o región.
12. Longitud fija de 8 bytes, uint64: Marca de inicio, que es el número total de microsegundos desde el 1 de enero de 1970, en tiempo medio de Greenwich, hasta el momento en que se realiza el primer clic izquierdo en una casilla no marcada.
13. Longitud fija de 8 bytes, uint64: Marca de finalización, que es el número total de microsegundos desde el 1 de enero de 1970, en tiempo medio de Greenwich, hasta el momento en que se abren todas las casillas no minas.
14. Cadena que termina con '\0', codificada en 'utf-8': La fuente original del grabado, incluyendo el nombre del software y la versión. Valores posibles incluyen "Arbiter", "0.97 beta", "Viennasweeper", "Meta 3.1.9", etc. Los sitios de clasificación deben verificar la fuente del grabado.
15. Cadena que termina con '\0', codificada en 'utf-8': solo presente en repeticiones transcodificadas: Nombre del software de transcodificación, incluyendo el nombre del software y la versión. Valores posibles incluyen "Meta 3.1.9", "Meta 3.1.11", "Meta 3.2", etc. Si está vacío, indica que esta repetición se generó directamente por el software en lugar de ser transcodificada.
16. Cadena que termina con '\0', codificada en 'utf-8': solo presente en grabaciones transcodificadas: Posibles métodos de codificación para el identificador de usuario, el identificador de competición y el identificador único de la grabación. Valores posibles incluyen 'utf-8', 'utf-16', 'utf-16-be', 'utf-16-le', 'gbk', 'gb2312', 'big5', 'shift-jis', 'cp932', 'latin-1', 'ascii', 'iso-8859-1', etc. Un valor vacío significa que es desconocido.
17. Cadena que termina con '\0', codificada en 'utf-8': Identificador de usuario (el usuario desea que el sitio web o software de clasificación muestre este identificador en la posición más destacada).
18. Cadena que termina con '\0', codificada en 'utf-8': Identificador de competencia (el usuario intente usar este registro como voucher para participar en una cierta competencia, pero no desea que el sitio/web de clasificación/muestra muestre este identificador).
19. Cadena que termina con '\0', codificada en 'utf-8': Identificador único (el usuario desea diferenciarse de otros usuarios con el mismo nombre, como apodo, ID del sitio de clasificación, provincia, correo electrónico, nombre en línea, lema, pero no desea que el sitio de clasificación o el software muestren este identificador).
20. Longitud fija de 2 bytes, uint16: Longitud del UUID.
21. Datos binarios de longitud variable: UUID relacionado con información del dispositivo, preferiblemente de 32 bits. Ten en cuenta que los desarrolladores deben proteger la privacidad del usuario.
22. El tablero ocupa ⌈filas × columnas / 8⌉ bytes. El bit `i × columnas + j` vale `1` si hay una mina en la fila `i` y la columna `j`, y `0` en caso contrario. Las filas y las columnas se numeran desde cero. Este tablero, donde `*` representa una mina, se codifica como `00110111 11110000`.

    ```text
    [[1, 3, *, *],
     [3, *, *, *],
     [*, *, *, *]]
    ```

23. Longitud fija de 2 bytes, uint16: Número de métricas personalizadas.
24. Lista de nombres de métricas personalizadas (estructura en bucle):
    - Cadena terminada en '\0', codificada en 'utf-8': Nombre de la clave.
25. Lista de eventos (estructura en bucle):
    - Longitud fija de 1 byte: Tipo de evento. Los eventos se clasifican en evento de ratón, evento de finalización, evento de tablero, evento de métrica y evento de pausa. Codificaciones de eventos de ratón: {1: "mv", 2: "lc", 3: "lr", 4: "rc", 5: "rr", 6: "mc", 7: "mr", 8: "pf", 9: "cc", 10: "l", 11: "r", 12: "m"}. Codificaciones de eventos de finalización: {81: "replay", 82: "win", 83: "fail", 99: "error"}. Codificaciones de eventos de tablero: {100: "cell_0", 101: "cell_1", 102: "cell_2", 103: "cell_3", 104: "cell_4", 105: "cell_5", 106: "cell_6", 107: "cell_7", 108: "cell_8", 110: "up", 111: "flag", 114: "cross mine", 115: "blast", 116: "mine", 118: "pressed", 120: "questionmark", 121: "pressed questionmark"}. Codificaciones de eventos de métrica: {200: "set key number value", 201: "set key string value"}. Codificación de evento de pausa: {255: "pause"}. El resto están reservados (excepto '\0').
    - Estructura del evento de ratón:
        - Longitud fija de 1 byte, uint8: Incremento del timestamp, en milisegundos. Comienza en 0 cuando se produce el primer clic izquierdo o derecho que afecte al tablero, y luego es la diferencia entre el timestamp siguiente y el anterior. Es decir, el timestamp del primer soltar del botón izquierdo en una celda no marcada no es necesariamente 0, y el timestamp de la última operación es mayor o igual que el tiempo real utilizado.
        - Longitud fija de 2 bytes, int16: Cambio en la distancia desde el borde izquierdo (en píxeles), que es el valor de la operación siguiente menos el anterior. El evento del tablero exterior se registra como la diferencia con `columns × cell size`.
        - Longitud fija de 2 bytes, int16: Cambio en la distancia desde el borde superior (en píxeles), que es el valor de la operación siguiente menos el anterior. El evento del tablero exterior se registra como la diferencia con `rows × cell size`.
    - Estructura de evento de estado del juego:
        - Longitud fija de 1 byte, uint8: Incremento del timestamp, en milisegundos.
    - Estructura de evento de estado del tablero:
        - Longitud fija de 1 byte, uint8: Incremento del timestamp, en milisegundos.
        - Longitud fija de 1 byte, int16: Cambio en la distancia desde el borde izquierdo (en celdas). La operación fuera del tablero desde el borde izquierdo se registra como "columnas".
        - Longitud fija de 1 byte, int16: Cambio en la distancia desde el borde superior (en celdas). La operación fuera del tablero desde el borde superior se registra como "filas".
    - Estructura de evento de métrica:
        - Longitud fija de 1 byte, uint8: Incremento del timestamp, en milisegundos.
        - Longitud fija de 2 bytes, uint16: Índice de la métrica (empezando en 0) + 10000.
        - Métrica numérica:
            - Longitud fija de 8 bytes, float64: Valor de la métrica.
        - Métrica de cadena:
            - Cadena que termina con '\0', codificada en 'utf-8': Valor de la métrica.
    - Estructura de evento de pausa:
        - Longitud fija de 2 bytes, uint16: Incremento del timestamp, en milisegundos.
26. '\0': Fin de la lista de eventos.
27. Longitud fija de 2 bytes, uint16: Longitud del checksum.
28. Datos binarios de longitud variable: Checksum.

### v0.3 (utilizado por Metasweeper 3.1.9, Metasweeper 3.1.11, Metasweeper 3.2.0)

Descripción del formato:

1. Longitud fija de 1 byte: número de versión. La versión descrita en esta especificación es '\3'.
2. Longitud fija de 1 byte: resumen. En escenarios de alta confianza, reduce la complejidad de la interpretación.

    > Longitud fija de 1 bit (2e7): Si el juego está completado, 1 significa completado. El software demuestra que el juego está completado, es decir, que no se han tocado minas y que no se han sobrepasado los valores. No se garantizan otras condiciones.

    > Longitud fija de 1 bit (2e6): Si es oficial, 1 significa oficial. El software demuestra que el juego es oficial, completado definitivamente, incluyendo que no se ha usado filtro 3BV, no se han usado funciones auxiliares, modo estándar y que no se han sobrepasado los valores. No es necesario cumplir con restricciones adicionales de 3BV para sitios de clasificación. (Este indicador es conveniente para sitios de clasificación que solo soportan el modo estándar de Buscaminas)

    > Longitud fija de 1 bit (2e5): Si es justo, 1 significa justo. El software demuestra que el juego se completó de forma justa, completado definitivamente, por ejemplo, sin usar filtro 3BV, sin usar funciones auxiliares y sin que se hayan sobrepasado los valores. Justo y oficial son diferentes: solo el modo estándar puede ser oficial, mientras que modos como upk, solvable, etc., no son oficiales pero pueden completarse de forma justa. Si es oficial, debe ser justo. (Este indicador es conveniente para sitios de clasificación que soportan múltiples modos)

    > Longitud fija de 1 bit (2e4): Si no tiene bandera (NF), 1 significa NF, equivalente a right == 0; 0 en otros casos.

    > Bits restantes reservados y establecidos en 0; añadidos según las necesidades de los sitios de clasificación y desarrolladores de aplicaciones de estadísticas de puntuaciones.
3. Longitud fija de 1 byte: configuraciones del juego. Estas configuraciones buscan proporcionar comodidad (o incomodidad) al jugador, mientras que son ampliamente reconocidas como no afectar la formalidad ni la justicia del puntaje.

    > Longitud fija de 1 bit (2e7): Si se desactivan los signos de interrogación, 1 significa desactivado.

    > Longitud fija de 1 bit (2e6): El puntero del ratón no puede salir del tablero, 1 significa que no puede salir.

    > Longitud fija de 1 bit (2e5): Si está habilitada la reinicio automático al perder, 1 significa habilitado.

    > Bits restantes reservados y establecidos en 0; añadidos según las necesidades de los desarrolladores de clonaciones.

4. Longitud fija de 1 byte: número de filas.
5. Longitud fija de 1 byte: número de columnas.
6. Longitud fija de 2 bytes: número de minas, en orden grande (big-endian).
7. Longitud fija de 1 byte: tamaño de la casilla.
8. Longitud fija de 2 bytes: modo de juego (símbolos y significados: 0->estándar, 1->upk; 2->trampa; 3->Densidad (del software Viennasweeper), 4->win7, 5->Clásico sin adivinaciones, 6->Estricto sin adivinaciones, 7->Débil sin adivinaciones, 8->Modo bendición, 9->Adivinable sin adivinaciones, 10->Modo suerte, 11->Apertura simultánea recursiva (recursiva estándar), 12->Bandera recursiva, 13->Apertura simultánea bandera recursiva, los restantes reservados, añadidos según las necesidades de nuevos desarrolladores de clonaciones), en orden grande (big-endian).
9.  Longitud fija de 2 bytes: valor 3BV, en orden grande (big-endian).
10. Longitud fija de 3 bytes: tiempo (rtime), en milisegundos, en orden grande (big-endian).
11. Cadena que termina con '\0': origen de la repetición. Por ejemplo, si proviene de Meta Minesweeper 3.1, será "Meta 3.1". Los sitios de clasificación deben verificar el origen de la repetición.
12. Cadena que termina con '\0': identificador del usuario (el usuario desea que el sitio de clasificación o el software lo muestre de forma destacada)
13. Cadena que termina con '\0': identificador de campeonato (el usuario desea usar este identificador como credencial para participar en un campeonato, pero no desea que el sitio de clasificación o el software lo muestre)
14. Cadena que termina con '\0': identificador único (el usuario desea diferenciarse de otros usuarios con el mismo nombre, como apodo, ID de saolei.wang, provincia, correo electrónico, nombre en línea, lema, pero no desea que el sitio de clasificación o el software lo muestre)
15. Cadena que termina con '\0': hora de inicio, recomendado usar los microsegundos totales desde el 1 de enero de 1970, en tiempo medio de Greenwich. La hora en que se libera el primer clic izquierdo en una casilla no marcada con bandera.
16. Cadena que termina con '\0': hora de finalización, recomendado usar los microsegundos totales desde el 1 de enero de 1970, en tiempo medio de Greenwich.
17. Cadena que termina con '\0': nombre o código de país o región. Se recomienda usar el código en mayúsculas de dos letras del estándar ISO 3166-1:2020 para que el jugador pueda mostrar correctamente la bandera nacional.
18. Cadena que termina con '\0': UUID relacionado con información del dispositivo, preferiblemente de 32 bits. Nota: los desarrolladores deben proteger la privacidad del usuario.
19. El tablero ocupa ⌈filas × columnas / 8⌉ bytes. El bit `i × columnas + j` vale `1` si hay una mina en la fila `i` y la columna `j`, y `0` en caso contrario. Las filas y las columnas se numeran desde cero. Este tablero, donde `*` representa una mina, se codifica como `00110111 11110000`.

    ```text
    [[1, 3, *, *],
     [3, *, *, *],
     [*, *, *, *]]
    ```

20. Formato de eventos del ratón (estructura en bucle):

    > Longitud fija de 1 byte: tipo de operación. 1: "mv"; 2: "lc"; 3: "lr"; 4: "rc"; 5: "rr"; 6: "mc"; 7: "mr"; 8: "pf"; 9: "cc"; 10: "l"; 11: "r"; 12: "m"; los restantes reservados (excepto '\0', '\255').

    > Longitud fija de 3 bytes: marca de tiempo, en milisegundos. Se registra a partir del primer clic izquierdo o derecho que afecte al tablero, como 0, luego se incrementa. La marca de tiempo del primer soltar clic izquierdo en una casilla no marcada puede no ser 0, y la marca de tiempo de la última operación es mayor o igual que el tiempo real utilizado. Orden big-endian.

    > Longitud fija de 2 bytes: distancia desde el borde izquierdo, en píxeles. La distancia de operaciones fuera del tablero se registra como "número de columnas × tamaño de casilla". Orden big-endian.

    > Longitud fija de 2 bytes: distancia desde el borde superior, en píxeles. La distancia de operaciones fuera del tablero se registra como "número de filas × tamaño de casilla". Orden big-endian.

21. Longitud fija de 1 byte: '\0' indica un checksum (generado directamente por el software); '\255' indica que no hay checksum (por ejemplo, traducido de archivos avf).

22. Longitud fija de 32 bytes: checksum, opcional.
