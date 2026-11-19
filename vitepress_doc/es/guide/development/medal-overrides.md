# Decisiones administrativas sobre medallas

Abre **Gestión de medallas** en `/#/staff/medals`. Introduce el ID del jugador y comprueba su nombre de usuario antes de elegir la medalla, la acción y el motivo.

## Orden de prioridad

- **Forzar la concesión**. Elige un nivel válido y una fecha de concesión. La medalla queda fijada en ese nivel para ese jugador, aunque después mejore su marca o dejen de ser válidas las pruebas que la justificaban.
- **Impedir la concesión**. Se retira la medalla de inmediato y se bloquean las concesiones automáticas posteriores. Puedes aplicar esta decisión antes de que el jugador la consiga por primera vez.
- **Restablecer la evaluación automática**. Se levanta la decisión manual, se retira su resultado y una tarea en segundo plano vuelve a evaluar los datos reales. La medalla puede aparecer como no obtenida hasta que termine la tarea. Las medallas conmemorativas manuales carecen de evaluador automático y no se vuelven a conceder por sí solas.

Una decisión se aplica a la combinación de jugador, código de medalla y `scope_key`. Deja la edición o el ámbito en blanco para las medallas ordinarias: así se evitan concesiones duplicadas. Las medallas conmemorativas por edición y las de torneo admiten un ámbito. Para una medalla de torneo existente, conserva el ámbito original para no mezclar ediciones.

El nivel que fija el administrador no modifica el progreso real ni activa otras medallas compuestas. Impedir una medalla individual tampoco impide una compuesta si el jugador cumple sus requisitos reales. Aplica por separado cada prohibición necesaria. El servidor sigue manteniendo el progreso automático. Desactivar globalmente una medalla la oculta incluso si se ha concedido manualmente. La decisión manual se conserva y puede levantarse incluso si se desactiva o se elimina la definición.

Solo se pueden conceder los niveles válidos en la definición actual. Un cambio posterior de umbrales no levanta el bloqueo manual. Al restablecer la evaluación automática, se usan los umbrales vigentes. Las medallas no otorgan puntos ni contribuyen a la puntuación total.

Todas las operaciones requieren una sesión de administrador y un motivo. Cada cambio registra el administrador, la acción, el ámbito, el nivel, la fecha de concesión y la hora del cambio. Restablecer la evaluación automática conserva el historial. El panel muestra los últimos 50 registros del jugador. Si intervienen varios administradores, prevalece la última decisión enviada y se conservan las anteriores en el historial. Las escrituras de los administradores y la evaluación en segundo plano bloquean la misma fila del jugador para evitar sobrescrituras simultáneas.

El panel permite gestionar decisiones sobre definiciones existentes. No permite crear medallas ni desactivarlas globalmente. Los perfiles públicos muestran las medallas sin revelar los motivos ni el historial de administración.

El evaluador automático cubre las medallas de accionista fundador, de principiante, de marca personal y las compuestas de los tres niveles de dificultad. Para los demás tipos que aún carecen de regla automática, incluidas las conmemorativas manuales, restablecer la evaluación únicamente elimina la decisión y retira el resultado manual.

## Despliegue de la base de datos

Esta función incorpora `MedalOverride` y `MedalOverrideLog`. Django genera la migración. El repositorio ignora `migrations/*.py`. En el entorno de despliegue, genera las migraciones siguiendo la práctica del proyecto y comprueba el plan antes de aplicarlas.

```powershell
cd E:\Tools\saolei_website\back_end\saolei
.\.venv\Scripts\python.exe manage.py makemigrations medal
.\.venv\Scripts\python.exe manage.py migrate medal --plan
.\.venv\Scripts\python.exe manage.py migrate medal
```

Tras aplicar la migración, inicia la nueva versión del sitio y `manage.py db_worker_robust`. Las concesiones modificadas manualmente antes de esta función no se convierten automáticamente en decisiones administrativas. Para mantener una medalla bloqueada, el administrador debe fijarla de nuevo en el panel. Así, una retirada ordinaria no se interpreta como una prohibición permanente.

## Pruebas de regresión

Las pruebas del servidor comprueban permisos, entradas no válidas, historial, aislamiento entre ámbitos y prioridad entre las decisiones manuales y las actualizaciones automáticas.

```powershell
cd E:\Tools\saolei_website\back_end\saolei
.\.venv\Scripts\python.exe manage.py test medal --keepdb --noinput
```

Pruebas unitarias de la interfaz con el servidor y de las condiciones de envío del cliente:

```powershell
cd E:\Tools\saolei_website\front_end
npm.cmd run vitest -- --run src/services/staffMedalService.test.ts src/services/medalService.test.ts
```

Las pruebas de componentes cubren el panel de administración y la página personal de medallas. Según las convenciones del proyecto, el usuario elige cuándo ejecutarlas.

```powershell
cd E:\Tools\saolei_website\front_end
npx.cmd cypress run --component --browser chrome --headless --spec "src/views/StaffView/Medal.cy.ts,src/views/UserView/UserMedals.cy.ts"
```

Para la comprobación manual se recomienda una cuenta de prueba dedicada.

1. Intenta acceder al panel y llamar directamente a la API con una cuenta ordinaria: ambas operaciones deben denegarse. Un administrador debe ver el catálogo completo, incluidas las medallas ocultas o desactivadas.
2. Fuerza la concesión de un nivel concreto de una medalla de habilidad y compruébalo en el perfil. Sube una marca mejor, congela la prueba y ejecuta la concesión retroactiva. El nivel fijado debe mantenerse.
3. Impide otra medalla que el jugador todavía no tenga. Añade una repetición que cumpla las condiciones y vuelve a calcular. El jugador debe seguir sin recibirla.
4. Restablece la evaluación automática. Cuando termine la tarea, recarga la página y comprueba que el nivel corresponda a las marcas reales. El historial debe incluir tanto las decisiones anteriores como el restablecimiento.
5. Aplica decisiones a jugadores o ediciones diferentes y comprueba que sean independientes. Forzar una medalla de una dificultad no debe alterar el progreso real ni activar la medalla compuesta de los tres niveles.
6. Al cambiar de jugador, retrasa la respuesta a la solicitud anterior. Ni su resultado ni sus errores deben sobrescribir los datos del nuevo jugador. Una operación en curso solo debe aplicarse al jugador al que estaba dirigida.

El resultado de restablecer la evaluación automática depende de la tarea en segundo plano. El sitio no envía notificaciones en tiempo real entre navegadores. El jugador puede volver a cargar su perfil después de la intervención del administrador.
