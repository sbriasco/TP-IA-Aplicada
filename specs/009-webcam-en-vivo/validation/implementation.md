# Registro de ejecución · Feature 009

## 2026-10-03 · Inicio

- Rama verificada: `feature/009-webcam-en-vivo`. Se reutiliza esta rama de feature y sus documentos pendientes; no se crea otro checkout que pierda el contexto.
- Spec Kit tasks: setup-tasks y check-prerequisites -RequireTasks -IncludeTasks ejecutados; generado tasks.md con36 tareas, US1=7, US2=6, US3=7, setup/foundation=12, validación=4.
- Gate de requisitos: requirements.md tiene16 casillas aprobadas, cero pendientes. No se modificó durante implementación.
- Hooks before/after_tasks y before_implement: únicamente Git opcional, disponible como `/speckit-git-commit`, no ejecutado.
- Entorno inspeccionado: Python3.13 instalado, Node24.11.1 instalado; faltan backend/.venv, frontend/node_modules y PostgreSQL17 local. No se instalaron dependencias ni runtimes.
- Los locks mantienen Python3.11, Node22.20, PostgreSQL17 y dependencias existentes. `.gitignore` cubre venv/node_modules/.tools/.postgres-data, secretos, pesos y salidas; no hace falta ampliar ignores.
- Pendientes de respuesta: autorización de preparación del entorno fijado y vínculo Azure Boards (o autorización explícita de vinculación posterior). No se declara funcionamiento sin ejecutar pruebas.
- T001: inspección de entorno/ignores/locks completada. El setup de runtimes sigue pendiente y se registra por separado; no se da por ejecutada ninguna prueba.

## Evidencia pendiente

### Entorno listo y primeros incrementos

- `install-prerequisites.ps1` finalizó: Python3.11.16, Node22.20.0, PostgreSQL17.6 local en5432, base flowsight. `.env` generado, no versionado. Pip lock --no-deps e instalación editable pasaron; npm ci instaló168 paquetes.
- `check-environment.ps1 -OutputFormat Json`: ready, todos los componentes ok. No nuevas dependencias ni cambios de versiones.
- Frontend base: TypeScript lint pasó; Vitest con1 worker pasó30 archivos/298 pruebas después de finalizar instalaciones. Intentos concurrentes previos dieron errores de arranque y un timeout de5000ms; el rerun sin carga de instalación los resolvió sin modificar frontend.
- Modelo/esquema parcial T003/T004: RED por ausencia de WEBCAM/tablas y falta de rechazo de source en sesión sintética; GREEN para3 pruebas, incluyendo upgrade0008→head dos veces y downgrade protegido. Falta ampliar aislamiento por estado/job/local y triggers correspondientes; estas tareas siguen pendientes.
- T009/T010:9 pruebas temporales live + regresión de conteo de archivos; tracker reset probado RED por método ausente y GREEN sin recargar pesos. El contador descarta candidato perdido antes de confirmar, confirma en el tiempo original, respeta frontera de oscilación y estado máximo2048.
- T011/T012:4 pruebas de muestreo RED por módulo ausente, GREEN tras implementación y ajuste de expiraciónTTL exacto1s. Reservoir y dirty slots acotados; no imágenes almacenadas.
- Última ejecución conjunta:29 pruebas backend aprobadas (live temporal, muestreo, conteo archivo, tracker y esquema). Captura hardware/worker/API/UI aún no implementados. Verificaciones físicas siguen pendientes.

Usuario autorizó instalar runtimes y dependencias fijados (2026-10-03). Instalación iniciada con scripts/install-prerequisites.ps1; primer intento sin red falló, reintentado con elevación autorizada. Destinos de limpieza verificados dentro del proyecto. Se retoma implementación sin requerir vínculo Azure Boards.

