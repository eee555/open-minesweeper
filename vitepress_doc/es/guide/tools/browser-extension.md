---
title: "Extensión del navegador (Yuanshen Helper)"
description: "Instrucciones de instalación y uso para la extensión de navegador Yuanshen Helper, que incluye búsqueda de usuarios, análisis de resultados y subida automática de repeticiones."
---

# Extensión del navegador (Yuanshen Helper)

Yuanshen Helper es una extensión de navegador de terceros diseñada para los jugadores de [Open Minesweeper](https://openms.top), no es un producto oficial del sitio web.

- **Búsqueda de usuarios**: Busca jugadores mediante su nombre real en chino, nombre de usuario, nombre en inglés, pinyin o ID numérico.
- **Subida automática de repeticiones**: Monitorea la carpeta local de repeticiones y sube periódicamente los nuevos archivos.
- **Análisis de resultados**: Muestra la tabla de marcas personales (PB), los resultados del frontend y el «Gran cuadro cibernético», también puede analizar archivos CSV locales.

[Página del proyecto](https://github.com/LockhartANR/yuanshen-helper) · [Descargar la versión más reciente](https://github.com/LockhartANR/yuanshen-helper/releases/latest)

## Plataformas compatibles

Versión para escritorio de Chrome 120 o superior. Los navegadores Chromium como Edge suelen ser compatibles, aunque no han sido específicamente probados.

## Instalación y actualización

1. Obtén `yuanshen-helper-<versión>.zip` de la página de descarga superior, descomprímelo en un directorio fijo y luego no lo muevas ni elimines.
2. Introduce `chrome://extensions` en la barra de direcciones de Chrome y activa el modo de desarrollador en la esquina superior derecha.
3. Haz clic en «Cargar extensión descomprimida» y selecciona la carpeta descomprimida.
4. Haz clic en el icono de rompecabezas en la barra de herramientas del navegador para fijar «Yuanshen Helper» en la barra de herramientas.

Al actualizar, reemplaza el contenido de la carpeta con la versión nueva, entra en la página de administración de extensiones y haz clic en «Recargar». Luego, actualiza las páginas de análisis y las pestañas de openms.top que ya estén abiertas. La página de descarga incluye valores SHA-256 para verificar la integridad si es necesario.

## Uso del programa

1. **Sincronización inicial**: Haz clic en el icono de la extensión, luego en «Sincronizar» o «Sincronizar inmediatamente» y espera a que termine.
2. **Búsqueda de jugadores**: Introduce un fragmento de nombre o ID numérico, haz clic en el resultado para abrir la página principal del jugador. Se admiten `↑` / `↓` para seleccionar, `Enter` para abrir y `Esc` para cerrar.
3. **Análisis de resultados**: Haz clic en el botón de gráfico a la derecha del resultado de búsqueda o en «Mis resultados» en la parte superior de la ventana. Si se analizan archivos locales, haz clic en «Análisis de CSV local».
4. **Subida automática de repeticiones**: Inicia sesión en openms.top, abre la página de subida automática, haz clic en «Seleccionar carpeta» y permite el acceso a la carpeta de repeticiones. Elige entre «Solo subir nuevas repeticiones» o «Completar subida de repeticiones existentes», luego haz clic en «Empezar monitoreo».
5. **Configuración**: Haz clic en el icono de engranaje en la esquina superior derecha para gestionar la sincronización, activar/desactivar el acceso al «Gran cuadro cibernético» en el sitio, introducir tu ID personal o borrar los datos locales.

## Notas importantes

- Cerrar la página de subida o minimizar no detiene automáticamente el monitoreo; al finalizar el uso, haz clic en «Pausar». Si se cierran todos los ventanas del navegador, se cierra el navegador o se mueve/elimina la carpeta de repeticiones, el monitoreo se detiene. Después de reiniciar el navegador, debes volver a hacer clic en «Empezar monitoreo». Si hay problemas de inicio de sesión o de permisos, sigue las indicaciones en la página.
- Los datos de perfil del jugador, el análisis de resultados y los registros de subida se almacenan localmente en tu equipo. Una vez que se active la subida automática, las repeticiones se envían a openms.top y no a servidores de terceros.
- La extensión guarda información de identificación de usuarios del sitio en tu equipo. No la uses en computadoras compartidas y sigue las reglas del sitio.
