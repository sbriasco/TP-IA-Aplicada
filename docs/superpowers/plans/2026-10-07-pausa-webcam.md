# Pausa webcam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pausar captura e inferencia y retomar en el mismo trabajo webcam, conservando conteos y registrando la pausa como tiempo no observado.

**Architecture:** Comandos bajo locks de PostgreSQL; el supervisor cierra la cámara sin terminar el trabajo y el runner confirma la pausa después del checkpoint. Se reutiliza la recuperación con apertura manual y confirmación de encuadre, manteniendo el origen monotónico y abriendo un segmento nuevo. El frontend consume el estado persistido por REST y el WebSocket existente.

**Tech Stack:** Python/FastAPI, SQLAlchemy/Alembic, PostgreSQL local, React/TypeScript estricto, CSS Modules y tokens existentes; pytest y Playwright. Sin dependencias nuevas.

**Spec:** [Especificación aprobada](../specs/2026-10-07-pausa-webcam.md).

## Global Constraints

- Se mantiene `ProcessingJob.status=processing` mientras el trabajo permanece pausado.
- El worker conserva la reserva del análisis y su modelo en memoria.
- No se comprime el eje temporal para ocultar la pausa.
- La reanudación exige encuadre nuevo confirmado.
- La detención tiene prioridad y nunca abre un trabajo nuevo.
- Un track previo a la pausa no se vincula con uno posterior.
- No se instalan dependencias ni se agregan servicios externos.
- No aplicar migraciones a Azure ni utilizar la base compartida o los datos de demo para pruebas destructivas.

## Review Focus

1. Una inferencia lenta termina después de solicitar pausa: conservar el resultado válido anterior al cierre y no anunciar pausa antes de persistirlo (tarea 2).
2. Checkpoint concurrente con pausa o stop: no sobrescribir el comando con `connected` (tareas 1–2).
3. Clics repetidos, token vencido y una cámara que cambia de resolución: no duplicar intervalos/segmentos ni retomar sin confirmación (tareas 1 y 3).
4. WebSocket entrega un frame viejo o se reconecta durante pausa: mantener el estado pausado hasta una reanudación válida (tarea 4).
5. Worker pierde ownership o muere durante pausa: conservar checkpoint, marcar cola desconocida y no inferir duración hasta el reinicio (tareas 3 y 5).

## Preparación de ejecución

- [ ] Inspeccionar `git status`, artefactos y `AGENTS.md`; preparar una rama `feature/pausa-webcam` sin mezclar ni trasladar modificaciones de otros cambios. Usar la skill `using-git-worktrees` para el aislamiento; seleccionar una base que incluya la consola aprobada y documentar cómo se incorpora si aún está sin commit. No resetear el checkout compartido.
- [ ] Confirmar cabeza Alembic: actualmente `0011_live_zone_dwell`. Si sigue siendo la cabeza, usar `0012_live_manual_pause`; si cambió, asignar la revisión siguiente conservando una sola cabeza.
- [ ] Comprobar Python existente en `backend/.venv`, npm y PostgreSQL local de tests. No imprimir credenciales; usar la guarda `destructive_database_url` y ejecutar suites DB secuencialmente. No instalar nada nuevo.

## Tarea 1: estados persistidos y comandos idempotentes

**Files:** modificar `backend/src/flowsight/db/models.py`, `backend/src/flowsight/services/live_jobs.py`, `backend/src/flowsight/api/live_routes.py`, `backend/src/flowsight/services/live_results.py`; crear `backend/alembic/versions/0012_live_manual_pause.py` y `backend/tests/contract/test_live_pause.py`; ampliar `backend/tests/integration/test_live_schema.py`.

**Interfaces:**
- `request_live_pause(database: Session, job_id: UUID, now: datetime, *, machine_id: str) -> ProcessingJob`.
- `request_live_continue(database: Session, job_id: UUID, now: datetime, *, machine_id: str) -> ProcessingJob`.
- `POST /jobs/{job_id}/live/pause` y `POST /jobs/{job_id}/live/continue`: 202, respuesta `{job_id, pause_requested: true}` o `{job_id, resume_requested: true}`. Se conserva `live/confirm-resume` para la confirmación.
- Nuevos estados `pausing`, `paused`; campos UTC nullable `pause_requested_at`, `paused_at`, `resume_requested_at`. `LiveInterruption.reason="operator_pause"` identifica la pausa voluntaria.

