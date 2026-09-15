# Experimento de validación de videos y tracking

Experimento local de la **Feature #4** (Azure Boards), hija del Epic #2.
No construye frontend, API, chat, editor visual ni PostgreSQL.

| Historia | Azure | Qué se hizo en este repo |
|---|---|---|
| US1 | #17 | Inventario y `fragments.csv` locales; ejemplos sintéticos versionados |
| US3 | #19 | YOLO `yolov8n` + ByteTrack CPU, zona/línea, overlays, `performance.csv` |
| US2 | #18 | `manual.csv` + revisión humana en `review.csv` (sin asociación automática) |
| US4 | #20 | Intervalos por timestamps del video e `outputs/viability-report.md` |

Especificación: `specs/001-validacion-videos-tracking/`.

Un `track_id` es temporal de sesión/cámara: **no** es identidad real.

## Qué está comprobado vs pendiente

**Comprobado en este equipo (`Tete`, CPU, 2026-09-15):**

- 46 tests sintéticos (`unittest discover`). Cubren código, **no** el tiempo de YOLO.
- Dos fragmentos reales: `frag-enterexit-crossing-001` `[8.0, 15.32)` de `EnterExitCrossingPaths1front.mpg` y `frag-onestop-group-002` `[36.0, 44.0)` de `OneStopMoveEnter1front.mpg`.
- Revisión manual de 2 personas y 2 cruces (entry 9.12 s, exit 9.60 s) contra overlays.
- T043: revisión manual de 6 personas y 2 oclusiones/solapamientos; no hubo cruces de línea. La ejecución automática mostró subconteo y fragmentación de `track_id`, por lo que la oclusión quedó `viable con ajustes`.
- T025: video 7.32 s / 183 frames; YOLO+ByteTrack 11.54 s; postproceso 0.70 s; total 12.24 s.
- T044 (sesión nueva, archivos `*-t044`): mismos 183 frames, 330 obs., 5 `track_id` y 38 eventos/cruces; detección **10.41 s**; postproceso **0.70 s**; total **11.11 s**. No se afirma reproducibilidad de velocidad.

**No comprobado / no evaluable aquí:**

- Tasa de ingreso, horarios pico, heatmap, GPU, BoT-SORT.
- Reproducibilidad de **velocidad** YOLO: T044 varió ~1.1 s vs T025 en el mismo PC.
- No se afirma reproducibilidad de GPU ni de otro PC.

Conclusiones de viabilidad (detalle en el informe local, no versionado): cruces, circulación en zona frontal y oclusión → `viable con ajustes`; para oclusión se observaron subconteo y fragmentación de tracks. Conteo por `track_id`, permanencia interior continua y ocupación total del local → `no viable con el material o configuración evaluados`. Picos, tasas y GPU → `no evaluable por falta de evidencia`.

## Entorno efectivamente usado

| Componente | Valor comprobado |
|---|---|
| OS | Windows 10; hostname `Tete` |
| Python | 3.11.16 (64 bit), venv local `.venv` |
| torch | `2.7.1+cpu` (`cuda.is_available() == False`) |
| ultralytics | `8.4.153` |
| opencv-python | `4.10.0.84` |
| lap | `0.5.13` (instalado por Ultralytics para ByteTrack; no se pidió otro peso) |
| Peso | `weights/yolov8n.pt` AGPL-3.0; origen en `weights/SOURCE.md` (el `.pt` no va a Git) |
| Tracker | ByteTrack (`ultralytics/cfg/trackers/bytetrack.yaml`) |

`pip check` no reportó roturas el 2026-09-15. No se instalaron dependencias nuevas en T039–T042.

## Comandos reproducibles (desde la raíz del repo)

Pruebas de código (ejecutadas en T042, 46 OK):

```powershell
$py = "experiments\video-tracking-validation\.venv\Scripts\python.exe"
$exp = "experiments\video-tracking-validation"
& $py -m unittest discover -s "$exp\tests" -p "test_*.py"
```

Duraciones observables desde `manual.csv` (timestamps del video, no tiempo de proceso):

```powershell
& $py "$exp\run_validation.py" `
  --write-behavior-intervals `
  --scene "$exp\config\scene.frag-enterexit-crossing-001.json" `
  --fragments "$exp\references\fragments.csv"
