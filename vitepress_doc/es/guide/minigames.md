---
title: "Juegos pequeños - Open Minesweeper"
description: "Reglas, tiempo, repeticiones, clasificaciones y juego offline para clic izquierdo, multi-touch, bandera y apertura simultánea y entrenamiento de casilla faltante."
---

# Minijuegos

[Juega a los juegos pequeños](https://openms.top/#/minigame) · [Ver clasificaciones](https://openms.top/#/ranking/minigame)

Estos juegos practican clics, colocación de banderas, aperturas simultáneas y observación. Cada uno tiene sus propias reglas y tiempo:

| Entrenamiento | Objetivo | El temporizador comienza |
| --- | --- | --- |
| Clic izquierdo | Haz clic en cada casilla segura individualmente | En el primer lanzamiento válido del botón izquierdo |
| Multi-touch | Toca cada casilla segura | Al primer contacto inicial |
| Bandera y apertura simultánea | Coloca bandera y apertura simultánea en cada duda | Al primer colocación exitosa de bandera |
| Casilla faltante | Encuentra la casilla segura faltante en 10 tableros consecutivos | Al primer lanzamiento del botón izquierdo, revelando el tablero 1 |

## Entrenamiento de clic izquierdo

Elige Principiante **8×8**, Intermedio **16×16** o Experto **16×30**, cada uno con una densidad de minas de **1/2, 3/4 o 7/8**, para un total de 9 modos.

Solo con ratón. Las minas están visibles, por lo que puedes inspeccionar el tablero antes de comenzar. Cada liberación del botón izquierdo abre solo la casilla segura seleccionada, sin apertura en cadena. Hacer clic en una mina pierde; abrir todas las casillas seguras detiene el temporizador. Los clics derechos y las aperturas simultáneas no tienen efecto.

Las casillas con minas tienen por defecto el estado elevado, con 50% de opacidad de mina. Ambos pueden ajustarse en las configuraciones del juego pequeño.

## Entrenamiento de multi-touch

Utiliza los mismos tamaños, densidades de minas y reglas de victoria/perder que el entrenamiento de clic izquierdo, pero **solo acepta entrada por pantalla táctil**. Puedes inspeccionar el tablero antes de comenzar. El primer contacto inicial activa el temporizador; cada dedo abre su casilla actual al tocarla. Mover o levantar un dedo no abre nada. No hay vista previa de la casilla presionada. Los contactos funcionan de forma independiente, y es posible jugar con un solo dedo.

La opacidad de las minas y el estado de la casilla presionada o elevada se comparten con el entrenamiento de clic izquierdo.

Arrastra con un solo dedo para desplazar el tablero y las páginas, sin detenerse en los bordes del tablero. El desplazamiento se detiene mientras se mantengan dos o más contactos. Ajusta el umbral de desplazamiento en las configuraciones del juego pequeño (0px por defecto); el desplazamiento comienza solo cuando un dedo se mueva más allá de este umbral, por lo que movimientos leves al tocar no desplazan la vista. En el modo Experto se ofrece horizontalmente **16 filas × 30 columnas** o verticalmente **30 filas × 16 columnas**. La orientación se guarda localmente; cambiarla conserva el juego actual y la repetición.

Pantalla completa elimina los marcos del tablero y el espacio circundante. Usa los botones más y menos del panel para ajustar el tamaño de la casilla sin activar el teclado en pantalla, que saldría del modo pantalla completa. La página de configuraciones aún acepta un valor exacto; ambos valores se comparten y guardan, sin redimensionamiento automático. Desplázate horizontal y verticalmente cuando sea necesario. Los contadores en pantalla completa son solo de visualización; usa el botón de reinicio del panel para comenzar un nuevo juego. Cambiar el tamaño o salir de pantalla completa conserva el juego actual y el tamaño de la casilla; salir restaura la acción de reinicio del contador.

## Entrenamiento de bandera y apertura simultánea

Principiante tiene **4 dudas en 8×8**; Intermedio tiene **15 en 16×16**. Cada número es **1**, con una mina adyacente visible. Cada duda ocupa su propio área no superpuesta de 3×3.

Haz clic derecho para colocar una bandera en la mina, luego usa un [clic clásico](./minesweeper/mouse-event) en el número: mantén presionados ambos botones del ratón y **libera cualquiera de ellos para activar**. Al abrir sus vecinos seguros, se completa la duda. El temporizador se detiene cuando se complete la última duda.

Haz clic derecho nuevamente para quitar una bandera incorrecta. Si el número de banderas no coincide, la apertura simultánea no tiene efecto; si el número coincide pero la bandera está en el lugar equivocado, pierdes. Los clics simples izquierdos no abren casillas.

## Entrenamiento de casilla faltante

Los niveles principiante, intermedio y experto usan **8×8 con 10 minas**, **16×16 con 40** y **16×30 con 99** respectivamente. El primer clic solo inicia la partida: su liberación con el botón izquierdo revela la casilla 1 y comienza el cronómetro.

Cada casilla segura, excepto una, ya está abierta. El objetivo y las minas están cubiertos, y los números visibles identifican únicamente al objetivo. No tiene casilla adyacente abierta con cero, pero puede ser cero mismo.

Haz clic en el objetivo para revelar el siguiente tablero de inmediato. Completa **10 tableros consecutivos** para detener el cronómetro; tocar una mina pierde toda la partida. Los clics con el botón derecho, las aperturas simultáneas y los clics en casillas abiertas no tienen efecto.

## Entrenamiento de reacción

El entrenamiento de reacción comienza en cualquiera de los extremos de cada línea. Sigue los números en esa dirección, saltando solo una mina conocida. Clicar en casillas abiertas o en la fila de banderas no tiene efecto; clicar en una mina saltada o en otra posición incorrecta pierde. Cada clic avanzado determina la siguiente casilla con una probabilidad del 25% o del 50% de ser una mina. Una casilla segura justo antes de la última siempre fuerza una mina final.

Los tableros son horizontales. El nivel principiante, intermedio y experto usan 5, 10 y 20 casillas por línea y requieren 10, 20 y 40 reacciones respectivamente; el primer clic de cada línea no cuenta. El cronómetro comienza con la liberación y continúa entre líneas. Los clics con el ratón izquierdo y el toque activan al liberar; los clics con el botón derecho y las aperturas simultáneas no tienen efecto. Los juegos exitosos guardan el historial local, accesible mediante el marcador en la esquina superior derecha para repetición. En el sitio web, sube manualmente tus puntuaciones a seis clasificaciones que cubren tres niveles y dos probabilidades. El ratón y el toque comparten estas clasificaciones.

Después de un éxito, el primer gráfico muestra cada reacción como dos intervalos superpuestos: desde la liberación anterior hasta el clic, y desde el clic hasta la liberación. Pasa el ratón para ver las tres fechas, las longitudes de los intervalos y su total; el indicador de progreso y la vista previa del tablero muestran el tiempo de liberación. Moverse lejos restaura la posición y el estado de juego anterior. A continuación, los histogramas izquierdo y derecho muestran los intervalos de liberación a liberación para clics adyacentes y de salto de una casilla, ambos usando intervalos de 0.01 segundos. El primer clic de cada línea se excluye. Pasa el ratón sobre un intervalo para resaltar sus reacciones en el gráfico anterior. Los clics ineficaces se omiten de los registros. Una vez que comienza el cronómetro, su tiempo transcurrido sigue contando hacia el total.

## Reiniciar y configuraciones

El contador en la esquina superior izquierda muestra clics o preguntas restantes; el contador en la esquina superior derecha tiene como valor por defecto los segundos con tres decimales. Fuera del modo completo, **clic en cualquier parte del contador para reiniciar**, o enfoque con Tab y presiona Enter o Espacio.

Haz clic izquierdo y toque múltiple para entrenar y obtén **Tiempo / CES** en ajustes locales y mediante el botón de texto en la esquina superior izquierda de la tabla completa de clasificaciones. `CES = CE / elapsed seconds`, donde CE cuenta los clics exitosos **excluyendo el primero**. Esto cambia el contador en la esquina superior derecha y la tabla completa de clasificaciones; las repeticiones usan la posición actual de reproducción. Los cuadros de clasificación y de historial local siempre muestran ambas puntuaciones, y cada columna es ordenable en el historial local.

Las configuraciones compartidas de tamaño de casilla y tecla de reinicio están disponibles debajo de los juegos y en la sección de configuraciones de Minigames del sitio web. El tamaño de casilla tiene como valor por defecto 32px y acepta un entero positivo; la tecla de acceso está desactivada. El entrenamiento con clic izquierdo y multi-toque comparte la opacidad de las minas y las configuraciones de casilla con mina presionada o levantada. Las preferencias se guardan en este navegador; el estado de la casilla de mina se excluye de los registros. Cambiar estos ajustes de visualización mantiene el juego actual, y las repeticiones usan los ajustes de visualización actuales. Cambiar el nivel o los parámetros del juego inicia un nuevo juego.

## Repeticiones y análisis

Después de finalizar el entrenamiento con clic izquierdo o con bandera y apertura simultánea, la repetición debajo del tablero muestra el rastro del ratón. Juega, pausa o arrastra el indicador de progreso; la reproducción se detiene al final.

Las repeticiones multicontacto usan los mismos controles de reproducción, mostrando un camino separado para cada contacto y marcadores para los dedos que están presionados actualmente. Los contactos diferentes nunca se conectan en una sola trayectoria.

- **Clic izquierdo:** las velocidades del ratón y el clic usan un ventana de un segundo traslado, medido en celdas/s y clics/s. El histograma mostrado abajo muestra los intervalos de presión y liberación del botón izquierdo, excluyendo el primer clic, en intervalos fijos de 0.01 segundos.
- **Bandera y apertura simultánea:** los gráficos muestran la velocidad del ratón durante un ventana de un segundo traslado y descomposiciones de timing para preguntas exitosas. La parte inferior de cada barra va desde la última colocación de bandera de esa pregunta hasta el clic izquierdo; la parte superior va desde ese clic hasta la apertura exitosa. Las aperturas fallidas e ineficaces se excluyen.

Pasa el ratón sobre el gráfico de velocidad para revisar los valores y el tablero en ese momento. Pasa sobre una barra de timing de bandera y apertura simultánea para localizar esa operación exitosa y marcarla en el gráfico de velocidad. Alejarse restaura el estado anterior de la repetición.

Después de completar con éxito una secuencia de 10 tableros sin celdas faltantes, los gráficos muestran el tiempo de cada tablero y una descomposición acumulada del tiempo total. Pasa el ratón sobre una barra o segmento para revisar ese tablero con su objetivo resaltado. El contador de la izquierda muestra cuántos tableros quedan en ese momento; el de la derecha muestra el tiempo de ese tablero. Alejarse restaura la vista final.

## Clasificaciones y resultados locales

Los dos marcadores en la esquina superior derecha abren clasificaciones y historial local. También puedes cambiar entre ellos en la parte superior del mismo panel. Las clasificaciones muestran los 20 mejores resultados actuales y tu posición cuando estés conectado. El panel se abre debajo de la barra de navegación y deja interactivo el resto de la página. Cambiar el nivel o la densidad selecciona su clasificación; una subida exitosa la actualiza automáticamente.

Después de completar un juego con éxito, haz clic en **Subir puntuación y repetición** debajo del tablero para enviarlo mientras estés conectado y no estés prohibido. **No se requiere nombre real, perfil de Buscaminas ni cuenta vinculada.** Cada modo conserva tu mejor tiempo personal y su repetición. Elige **Clasificaciones completas** en la parte inferior del panel para abrir la página de clasificaciones de este juego. Haz clic en una columna de puntuaciones para ordenarlas, o pasa el ratón sobre una puntuación para ver cuándo fue alcanzada. **Haz clic en una puntuación para ver su repetición**, sin necesidad de estar conectado. Las repeticiones en línea usan la misma interfaz y configuración local que tus juegos completados, inicialmente pausadas al final. Reinicia o cambia los parámetros del juego para comenzar un nuevo juego.

Todos los cinco juegos guardan los resultados exitosos en este navegador para su reproducción desde el historial local. El historial local muestra los resultados exitosos para el juego y la configuración actuales, actualizándose cuando cambies la configuración. Los resultados están ordenados por más reciente. Filtra además por rango de fechas, haz clic en la cabecera de tiempo para alternar orden ascendente o descendente, y haz clic en una fila para reproducir su repetición. No se requiere inicio de sesión, y ver ni guarda otro resultado ni sube una puntuación. Los juegos fallidos o incompletos no se guardan. Todavía no están disponibles las descargas de repeticiones. Reiniciar borra la vista actual mientras conserva los juegos exitosos guardados; borrar los datos del sitio del navegador elimina los registros locales.

## Juego offline

Elige **Descargar versión offline** en una página de juego, extrae el ZIP y abre `index.html` en Chrome o Edge para jugar sin conexión. La versión offline soporta ajustes, resultados guardados y navegación por historial. Abre el atajo de historial en la esquina superior derecha para filtrar los resultados de la configuración actual por fecha, ordenar por tiempo y hacer clic en una fila para repetir la partida. **No sube ni puntuaciones ni repeticiones**, y sus registros locales pueden ser distintos de los del sitio web.