- [ ] Escribir tests de contrato `test_pause_is_idempotent`, `test_continue_requires_acknowledged_pause`, `test_stop_wins_over_pause_and_continue`, `test_pause_rejects_wrong_machine_and_non_live_job`. Assert: mismo job/sesión, una solicitud por transición; 409 si estado incompatible; sin cambios ante ownership incorrecto o sesión retirada.
- [ ] Ejecutar desde `backend`: `.venv/Scripts/python.exe -m pytest tests/contract/test_live_pause.py -q`. Confirmar fallo por ausencia de endpoints/estados.
- [ ] Agregar migración reversible y estados/campos del modelo. Usar locks y orden de adquisición compatibles con comandos de recuperación; verificar sesión activa y lease. No reutilizar `stop_requested_at` para pausa. Repetir pausa en `pausing/paused` no reinicia el ciclo; repetir continue pendiente no reinicia probe ni nonce. Un stop ya solicitado rechaza nuevos comandos.
- [ ] Proteger `persist_live_checkpoint`: la presencia de un comando nuevo tiene prioridad frente al frame persistido; no borrar una confirmación nueva por un checkpoint anterior. Exponer los estados en `load_live_results` sin cambiar conteos ni la clasificación de los eventos.
- [ ] Agregar test de upgrade/downgrade en PostgreSQL local: una fila anterior mantiene sus conteos; la nueva constraint acepta `paused` y rechaza estados desconocidos; downgrade no oculta silenciosamente trabajos pausados activos.
- [ ] Ejecutar contrato y esquema hasta PASS. Commit limitado a los archivos de esta tarea: `feat: persist webcam pause commands`.

## Tarea 2: cerrar captura y confirmar la pausa sin finalizar

**Files:** modificar `backend/src/flowsight/worker/live_analysis.py`, `backend/src/flowsight/services/live_results.py`, `backend/src/flowsight/worker/live_checkpoint.py` solo si su interfaz de flush lo exige; crear `backend/src/flowsight/worker/live_pause.py` y `backend/tests/integration/test_live_pause.py`; ampliar `backend/tests/unit/test_live_control.py`.

**Interfaces:**
- `LiveStopControl.pause_pending: threading.Event`, `pause_capture_ns: int | None`, `acknowledge_pause() -> None`. Separados de `stopping` y `capture_stopped_ns`.
- `acknowledge_live_pause(factory, job_id: UUID, *, boundary_seconds: Decimal, now: datetime, owner_guard: Callable[[Session], bool]) -> int`: retorna revisión persistida; cierra segmento y crea un único intervalo de pausa bajo locks.
- `wait_for_live_continue(factory, job_id: UUID, *, control, owner_guard) -> bool`: conserva heartbeat; retorna false si stop, sin abrir cámara mientras está pausado.

- [ ] Escribir `test_pause_closes_camera_without_terminal_status`, `test_pause_waits_for_inflight_inference_and_checkpoint`, `test_checkpoint_does_not_erase_pause_or_stop`. Assert: fuente cerrada, ningún frame/inferencia adicional, job processing, solo un intervalo operator_pause y conteos previos íntegros.
- [ ] Ejecutar `.venv/Scripts/python.exe -m pytest tests/unit/test_live_control.py tests/integration/test_live_pause.py -q --basetemp=.pytest-tmp-pause`. Confirmar fallos específicos antes de implementar.
- [ ] Extender el supervisor: observar pausa, cerrar fuente y recordar límite monotónico sin activar `stopping`. Stop/fallo de ownership mantienen prioridad; la pausa no termina el supervisor.
- [ ] Integrar rama manual en el runner antes de leer otra imagen y en el manejo de lectura cerrada. Terminar solo la inferencia válida que ya estaba iniciada; cortar counter/dwell/sampler y tracker, descartar candidatos pendientes según reglas existentes, persistir y hacer flush antes de `paused`. La revisión del acuse supera cualquier frame del segmento anterior.
- [ ] Implementar helpers en `live_pause.py`: intervalo único por ciclo; registrar el tramo desde la última observación hasta el cierre como no observado cuando corresponda. Mantener `epoch_ns`; no sumar estadía durante espera. El bucle espera continue o stop con polling acotado y verificación de ownership, sin capturar ni inferir.
- [ ] Ejecutar pruebas hasta PASS incluyendo repetición del comando durante inferencia. Commit: `feat: pause live capture at a durable checkpoint`.