Actualización del usuario (2026-10-03): este agregado queda fuera de Azure Boards porque corresponde a la expo del profesor y no al TP. T002 completada mediante registro local; spec/plan/research alineados. Usuario confirma que esta PC no tiene el entorno del proyecto. La autorización de instalación sigue pendiente; no se instaló nada.

Registrar RED→GREEN de cada incremento, resultados concretos de PostgreSQL, worker/API, Vitest/build/Playwright, sobrecarga600s y estabilidad7200s. Validación física tiene archivo separado; fuente fake no prueba precisión ni latencia con hardware real.

### Fundación y afinidad de equipo
- T003–T008 completadas: esquema con restricciones entre sesión/job/segmento/local, lease exclusivo por equipo, heartbeat independiente, reservas y captura spawn con slot único.
- Verificación: test_live_schema.py (10), test_live_capture.py (5), test_live_spatial.py (9), test_live_sampling.py (4), test_ultralytics_tracker.py (8).
- Pruebas de afinidad y regresión de admisión: test_jobs_gate_api.py + test_video_analysis_job.py + test_live_machine.py: 33 passed.
- Tras separar admisión del controlador: test_live_control.py + test_live_machine.py: 8 passed.
- No se ha validado una webcam física ni rendimiento de YOLO en este equipo.


### Preparación e inicio (2026-10-04)
- T013/T014: ocho contratos REST aprobados después del RED por rutas ausentes: preparación sin job, probe fallido sin persistencia, confirmación obligatoria, token consumible/expirado/de otra sesión, retiro de cámara durante probe e índices allowlist.
- T015: cuatro pruebas worker (claim scoped, stop pendiente sin abrir cámara/modelo, checkpoint con tiempos de captura, stop liberando cámara durante inferencia).
- Suite de preparación/worker/regresión de admisión: 32 passed en105.57s.
- Frontend: LivePreparationPage.test.tsx, 2 passed después del RED por módulo ausente y corrección de etiquetas explícitas. Lint aún en ejecución.
- Ruling: adelantar transporte de control T020/T021 antes de cerrar US1 — live/probe depende del WS interno, aunque tasks lo ubica en US2 — coste: cambiar el orden de integración, sin ampliar alcance.
- Ruling: ubicar pruebas React en frontend/tests como el resto del repositorio; paths en tasks alineados.
- T016/T017/T018/T019 permanecen pendientes hasta conectar canal real, terminar contrato/control REST y verificar navegación/E2E. Runner básico ya existe, pero todavía faltan buckets, publicación, segmentos de recuperación y buffers ante fallo DB.


### Canal, estadísticas y lectura durable (2026-10-05)
- T019: formulario, comprobación con vencimiento, confirmación y navegación de origen; Vitest2 y TypeScript lint aprobados. Tests React en frontend/tests siguiendo estructura existente; E2E pendiente T018/T025.
- T020: WS productor loopback/owner/token, rechazo de peer remoto, probe request/reply autenticado, clock público, mensajes finitos/bounded, revision/sequence, ocho observadores y TTL. Última suite: test_live_preview.py + test_live_publisher.py:16 passed (17.87s).
- Prueba clock sin imagen de referencia como vivo:1 passed. Se interrumpió primer intento porque aún iba por branch sintético y no respondía al ping; después de agregar branch live pasó.
- T022 parcial: buffers de minutos60/local, atribución original, cobertura global tras eviction, checkpoint transaccional idempotente con rollback completo y snapshot imagen/cifras. Suite buckets + estadísticas + runner:11 passed. Falta completar writer independiente/buffers de falla y cadencia bajo inferencia lenta (T028).
- Primeros contratos de resultados/eventos: RED por endpoints ausentes; reader incluye aislamiento/soft-delete, filtros y cursor ligado a job/shop/filtros/horizonte durable. Resultado de suite pendiente de registrar.
- T021 productor/control y public observer implementados; falta verificar API/worker reales con fuente fake, junto al recorrido E2E.

## Ejecución 2026-10-05 · Pantallas y checkpoints independientes

