---
title: "Guía del usuario de MetaSweeper"
description: "Descarga e instala MetaSweeper, migra las configuraciones y partidas anteriores, configura el juego y los contadores, y utiliza sus modos especiales y atajos de teclado."
---

# Guía del usuario de MetaSweeper

[MetaSweeper](https://github.com/eee555/Metasweeper) es una aplicación de Buscaminas de código abierto para Windows 10 y Windows 11.

Esta guía utiliza la interfaz y las capturas de pantalla del tutorial original 3.3.x. Los menús, opciones y directorios de datos pueden variar entre versiones. Puedes desplegar las capturas en chino que aparecen a continuación. Se agradecen capturas en español.

## Descarga e instalación

### Descarga y ejecuta

Descarga el instalador desde la página de [versiones de GitHub](https://github.com/eee555/Metasweeper/releases), que también lista versiones anteriores. También puedes visitar la página del proyecto en [Gitee](https://gitee.com/ee55/Metasweeper).

Haz doble clic en el instalador. Si Windows muestra una aplicación no reconocida, confirma que el archivo proviene de la página de versiones del proyecto, luego haz clic en **Más información** (更多信息).

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-1.png" alt="More info in the Windows SmartScreen prompt" width="600" />
</details>

Haz clic en **Ejecutar de todos modos** (仍要运行).

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-2.png" alt="Run anyway in the Windows SmartScreen prompt" width="600" />
</details>

Elige el idioma para el instalador.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-3.png" alt="Choose the installer language" width="600" />
</details>

Elige un directorio de instalación. Si tienes una instalación anterior de Metaminesweeper, elige un directorio diferente.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-4.png" alt="Choose the MetaSweeper installation directory" width="600" />
</details>

Elige las asociaciones de archivos. Los tipos de archivos seleccionados se abrirán por defecto en MetaSweeper.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-5.png" alt="Choose replay file associations" width="600" />
</details>

Elige si crear un atajo en el escritorio.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-6.png" alt="Choose whether to create a desktop shortcut" width="600" />
</details>

Revisa las opciones y haz clic en **Instalar**.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-7.png" alt="Review the installation options" width="600" />
</details>

Haz clic en **Finalizar** cuando la instalación esté completa.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/install-8.png" alt="MetaSweeper installation complete" width="600" />
</details>

### Migración desde una versión anterior

Para conservar las configuraciones y partidas de una instalación anterior de MetaMineSweeper, copia el directorio `replay` y los archivos `gameSetting.ini`, `record.ini` y `scoreBoardSetting.ini`. Pégalos en el directorio de datos de la nueva versión, reemplazando los archivos y directorio correspondientes.

En versiones 3.2.0 y anteriores, estos archivos y el directorio están dentro del directorio de instalación, por ejemplo `D:\SomePath\Metasweeper\`.

A partir de la versión 3.2.1, la ubicación de los datos depende de si el directorio de instalación es escribible:

| Directorio de instalación | Ubicación de datos |
| --- | --- |
| Escribible, como un directorio normal en D, E o F | El directorio de instalación, por ejemplo `D:\SomePath\Metasweeper\`. |
| No escribible, como un directorio de sistema protegido | El directorio de datos de la aplicación del usuario, por ejemplo `C:\Users\username\AppData\Roaming\MetaMineSweeper3.2.1\`. El nombre final del directorio varía según la versión. |

Si la migración aún falla, reporta el problema a través de [Issues de GitHub](https://github.com/eee555/Metasweeper/issues) o [Issues de Gitee](https://gitee.com/ee55/Metasweeper/issues).

## Configuración del juego

Abre **Configuración → Configuración del juego** (设置 → 游戏设置) o presiona `S`. Las configuraciones se guardan en `gameSetting.ini`.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/settings.png" alt="MetaSweeper game settings in Chinese" width="600" />
</details>

### Opciones básicas

| Opción | Significado |
| --- | --- |
| Tamaño de la casilla (longitud del lado del cuadrado) | Medido en píxeles, con un mínimo de 5. |
| Identificador del jugador (identificación) | La identidad del jugador que se muestra debajo del tablero durante la reproducción de partidas, normalmente un nombre o apodo. |
| Identificador de torneo (identificación de competición) | Una credencial para participar en torneos, normalmente proporcionada por el organizador al comenzar el torneo. No se muestra como identificador público del jugador. |
| Identificador personal o de unicidad (identificación personal o identificación de unicidad) | Información adicional que distingue a los jugadores con el mismo nombre, como un apodo, ID de Minesweeper.cn, provincia, dirección de correo electrónico o lema. No se muestra como identificador público del jugador. |
| País o región (País o región) | Soporta autocompletado. Por ejemplo, al escribir 宁 en la interfaz en chino, se muestra 贝宁 (Benin). Seleccionar un país también establece su bandera. |
| Marcar minas después del juego (Marcar minas después del juego) | Muestra todas las posiciones de las minas al finalizar un juego. Elige según tus preferencias. |
| Mantener el cursor dentro del borde (El cursor no puede salir del borde) | Restringe el cursor al borde tras comenzar un juego. |

Consulta [Identificadores de jugador](../identifier.md) para gestionar los identificadores de jugador y de torneo en Open Minesweeper.

### Guardado automático de repeticiones

Con **Guardado automático de repeticiones** (Guardar automáticamente las repeticiones) activado, cada juego ganado se guarda en `replay`, independientemente del modo o de la elegibilidad para clasificaciones. Los juegos perdidos deben guardarse manualmente.

Con **Guardado automático de conjuntos de repeticiones** (Guardar automáticamente los conjuntos de repeticiones) activado, los conjuntos `.evfs` se guardan en `replay`, registrando victorias, derrotas y reinicios. Cambiar el país, el identificador del jugador, el identificador del torneo o el identificador de unicidad reinicia el progreso del conjunto. Desactiva esta opción si no necesitas estadísticas como tasa de victorias o victorias consecutivas y deseas ahorrar espacio en el disco.

### Generación de tableros sin adivinanzas

Con **Siempre usar filtrado para colocar minas** (Siempre usar filtrado para colocar minas) activado, los tableros sin adivinanzas se obtienen siempre mediante filtrado de tableros candidatos. En densidades altas de minas, esto puede aumentar considerablemente el tiempo de generación o agotar los recursos computacionales.

### Reinicio automático

Normalmente, al tocar una mina se requiere un clic adicional para reiniciar. Activa **Reinicio automático** (Reinicio automático) y establece un porcentaje de finalización para que comience automáticamente el siguiente juego cuando toques una mina antes de alcanzar ese porcentaje.

### Notificaciones de récord personal

Con **Permitir notificaciones de récord** (Permitir notificaciones de récord) activado, aparece un cuadro cuando se rompe un récord personal. Los récords incluyen `rtime`, `3BV/s`, `STNB`, `IOE`, `path`, y `rqp` en niveles Principiante, Intermedio y Experto en modos como Estándar, Estándar NF, Win7, Fuerte sin adivinar, Débil sin adivinar, Veloz sin adivinar, Quasi sin adivinar, Fuerte adivinable y Débil adivinable, así como los tiempos personales más rápidos en modo Estándar.

Los récords se almacenan en `record.ini`. Editar sus valores cambia el momento en que aparecen las notificaciones de récord.

### Restricciones de tablero y límite de intentos

Las restricciones de tablero filtran tableros específicos para entrenamiento. **Las repeticiones generadas con cualquier restricción de tablero no son elegibles para clasificaciones.**

Las restricciones usan sintaxis de expresiones en Python y deben devolver un valor booleano.

Variables disponibles: `bbbv`, `op`, `isl`, `cell0`, `cell1`, `cell2`, `cell3`, `cell4`, `cell5`, `cell6`, `cell7`, `cell8`.

Funciones disponibles: `sin`, `cos`, `tan`, `log`, `len`, `abs`, `max`, `min`, `all`, `any`, `sum`, `divmod`, `pow`, `round`, `bool`, `float`, `int`.

Ejemplos válidos:

```python
bbbv < 120
(cell8 < cell7 or cell3 > 5) and cell0 == 14
sin(3.14 / 3) <= cell0 / cell1 - 2
cell2**2 == 25 * abs(1j * 1j)
all([cell8 > 1, cell7 > 2, cell6 > 3])
```

**Límite de intentos** (Número de intentos) establece la cantidad máxima de intentos para colocar minas que se usan para satisfacer la restricción.

## Colocación de minas

Sin restricciones adicionales, el algoritmo de colocación de minas no excluye tableros extremadamente simples. Por lo tanto, es posible que se generen tableros con `3BV = 1`.

## Contadores

La ventana del contador tiene varias filas y dos columnas. Cada fila contiene un indicador: su nombre en la primera columna y su valor en la segunda. La configuración se guarda en `scoreBoardSetting.ini`.

<details>
    <summary>Ver captura de pantalla en chino</summary>
    <img src="/metasweeper/counters.png" alt="MetaSweeper counters and an editable formula" height="550" />
</details>

- Haz doble clic en la primera columna para editar el nombre de un indicador. Para eliminar una fila, borra su nombre y haz clic en otro lugar.
- Haz doble clic en la segunda columna para editar su fórmula.
- Mueve el puntero al final de la ventana del contador y haz clic en el botón **+** para añadir una fila.

Las fórmulas usan sintaxis de expresiones en Python y deben devolver una cadena, un entero o un número decimal.

Variables disponibles: `time`, `row`, `column`, `minenum`, `left`, `right`, `double`, `cl`, `lce`, `rce`, `dce`, `left_s`, `right_s`, `double_s`, `cl_s`, `ce_s`, `path`, `flag`, `flag_s`, `rtime`, `etime`, `bbbv_solved`, `bbbv_s`, `bbbv`, `op`, `isl`, `zini`, `hzini`, `ioe`, `thrp`, `corr`, `ce`, `mode`, `pluck`, `is_official`, `is_fair`, `stnb`, `qg`, `rqp`, `max_block_len`.

Las funciones disponibles son las mismas que para las restricciones del tablero. Ejemplos de fórmulas:

```python
f'{bbbv_solved}/{bbbv}'
f"ce/s is: {ce / time:.3}"
checksum_ok and is_fair
'Concatenating strings with addition: ' + f"{isl}"
```

## Modo de transmisión

Empieza el identificador del jugador con `[live]` para entrar en modo de transmisión. Por ejemplo, cambia `Player` a `[live]Player`. Activa este modo cuando estés transmitiendo. Aparte del identificador, sus repeticiones son iguales a las producidas en modo normal.

## Modo de retraso

Si un ordenador lento desencadena frecuentemente reinicios por antifraude, empieza el identificador del jugador con `[lag]`, por ejemplo `[lag]Player`, para entrar en modo de retraso con límites más flexibles. Aparte del identificador, sus repeticiones son iguales a las producidas en modo normal.

## Modo de estudio

Pulsa `Ctrl+Space` para capturar un tablero de Buscaminas; también se puede usar una imagen de tablero. Si la reconocimiento óptico del tablero es exitoso, se abre el modo de estudio y se muestra la probabilidad de que cada casilla no abierta contenga una mina.

## Atajos de teclado

| Atajo o acción | Función |
| --- | --- |
| `1`, `2`, `3`, `4`, `5`, `6` | Alternar entre los modos Principiante, Intermedio, Experto y personalizado (4, 5, 6 respectivamente). |
| `F1` | Abrir el gestor de plugins. |
| `F2`, `N` | Empezar un nuevo juego. |
| `F3` | Reproducir el tablero anterior como un juego. |
| `B`, `I`, `E`, `C` | Alternar entre los modos Principiante, Intermedio, Experto o Personalizado respectivamente. |
| `R` | Reproducir la repetición del juego anterior. |
| `Ctrl+S` | Guardar la repetición actual, o guardar la repetición que estás reproduciendo como un archivo `.evf`. |
| `Ctrl+C` | Antes de un juego, después de ganar o perder, durante la reproducción de una repetición o en modo de estudio, copia el tablero actual como una matriz numérica o como datos en emojis/ASCII renderizados en un archivo `.board` o como un archivo. |
| `Ctrl+V` | Antes de un juego, después de ganar o perder, durante la reproducción de una repetición o en modo de estudio, pega un tablero y entra en modo de estudio. |
| `Ctrl+Space` | Accede al modo de estudio capturando un tablero. |
| `Space` | Durante un juego, mantén presionado para ver las probabilidades de minas en las casillas no abiertas. Durante la reproducción de una repetición, pulsa una vez para mostrarlas y de nuevo para ocultarlas. |
| `/` | Mostrar o ocultar la ventana del contador. |
| `S` | Ajustes del juego. |
| `Z` | Ajustes de atajos. |
| `O` | Abrir una repetición o un conjunto de repeticiones. |
| `A` | Acerca de. |
| `M` | Ajustes del ratón. |
| Mantén presionado `Ctrl` y rueda el ratón antes de comenzar un juego | Aumentar o disminuir el tamaño de la casilla. |
| Rueda el ratón sobre el número de minas en la esquina superior izquierda antes de comenzar un juego | Cambiar rápidamente el número de minas. |
| Rueda el ratón sobre el número de velocidad de reproducción durante la reproducción de una repetición | Cambiar la velocidad de reproducción. |
| `Ctrl+X` | Salir. |
