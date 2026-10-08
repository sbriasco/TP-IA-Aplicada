# Pausa manual del análisis webcam

Fecha: 2026-10-07. Diseño preparado con asistencia de IA.
Estado: especificación y plan aprobados por el usuario el 2026-10-07; implementación realizada y verificada con fuente simulada. Aplicación a la base de la app pendiente de migración 0012.

## Objetivo y alcance aprobado

Permitir que el operador pause un análisis webcam durante un período sin actividad y luego continúe en la misma sesión y el mismo trabajo. Pausar detiene captura e inferencia; conserva configuración, modo de etiquetas, cruces confirmados, estadías ya observadas, buckets y posiciones. Detener continúa siendo la acción definitiva.

Al retomar se solicita una imagen nueva y confirmación de encuadre antes de analizar. El seguimiento comienza un segmento nuevo: un track previo a la pausa no se vincula con uno posterior. No se instalan dependencias ni se agregan servicios externos.

## Comportamiento de interfaz

- En captura activa, la cabecera ofrece «Pausar análisis» junto a «Detener análisis» y el reporte.
- Tras solicitar la pausa, muestra «Pausando…» y bloquea solicitudes duplicadas. No anuncia «Pausado» hasta que el worker haya cerrado la captura y persistido el checkpoint.
- Pausada, la consola muestra «Análisis pausado», una indicación de que no está observando la cámara y «Retomar análisis». Conserva las cifras anteriores, identificadas como último estado observado; no las presenta como ocupación actual ni telemetría fresca.
- Retomar solicita un encuadre nuevo usando el transporte de recuperación existente. No inicia inferencia por sí solo: el operador confirma la imagen y pulsa «Reanudar análisis».
- Un encuadre vencido o una cámara no disponible permite reintentar, manteniendo el mismo trabajo y el intervalo abierto sin observaciones.
- «Detener análisis» permanece disponible durante pausa, apertura de cámara y confirmación. La detención tiene prioridad y nunca abre un trabajo nuevo.
- Recargar o perder el WebSocket no elimina la pausa. REST permite reconstruir el estado persistido; reconectar el navegador no reanuda la cámara automáticamente.
- La consola conserva los tokens visuales actuales y el ajuste de escritorio a la altura disponible. Los controles siguen siendo accesibles por teclado.

## Estados y comandos

Se mantiene `ProcessingJob.status=processing` mientras el trabajo permanece pausado. El estado de captura incorpora `pausing` y `paused`; se distinguen de `interrupted`, que representa un fallo de captura.

Transiciones principales:

1. `connected` → solicitud de pausa → `pausing` → checkpoint y cierre de cámara → `paused`.
2. `paused` → solicitud de retomar → apertura de cámara → `awaiting_confirmation` → confirmación válida → primer frame analizado → `connected`.
3. Una solicitud de stop desde cualquiera de esos estados conduce a `stopping` y a la finalización existente.

El endpoint de pausa y el de solicitud de retomar devuelven aceptación del comando, no una confirmación anticipada del estado final. Las solicitudes repetidas son idempotentes dentro de la misma transición. Pausar no es válido antes de comenzar ni después de finalizar. No se permite retomar durante una pausa aún no confirmada o una detención.

Los comandos se validan por sesión activa, trabajo webcam, equipo propietario y lease; las transiciones se serializan con los locks de trabajo/estado existentes. Se versionan los nuevos campos de control y estados mediante Alembic. El número de migración se elegirá contra la cabeza real al implementar.

## Worker y persistencia

El supervisor de captura debe poder cerrar la fuente ante una petición de pausa sin activar la señal de terminación definitiva. El bucle de inferencia diferencia una pausa manual de un error de lectura y de un stop.

Una inferencia ya iniciada puede terminar antes del acuse de pausa: se conserva su resultado si pertenece a un frame válido capturado antes del cierre. No se inicia otra inferencia tras reconocer la solicitud. La pausa no promete interrumpir una llamada bloqueada de GPU; la interfaz mantiene «Pausando…» hasta el checkpoint y explica una demora prolongada.

Antes de confirmar `paused`, el worker cierra la continuidad espacial y de estadías, descarta cruces pendientes no confirmados según las reglas existentes, vacía el writer y persiste el fin del segmento y el inicio del intervalo con motivo `operator_pause`. Esa operación es única por ciclo de pausa. Los checkpoints no pueden sobrescribir una solicitud de pausa o stop concurrente con `connected`.