- T023: parser con límites e identidad/revisión/secuencia, calibración por mínimo RTT y buckets del backend; pantalla reemplaza imagen/cifras juntas y espera `job.terminal` al detener. Vitest `LiveAnalysisPage.test.tsx liveMessages.test.ts`: 8 aprobadas tras RED por página ausente y contrato de buckets incorrecto.
- Historial de webcam con cruces, cobertura independiente del cierre, duración del checkpoint, huecos y muestra máxima 2000 puntos sobre la referencia. Pruebas `LiveResultsPage.test.tsx`: 2 aprobadas; `SessionsPage.test.tsx` + historial: 9 aprobadas. Recuperación de encuadre todavía pendiente, por eso T032 sigue abierta.
- T029/T030: contratos REST, cursores ligados al job/local/filtros, snapshot repeatable-read, historial source-aware y muestras con `capture_timestamp_seconds`; no video_timestamp falso. Chat rechazado antes de cifras/LLM, incluyendo guard tras resolución de sesión. `pytest tests/contract/test_live_results.py`: 7 aprobadas. Regresión de chat/archivos aún pendiente en T034.
- Prueba completa API/worker/Playwright detectó una incompatibilidad real: `ProcessFrameSource` no acepta `environment`; se retiró ese argumento del probe y runner. Test de constructor RED con TypeError y luego GREEN. El navegador Chromium de Playwright se instaló dentro de `.tools/playwright` (ignorado), como parte del entorno de pruebas autorizado.
- Import de API medido: 29.23 s con caché fría en esta máquina; el runner E2E da 120 s de arranque en Windows. No cambia presupuestos de captura ni latencia analítica.
- Writer de checkpoints independiente cada 1 s: snapshot sin imagen, deltas acotados, ACK solo tras commit y conserva reemplazos llegados durante write. Límite 4096 hechos/20000 slots y 5 s sin commit; callback cierra captura ante fallo. Unit tests writer 4 aprobadas.
- Cierre captura durante inferencia y timestamp de stop conservado: RED mostró 99 s ficticios en duración; ahora guarda 1 s cuando se cierra antes de que la inferencia retorne. Checkpoint del primer frame se verifica mientras se bloquea la siguiente inferencia.
- Recuperación scoped del worker deja failed/unknown_tail y cierra buckets sin inventar el fin de captura. Suite combinada `test_live_checkpoint.py test_live_publisher.py test_live_analysis_job.py test_live_statistics.py test_live_recovery.py`: 16 aprobadas. Ruff de estos archivos aprobado. T016/T028 siguen abiertas: faltan recuperación de cámara, fence de owner y ensayo DB completo.
- E2E fake escrito para preparación/editor/check/start/reload/stop/historial; ejecución posterior a las correcciones todavía pendiente. Ninguna prueba física o de estabilidad se declara cumplida con estas pruebas.
## E2E completo 2026-10-05 · Cámara reproducible

`npm run test:e2e -- live.spec.ts` con `PLAYWRIGHT_BROWSERS_PATH=.tools/playwright`: **1 passed (22.8 s)**; recorrido de prueba19.1 s. API/worker/PostgreSQL/WS/Chromium reales, fuente y detector fake. Preparación201, edición/guardado de escena, check200, start201, preview vivo/gráfico/contadores, reload, stop202→completed/result_complete y consulta histórica de muestra/heatmap sin video/chat.

La ejecución detectó dos fallos que se corrigieron antes de esta evidencia: imports completos del worker al hacer spawn en Windows (se movieron al entry point), y cierre concurrente del proceso de captura desde runner/control. La carrera de `Process.close()` se reprodujo con un test determinista (ValueError RED), se serializó el ciclo de vida y quedó GREEN. No se ampliaron budgets analíticos/probe para hacer pasar la captura. Config/bootstrap y pruebas writer/probe:28 aprobadas +5 subtests.

