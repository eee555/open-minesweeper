---
title: "Torneo semanal - Open Minesweeper"
description: "Reglas del torneo semanal organizado por Open Minesweeper, incluyendo horario, puntuación y guía de participación."
---

# Torneo semanal

Open Minesweeper organiza de forma independiente los torneos de Velocidad Semanal y Eficiencia Semanal. Puedes participar en ambos durante la misma semana; regístrate por separado y utiliza el token específico de cada torneo [aquí](./identifier.md#tournament-token).

La inscripción requiere un nombre real o verificación por parte de un jugador verificado. Consulta [Torneos de Buscaminas](./tournament.md).

## Reglas

**Los torneos de Velocidad Semanal y Eficiencia Semanal tienen sesiones independientes de dos horas. Puedes elegir horarios separados dentro de la misma semana, y las sesiones pueden superponerse; no es necesario participar en ambos al mismo tiempo.**

El torneo comienza a las 00:00 UTC el lunes y termina a las 24:00 UTC el domingo. Puedes elegir un intervalo de dos horas por separado para cada torneo dentro de ese periodo. Durante el torneo, puedes registrarte en su página y recibir un identificador único de torneo. Después de registrarte, tendrás dos horas para subir las repeticiones del torneo. Si te registras después de las 22:00 UTC el domingo, la hora de finalización de tu torneo seguirá siendo las 24:00 UTC del domingo, así que ten cuidado con el tiempo.

Tras la confirmación, tu sesión de dos horas comienza inmediatamente y no puede cancelarse ni elegirse nuevamente. Si te registraste por error y no tienes repeticiones del torneo, contacta al organizador o a un administrador tras finalizar tu ventana personal para reiniciarla. El torneo general debe seguir en curso.

Ambos torneos consideran únicamente las repeticiones oficiales en formato estándar, incluyendo NF. El software debe soportar tokens de torneo.

### Velocidad Semanal

El formato clásico 2E+5I suma los tiempos más rápidos de 2 jugadores Expertos y 5 jugadores Intermedios. Los tiempos intermedios deben ser inferiores a 60 segundos y los de expertos inferiores a 240 segundos. Los juegos ausentes se cuentan como estos límites respectivos.

### Eficiencia Semanal

Cada partida se califica por `Time / IOE`, equivalente a `clicks / 3BV/s`; menor es mejor. Suma las puntuaciones más bajas de 2 partidas Expert y 5 partidas Intermedia. Las puntuaciones Intermedia deben ser inferiores a 60, Expert inferiores a 240, sin límite adicional de IOE. Las partidas ausentes se cuentan como 60 y 240 respectivamente.

## Cálculo de resultados y descalificación

Los resultados finales se calculan al menos una hora después de que termine el torneo general. Esto no extiende tu sesión ni tu ventana de subida. Después de otorgar los puntos, solo el organizador del torneo puede descalificar a un jugador por violar las reglas. Los puntos otorgados se revocan; los archivos de repetición se mantienen.

## Recompensas por puntos

Después de que termine el torneo, se otorgarán puntos según el puesto. La fórmula es `50/rank`: por ejemplo, el primer puesto recibe 50 puntos, el segundo 25 puntos, y así sucesivamente.
