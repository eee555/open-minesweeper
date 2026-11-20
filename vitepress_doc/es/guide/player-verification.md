---
title: "Verificación del jugador - Open Minesweeper"
description: "Cómo funciona la verificación del jugador en Open Minesweeper: obtener verificación, verificar a otros jugadores y cómo la verificación se relaciona con las subidas de partidas repetidas, la participación en torneos y el mantenimiento de superusuarios."
---

# Verificación del jugador

La verificación del jugador es la forma en que Open Minesweeper confirma la identidad de un jugador y desbloquea las subidas de partidas repetidas y la participación en torneos. Una vez que tengas un nombre real en tu perfil o seas verificado por un jugador verificado, podrás subir partidas repetidas y participar en torneos. El estado de acceso se actualiza inmediatamente cuando cambie tu nombre real o tu verificación — no es necesario volver a iniciar sesión.

## ¿Por qué existe la verificación?

Queremos que todos los usuarios de Open Minesweeper sean personas reales y fomentamos que los jugadores se conecten entre sí — en persona, especialmente fuera de línea. Si estás seguro de que un jugador es una persona real, te recomendamos que lo verifiques desde la sección **Verificación del jugador** de tu página de configuración. La verificación con nombre real y la verificación del jugador juntas forman una comunidad que pone a las personas reales en primer lugar: un nombre real es tú mismo detrás de tu identidad, mientras que verificar a otro jugador es tú que le pasas esa confianza a un amigo que realmente conoces.

## ¿Qué desbloquea la verificación?

- El acceso manual a la subida de partidas repetidas.
- Participación en torneos (incluyendo el Torneo Semanal, Copa de la Oveja de Oro y otros).

El acceso se abre en cuanto se cumpla cualquiera de las condiciones: "tiene un nombre real" o "verificado por un jugador verificado". El acceso se calcula en tiempo real a partir de tu ID de usuario efectivo, nombre real (incluyendo un nombre oculto) y estado de verificación — no se almacena como campo separado.

## Cómo obtener verificación

Cualquiera de las siguientes opciones es suficiente:

### Opción 1: Añade tu nombre real

Introduce tu nombre real en tu perfil. El nombre real actúa como tu credencial de identidad y el acceso se abre inmediatamente. Una vez verificado como jugador, podrás habilitar el ocultamiento del nombre en tu perfil; los jugadores verificados aún pueden verificarte posteriormente.

### Opción 2: Ser verificado por un jugador verificado

Un jugador verificado puede verificarte directamente desde la sección **Verificación del jugador** de su página de configuración, introduciendo tu ID de sitio:

- No es necesario enviar una solicitud previa ni haber un paso de aprobación;
- La verificación se aplica inmediatamente y se crea la relación entre tú y ellos;
- Una vez creada, no puedes eliminar la relación tú mismo.

## Cómo verificar a otros jugadores

Cuando tú mismo estés **verificado**, la sección **Verificación del jugador** de tu página de configuración muestra un campo de entrada:

1. Introduce el ID de sitio del jugador objetivo (el número en la URL de su perfil) en **ID de usuario objetivo**;
2. Haz clic en **Verificar usuario**.

Nota: la verificación es una relación dirigida, con la dirección "verificador → verificado". Puedes verificar a varios jugadores y ser verificado por varios jugadores; las relaciones inversas y mutuas son ambas válidas e independientes, pero no puedes verificar a ti mismo.

## Verificación de tu propio estado

Abre la sección **Verificación del jugador** de tu página de configuración para ver:

- **Estado**: Verificado / No verificado;
- **Acceso a partidas repetidas y torneos**: Permitido / Bloqueado.

Ambos estados se actualizan inmediatamente tras cambiar tu nombre real o tu verificación.

## Durante mantenimiento

Cuando un superusuario realiza ajustes masivos en las relaciones de verificación, abre una sesión exclusiva de mantenimiento (duración elegida por el superusuario, hasta una hora). Mientras dure la sesión de mantenimiento:

- La verificación jugador-a-jugador se pausa;
- Los puntos de acceso para consultar el estado y la estructura del gráfico permanecen disponibles;
- El superusuario aún puede realizar ajustes masivos dentro de la sesión de mantenimiento.

La sesión de mantenimiento se recupera automáticamente cuando expira, o se libera inmediatamente cuando el superusuario la termina.

## Preguntas frecuentes {#faq}

### Estoy verificado, ¿por qué aún no está disponible la entrada de subida?

El acceso depende tanto de tu nombre real como de tu estado de verificación. Si revocaste tu nombre real o fue eliminada tu verificación, el acceso se cierra según corresponda. Verifica que la línea **Acceso a repeticiones y torneos** en la sección **Verificación del jugador** de tu página de configuración muestre **Concedido**.

### ¿Puedo quitar mi propio estado de verificado?

No. Una vez que se crea una relación de verificación, se vincula tú y el verificador, y no es posible eliminarla por tu cuenta. Contacta al superusuario si se necesita un ajuste.

### ¿La verificación es lo mismo que un nombre real?

No. Un nombre real es la credencial de nombre que introduces tú mismo; la verificación del jugador es la relación que otros jugadores verificados tienen contigo. `verified` es tu resultado actual de verificación efectivo — no significa que tengas un nombre real ni implica un rol de personal.