T018/T021/T022/T025/T031 cerradas con esta evidencia y las pruebas previas; no se declara terminada US3, precisión física ni estabilidad2h.

## Recuperación y propiedad exclusiva · 2026-10-05

- El inicio analítico usa el primer frame disponible después de cargar el detector: el tiempo previo no se agrega a duración/cobertura. Integración de reloj y estadísticas: 9 aprobadas (29.96 s).
- RED/GREEN: un checkpoint atrasado reabría `capture_status=connected` después de un fallo. El writer ahora verifica el estado del job bajo lock y omite escrituras posteriores al estado terminal.
- Fence transaccional del `owner_epoch` de WorkerMachine antes del lock del job. Un owner anterior no puede guardar ni finalizar; la pérdida de ownership detiene el writer inmediatamente y el supervisor cierra captura independientemente de la inferencia. Main/lifecycle transmiten health/epoch al runner.
- RED/GREEN: detener durante `source.start()` producía failed. Ahora finaliza con duración cero, sin cargar el modelo, y conserva el control de propiedad antes de la transición.
- `pytest test_live_analysis_job.py test_live_statistics.py test_live_checkpoint.py test_live_control.py`: **19 passed (45.27 s)**. Test adicional del supervisor cerrando por ownership sin gracia DB: **1 passed (2.84 s)**. Ruff de los nueve archivos modificados aprobado.
- Una ejecución previa produjo 12 aprobadas y un error de setup por ACL de `.pytest-tmp` en Windows. Se repitió en un directorio nuevo bajo `.verification`, sin borrar ni cambiar permisos del anterior, y pasó la suite anterior.
- RED/GREEN frontend: si REST fallaba al reconectar el WS, la pantalla abandonaba los reintentos. Ahora continúa con pausas 1/2/5 s y limpia los timers al salir. `LiveAnalysisPage.test.tsx`: **4 passed**; TypeScript lint aprobado.
- T016/T024/T026–028/T032 siguen abiertas: falta reconexión del dispositivo con confirmación de encuadre, nuevos segmentos, validación DB completa y medición del primer pintado. No se cierran tareas por estos arreglos parciales. Estabilidad, regresión completa y webcam física siguen pendientes.

- Huecos analíticos mayores a 1 s: RED detectó que el runner conservaba el mismo segmento. Ahora hace flush del anterior, reinicia tracking y continuidad de muestras, y guarda el cierre/nuevo segmento/interrupción conocidos en el siguiente checkpoint transaccional. La prueba conserva un cruce anterior y demuestra que no inventa un cruce a través del hueco, con muestras vinculadas a ambos segmentos y tiempos 0–0.5 / 2.7–3.1 s. Suite runner/estadísticas/writer/supervisor/contador/sampler: **34 passed (61.57 s)**; Ruff aprobado. Sigue pendiente la reconexión física con nuevo encuadre, que es un flujo distinto de este hueco de inferencia.

- T017: todas las rutas REST live exponen errores DB como 503 seguro; cinco contratos RED por SQLAlchemyError sin manejar y luego GREEN. Contrato de retry/confirm-resume demuestra que retry invalida el nonce anterior, requiere confirmación explícita y consume una vez el nonce nuevo. RED aceptaba el nonce anterior con 202; corregido con invalidación por job. `test_live_sessions.py` + `test_live_recovery.py`: **17 passed (64.84 s)**. Se cierra la exposición REST T017; el worker y WS de recuperación T027 y su UI T032 permanecen pendientes.

## Canal y controles de encuadre · 2026-10-05

