# Modelo de datos del experimento

El experimento usa archivos locales y no crea modelos ni tablas de PostgreSQL. Los nombres
son contractuales a nivel de documentación; los tipos concretos se implementarán después.

## Video candidato

Representa un video ya seleccionado por el equipo.

- `video_id`: identificador estable local.
- `path`: ruta local fuera de Git.
- `filename`: nombre del archivo.
- `license_or_usage`: condiciones de uso documentadas.
- `metadata`: resolución, fps, duración, fecha real si se conoce y observaciones.
- `selection_status`: seleccionado, limitado o no evaluable.

## Fragmento representativo

Intervalo seleccionado para una prueba.

- `fragment_id`: identificador estable.
- `video_id`: referencia al video.
- `start_timestamp`: inicio según el video.
- `end_timestamp`: fin según el video.
- `start_video_seconds`: inicio en segundos del video original.
- `end_video_seconds`: fin en segundos del video original, excluido del intervalo.
- `relative_time_unit`: `seconds`.
- `time_conversion`: `relative_seconds = video_timestamp_seconds - start_video_seconds`.
- `selection_reason`: circulación, oclusión, entrada, frente u otra razón.
- `covered_cases`: casos observables cubiertos.
- `coverage_limitations`: casos ausentes o insuficientes.

## Escena preconfigurada

Configuración manual de la geometría usada por el experimento.

- `scene_id`: identificador.
- `frame_reference`: frame y dimensiones originales de referencia.
- `front_zone`: polígono con nombre, puntos y propósito.
- `entry_line`: línea con nombre, dos puntos y sentido esperado si es observable.
- `parameters`: parámetros de la prueba sin valores predeterminados de precisión.

## Referencia manual

Observaciones humanas sobre uno o más fragmentos.

- `manual_id`: identificador.
- `fragment_id`: fragmento observado.
- `observation_id`: identificador de cada ocurrencia manual.
- `relative_time`: intervalo relativo al fragmento.
- `video_timestamp`: intervalo absoluto en segundos del video original.
- `observation_type`: persona observable, entrada en zona, cruce, oclusión, pérdida de
  visibilidad u otro caso.
- `location_or_target`: zona o línea involucrada.
- `direction`: entrada, salida, desconocida o no aplicable.
- `covered_cases`: casos cubiertos por la observación.
- `notes`: criterio y limitaciones.

La muestra se amplía antes de concluir sobre cruces u oclusiones si esos casos no están
cubiertos. No se exige una cantidad numérica fija.

## Resultado de detección y tracking

Resultado automático por frame o evento.

- `session_id`: identificador de la ejecución local.
- `fragment_id`: fragmento procesado.
- `frame_index`: índice del frame.
- `video_timestamp`: timestamp del video.
- `track_id`: ID temporal dentro de la sesión y cámara.
- `bbox_or_reference_point`: posición observada para evaluación.
- `zone_state`: estado respecto de la zona frontal.
- `line_event`: cruce y dirección si se detectan.
- `visibility_state`: visible, ocluido, perdido u otro estado documentado.

Un cambio de `track_id` se analiza como continuidad por separado; no se marca como duplicado
automáticamente.

## Comparación

Vincula una ocurrencia manual con resultados automáticos sin tratar los IDs como identidad.

- `comparison_id`: identificador.
- `manual_observation_id`: observación manual.
- `automatic_observation_ids`: resultados candidatos.
- `match_status`: coincidencia, omisión, duplicado, no comparable o espurio dentro de la
  muestra manual revisada.
- `comparison_basis`: ocurrencia observable, intervalo, zona o línea, dirección.
- `track_continuity_status`: continua, posible pérdida, cambio de ID, no evaluable.
- `error_category`: detección faltante, detección espuria, oclusión, pérdida, duplicado,
  cruce omitido u otro.
- `evidence_notes`: explicación revisable.

La revisión es humana y asistida por una visualización local de detecciones, tracks y
eventos. No hay algoritmo de asociación. Una observación automática fuera de la muestra
manual revisada no se clasifica como espuria por ausencia de anotación.

## Dirección de cruces

- `A_to_B`: primer sentido, declarado en la escena como `entry` o `exit`.
- `B_to_A`: sentido inverso, declarado como el sentido contrario o `unknown`.
- `direction_mapping`: correspondencia explícita entre ambos sentidos y `entry`/`exit`.

## Rendimiento por fragmento

- `session_id`: ejecución local.
- `fragment_id`: fragmento.
- `device`: CPU/GPU y equipo identificable.
- `video_duration_seconds`: duración según el video.
- `frames_processed`: frames procesados.
- `processing_time_seconds`: tiempo de ejecución medido.
- `measurement_timestamp`: momento de la medición, separado del tiempo de comportamiento.

## Resultado de viabilidad

- `measurement`: tráfico total, flujo temporal, paso frente a local, entradas/salidas,
  tasa de ingreso, permanencia, ocupación observable u horarios pico.
- `status`: viable, viable con ajustes, no viable con el material o configuración evaluados,
  o no evaluable por falta de evidencia.
- `direct_evidence`: evidencia comprobada directamente.
- `limitations`: límites del material, muestra o configuración.
- `required_adjustments`: ajustes o decisiones pendientes.
- `negative_result_is_valid`: indica que una conclusión negativa respaldada por evidencia
  completa la validación.
