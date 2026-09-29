# Quickstart: validar carga, configuración y editor de escenas

Esta guía sirve para validar la feature, no para implementarla. Los contratos están en [contracts/](./contracts/) y el modelo en [data-model.md](./data-model.md). Los resultados medidos (SC-001, SC-003, SC-004) se registran en `validation/` sin rutas absolutas, nombres de equipo ni secretos.

## Prerrequisitos

- El entorno base de specs/002 funcionando (ver `README.md` "Verificación inicial") y PostgreSQL local.
- El backend reinstalado desde el lock actualizado, que ya incluye `opencv-python-headless`:
  `backend/.venv/bin/pip install -r backend/requirements.lock && backend/.venv/bin/pip install --no-deps -e backend`.
- En `.env`, las variables nuevas (ver `.env.example`):
  ```dotenv
  FLOWSIGHT_VIDEOS_DIR=/ruta/absoluta/a/videos-flowsight   # carpeta fuera del repo
  FLOWSIGHT_MACHINE_ID=equipo-01
  ```
- Migraciones: desde `backend/`, `alembic upgrade head`. Si falla, se corrige la causa y se vuelve a correr; nunca se hace `downgrade`.
- Un video de prueba. Para las verificaciones automáticas, el helper `flowsight.video.fixtures` genera clips cortos. Para SC-001 hace falta un video real de ~5 min que no esté en Git.

## Verificaciones automáticas

```bash
# desde backend/
.venv/bin/ruff check .
.venv/bin/pytest tests/unit/test_scene_geometry.py      # tolerancias, A/B, autointersección
.venv/bin/pytest tests/unit/test_video_probe.py         # conteo de frames, fps estimado, errores
.venv/bin/pytest tests/integration/test_migration_0002.py  # cámaras desde sesiones sintéticas + conflicto
.venv/bin/pytest tests/contract/test_scene_api.py       # versiones, inmutabilidad, compuerta de trabajos
.venv/bin/pytest                                        # todo, incluidas las pruebas de specs/002

# desde frontend/
npm run lint && npm test && npm run build
npm run test:e2e                                        # incluye el recorrido del editor
```

Resultado esperado: todo en verde, incluidas las pruebas de specs/002 sin cambios (compatibilidad de `POST /sessions`).

## Escenarios manuales

### 1. Registrar un video (US1, SC-001, SC-002)

1. Levantar la API y `npm run dev`. Abrir `/`, crear la cámara "Cam 01" y registrar el video de ~5 min.
2. **Esperado**: la sesión muestra resolución, fps (indica si es estimado), duración, cantidad de frames, equipo de origen, SHA-256 y el frame de referencia. El archivo queda en `FLOWSIGHT_VIDEOS_DIR/<session_id>.<ext>` y no quedan archivos en `.incoming/`. Medir el tiempo desde "Registrar" hasta ver el frame: debe ser menor a 30 s (SC-001) y se registra en `validation/`.
3. Crear otra cámara con el nombre " cam 01 ": se rechaza y se ofrece elegir la existente.
4. Registrar un archivo vacío, un `.txt` renombrado a `.mp4` y un video truncado: se rechazan con `file_empty`, `unsupported_format` o `no_decodable_frames`, sin sesión ni archivo nuevo (SC-002).
5. Volver a registrar el mismo video: se crea la sesión y aparece el aviso de duplicado.

### 2. Disponibilidad entre equipos (US1 escenarios 3 y 4, SC-007)

1. Mover el video fuera de `FLOWSIGHT_VIDEOS_DIR` y recargar el detalle de la sesión: aparece "Video no disponible en este equipo", y el frame de referencia y los metadatos se siguen viendo.
2. Recargar el video con otro archivo: `hash_mismatch`. Con el archivo correcto: vuelve a `available`.
3. Con la base compartida, desde un segundo equipo: se ve el frame y el estado es `missing`, sin error genérico.

### 3. Configuración versionada sin editor (US2, SC-005, SC-006, SC-008)

Con la API (`curl` o `/docs`), sobre la sesión del escenario 1:

1. `POST /cameras/{id}/scene-versions` con un local válido: devuelve 201, `version_number = 1` y coordenadas en [0, 1].
2. Enviar el conjunto de casos inválidos (< 3 vértices, vértices a ≤ 2 px, autointersección, área < 100 px², línea < 10 px, fuera de rango, sin frontal, sin línea, nombres repetidos): cada uno devuelve 422 con `rule`, `element` y `shop_index` correctos.
3. Guardar una segunda versión que renombra el local (mismo `shop_id`): devuelve `version_number = 2` y el mismo `shop_id`. `GET /scene-versions/{v1}` devuelve la v1 idéntica a la original.
4. Intentar `UPDATE scene_zones …` directo en psql: falla con `scene configuration is immutable`.
5. `POST /sessions/{id}/jobs {"kind":"video_analysis"}` sobre una cámara sin versiones: `scene_not_configured`. Con una versión de otra cámara: `scene_version_other_camera`. Con una sesión 4:3 y una versión 16:9: `aspect_ratio_mismatch`. Con una sesión 16:9 de otra resolución: 201, y el trabajo queda `pending`.

### 4. Editor visual (US3, SC-003, SC-004)

1. Abrir `/sessions/{id}/editor`. Crear el local "Local A" con zona frontal, interior, vidriera y línea de entrada, y elegir el sentido A→B. El editor muestra A, B y la flecha de entrada.
2. Redimensionar la ventana a tres tamaños y cambiar el zoom del navegador: el dibujo sigue alineado con la imagen.
3. Guardar y comparar las coordenadas de `GET /scene-versions/{id}` con las del estado del editor: la diferencia es < 0,5 % (SC-004).
4. Dibujar un polígono autointersectado y guardar: queda marcado el elemento con el mensaje y el dibujo no se pierde.
5. Con cambios sin guardar, intentar salir: aparece la advertencia.
6. SC-003: una persona que no participó del desarrollo configura un local completo; medir el tiempo (< 5 min) y registrarlo en `validation/`.
7. Accesibilidad: con solo el teclado se puede crear un local, elegir el rol y el sentido, mover un vértice con las flechas y guardar.
