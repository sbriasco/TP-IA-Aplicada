# Contrato: registro y recarga de video

Complementa `POST /video-sessions` y `PUT /sessions/{id}/video` de [openapi.yaml](./openapi.yaml). Las decisiones están en [research.md](../research.md) (R1 a R7).

## Configuración por equipo

| Variable | Obligatoria para arrancar | Regla |
|---|---|---|
| `FLOWSIGHT_VIDEOS_DIR` | No | Ruta absoluta de la carpeta local de videos. La API crea `.incoming/` dentro. |
| `FLOWSIGHT_MACHINE_ID` | No | `^[a-z0-9][a-z0-9-]{2,39}$`. Estable por equipo; sin nombre de la persona ni usuario del sistema. |

Si falta alguna, la API y el worker arrancan igual, pero registrar o recargar video responde 503 con el código correspondiente.

## Secuencia de registro

1. Se validan `name`, `registered_camera_id` (existe) y la extensión de `filename`. Si la extensión no es válida, se rechaza (`unsupported_format`) sin leer el cuerpo.
2. Se verifica que la carpeta esté configurada y se pueda escribir.
3. El cuerpo se copia por bloques de 1 MiB a `.incoming/<uuid>.partial` mientras se calculan SHA-256 y tamaño. Luego `fsync`.
4. Se sondea con OpenCV: se cuentan los frames, se obtienen fps y resolución y se toma el primer frame decodificable como JPEG.
5. En una transacción: INSERT de `sessions` (`video_file`), `video_sources` y `reference_frames`. Luego `os.replace` al nombre final `<session_id><ext>` y commit.
6. Si algo falla en los pasos 3 a 5, se borran el parcial y el destino. No queda la sesión.

La recarga (`PUT /sessions/{id}/video`) repite los pasos 2 y 3, compara el SHA-256 y, si coincide, hace `os.replace` a `relative_path`. No vuelve a sondear ni modifica metadatos.

## Códigos de error

| HTTP | `code` | Causa | Acción sugerida en `message` |
|---|---|---|---|
| 404 | `not_found` | Cámara o sesión inexistente | Elegir una cámara o sesión existente |
| 409 | `hash_mismatch` | Recarga con un archivo distinto del registrado | Elegir el mismo archivo que se registró originalmente |
| 409 | `not_video_session` | Recarga sobre una sesión sintética | — |
| 422 | `file_empty` | Cuerpo de 0 bytes | Elegir un archivo con contenido |
| 422 | `unsupported_format` | Extensión no admitida u OpenCV no puede abrir el archivo | Convertir a MP4 o MPEG |
| 422 | `no_decodable_frames` | Abre pero no decodifica ningún frame (corrupto o truncado) | Verificar el archivo con un reproductor |
| 422 | `fps_unknown` | No se pudo determinar ni estimar el fps | Volver a codificar el video con fps fijo |
| 422 | `upload_interrupted` | El cliente cortó la subida | Volver a intentar |
| 503 | `videos_dir_not_configured` | Falta `FLOWSIGHT_VIDEOS_DIR` | Definirla en `.env` (ver `.env.example`) |
| 503 | `videos_dir_not_writable` | No existe o no se puede escribir | Crear la carpeta o revisar permisos |
| 503 | `machine_id_not_configured` | Falta `FLOWSIGHT_MACHINE_ID` o es inválido | Definirla en `.env` |
| 507 | `insufficient_storage` | Disco lleno durante la copia | Liberar espacio |

"Archivo inexistente" e "ilegible" (FR-003, FR-011) aparecen en el navegador antes de llegar a la API: el selector no devuelve archivos que no existen y los errores de lectura cortan el envío. El frontend los muestra como "No se pudo leer el archivo elegido" y no llama a la API. Si el envío llega a empezar y se corta, la API responde `upload_interrupted`.

Ningún `message` incluye rutas absolutas, `FLOWSIGHT_DATABASE_URL` ni credenciales (FR-013). Las rutas solo aparecen como `relative_path`.

## Progreso en la interfaz

- Durante la subida, una barra determinada que usa `XMLHttpRequest.upload.onprogress`.
- Mientras la API sondea el video, un indicador indeterminado con el texto "Analizando video…", hasta la respuesta.
