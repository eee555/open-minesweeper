# Imágenes de medallas y coloreado frontend

Las imágenes originales se guardan en `front_end/src/assets/medal-templates/` y los archivos publicados se generan unificadamente por `front_end/scripts/build_medal_art.py` en `front_end/public/assets/medals/`. Cada serie solo publica una imagen WebP; las versiones principiantes, intermedias y avanzadas comparten el mismo fondo; los colores se aplican en el frontend y los números mediante superposición de CSS. No se permiten generar imágenes completas según el nivel, el umbral de desempeño o cada color específico.

## Plantillas y generación

Actualmente se utilizan 17 imágenes confirmadas de versión v3 sin borde, en formato PNG con transparencia. El generador conserva directamente la alpha, no puede recortar el fondo en negro o gris, ni aplicar repetidamente la alpha al pegar. Ocho series de habilidades por nivel mantienen el cuadro original completo para asegurar que las áreas de medallas secundarias y las estrellas no se desplacen; las demás series se adaptan según los bordes transparentes. Todas las imágenes de fondo se exportan en 128×128 WebP, con `quality=50`, `alpha_quality=45`, `method=6`.

Tres recursos originales independientes por dificultad se encuentran en `front_end/src/assets/medal-overlays/difficulty/`, manteniendo el cuadro común, y se exportan como `difficulty/b.webp`, `i.webp`, `e.webp`, cada una de 64×64. Para principiante con una estrella, intermedio con dos estrellas y avanzado con tres estrellas, una estrella arriba y dos abajo. No se permiten recortes por bordes coloreados por grupo, ni se puede erróneamente marcar una finalización de tres niveles como avanzado.

Durante la generación, se completan todos los procesos de codificación y verificación de presupuesto en un directorio temporal; solo después de que todo pase se actualiza el archivo de publicación en su totalidad, evitando que errores en las imágenes originales o en el presupuesto dejen fragmentos de resultados publicados. Los bocetos artísticos históricos y los registros de revisión solo se conservan localmente, no se distribuyen con el repositorio ni se consideran dependencias de construcción.

## Colores, estrellas y números

El archivo `medalAppearance.ts` configura explícitamente 24 grupos de umbral para habilidades por nivel único, con un total de 241 umbrales; los valores de umbral corresponden a unidades enteras del backend, no se pueden deducir por el orden de fase o el sufijo de código. El tiempo para principiantes se mantiene con los grupos ya revisados; para otros niveles y métricas se aplican grupos definidos explícitamente, sin afirmar niveles de porcentaje ni posiciones en clasificaciones. Los umbrales no mapeados se muestran en color neutro.

El archivo `medalMaterial.ts` define el material predeterminado de metal suave confirmado por el usuario. El archivo `medalToneFilter.ts` comparte filtros SVG por color, utiliza una mapeo de brillo en sRGB, sin modificar la alpha; se conservan hasta 32 filtros temporales no utilizados. Los nuevos colores no incrementan las peticiones de imágenes.

El componente `MedalArt.vue` aplica las curvas en la capa principal; el NF fija el badge secundario mediante un área circular manualmente registrada en `medalFixedBadge()`, mostrando la imagen original sin aplicar en tiempo real un área coloreable por píxeles dorados. Cualquier plantilla nueva debe reconfirmar el área fija. Las estrellas independientes no participan en el cambio de color de la capa principal. La posición principal se mantiene con el diseño ya revisado: estrellas en el 4% a la izquierda, 0% arriba, con ancho y alto del 36%.

Los números son texto HTML/CSS, separados de los filtros de imagen. El nombre completo del título, el umbral y el rango de color siempre se mantiene accesible. Las medallas de tres niveles, únicas y de celebración usan temas fijos, sin añadir estrellas por nivel; las representaciones de cobre y plata para los socios originales indican antigüedad y mantienen sus reglas especiales.

## Coloración personalizada

El archivo `medalPalette.ts` gestiona la configuración y validación por versión, mientras que `medalPaletteStore.ts` gestiona las preferencias reactivas del usuario actual y su almacenamiento local. Se prioriza el ajuste personalizado por `code + stage`, y luego se usa el color por rango de desempeño definido. No se modifican las condiciones de otorgamiento, los datos del jugador ni los ajustes de otros usuarios.

El componente `MedalPaletteSettings.vue` se reutiliza en la página de medallas y en la página de configuración, ofrece un selector de cinco niveles, vista inmediata en HEX, vista previa por dificultad de cada serie, cobertura por umbral individual, restauración a valores predeterminados, importación y exportación en JSON. Un importación fallida no sobrescribe la configuración actual; se muestra claramente si no se puede guardar de forma persistente. Todos los puntos de acceso se comparten con `MedalArt.vue`, sin solicitar resúmenes completos por jugador en los mensajes de nombre.

## Presupuesto y caché

- Cada fondo gráfico no supera los 8 KiB, y cada estrella no supera los 2 KiB.
- El total de imágenes de medallas no supera los 160 KiB; el límite conservador para seis fondos sigue siendo de 44 KiB.
- Actualmente 17 mapas de fondo suman 60.134 bytes, 3 mapas estrella suman 2.808 bytes, totalizando 62.942 bytes.
- La versión del URL del mapa de fondo es `v=6`, y la de los mapas estrella es `v=1`; después de modificar el contenido de la misma ruta, es necesario actualizar la versión.
- La página solo referencia los mapas de publicación y no carga directamente los modelos de alta resolución del origen. El segundo capa fija de la marca SVG reutiliza la misma URL.

## Verificación y compilación

```powershell
python front_end/scripts/build_medal_art.py
python -m unittest discover -s front_end/scripts -p test_medal_art.py
cd front_end
npm run vitest -- run src/services/medalAppearance.test.ts src/services/medalPalette.test.ts src/services/medalService.test.ts src/services/medalRecolor.test.ts
npm run build:openms
```

El Codex inicia el proceso de revisión y corrección (lintfix) y verificación de tipos (typecheck) según el flujo específico de revisión por agentes en el archivo `AGENTS.md` en el directorio raíz. Los registros se almacenan en `.tmp/checks/`. Los casos de Cypress se mantienen actualizados, y solo se ejecutan cuando el usuario los solicite explícitamente; el proxy no ejecuta pruebas E2E. La transparencia de los mapas de origen, las dimensiones de publicación, la lista completa de archivos y el presupuesto de recursos están cubiertos por pruebas del script de generación.