Durante la pausa no se producen detecciones, posiciones ni frames de cámara. Continúan heartbeat, lease, lectura de comandos y transporte de estado. La cámara se libera; el worker conserva la reserva del análisis y su modelo en memoria. Pausar no habilita iniciar otro trabajo con el único worker ni promete liberar VRAM.

La apertura/confirmación reutiliza las comprobaciones acotadas de recuperación, nonce, vencimiento y dimensiones. Una pausa manual no ejecuta los reintentos automáticos de una captura perdida. Al retomar se cierra el intervalo en el primer frame válido del segmento siguiente y se reinician tracker, reglas de cruces, continuidad de estadías y ventanas de rendimiento. Se conservan los acumuladores del trabajo.

Si se detiene durante la pausa, el intervalo se cierra con el instante monotónico de la detención y se finaliza mediante el recorrido existente. Si el proceso muere o pierde ownership, se aplica la recuperación existente con final desconocido: no se inventa una duración hasta el reinicio ni se retoma automáticamente.

## Tiempo, cobertura y métricas

Se conserva el mismo origen monotónico de captura durante toda la vida del trabajo. No se comprime el eje temporal para ocultar la pausa.

Ejemplo: pausa al segundo 120 y primer frame retomado al segundo 180. El intervalo queda registrado como no observado; no agrega 60 segundos a permanencia, ocupación, posiciones ni cruces. Los buckets afectados conservan cobertura parcial o sin datos, nunca ceros inferidos. La duración conocida de la sesión incluye ese intervalo, como ya establece el historial webcam.

La cobertura distingue una pausa del operador de un fallo de cámara. El reporte mantiene el aviso de observaciones incompletas e identifica la pausa voluntaria en sus detalles. Una visita que estaba en curso queda cortada al pausar, sin afirmar continuidad ni identidad después de retomar.

## Transporte y compatibilidad

Se extienden los mensajes de estado y REST para representar la pausa y sus revisiones. Se mantienen el WebSocket actual, la pareja atómica frame/métricas y las validaciones de sesión, trabajo, secuencia y segmento. La UI ignora mensajes viejos que intentarían volver a captura activa después de un acuse de pausa o finalización más reciente.

No cambia la configuración inmutable de escenas ni el significado de Entrada/Salida y A/B. Los análisis de video, jobs ya finalizados y reportes históricos mantienen su comportamiento. La recuperación por fallo conserva su reconexión actual y la confirmación obligatoria de encuadre.

Los cambios de medición y operación están registrados en `AGENTS.md` y `docs/decisiones-tecnicas.md`, distinguiendo pausa voluntaria de interrupción accidental.

## Criterios de aceptación y verificación

1. Pausar y retomar conservan `session_id`, `job_id`, escena, etiquetas y conteos; no crean un trabajo nuevo.
2. No hay inferencia, frames ni posiciones durante la pausa confirmada. La cámara se cierra y el lease permanece.
3. La pausa no agrega estadías ni cruces; un track y un candidato de cruce anterior no continúan en el segmento posterior.
4. La reanudación exige encuadre nuevo confirmado; solicitudes repetidas o tokens vencidos no producen segmentos o intervalos duplicados.
5. Stop durante pausa, inferencia lenta, apertura y confirmación prevalece y finaliza sin quedar esperando un retomar.
6. Pausa/stop y checkpoint concurrentes no se pierden; un mensaje retrasado no reactiva la UI ni el worker.
7. Recarga/reconexión conserva pausa; un reinicio del worker conserva el checkpoint sin inventar la cola desconocida.
8. Frontend y API preservan aislamiento entre sesiones y ownership entre equipos.
9. Se cubren ambas etiquetas y varios ciclos de pausa con fuente fake, reloj controlado y PostgreSQL local en tests de contrato/integración; Playwright verifica controles, estado, recarga, confirmación y reporte.
10. Build y suites focalizadas pasan. La prueba física de cámara y su tiempo de reacción se documentan por separado; fixtures no acreditan rendimiento real.

## Límites de esta etapa

Se implementaron los comandos persistidos, supervisor, runner, recuperación manual, transporte de estado e interfaz. Las pruebas usan PostgreSQL local aislado y una fuente simulada; no acreditan tiempo de reacción ni rendimiento de una cámara física. No se aplicaron migraciones a la base configurada en `.env` ni a Azure. Antes de usar la funcionalidad en la app, aplicar `0012_live_manual_pause` con Alembic y reiniciar API y worker. Ver resultados y límites en el plan de implementación.