- `capture.reconnect-check` validado separadamente: UUID/job/segment/revisión, allowlist de dispositivo/backend, dimensiones y JPEG acotados; no admite métricas ni timestamps de análisis. API exige owner vigente y job claimed/processing/awaiting_confirmation, emite nonce ligado al próximo segmento y publica `live.reconnect-check` neutral. No modifica horizonte ni cifras.
- Broker mantiene una sola imagen neutral con TTL10 s, también al suscribir después de reload, y elimina pendientes vencidos. Pruebas RED por schema/método ausentes; GREEN después de implementación. El contexto de dispositivo/segmento/revisión incorrecto cierra1008. `test_live_preview.py`: **19 passed (21.66 s)**; Ruff aprobado.
- Invalidación de nonce de retry dentro del lock del job: producer ingress adquiere el mismo lock antes de emitir nonce nuevo. Evita invalidar por carrera una comprobación emitida después del commit. Contrato retry previo sigue GREEN: **1 passed (2.72 s)**.
- Frontend valida runtime el mensaje neutral, requiere checkbox explícito, vence el control en60 s, ofrece retry y conserva el par imagen/cifras anterior hasta un frame válido del nuevo segmento. La imagen de comprobación está separada y etiquetada como no analizada. Tests RED por controles ausentes y GREEN después; no se infiere recuperación física de estas pruebas.
- RED/GREEN adicional: un mensaje anterior al checkpoint REST se aceptaba como vivo. La pantalla ahora conserva una revisión mínima durable al reconectar y rechaza mensajes anteriores.
- `LiveAnalysisPage.test.tsx`, `LiveResultsPage.test.tsx`, `SessionsPage.test.tsx`, `liveMessages.test.ts`: **22 passed (4.07 s)**. TypeScript lint repetido con todas las modificaciones anteriores: aprobado (exit0).
- T027/T032 permanecen abiertas hasta integrar el ciclo del dispositivo, los tres intentos, la espera de confirmación y Playwright de recuperación con API/worker reales. No hay cambios de estado global del goal ni evidencia de webcam física.

## Cierre de implementación · 2026-10-05

- Reconexión del runner implementada: tres opens por ciclo, espera neutral, TTL60s y retry manual; no inferencia hasta confirmación. Continuidad reiniciada conserva cruces previos, nuevos segmentos y huecos. Confirmación/stop/retry sobreviven a la desconexión WS porque son flags transaccionales DB, una decisión documentada respecto del control WS inicial.
- Recovery/runner/estadísticas:19 aprobadas (52.75s); recovery/control/capture/config:37 aprobadas +5 subtests (25.30s). Neutral WS:19 aprobadas. E2E real API/worker/PostgreSQL/Chromium, fuente/detector fake:2 aprobadas (46.9s), incluyendo falla inyectada, reload de comprobación neutral, ausencia de análisis durante espera, confirmación y cierre histórico con hueco.
- DB outage se inyecta con OperationalError después del primer checkpoint: captura se cierra, el horizonte durable permanece y restart marca cola desconocida sin inventar fin. Writer usa lock con timeout acotado. Recovery+writer:13 aprobadas (36.15s). No se apagó una base compartida ni se usó Azure.
- FPS diagnósticos usan deltas de ventana5s, reset en discontinuidad y máximo2048 puntos. Prueba de secuencia inicial alta, cambio de frecuencia y reset: GREEN; FPS+writer6 aprobadas.
- Primer pintado estimado mediante load + dos requestAnimationFrame y reloj calibrado; publica solo agregados flowsight:live-latency, sin imágenes ni buffer de muestras. Test comprueba que no emite antes del pintado y no duplica; declara sin calibración cuando corresponde. LiveAnalysis8 aprobadas. Esto no demuestra p95 físico.
- Token vacío de .env.example ahora equivale a no configurado: prueba RED/GREEN. Config22 aprobadas +5 subtests.
- Smoke Overload10s: captura fake real30FPS/proceso separado, consume lento y elimina demora al80%;135 analizados,148 descartados, pendiente máximo1,220 muestras; cierre liberado. Harness permite600/7200s y RSS externo/almacenamiento opcional. Alcance es captura+sampler; no se presenta como estabilidad de aplicación completa ni SC-003/SC-007 cumplidos.
- Revisión final independiente requerida por skill: sin errores Critical/Important confirmados; física y larga duración pendientes.
- Regresión backend completa:603 aprobadas,1 omitida por permisos POSIX en Windows,1 deseleccionada y5 subtests (948.52s). Ejecutada antes de los últimos cambios de FPS/token, ver comprobación adicional final. Ruff backend y git diff --check aprobados. Build frontend aprobado; advertencia de chunk >500kB permanece.
- Primera regresión Vitest:315 aprobadas y1 timeout de SessionResultsPage durante carga concurrente. Ese archivo solo pasó7/7 en14.54s; se repite suite completa sin cambiar timeout ni ocultar fallo.