## Tarea 3: retomar con encuadre nuevo y segmento aislado

**Files:** modificar `backend/src/flowsight/worker/live_recovery.py`, `backend/src/flowsight/worker/live_analysis.py`, `backend/src/flowsight/services/live_jobs.py`, `backend/src/flowsight/services/live_results.py`, `backend/src/flowsight/worker/lifecycle.py` solo en el tratamiento necesario de la cola pausada; ampliar `backend/tests/integration/test_live_pause.py` y `backend/tests/integration/test_live_recovery.py`.

**Interfaces:** extender `recover_capture(..., interruption_reason: str="capture_lost", interruption_registered: bool=False) -> ResumedCapture | None`. Para pausa, invocarlo únicamente después de `wait_for_live_continue=True`, con motivo operator_pause ya registrado. `ResumedCapture(source, minimum_sequence, revision)` y `confirm-resume` mantienen el contrato existente.

- [ ] Tests: `test_pause_resume_keeps_ids_and_totals`, `test_pause_does_not_extend_dwell_or_link_tracks`, `test_pause_120_resume_180_keeps_missing_interval`, `test_expired_probe_requires_retry`, `test_stop_during_pause_probe_and_confirmation`, `test_worker_restart_during_pause_preserves_unknown_tail`. Añadir dos ciclos y secuencias monotónicas sin segmentos duplicados.
- [ ] Ejecutar `.venv/Scripts/python.exe -m pytest tests/integration/test_live_pause.py tests/integration/test_live_recovery.py -q --basetemp=.pytest-tmp-pause`. Confirmar fallos por falta de reanudación manual.
- [ ] Reutilizar apertura y token de recuperación sin registrar un segundo intervalo capture_lost para la misma pausa. Si falla el probe, conservar intervalo original y permitir retry/confirm-resume bajo las validaciones existentes. No retomar por reconexión del navegador.
- [ ] En el primer frame confirmado, cerrar el intervalo operator_pause, incrementar segmento, descartar frames neutrales usados por el probe y limpiar comandos de ese ciclo bajo lock. Continuar acumuladores; reiniciar continuidad del tracker/reglas y rendimiento. Registrar `reason="operator_resume"` en el segmento nuevo si su constraint lo requiere.
- [ ] Cerrar el intervalo abierto al detener desde pausa utilizando el límite de captura monotónico de stop; actualizar cobertura/buckets sin inferir ocupación. Fallo/reinicio mantiene desconocida la cola cuyo final no se pudo medir, incluso si la pausa era manual.
- [ ] Ejecutar suites de pausa, recuperación, análisis y estadística secuencialmente. Commit: `feat: resume paused webcam with framing confirmation`.

## Tarea 4: interfaz, estado ordenado y reporte

**Files:** modificar `frontend/src/api/live.ts`, `frontend/src/api/liveMessages.ts`, `frontend/src/types/live.ts`, `frontend/src/pages/LiveAnalysisPage.tsx`, `frontend/src/pages/LiveAnalysisPage.module.css`, `frontend/src/pages/LiveResultsPage.tsx`; extender `frontend/tests/LiveAnalysisPage.test.tsx` y `frontend/tests/LiveResultsPage.test.tsx`; ampliar `backend/tests/contract/test_live_preview.py` y, si hace falta, `backend/src/flowsight/api/live_public.py`.

**Interfaces:** `pauseWebcam(base: string, jobId: string): Promise<void>` y `continueWebcam(base: string, jobId: string): Promise<void>`. Parsear `live.status` con identidad, revisión entera no negativa, captura y cobertura. REST reconstruye la pausa al montar; el WS público actual ya consulta estado de DB cuando no hay frames.

