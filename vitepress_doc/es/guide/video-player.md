---
title: "Reproductor de vídeo - Open Minesweeper"
description: "Reproductor nativo de Open Minesweeper con contadores personalizados y estadísticas de repetición."
---

# Reproductor de vídeo

Open Minesweeper utiliza su reproductor nativo, que maneja automáticamente las repeticiones comprimidas en sitios web. Los botones de descarga guardan el archivo original de la repetición.

## Reproductor nativo

El reproductor nativo está integrado en el sitio web. Su tablero se renderiza mediante [`@putianyi888/vue3-minesweeper-board`](https://www.npmjs.com/package/@putianyi888/vue3-minesweeper-board) y las repeticiones se analizan mediante [`ms-toollib`](https://www.npmjs.com/package/ms-toollib). Además de la reproducción, soporta contadores personalizados usando la sintaxis `expr-eval`.

Consulta [Expresiones de repetición](./replay-expressions) para conocer los campos, operadores, expresiones condicionales y lógicas, funciones integradas y diferencias con los contadores del analizador y los eventos personalizados.