### Auditoría de alcance

| Requisito | Implementación y evidencia | Límite |
|---|---|---|
| FR-001–003 | Preparación/check/start, escena inmutable y confirmación; contratos + E2E | Webcam física pendiente |
| FR-004–007 | YOLO/ByteTrack vigente, latest frame, reloj de captura y contador temporal | Precisión de YOLO real sin medir en esta PC |
| FR-008–011 | Par imagen/cifras, sentidos, buckets, WS acotado, reloj/FPS/pintado | p95 objetivo no evaluado |
| FR-012 | Tres retries, comprobación neutral, reset y huecos | Recuperación física pendiente |
| FR-013–014 | Resultados y heatmap persistidos, guard chat, solo referencia en disco | Auditoría prolongada pendiente |
| FR-015–017 | Origen separado, FrameSource futuroIP, owner/aislamiento/bajas | IP no implementada |
| FR-018–021 | Evidencia explícita, reservoir20k/query2k, atribución tardía, flush/fallo | Duración2h y multitud no evaluadas |
| SC-001 | Recorrido sintético E2E aprobado | Parte física pendiente |
| SC-002–003 | Instrumentación y ensayo de componentes disponibles | 10min y p95 completos no evaluados |
| SC-004 | Trayectorias temporales exactas aprobadas | No implica precisión visual |
| SC-005 | Formato de anotación documentado | 40 cruces reales no evaluados |
| SC-006 | Desconexión/reload/confirmación sintética aprobados | Dispositivo físico pendiente |
| SC-007 | Bounds unitarios y harness con RSS | Sesión completa2h no evaluada |
| SC-008–011 | Persistencia, restart/unknown tail, aislamiento de muestra, buckets tardíos, guard chat y regresión | Revisión prolongada de disco pendiente |

T016/T024/T026/T027/T028/T032 cierran con evidencia anterior. T035 queda abierta por requerir hardware y anotación humana; las verificaciones físicas no se simulan para marcarla cumplida. T033 contiene harness de componentes y observación externa, no equivalencia a la aceptación completa. Guía y decisiones actualizadas para el comportamiento implementado.

- Segunda regresión Vitest completa: **317 aprobadas,34 archivos (58.33s)**. El timeout anterior no reapareció. Lint TypeScript aprobado.

- Regresión Playwright completa detectó4 fallos de admisión de archivos (8 aprobadas, incluidas ambas live). La aparición de WorkerMachine tras vivo bloqueaba cualquier segundo archivo pendiente. Se preservó la cola de archivos, manteniendo claim serial y rechazo ante vivo/reserva; dos contratos pending/processing reprodujeron409 RED. Decisión R3 corregida para cumplir FR-015. Se repiten contratos y Playwright; no se oculta el fallo ni se cambia timeout.

- Corrección de cola de archivos GREEN: contratos de jobs, propiedad de máquina, preparación/errores live y FPS **42 aprobadas (116.98s)**. Prueba adicional conserva rechazo machine_busy ante job live pendiente: **1 aprobada (1.68s)**. Revisor confirmó que locks/reservas/start y claim siguen serializando; sin observaciones Important.