```

Visor de segundos del video original (sin detecciones automáticas):

```powershell
& $py "$exp\preview_manual_timestamps.py"
```

Detección YOLO + medición de tiempos (ejecutado en US3/T025, **no** repetido en el polish). Requiere video local, peso local e inventario gitignored:

```powershell
& $py "$exp\run_validation.py" `
  --fragments "$exp\references\fragments.csv" `
  --inventory "$exp\inputs\video-inventory.csv" `
  --scene "$exp\config\scene.frag-enterexit-crossing-001.json" `
  --fragment-id frag-enterexit-crossing-001 `
  --weights "$exp\weights\yolov8n.pt" `
  --device cpu `
  --measure-detect `
  --annotate-overlays `
  --write-performance
```

`--measure-detect` no reescribe `detections.jsonl`. Para regenerar detecciones hace falta `--detect` (no se corrió en T039–T042).

## Resultados locales (excluidos de Git)

| Archivo | Contenido |
|---|---|
| `outputs/detections.jsonl` | 330 observaciones, 5 `track_id` |
| `outputs/events.csv` | 38 eventos |
| `outputs/overlays/` | frames anotados `overlay_f000200.jpg`… |
| `outputs/performance.csv` | fila del fragmento + resumen trazable |
| `outputs/behavior-intervals.csv` | duraciones = fin − inicio del video |
| `outputs/review.csv` | coincidencia / omisión / duplicado / no comparable / espurio |
| `outputs/viability-report.md` | informe US4 |
| `references/manual.csv` | muestra humana |
| `config/scene.frag-enterexit-crossing-001.json` | escena 384×288 |

Limitaciones del material: 384×288; baranda; maniquíes; personas pequeñas; clip de 7.32 s; un solo equipo CPU.

## Git (T040)

Comprobado con `git check-ignore` (2026-09-15): videos (`/[Vv]ideos/`), `*.pt`, `outputs/*`, overlays, `manual.csv` / `fragments.csv` / inventario / escena real, `.venv/` y `*.db` quedan fuera.

Quedan versionables (no ignorados, o excepciones `!`): código y tests, `README.md`, `config/scene.example.json`, `references/*.example.csv`, `weights/SOURCE.md`, specs en `specs/001-validacion-videos-tracking/`.

La carpeta del experimento aún puede estar **untracked** en el clon local; eso no implica que los binarios se suban si se respeta `.gitignore`.

## Asistencia de IA (T041)

Decisiones y validaciones hechas con asistencia de Cursor/Grok en este experimento, contrastadas con el material y las pruebas:

- Intervalo semiabierto `[start, end)` y `relative_seconds = video_timestamp − start`, sin usar tiempo de proceso como permanencia.
- `CAP_PROP_FRAME_COUNT` en MPEG no es fiable; se cuentan frames con `read()`.
- Cruce contra el **segmento** del umbral, no la recta infinita; oscilación ≤10 frames no confirma dos cruces; cambio de `track_id` no es duplicado automático.
- Agrupar eventos por `(session_id, track_id)` para no mezclar el mismo `track_id` numérico entre sesiones.
- Muestra manual anotada mirando el video original (overlay de timestamps), **después** comparación con automáticos.
- No se inventó oclusión ni umbral de precisión; las conclusiones negativas (tráfico-por-id, stay interior) se dejaron en el informe.

Fuentes oficiales consultadas en el plan/origen del peso: [Ultralytics tracking](https://docs.ultralytics.com/modes/track/), [YOLOv8](https://docs.ultralytics.com/models/yolov8/), release `yolov8n.pt` v8.4.0, documentación de PyTorch/OpenCV citada en `research.md`.

## Trazabilidad (T042)

| Azure | Artefacto |
|---|---|
| Feature #4 | este experimento + `specs/001-validacion-videos-tracking/` |
| US1 #17 | `fragments.example.csv`; inventario/fragmentos locales |
| US3 #19 | `run_validation.py`, detecciones/eventos/overlays/performance locales |
| US2 #18 | `manual.example.csv`, `review.example.csv`; CSV locales de revisión |
| US4 #20 | `viability-report.md` local; `behavior_duration_seconds` en código |

Aislamiento: `tests/test_session_isolation.py` (ids de observación prefijados por sesión; mismo `track_id` no mezcla trayectorias).

T042 reejecutó `unittest discover`: 46 OK. No se encontraron `.env` ni archivos grandes versionados en esta carpeta (el experimento aún no está en el índice de Git).
