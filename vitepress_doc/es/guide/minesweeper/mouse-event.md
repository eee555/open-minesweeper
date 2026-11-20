---
title: "Controles y reglas - Open Minesweeper"
description: "Explicación de los controles de Buscaminas, incluyendo el modo clásico, la técnica de 1,5 clics, el doble clic con botón izquierdo, pantallas táctiles y la apertura simultánea asistida."
---

# Controles y reglas

## Modo de control clásico

El modo de control clásico proviene de Winmine. Es el modo de referencia y el más extendido. En resumen, hay tres reglas: el clic izquierdo se activa al soltar el botón, el clic derecho se activa al presionar el botón y la apertura simultánea se activa al soltar. La implementación se muestra a continuación:

```automaton
stateDiagram-v2
    Idle --> LeftButtonDown: pulsar el botón izquierdo
    Idle --> TriggerFlag: pulsar el botón derecho

    LeftButtonDown --> TriggerLeft: soltar el botón izquierdo
    TriggerLeft --> Idle

    LeftButtonDown --> ChordDown: pulsar el botón derecho

    TriggerFlag --> Idle: soltar el botón derecho
    TriggerFlag --> ChordDown: pulsar el botón izquierdo

    ChordDown --> TriggerChordRight: soltar el botón izquierdo
    ChordDown --> TriggerChordLeft: soltar el botón derecho

    TriggerChordRight --> Idle: soltar el botón derecho
    TriggerChordLeft --> Idle: soltar el botón izquierdo

    TriggerChordRight --> ChordDown: pulsar el botón izquierdo
    TriggerChordLeft --> ChordDown: pulsar el botón derecho
```

### Técnica de 1,5 clics

Colocar una bandera y hacer una apertura simultánea suelen ser dos acciones consecutivas. Si cada una exigiera pulsar y soltar un botón, harían falta cuatro movimientos. En el modo clásico basta con tres: pulsa el botón derecho para colocar la bandera, mantenlo pulsado, pulsa el izquierdo sobre el número y suelta ambos para abrir las casillas vecinas. Como tanto pulsar como soltar requiere tiempo, la secuencia tarda aproximadamente lo que un clic y medio. De ahí su nombre.

La ganancia real depende del tiempo que tardes en mover el puntero de la casilla que marcas al número que quieres abrir. En el caso extremo, pulsas el izquierdo inmediatamente después del derecho y sueltas ambos a la vez. Así las dos operaciones duran aproximadamente lo mismo que un solo clic.

## Otros modos de control

### Apertura con el botón izquierdo

Muchos programas y plataformas modernos permiten abrir las casillas vecinas usando solo el botón izquierdo. Este modo distingue dos momentos: al soltar el izquierdo y al pulsar el derecho. Si sueltas el izquierdo sobre una casilla cerrada, la abres. Si lo sueltas sobre un número ya descubierto, se intenta una apertura simultánea. Los dos botones funcionan de forma independiente. Cada plataforma trata a su manera las pulsaciones simultáneas, por lo que no hay un diagrama único para este modo.

### Controles táctiles

Un toque equivale a un clic izquierdo. Para emular el botón derecho, algunas aplicaciones ofrecen un selector entre abrir y marcar. Otras distinguen el toque breve de la pulsación prolongada.

### Clic por deslizamiento

Al mantener pulsado un botón, se activa cada casilla por la que pasa el puntero hasta que lo sueltas. Este modo cambia considerablemente el manejo del tablero y pocos programas lo ofrecen.

### Apertura simultánea asistida

El programa detecta los números que ya tienen suficientes banderas alrededor y abre automáticamente sus casillas vecinas. Algunos programas repiten la operación de forma recursiva. Esto permite centrarse en las deducciones y ha dado más popularidad a este modo que al clic por deslizamiento. Minesweeper Go, Chocolate Sweeper y Meowsweeper admiten la apertura recursiva.