- **Playwright final completo:12 aprobadas (1.7min)**. Incluye webcam normal y recuperación confirmada, editor, preview sintética, archivos en cola, chat, historial, baja y cancelación. Corrección de compatibilidad confirmada. T034 completa; única tarea restante T035 (webcam/40cruces/p95 físicos). Hardware y estabilidad completa2h siguen no evaluados. No hubo commit, push ni publicación en Azure Boards.

## Ajuste aprobado: selector de webcams por nombre · 2026-10-05

- Sustituida lista ficticia0–3 por enumeración DirectShow Windows/FriendlyName en helper nativo acotado; sin streaming, grabación, dependencias ni migraciones nuevas. UI agrega Actualizar cámaras, nombres, estados buscando/vacío/error y bloqueo si desaparece selección. Fake solo en entorno test, identificado como simulado. Probe DSHOW preserva correspondencia nombre/índice; .env no contiene selección de dispositivo.
- RED/GREEN: contratos API detectaron nombres inventados y200 ante fallo de descubrimiento; UI detectó botón/estado vacío ausentes. Unitarios validan orden/nombres repetidos/lista vacía/timeout/payload inválido. Probe RED por backend auto frente a DSHOW y GREEN después.
- Backend:23 aprobadas (unit discovery + contratos live,51.04s), más17 aprobadas (discovery/publisher/capture,3s). Ruff backend aprobado. Revisión independiente del delta sin Important; confirmó layout COM, releases, timeout, orden y estado de refresh.
- Smoke de enumeración nativa en esta PC:2 dispositivos detectados, sin abrir streams. No demuestra detección YOLO, precisión ni disponibilidad de las webcams; la lista puede incluir cámaras virtuales.
- Playwright live con API/worker/PostgreSQL/Chromium reales y fuente fake:2 aprobadas (57.3s), incluyendo nombre/refresh, preparación, editor, vivo, desconexión/confirmación y consulta histórica.

- Regresión frontend completa:319 aprobadas en34archivos (95.45s), antes de agregar una comprobación adicional de selección no-cero. Archivo final LivePreparationPage:5 aprobadas (1.42s), incluyendo payload real device_index1. TypeScript lint y build aprobados; advertencia previa de chunk>500kB conservada. Para este ajuste, backend se verificó con40pruebas pertinentes; no se repitió toda la suite de603 del cierre anterior.

## Verificación para commit y PR · 2026-10-05

- Frontend final:320 pruebas aprobadas en34archivos (102.52s). Ruff backend y diff staged --check aprobados. Índice revisado:112 archivos de la feature y extensión, sin videos/modelos/bases ni secretos; .env permanece excluido.
- Primer intento de regresión backend:560 aprobadas,56 errores de fixture por datos live de E2E previos incompatibles con downgrade y1 fallo intermitente de captura. Limpieza mediante fixture protegida live_engine en ejecución separada:13 pruebas aprobadas, incluyendo captura. Se repite suite completa desde la base limpia; no se modifica la migración ni se ocultan resultados.
- Regresión backend final desde base limpia:617 aprobadas,1 omitida por permisos POSIX en Windows y5 subtests aprobados (783.80s). No reapareció el fallo intermitente de captura. Validación física T035 y duración completa2h permanecen pendientes.

## Correcciones de CI · 2026-10-05

- Enumeración: CREATE_NO_WINDOW obtenido con getattr(...,0) para tests que simulan Windows sobre Ubuntu. Regresión reproduce AttributeError al quitar la constante;9 pruebas de enumeración y Ruff aprobados (commit bcfbe7f).
- E2E video: worker iniciado antes de navegar, espera de frame/mensaje de30s y presupuesto de60s para ese caso. Primer ensayo reprodujo una segunda carrera: timestamp guardado0.84s frente a pantalla ya en1.96s. La comparación ahora vuelve a leer el último mensaje en cada intento, conservando la comprobación de sincronización. Resultado final:2 recorridos de video-analysis.spec.ts aprobados (9.2s) y TypeScript lint aprobado. CI remoto pendiente de resultado.
