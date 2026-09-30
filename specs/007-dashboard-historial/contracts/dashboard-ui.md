# Pantallas del historial y del tablero

Leen los contratos de esta carpeta y los ya publicados. No calculan métricas.

## Historial

Sobre el listado de sesiones que ya existe, una sección aparte. No reemplaza el alta de video.

Cada fila muestra nombre, archivo de video, estado, fecha de procesamiento (`finished_at`) y número de versión. Si el estado es fallido o cancelado, el motivo queda en la misma fila y esa fila no se presenta como resultado final. Si no hay filas, el texto es que todavía no hay sesiones procesadas.

Abrir una fila navega a `/sessions/{session_id}/results`.

## Resultados

| Situación | Contenido |
|---|---|
| Análisis completado | Los ocho indicadores del local elegido, para toda la sesión. El flujo de los minutos que se solapan con el tramo. Hechos de ese local e intervalo |
| Análisis pendiente o en curso | Solo entradas, salidas y ocupación visible, con el texto «parcial» |
| Fallido o cancelado | El motivo. Sin los ocho indicadores |
| Video `missing` o `mismatch` | Los resultados se leen igual. El texto dice que el archivo no está en este equipo. La imagen del frame de referencia sigue |
| Métrica no disponible | El texto «no disponible» y el motivo si vino en la cifra. No se muestra un cero |
| Sin muestra de posiciones | El mapa explica el vacío. Los indicadores siguen |

El local inicial es el primero de la versión. El tramo inicial es el video entero. Cambiar de local vuelve a pedir las métricas. Cambiar el tramo no las vuelve a pedir: filtra minutos y hechos.

Rótulos visibles, no solo color: «estimación de visitas», «visible», «observable», «parcial» y «no disponible».

El gráfico del flujo es de barras, una por minuto mostrado. El horario pico es el que ya vino en la respuesta, no el máximo de los minutos filtrados.

## Mapa

Opcional. Si se incluye, los pies se dibujan sobre el frame de referencia. Si la muestra no está en este equipo, el estado vacío lo dice y el resto de la pantalla queda usable.
