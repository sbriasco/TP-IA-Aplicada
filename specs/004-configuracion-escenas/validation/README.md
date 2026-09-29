# Validación — specs/004 (configuración de escenas)

Registro de los escenarios de [quickstart.md](../quickstart.md). Fecha: 2026-09-29. Commit validado: `3c70e9a` (rama `feature/004-configuracion-escenas`).

**Entorno**: Linux, Python 3.11 (backend `venv` desde `requirements.lock`), Node + Chromium de Playwright, PostgreSQL 16 local de pruebas (contenedor), API y Vite locales. Carpeta de videos temporal y `FLOWSIGHT_MACHINE_ID=validacion-004`. Sin la base compartida de Azure.

**Material**: solo clips sintéticos de `flowsight.video.fixtures` (2 s, 25 fps, 50 frames): MJPG 1280×720 y 640×480, mp4v 1280×720 y 1920×1080, MPEG-1 PIM1, y variantes corruptas derivadas de ellos. En este equipo no hay video real ni el material del experimento 001, así que todo lo que depende de ese material queda **pendiente**.

## Resumen

| Criterio | Estado | Resultado |
| --- | --- | --- |
| Verificaciones automáticas (T048) | `pass` | backend: ruff OK, pytest 345 passed / 3 skipped (solo Windows); frontend: lint OK, 245 tests, build OK; e2e: 5 passed |
| SC-001 (video real ~5 min, < 30 s) | **`pending`** | falta un video real de ~5 min. El clip sintético de 2 s tardó 0,10 s de registro a frame, pero **no** sirve como medición de SC-001 |
| `.mpg` real del experimento 001 (`frame_count` contado frente al encabezado, G1) | **`pending`** | falta el material. Con el MPEG-1 sintético el conteo da 50 de 50 frames generados |
| SC-002 (rechazo de archivos inválidos) | `pass` | vacío, texto renombrado a `.mp4`, AVI truncado a 4 KB y AVI sin datos de frames rechazados, sin sesión ni archivo nuevo. Ver la observación sobre el AVI truncado a la mitad |
| SC-003 (persona que no participó del desarrollo, < 5 min) | **`pending`** | falta una persona que no haya participado del desarrollo |
| SC-004 (< 0,5 % tras tres tamaños) | `pass` | error máximo 0,0000 % en 13 puntos, con escalas de pantalla 1×, 1,5× y 2× |
| SC-005 / SC-006 / SC-008 (versiones, inmutabilidad, compuerta) | `pass` | ver escenario 3 |
| Escenario 2.3 (segundo equipo con base compartida) | **`pending`** | necesita un segundo equipo y la base compartida |

## Escenario 1: registro de video (API)

| Paso | Estado | Observado |
| --- | --- | --- |
| 1.1–1.2 registrar | `pass` | 201; 1280×720, 25 fps (no estimado), 50 frames, 2,0 s, SHA-256 de 64 caracteres, equipo `validacion-004`, `available` |
| 1.2 frame de referencia | `pass` | `GET /sessions/{id}/reference-frame` → `image/jpeg` |
| 1.2 archivo y `.incoming/` | `pass` | archivo en `<videos>/<session_id>.avi`, `.incoming/` vacío |
| 1.3 nombre " cam 01 " normalizado | `pass` | 409 `camera_exists` con la cámara existente |
| 1.4 archivo vacío | `pass` | `file_empty` |
| 1.4 texto renombrado a `.mp4` | `pass` | `unsupported_format` |
| 1.4 AVI truncado a 4 KB (solo encabezado) | `pass` | `unsupported_format` |
| 1.4 AVI con encabezado intacto y datos de frames en cero | `pass` | `no_decodable_frames` |
| 1.4 sin sesión ni archivo nuevo tras los rechazos | `pass` | cantidad de sesiones y archivos sin cambios |
| 1.5 mismo video otra vez | `pass` | 201, con la primera sesión en `duplicate_session_ids` |

**Observación (sin decidir)**: un AVI MJPG cortado a la mitad del archivo **se acepta** (201) con `frame_count = 26`, los frames que se pueden decodificar. Es coherente con R3, que rechaza solo si no se decodifica ningún frame. Queda por confirmar si cumple la intención de SC-002 para "video truncado".

## Escenario 2: disponibilidad (API)

