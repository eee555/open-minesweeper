---
title: "Identificadores de jugador - Open Minesweeper"
description: "Cómo configurar identificadores de jugador y tokens de torneo en el software de Buscaminas y gestionarlos en Open Minesweeper."
---

# Identificadores de jugador

Un identificador es una firma de cadena introducida por el jugador y almacenada en la repetición. En Minesweeper Arbiter, se llama "identidad del jugador". En las configuraciones de MetaSweeper, se llama "identificador".

Antes de subir repeticiones manualmente, necesitas tener un nombre real en tu perfil o ser verificado por un jugador verificado. Sin ninguno de los dos, la entrada de subida está desactivada. Un jugador verificado puede verificarte introduciendo tu ID de sitio: no hay solicitud ni aprobación, y no puedes eliminar la relación tú mismo. Los cambios en el acceso se actualizan en cuanto cambie alguna de estas condiciones.

## Configuración de identificadores en diferentes software

<details>
    <summary>MetaSweeper</summary>
    <span>Configuración de opciones - Configuración del juego desde la barra de menús, o presiona S para abrir la ventana de configuración.</span>
    <img src="/metasweeper-identifier.png" />
    <span>Después de la configuración, se ve así:</span>
    <img src="/metasweeper-identifier2.png" />
</details>
<details>
    <summary>Minesweeper Arbiter</summary>
    <span>Acceder a Opciones - Preferencias desde la barra de menús, o presiona F5 para abrir la ventana de configuración.</span>
    <img src="/arbiter-identifier.png" />
    <span>Después de la configuración, se ve así:</span>
    <img src="/arbiter-identifier2.png" />
</details>

## Gestión de identificadores en Open Minesweeper

La zona de gestión de identificadores se encuentra en la parte inferior de la pestaña **Resumen** en tu página de perfil. Puedes añadir o eliminar tus identificadores allí. Después de añadir o eliminar un identificador, todas las repeticiones con ese identificador se actualizan, principalmente incluyendo las verificaciones de elegibilidad en la clasificación.

## Identificadores de torneo {#tournament-token}

Los identificadores de torneo demuestran que una repetición fue creada después de que haya comenzado un torneo. Cuando comienza un torneo, el sistema genera un identificador aleatorio. Durante el torneo, solo las repeticiones que contengan ese identificador de torneo son reconocidas automáticamente como repeticiones de torneo. El identificador debe establecerse antes de jugar y solo se revela cuando comience tu ventana de participación, incluso si te registras antes.

Las repeticiones deben subirse dentro de tu ventana de participación. Las subidas tardías no se cuentan, incluso si el torneo mismo no ha terminado.

**Para incluir la misma repetición en múltiples torneos, coloca todos los tokens de torneo en el campo de identificador de torneo del juego, separados por comas (`,`) sin espacios, por ejemplo `TOKEN1,TOKEN2`.** Cada torneo sigue aplicando su propia ventana de participación y reglas de puntuación.

### Configuración de un identificador de torneo

<details>
    <summary>MetaSweeper</summary>
    <span>Configuración de opciones - Configuración del juego desde la barra de menús, o presiona S para abrir la ventana de configuración.</span>
    <img src="/tournament/metasweeper-token-zh.png" />
</details>
<details>
    <summary>Minesweeper Arbiter</summary>
    <span>Minesweeper Arbiter no soporta identificadores de torneo. Por favor, sigue las reglas de identificadores establecidas por el organizador del torneo.</span>
</details>

## Preguntas frecuentes {#faq}

### ¿Por qué no se actualizó mi registro tras subir una repetición?

Puedes ver todas tus repeticiones en la pestaña **Repeticiones** de tu página de perfil. Si el estado de una repetición es "desajuste de identificador", no se incluye en las estadísticas del registro. Necesitas registrar el identificador correspondiente, y luego la repetición entrará en las estadísticas del registro.

### Ya registré el identificador. ¿Por qué aún dice la repetición "desajuste de identificador"?

Open Minesweeper realiza coincidencias exactas de cadenas para identificadores. Algunas cadenas pueden parecer idénticas pero en realidad son diferentes, causando un desajuste. Las causas más comunes son:

- Espacios y otros caracteres invisibles
- Diferencias en puntuación entre chino y inglés

La página de gestión de identificadores tiene un botón de copiar para identificadores registrados. Puedes copiar el identificador registrado y compararlo en otro programa.

### ¿Por qué falló al añadir un identificador?

1. No tienes ninguna repetición con ese identificador. Al usar un nuevo identificador, primero debes subir al menos una repetición que lo contenga, y luego añadir el identificador.
2. El identificador ya está en uso por otro usuario
