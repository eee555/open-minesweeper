---
title: "Software de Buscaminas - Open Minesweeper"
description: "Software de Buscaminas y formatos de repetición soportados en Open Minesweeper, incluyendo EVF, RMV, AVF, MVF y reglas de elegibilidad para repeticiones."
---

# Software de Buscaminas

Open Minesweeper actualmente soporta los formatos de repetición `EVF`, `RMV`, `AVF` y `MVF`. `EVF` y `RMV` son formatos generales para repeticiones de Buscaminas, `AVF` es específico para Minesweeper Arbiter y `MVF` es específico para Minesweeper Clone.

Si deseas que Open Minesweeper soporte más software de Buscaminas, puedes elegir generar archivos `EVF` o `RMV`, o ayudar a que `ms-toollib` soporte tu formato personalizado.

Consulta la [Guía del usuario de MetaSweeper](./minesweeper/metasweeper.md) para la instalación, configuraciones y atajos de teclado.

## Elegibilidad para repeticiones

Para garantizar la equidad, Open Minesweeper solo acepta repeticiones de Buscaminas jugadas bajo reglas específicas.

### Características no tradicionales no soportadas

- No se soporta el doble clic con el botón izquierdo.
- No se soporta el chording recursivo.
- Las repeticiones deben contener los caminos completos del ratón. No se soportan las repeticiones en pantallas táctiles.

### Características no tradicionales soportadas

- Bloqueo del ratón dentro de los bordes. Esta función fue introducida primero por Minesweeper Arbiter y puede mejorar significativamente los tiempos de principiantes. MetaSweeper también la soporta ahora. Aunque afecta la equidad, en la práctica mejora la competitividad y el entretenimiento del nivel de principiantes. Además, otros programas como [Magpie](https://github.com/Blinue/Magpie) pueden bloquear el ratón dentro de cualquier región rectangular, por lo que también puedes usar este comportamiento con otros software.

## Preguntas frecuentes {#faq}

### ¿Por qué no se soportan las repeticiones en pantallas táctiles?

Sabemos que hay muchos jugadores de Buscaminas en pantallas táctiles, pero las repeticiones en pantallas táctiles hacen mucho más difícil la detección de trampas. No incluyen el movimiento de la mano; solo muestran que el cursor se mueve al azar, lo cual puede ser difícil de distinguir de un juego automatizado. Los caminos del ratón son evidencia clave para determinar si la operación fue realizada por una persona real.

### ¿Por qué no se soporta el doble clic con el botón izquierdo?

Históricamente, el chording en Buscaminas significaba presionar al mismo tiempo los botones izquierdo y derecho. El doble clic con el botón izquierdo fue inventado para apoyar el uso de Buscaminas en pantallas táctiles. Al usarlo con un ratón, es más fácil y más tolerante que el chording tradicional izquierdo-derecho, por lo que es injusto en la misma clasificación.