| Paso | Estado | Observado |
| --- | --- | --- |
| 2.1 video movido fuera de la carpeta | `pass` | `missing`; frame de referencia y metadatos visibles |
| 2.2 recarga con otro archivo | `pass` | `hash_mismatch` |
| 2.2 recarga con el archivo correcto | `pass` | vuelve a `available` |
| 2.3 segundo equipo con base compartida | **`pending`** | no ejecutado |

## Escenario 3: configuración versionada sin editor (API y psql)

| Paso | Estado | Observado |
| --- | --- | --- |
| 3.1 local válido | `pass` | 201, `version_number = 1`, coordenadas en [0, 1] |
| 3.2 casos inválidos | `pass` | 422 `invalid_scene_configuration` con `rule`, `element` y `shop_index` correctos para `too_few_vertices`, `vertices_too_close`, `self_intersection`, `area_too_small`, `line_too_short`, `out_of_range`, `missing_front_zone`, `missing_entry_line` y `duplicate_shop_name` (en el local 1) |
| 3.3 renombrar con el mismo `shop_id` | `pass` | `version_number = 2`, mismo `shop_id`; `GET` de la v1 idéntico al original |
| 3.4 `UPDATE scene_zones` directo | `pass` | falla con `scene configuration is immutable` |
| 3.5 cámara sin versiones | `pass` | `scene_not_configured` |
| 3.5 versión de otra cámara | `pass` | `scene_version_other_camera`. La cámara de la sesión tiene que tener su propia versión: por el orden de R12, sin versiones responde antes `scene_not_configured` |
| 3.5 sesión 4:3 con versión 16:9 | `pass` | `aspect_ratio_mismatch` |
| 3.5 sesión 16:9 de otra resolución (1920×1080) | `pass` | 201, trabajo en `pending` (no se procesa hasta #56) |

## Escenario 4: editor visual (Chromium con Playwright)

Se corrió con escalas de pantalla (`deviceScaleFactor`) 1×, 1,5× y 2×, que reproducen el efecto del zoom del navegador sobre la densidad de píxeles, y con tres tamaños de ventana (900×700, 1600×900 y 700×1000).

| Paso | Estado | Observado |
| --- | --- | --- |
| 4.1 Local A con frontal, interior, vidriera y línea A→B | `pass` | se ven A, B y la flecha de entrada, en las tres escalas |
| 4.2 tres tamaños y tres escalas | `pass` | desvío máximo vértice ↔ imagen de 0,86 px CSS (tolerancia 1,5 px) |
| 4.3 SC-004 | `pass` | error máximo entre lo guardado y lo dibujado de 0,0000 % del ancho y del alto, en 13 puntos por escala |
| 4.4 polígono autointersectado | `pass` | queda marcado (`aria-invalid`), se conservan los 4 vértices y no se crea una versión |
| 4.5 salir con cambios sin guardar | `pass` | pide confirmación al usar el enlace interno y al cerrar la pestaña (`beforeunload`) |
| 4.6 SC-003 | **`pending`** | falta una persona que no haya participado del desarrollo |
| 4.7 solo teclado | `pass` | con Tab, Enter y las flechas: crear un local, elegir el rol, dibujar con "Agregar vértice", elegir el sentido (flechas dentro del grupo de radios), mover un vértice (+10 px con Shift) y guardar |
| sin errores de página | `pass` | ninguno en las tres escalas |

SC-004 compara las coordenadas guardadas con los vértices del estado del editor, que es lo que pide el quickstart. La alineación en pantalla después de cada cambio de tamaño la cubre 4.2.

## Pendiente para cerrar T049

1. **SC-001**: registrar un video real de ~5 min desde la UI y medir el tiempo de "Registrar" hasta ver el frame. Si supera los 30 s, documentarlo y aplicar la alternativa de R3.
2. **G1**: registrar un `.mpg` real del material del experimento 001 y comparar el `frame_count` contado con el que declara el encabezado.
3. **SC-003**: una persona que no haya participado del desarrollo configura un local completo; registrar el tiempo (< 5 min).
4. **2.3**: desde un segundo equipo con la base compartida, ver el frame y el estado `missing`.

Al registrar estas mediciones no se anotan rutas absolutas, nombres de equipo, nombres de personas ni secretos.
