---
title: "Torneos - Open Minesweeper"
description: "Puntos, identificadores, reglas de visibilidad de repeticiones y subida automática para Copas de la Oveja de Oro y Torneos Semanales."
---

# Torneos de Buscaminas

El sitio web soporta Copas de la Oveja de Oro, Torneos Rápidos Semanales y Torneos de Eficiencia Semanales. Contáctate con los desarrolladores para organizar otros formatos de torneo.

Para registrarte o subir repeticiones de torneo necesitas tener un nombre real en tu perfil o ser verificado por un jugador verificado. Un jugador verificado puede verificarte introduciendo tu ID de sitio: no hay solicitud ni aprobación, y no puedes eliminar la relación tú mismo. Los roles de personal o superusuario no otorgan acceso. La verificación está gestionada por administradores; si se elimina, un usuario con nombre real puede seguir participando.

## Puntos de Torneo

Los puntos de clasificación se otorgan tras que los resultados del torneo estén finalizados. Aún no se soporta convertir dinero en puntos.

Los mejores personales se registran de forma separada para Copas de la Oveja de Oro, Torneos Rápidos Semanales y Torneos de Eficiencia Semanales, contando solo los torneos otorgados. El selector de clasificación proporciona una tabla general y una tabla separada para cada tipo.

### Puntos de Clasificación

Puntos de clasificación = coeficiente del torneo / clasificación. Por ejemplo, el quinto puesto en un Torneo Semanal obtiene 50 / 5 = 10 puntos.

| Torneo | Coeficiente |
| --- | --- |
| Copa de la Oveja de Oro | 1000 |
| Velocidad Semanal | 50 |
| Eficiencia Semanal | 50 |

### Degradación de puntos

Los puntos actuales se devalúan con el tiempo, reduciéndose a la mitad cada 2 años. Los totales históricos no se ven afectados.

## Repeticiones de Torneo

Las repeticiones de torneo están ocultas por defecto: no aparecen en listas públicas de repeticiones ni en clasificaciones, pero aún puedes ver las tuyas. Se vuelven públicas tras la entrega de premios, a menos que también pertenezcan a otro torneo no otorgado. Los torneos cancelados no impiden su divulgación.

### Visibilidad en múltiples torneos

Si una repetición pertenece a varios torneos, una vez que uno de ellos reciba una recompensa, otros usuarios pueden ver sus resultados a través del exportado completo de datos de ese torneo y las páginas individuales de participantes, incluso si otro torneo mantiene oculta la repetición.

Otros usuarios aún no pueden jugar ni descargar la repetición. La excepción para ver resultados se aplica únicamente tras la entrega de premios, no simplemente cuando finalice el torneo.

### Revelación manual

En la lista de repeticiones de tu perfil, abre el menú de tres puntos de una fila de repetición y elige "Revelar video".

Las repeticiones reveladas no pueden volver a ocultarse, y la revelación se aplica a todos los torneos a los que pertenecen. Aún cuentan hacia los resultados de torneo y no se consumen tu cuota de repeticiones.

## Subida automática de repeticiones de torneo {#auto-upload}

La subida automática requiere un navegador que soporte el acceso a carpetas. Durante tu periodo de participación, selecciona una carpeta de repeticiones, configura el intervalo y el nivel de filtro para subir nuevas repeticiones que coincidan. Cada nivel de filtro incluye todas las condiciones previas. El nivel 2 es el predeterminado.

Al seleccionar por primera vez una carpeta, elige si subir solo repeticiones nuevas o también procesar las existentes. Mantén la página del torneo abierta; la subida automática se detiene cuando abandonas la página.

### Torneos Semanales

1. Todas las repeticiones de torneo: incluye tu [identificador de torneo](./identifier.md#tournament-token). No se soporta AVF.
2. Vídeos de torneos compatibles: repeticiones de nivel Intermedio o Experto en modo Estándar. Efficiency Weekly también requiere `Time / IOE` por debajo de 60 para Intermedio o 240 para Experto.
3. Vídeos para mejorar tu puntuación: la repetición mejora tus mejores 5 resultados Intermedio o 2 Expertos. Speed Weekly compara tiempos; Efficiency Weekly compara `Time / IOE`.

### Copa de la Oveja de Oro

1. Todas las repeticiones de torneo: las repeticiones AVF deben tener un identificador de jugador no vacío que coincida exactamente con tu identificador registrado como Arbiter. Otros programas deben incluir este [identificador del torneo](./identifier.md#tournament-token).
2. Niveles y modos compatibles: Principiante, Intermedio o Experto en modo Estándar.
3. Se debe alcanzar un mínimo de 3BV: al menos 10 para Principiante, 30 para Intermedio y 100 para Experto.

No se pueden actualizar las repeticiones personales mientras se realiza el envío automático, y deben cargarse completamente antes de que se pueda iniciar. Si has instalado el sitio como aplicación y tu navegador lo soporta, el icono de la aplicación mostrará una etiqueta mientras se procesan las repeticiones.

## Preguntas frecuentes

### ¿Por qué mi repetición subida no aparece en mis resultados en vivo?

- Solo las repeticiones marcadas como "Válida" cuentan hacia tu puntuación. Las pendientes, congeladas o con desincronización de identificador no se cuentan.
- Los identificadores de torneo [identificadores de torneo](./identifier.md#tournament-token) deben coincidir exactamente, incluyendo mayúsculas, espacios y caracteres invisibles.
- En MetaSweeper, utiliza el campo separado [identificador de torneo](./identifier.md#tournament-token). No lo agregues al identificador habitual.
- Algunos torneos comienzan tu ventana de participación en cuanto te registres. Sube antes de que termine tu propia ventana.
