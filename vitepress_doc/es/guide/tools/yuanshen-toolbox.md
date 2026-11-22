---
title: "Yuanshen Toolbox - Open Minesweeper"
description: "Yuanshen Toolbox es una herramienta de escritorio para Windows que lee localmente las repeticiones evf de MetaSweeper y avf de Minesweeper Arbiter, registra PB, práctica diaria y LSF, y sube los resultados a Open Minesweeper de forma manual o automática."
---

# Yuanshen Toolbox

Yuanshen Toolbox (元神工具箱) es una herramienta de escritorio para Windows que lee en tu propio equipo las repeticiones de MetaSweeper (`.evf`) y de Minesweeper Arbiter (`.avf`), registra tus PB, tu práctica diaria y tu LSF, y sube los resultados a Open Minesweeper.

El autor es un jugador de este sitio (Saolei.wang #27415, Open Minesweeper #3). **Es una herramienta de terceros, sin relación con Open Minesweeper, MetaSweeper ni Minesweeper Arbiter**: solo lee repeticiones locales, solo utiliza las interfaces públicas de este sitio, no sube ningún dato más allá de las propias repeticiones y nunca modifica ni elimina archivos de repetición.

La interfaz está actualmente solo en chino; esta página muestra las etiquetas chinas con su significado en español.

## Descarga

Descarga la última versión de `YuanshenToolbox.exe` (archivo único, unos 27 MB) desde [Releases](https://github.com/Corday-nkusky/yuanshen-toolbox/releases/latest). Sin instalación y sin Python: haz doble clic para usarlo.

El nombre del archivo es fijo y no lleva número de versión: para actualizar, sobrescribe el archivo en su sitio y los accesos directos del escritorio siguen funcionando. La versión actual aparece en el título de la ventana.

## Primer inicio

1. **Colócalo**: pon el exe en la carpeta `Metasweeper<versión>` de MetaSweeper, junto a `replay`. Si no sabes dónde está `replay`, abre el menú de MetaSweeper 查看 → 录像目录 (Ver → Carpeta de repeticiones, tecla `W`) y sube un nivel.
2. **Ejecútalo**: haz doble clic. El programa lee primero la carpeta `replay` junto al exe; si no existe, busca todos los `Metasweeper*` en `%APPDATA%` y `%LOCALAPPDATA%`; solo si no encuentra nada te pide elegir una carpeta una vez, y la recuerda.
3. **Espera el primer escaneo**: el primer escaneo reproduce cada partida — unos 3 minutos para 20 000 partidas, con progreso y tiempo restante en la parte inferior. Los escaneos posteriores usan la caché y terminan en segundos. El escaneo se ejecuta en segundo plano y la ventana no se congela.

La carpeta de repeticiones de Arbiter **no se añade automáticamente**: su directorio de instalación suele acumular repeticiones de otros jugadores descargadas para estudiarlas, y contarlas atribuiría sus resultados a tu cuenta. Añádela manualmente en 路径 (Rutas) y asegúrate de que todas las repeticiones dentro sean tuyas.

## Las seis pestañas

| Pestaña | Qué muestra |
| --- | --- |
| 概览 (Resumen) | Partidas por nivel, mejor tiempo / 3BV/s / Stnb; las partidas recientes comparadas con tus PB |
| 每日 (Diario) | Una fila por día: número de partidas, horario de la sesión, distribución de tiempo / 3BV/s / Stnb; clic derecho para copiar una imagen de resumen |
| PB 表 (Tabla de PB) | La partida más rápida de cada (nivel × 3BV), en una cuadrícula de 3BV |
| lsf | Top 5 por nivel e indicador, más tu tarjeta personal de LSF |
| 上传 (Subida) | Elige los alcances y sube los resultados locales manualmente |
| 自动上传 (Subida automática) | Sube los resultados nuevos automáticamente mientras juegas |

### Diario

- Una partida pertenece al día en que **empezó**; las que cruzan la medianoche cuentan para el día de inicio. Las horas vienen de la marca de tiempo dentro de la repetición, no de la fecha de modificación del archivo, así que copiar o descomprimir archivos no cambia nada.
- La columna central es la **media aritmética**, el mismo criterio que el Daily Review de Arbiter. Un nivel a la vez, Experto por defecto.
- Haz doble clic en un día para ver sus partidas; haz doble clic en una partida para reproducirla en MetaSweeper.
- **Haz clic derecho en un día** para copiar una imagen de resumen o una imagen de repaso detallado: una tarjeta vertical que se muestra 1:1 en la pantalla del móvil, solo del nivel actual o de todos los niveles combinados, y también para fechas pasadas. La tarjeta detallada repasa el día: mejor partida e insignias de PB, tres indicadores comparados con tus últimos 7 días de buscaminas, un diagrama de dispersión 3BV × tiempo con tu curva de PB, las 5 partidas más rápidas y los tramos de ritmo.

### Tabla de PB

- Los tres niveles comparten una cuadrícula de 3BV con desplazamiento vertical: las filas son las decenas de 3BV, las columnas las unidades, un 3BV por celda. Las franjas que nunca jugaste conservan su fila vacía completa, así que los huecos se ven de un vistazo.
- El valor de las celdas alterna entre tiempo / 3BV/s / Stnb / puesto nacional; el color indica tu posición **nacional** en ese 3BV. Sin iniciar sesión, se usa el tercil local de 3BV/s.
- Haz clic en una celda para ver los detalles (incluido «mantenido N días · roto en M días»); haz doble clic para reproducir la repetición en MetaSweeper.
- La búsqueda solo **resalta el borde** de las celdas coincidentes y nunca oculta las demás: ocultarlas crearía huecos falsos en la cuadrícula.

### lsf

- Top 5 por nivel de tiempo / 3BV/s / Stnb, filtrado por los umbrales oficiales de 3BV por defecto (Principiante 10 / Intermedio 30 / Experto 100, ajustables en la página); las reglas de las clasificaciones están en [Clasificaciones top y LSF](../top-lsf.md).
- La tarjeta superior muestra tu LSF, tu categoría y el et equivalente. 明细 (Detalles) muestra qué cinco partidas sustentan cada entrada, además del LSF calculado con solo tus mejores 1 / 5 / 25 partidas: cuanto más cerca estén los tres valores, más constante es tu juego.
- Tras iniciar sesión, las tablas incorporan las clasificaciones top del sitio, con una columna de origen que marca local / sitio / ambos.
- La referencia del LSF sigue por defecto los anclajes en vivo del sitio; para reproducir la hoja de cálculo sin conexión, cambia a 固定基准 (base fija, un anclaje de temporada integrado) en 设置 (Ajustes).

## Qué se cuenta

- **Solo el modo estándar.** Las repeticiones sin conjeturas, con conjeturas, win7, upk y de tableros personalizados nunca entran en las estadísticas; las partidas sin terminar no cuentan.
- **Las copias de una misma partida cuentan una sola vez**: los duplicados se detectan por bytes de archivo idénticos (las exportaciones de récord de Arbiter y las copias de archivo suelen ser idénticas byte a byte al original). No se toca ningún archivo del disco.
- **Dos tablas**: la tabla general de PB toma la partida más rápida en cualquier estilo; la tabla de PB NF solo toma partidas [NF](../minesweeper/terminology.md). FL no tiene tabla propia: es solo una etiqueta de estilo.
- Tras iniciar sesión, la tabla de PB incorpora tus PB del sitio, conservando la más rápida entre local y sitio por celda, marcada como local / sitio / empate.
- **El modo sin conjeturas estricto es la excepción**: queda fuera de las estadísticas, pero puede subirse por separado (el sitio tiene clasificaciones propias para él); consulta [Subida automática](#subida-automatica).

## Subida

La primera vez, haz clic en 登录… (Iniciar sesión) en la pestaña de Subida e introduce tu usuario, contraseña y captcha de Open Minesweeper. Deja marcado 保持登录 90 天 (mantener la sesión 90 días) y no volverás a necesitar la contraseña.

- Los alcances se acumulan: PB (general / NF), clasificaciones top (general / NF), todas las partidas terminadas. Tras iniciar sesión, los registros locales más lentos que tus PB del sitio se excluyen automáticamente.
- **Sin subidas duplicadas**: cada candidata se compara con las repeticiones ya presentes en el sitio usando la propia regla de deduplicación del sitio; las coincidencias se marcan como «ya en el sitio».
- **Los identificadores no coincidentes se bloquean localmente**: si el identificador de la repetición no coincide exactamente con ninguna entrada registrada en tu cuenta (espacios y caracteres de ancho completo/medio cuentan como distintos), se marca como no coincidente; subirla no entraría en ninguna clasificación. Corrígelo primero según [Identificadores de jugador](../identifier.md).
- Un cuadro de confirmación enumera el nivel / tiempo / 3BV / tamaño / nombre de archivo del lote antes de enviar nada.
- Los fallos individuales se reintentan automáticamente; si cierras el programa a mitad de un lote, al reabrirlo se reanuda sin volver a subir lo ya logrado. Solo los problemas de cuenta (sesión caducada, cuota llena, etc.) detienen todo el lote.
- La casilla 含阿比特录像 (incluir repeticiones de Arbiter) decide si los `.avf` participan en el lote; marcada por defecto.

## Subida automática

Deja esta pestaña abierta mientras juegas: los resultados nuevos se detectan en uno o dos segundos tras caer en la carpeta y se suben si encajan en los alcances activados. Sin ventanas emergentes y sin robar el foco: un solo diálogo puede arruinar una partida mientras MetaSweeper está en primer plano.

- Tres interruptores independientes: partidas de clasificación (partidas que mejorarían tus clasificaciones top del sitio; requiere sesión iniciada), PB general y PB NF. Los dos primeros están activados por defecto.
- Los resultados **anteriores** a activar un interruptor no se suben retroactivamente; las partidas jugadas con el equipo apagado se recuperan en el siguiente inicio.
- Solo se suben los `.evf` de MetaSweeper. Las partidas con identificador no coincidente o que serían congeladas se omiten: no entrarían en ninguna clasificación y solo gastarían cuota.
- Los problemas de cuenta solo pausan, sin ventanas emergentes; los fallos de red repetidos esperan unos minutos antes de reintentar. Los últimos 100 registros se conservan en esta pestaña.
- **El modo sin conjeturas estricto se configura aparte**: en 设置 → 强无猜上传 (Ajustes → subida sin conjeturas estricto), elige desactivado / solo si clasifica / subir todo. «Solo si clasifica» compara con las seis casillas de las clasificaciones sin conjeturas estricto del sitio (Principiante / Intermedio / Experto × tiempo / 3BV/s) y solo sube cuando una casilla mejoraría o se llenaría; las partidas NF se comparan con las clasificaciones NF.

## Dónde se guardan los datos

Todos los datos de ejecución están en `YuanshenToolbox-data\`, junto al exe: ajustes, la cuenta cifrada, el registro de subidas, la caché de escaneo y los registros. Borrar esta carpeta devuelve la herramienta a un estado nuevo. Si el exe está en una ubicación sin permisos de escritura (como `C:\Program Files`), los datos van a `%APPDATA%\YuanshenToolbox\`.

La contraseña y la cookie de sesión se guardan cifradas con Windows DPAPI, vinculadas al usuario de Windows actual y a este equipo: otro equipo no puede descifrarlas. Los registros no contienen contraseñas, captchas ni cookies.

## Preguntas frecuentes

| Situación | Qué hacer |
| --- | --- |
| Las estadísticas parecen mal, o acabas de jugar partidas nuevas | Haz clic en 重新扫描 (Reescanear); si sigue mal, borra la caché de escaneo en 设置 → 诊断 (Ajustes → Diagnóstico) y reescanea |
| El sitio muestra `d` (identificador no coincidente) tras subir | Haz que el identificador de la repetición coincida con el registro de tu cuenta según [Identificadores de jugador](../identifier.md) y vuelve a subir |
| Una subida se detuvo a mitad | Lo ya subido no se afecta; haz clic en 重试失败 (Reintentar fallidas) para subir solo el resto |
| El programa se cerró de golpe | El archivo `logs\crash-<hora>.txt` de la carpeta de datos contiene el error completo; adjúntalo al informar |
| Quieres informar de un problema | 设置 → 诊断 → 导出诊断包 (Ajustes → Diagnóstico → Exportar diagnóstico): el zip contiene información del sistema, ajustes y registros, nunca credenciales cifradas |

El código se publica bajo licencia MIT; el [README](https://github.com/Corday-nkusky/yuanshen-toolbox) del repositorio documenta todas las reglas de conteo y las limitaciones conocidas.