- [ ] Tests frontend: `pause_waits_for_worker_ack`, `reload_keeps_paused`, `stale_update_cannot_override_pause`, `terminal_wins_over_continue`, `resume_requires_fresh_confirmation`. Assert: controles exactos de la spec, conteos retenidos, telemetría no fresca y ninguna llamada duplicada. Backend preview: estados pausing/paused y rechazo de frames anteriores al acuse.
- [ ] Ejecutar desde `frontend`: `npm test -- tests/LiveAnalysisPage.test.tsx tests/LiveResultsPage.test.tsx`; desde backend ejecutar test_live_preview. Confirmar fallos específicos.
- [ ] Agregar botones Pausar/Retomar, estado Pausando/Pausado y overlay que distingue pausa de stop/fallo. Mantener Detener y reporte. Reutilizar controles de confirmación; no sustituir el estado real por el éxito del POST. Tras un fallo de comando, explicar y permitir reintentar.
- [ ] Incorporar revisión mínima de los mensajes de estado para rechazar live.update atrasados; admitir primer frame nuevo después de confirmación. Restablecer el estado desde REST al recargar y continuar la recuperación del WS existente. Mientras pausa, ocultar o marcar frame/latencia como última observación, sin declarar frescura.
- [ ] Mostrar el motivo operator_pause como «Pausa del operador» en diagnóstico del reporte, conservando cobertura incompleta y duración total conocida. Conservar ambos modos de etiquetas y el layout de escritorio sin scroll.
- [ ] Ejecutar tests hasta PASS y `npm run build`. Commit: `feat: add pause controls to live monitoring`.

## Tarea 5: recorridos completos y documentación

**Files:** ampliar `frontend/e2e/live.spec.ts`, `frontend/e2e/live-statistics.spec.ts`, `AGENTS.md`, `docs/decisiones-tecnicas.md`, `docs/monitoreo-webcam-2026-10-06.md`; registrar resultado en este plan.

- [ ] Añadir Playwright con fixtures: active→pausing→paused→reload→continue→confirmación→nuevo frame; stop desde pausa; reporte con pausa voluntaria y conteos conservados. Verificar escritorio 1366×768 y 1920×900, móvil y teclado, ambas etiquetas, y cero scroll de página/panel principal con detalles cerrados.
- [ ] Añadir al recorrido integrado fake dos ciclos con mismo job y sesión, uno terminado durante pausa. Usar PostgreSQL local aislado y fuente fake, sin cámara física ni cambios a sesiones de demo.
- [ ] Ejecutar `npm run test:e2e:ui -- live-statistics.spec.ts`; luego `npm run test:e2e -- live.spec.ts` con el runner existente y su configuración de pruebas. Ejecutar suites backend focalizadas secuencialmente, `npm run build` y `git diff --check`. Revisar capturas y cualquier regresión de reconexión o etiquetas.
- [ ] Alinear AGENTS y decisiones técnicas: cámara liberada, worker reservado, duración incluyendo pausa, ausencia de continuidad de tracks, pausa voluntaria frente a fallo. Registrar comandos y resultados realmente ejecutados y límites de hardware; no afirmar latencia o rendimiento físico sin medición.
- [ ] Revisar el conjunto contra los diez criterios de la spec y los cinco riesgos de este plan. No declarar terminado si algún test de invariantes está omitido por infraestructura; resolver o documentar el bloqueo concreto.
- [ ] Commit final de tests/docs. Preparar un PR breve solo con esta funcionalidad, base correcta y tarea de Boards si se proporciona/aplica al agregado webcam; no inventar IDs ni integrar/mergear otras modificaciones del workspace.

## Revisión del plan

La auto-revisión cubrió todos los criterios de la especificación: comandos/aislamiento (tarea 1), captura y checkpoint (2), métricas/segmentos/stop/reinicio (3), transporte/UX/recarga (4), pruebas completas y documentación (5). Las interfaces entre tareas coinciden. La reutilización de recuperación es deliberadamente limitada: una pausa nunca debe disparar la reconexión automática antes del comando continue.

Estado: plan aprobado por el usuario e implementado el 2026-10-07 mediante ejecución en este chat. La aplicación de la migración a la base de la app sigue pendiente.

## Resultado de ejecución

La lista anterior conserva los pasos del plan original. Las cinco tareas se implementaron y verificaron; las siguientes sustituciones registran el alcance realmente ejecutado:

