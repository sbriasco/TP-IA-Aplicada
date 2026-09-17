# Quickstart planificado: Entorno local reproducible

Esta guía describe el recorrido que deberá quedar operativo. No autoriza instalaciones.

## 1. Requisitos

- Git.
- Python 3.11.16 de 64 bits.
- Node.js 22.20.0 y npm.
- PostgreSQL 17 local, con base y usuario propios.
- PowerShell en Windows.

La CPU es suficiente. No se requiere GPU, video, peso ni credencial de Azure.

Quien no tenga PostgreSQL debe instalar PostgreSQL 17 mediante el instalador oficial para Windows, registrar el puerto y crear un usuario y una base exclusivos para FlowSight. La verificación debe mostrar la versión encontrada. No se usa una base compartida ni se exige Docker.

## 2. Preparación

1. Clonar el repositorio y usar la versión de `.node-version`.
2. Crear `backend/.venv` e instalar dependencias fijadas.
3. Instalar el frontend desde su lockfile.
4. Copiar `.env.example` a `.env` y completar valores locales.
5. Crear una base PostgreSQL vacía; no compartirla entre integrantes.
6. Ejecutar `scripts/check-environment.ps1`.

La verificación identifica Python, Node, PostgreSQL, variables o conexión faltantes sin imprimir contraseñas ni la URL completa.

## 3. Inicialización repetible

1. Aplicar Alembic hasta `head` y repetir el comando sin cambios destructivos. Si falla, detener la preparación, conservar los datos y la revisión previa e informar `current` y `head`; no borrar la base ni ejecutar `downgrade` automáticamente.
2. Cargar `fixtures/synthetic/base-flow.json` y repetir sin duplicar datos.

## 4. Inicio

Iniciar en este orden y en terminales separadas:

1. PostgreSQL local y `scripts/check-environment.ps1`.
2. `scripts/start-api.ps1`.
3. `scripts/start-worker.ps1`.
4. servidor de desarrollo del frontend.

La API y el worker deben detener su inicio con un mensaje accionable si falta configuración o PostgreSQL. El frontend puede iniciar sin ellos, pero debe informar que la API no está disponible. La API expone salud y documentación local. El worker recupera trabajos interrumpidos antes de reclamar uno pendiente.

## 5. Flujo sintético

1. Crear sesión con `POST /sessions`.
2. Crear trabajo con `POST /sessions/{session_id}/jobs`.
3. Consultar `GET /jobs/{job_id}` hasta estado terminal.
4. Consultar la traza y confirmar sesión, cámara, frames y timestamps.
5. Reiniciar API y worker y volver a consultar.

Para probar interrupción, detener el worker en `processing` y reiniciarlo. El trabajo queda `failed` con `worker_interrupted`, sin reintento.

## 6. Previsualización

Conectar a `WS /ws/jobs/{job_id}/preview` con un consumidor normal, uno lento y otro que se desconecta. El lento conserva como máximo una actualización pendiente y recibe la última publicada antes del estado terminal. Una conexión tardía o reconexión consulta primero el estado REST; si el trabajo terminó, no se reconstruyen previews. Ningún cliente cambia el resultado persistido.

El fixture publica JPEG sintético de 320×180, hasta 100 KiB, con valor de ejemplo de 5 actualizaciones por segundo. Cambiar esa frecuencia no cambia los timestamps del video.

## 7. Verificación integral

`scripts/verify-base.ps1` valida configuración, conexión, migraciones, tests, aislamiento, flujo sintético y evidencia del ambiente; falla con código distinto de cero. Para rendimiento ejecuta tres veces el fixture y tres consultas a `/health`, informa medianas y registra equipo y versiones. Se ejecuta en CPU y, cuando esté disponible, en la PC de referencia. GPU puede quedar `not_evaluated` sin invalidar CPU.

El informe completo queda local y excluido de Git. Solo puede versionarse un resumen que elimine nombre de equipo, usuario, rutas absolutas, direcciones de red y secretos.

## 8. Detención

Detener frontend, worker y API. PostgreSQL puede seguir como servicio. La detención no borra datos ni ejecuta migraciones descendentes.
