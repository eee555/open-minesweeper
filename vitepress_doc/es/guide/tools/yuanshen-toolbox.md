---
title: "Yuanshen Toolbox - Open Minesweeper"
description: "Yuanshen Toolbox es una herramienta de escritorio para Windows que lee los videos de evf de MetaSweeper y los de avf de Abit, cuenta los registros de PB y los resultados del frontend, determina NF/FL y sube las partidas completadas a Open Minesweeper."
---

# Yuanshen Toolbox

Yuanshen Toolbox es una herramienta de escritorio para Windows que lee localmente los videos de MetaSweeper (`.evf`) y de Abit (`.avf`).

El autor es un jugador de este sitio (Saolei.wang #27415, Open Minesweeper #3). **Esta es una herramienta de terceros, sin relación con Open Minesweeper, MetaSweeper ni Abit**: solo lee videos locales, solo utiliza interfaces públicas de este sitio y no sube ningún dato fuera de los videos.

## ¿Qué puede hacer?

Sube los registros de PB locales y los resultados del frontend a Open Minesweeper.

Otras funciones están en desarrollo, bienvenidos a proponer sugerencias.

## Descarga

Descarga la versión más reciente de `YuanshenToolbox.exe` (archivo único, aproximadamente 27 MB) desde [Releases](https://github.com/Corday-nkusky/yuanshen-toolbox/releases/latest). No requiere instalación, no necesita Python, simplemente haz doble clic para usarlo.

> El nombre del archivo en GitHub no soporta caracteres chinos, por lo que el archivo se llama `YuanshenToolbox.exe`; después de descargarlo, puedes cambiar el nombre libremente sin afectar su funcionamiento.

## Uso del programa

1. **Ubicación**: coloca el exe en el directorio `Metasweeper<versión>` de MetaSweeper, es decir, en el directorio superior al directorio `replay`. Si no sabes dónde está el `replay`, abre el menú de MetaSweeper «Ver → Directorio de repetición» (tecla rápida `W`) y vuelve un nivel arriba.
2. **Ejecuta**: haz doble clic para ejecutar. El programa prioriza leer el directorio `replay` junto al archivo exe; si no lo encuentra, buscará en `%APPDATA%` y `%LOCALAPPDATA%` todos los directorios que comiencen con `Metasweeper*`; si no encuentra ninguno, te pedirá que elijas manualmente el directorio. Una vez elegido, se guardará para futuras sesiones.
3. **Espera la primera escaneo**: la primera escaneo debe reproducir cada partida de forma secuencial, aproximadamente 20,000 partidas en 3 minutos, con una barra de progreso y tiempo restante; después se usa el caché para completar en segundos.
4. **Ve los resultados**: cambia entre pestañas: «Resumen / Tabla de PB / Resultados del frontend / Subida». Haz clic en la cabecera para ordenar, y haz doble clic en una fila para copiar la ruta completa del video.
5. **Sube** (opcional): en la pestaña «Subida», haz clic en «Iniciar sesión…», introduce tu nombre de usuario, contraseña y código de verificación, marca «Mantener sesión activa durante 90 días» para iniciar sesión una vez, y luego usarás la sesión guardada en el cookie. Elige el rango y haz clic en «Subir todo no enviado». Antes de subir aparecerá un cuadro de confirmación que muestre el nivel, estilo, hora y tamaño de esta serie.

El directorio de los videos de Abit **no se añade automáticamente**: para añadirlo, haz clic en «Ruta (N)…» y añádelo manualmente, asegurándote de que todos los videos sean tuyos y que estés de acuerdo en subirlos a Open Minesweeper.

## ¿Dónde se almacenan los datos?

Todo lo generado durante la ejecución se almacena en el directorio `元神工具箱-data\` dentro del mismo directorio del archivo exe: configuración de interfaz, credenciales cifradas, historial de subidas, caché de escaneo y registros. Borrar este directorio restaurará el estado inicial. Si el archivo exe se coloca en una ubicación no escribible (por ejemplo, `C:\Program Files`), se moverá automáticamente a `%APPDATA%\元神工具箱\`.

Las credenciales y el cookie de sesión se cifran con Windows DPAPI y se almacenan vinculadas al usuario actual y a la máquina local. No se puede abrir en otra máquina, y no hay texto plano en el archivo. Los registros no contienen contraseñas, códigos de verificación ni cookies.

## Preguntas frecuentes

| Situación                 | Solución                                           |
| ------------------ | -------------------------------------------- |
| Los resultados están mal calculados o acabo de jugar una nueva partida       | Haz clic en «Reescanear»; si sigue siendo incorrecto, en «Diagnóstico…» elimina el caché de escaneo y vuelve a escanear.                |
| Después de subir, el sitio muestra `d` (identificación no coincidente) | La identificación del video no coincide con la registrada en tu cuenta. Modifica la identificación según [Identificador de Saolei](../identifier.md) y vuelve a subirla. |
| La subida se interrumpió             | Las partidas ya subidas no se ven afectadas. Al recuperar la sesión, haz clic en «Reintentar fallo» para reenviar solo las que quedaron pendientes.                    |
| Quieres reportar un problema               | Haz clic en «Diagnóstico…» → «Exportar paquete de diagnóstico…», el archivo zip incluirá información del sistema, configuración y registros, pero no contiene datos cifrados de credenciales.    |

El código fuente se publica bajo licencia MIT. Los criterios de estadística, reglas de eliminación de duplicados y limitaciones conocidas se detallan en el README del repositorio.