| Tarea | Resultado |
| --- | --- |
| 1. Persistencia y comandos | Migración `0012_live_manual_pause`, comandos idempotentes bajo locks y pruebas de contrato/esquema. El test de contrato se llama `test_live_pause_commands.py` para evitar colisión de módulos pytest. |
| 2. Pausa durable | Cámara cerrada por supervisor, inferencia en curso y checkpoint terminados antes del acuse. La pausa no termina el job ni su reserva. |
| 3. Reanudación | Reutiliza recuperación y confirmación de encuadre. Conserva IDs y métricas positivas, corta continuidad, registra `operator_resume` y mantiene duración/cobertura. Los casos de probe vencido y stop durante recuperación usan las pruebas existentes de recuperación. |
| 4. Interfaz y reporte | Pausar/Retomar, REST al recargar, revisiones y frames atrasados, checkpoint final de la línea seleccionada, reporte de pausa y estilos existentes. |
| 5. Recorridos y documentación | `live-pause.spec.ts` integra API, worker y PostgreSQL local; `live-statistics.spec.ts` verifica teclado, ambos temas y etiquetas, escritorio sin scroll y ancho móvil. AGENTS y decisiones alineados. |

Revisión final independiente: se corrigieron dos hallazgos, reproduciendo cada fallo antes de corregirlo: un checkpoint con segmento `analysis_gap` podía borrar la solicitud de pausa; el panel podía conservar métricas anteriores a la última inferencia al recibir el acuse. Se agregó además una regresión para respetar la línea seleccionada al refrescar ese checkpoint.

Verificación final:

- Frontend: `npm test -- --maxWorkers=1`: **351 pruebas, 36 archivos aprobados**. La ejecución concurrente presentó un timeout ajeno en `SessionResultsPage`; se verificó la suite completa en serie sin cambiar ese componente.
- `npm run build`: aprobado; continúa la advertencia existente por bundle mayor a 500 kB.
- `npm run test:e2e:ui -- live-statistics.spec.ts`: **8 recorridos aprobados**; capturas de pausa y confirmación de encuadre inspeccionadas. Escritorio 1366×768 y 1920×900, móvil, modo claro/oscuro y ambas etiquetas.
- `npm run test:e2e -- live-pause.spec.ts`: **1 recorrido integrado aprobado**, con dos ciclos, recarga, misma sesión/job, conteos conservados y stop desde pausa.
- Backend focalizado: **66 pruebas aprobadas** en comandos, preview, pausa, recuperación, runner, esquema, estadísticas y control. Se explicitó el worker ID del fixture de contrato para que pueda ejecutarse solo, sin depender del orden de la suite.
- Suite completa backend, desde `backend`, con PostgreSQL de pruebas aislado: **640 aprobadas, 3 fallidas, 1 omitida por permisos POSIX en Windows, 1 deseleccionada y 5 subtests aprobados**. Dos contratos antiguos de carga esperan error por machine ID ausente/inválido, aunque la inicialización automática existente genera el equipo local (`configure_local_webcam`, fuera de este cambio). El diagnóstico `test_reports_ready_environment_without_exposing_database_url` lee la base real de `.env`, que no respondió. Se preservó esa configuración y no se modificaron esas pruebas ajenas.
- Ruff de los archivos backend modificados y `git diff --check`: aprobados. Logs y capturas locales en `.verification/pausa-webcam/`.

Los comandos integrados usan bases dedicadas al puerto local 55432. API y worker de E2E comparten puerto 8015. No se instalaron dependencias, no se usaron datos de demo ni se aplicaron migraciones a Azure. La cámara física y el tiempo de reacción quedan sin medir.

El worktree nativo se creó, pero el sandbox rechazó sus escrituras; se archivó y se aplicó el fallback documentado al checkout actual. No se hicieron commits ni PR para evitar mezclar cambios previos del workspace. No se inventó una tarea de Boards.

Para activar en la app: desde `backend`, ejecutar `& ..\scripts\update-database.ps1` y reiniciar API y worker. Este script carga el `.env` de la raíz antes de llamar a Alembic; `python -m alembic` por sí solo requiere exportar previamente `FLOWSIGHT_DATABASE_URL` al proceso. Esta ejecución solo migró las bases locales descartables de pruebas.
