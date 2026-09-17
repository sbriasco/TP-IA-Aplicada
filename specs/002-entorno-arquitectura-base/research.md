# Research: Entorno local reproducible y arquitectura base

## Runtimes y dependencias

### Python

**Decisión**: usar Python 3.11.16, ya disponible y validado en el experimento anterior. Las dependencias exactas del backend se fijarán en `pyproject.toml` al aprobar su primera instalación.

**Motivo**: permite compartir código entre API y worker sin abrir otra validación de runtime.

**Alternativas descartadas**: actualizar Python ahora agrega riesgo sin aportar una capacidad requerida; otro lenguaje para el worker duplica contratos y herramientas.

### Node, React y Vite

**Decisión**: usar Node 22.20.0, React 19, TypeScript estricto y Vite 7. Las versiones exactas de paquetes quedarán en `package-lock.json`.

**Motivo**: Node 22.20.0 ya está disponible y supera el mínimo de Node 22.12 indicado por Vite 7.

**Alternativas descartadas**: cambiar de Node requiere instalar herramientas sin necesidad; construir la interfaz completa excede esta Feature.

### PostgreSQL

**Decisión**: usar PostgreSQL 17 local con una base por integrante, SQLAlchemy 2.x, Alembic y psycopg 3.x. La compatibilidad exacta se comprobará antes de fijar paquetes.

**Motivo**: valida el motor ya acordado y las migraciones repetibles sin depender de una base compartida.

**Alternativas descartadas**: SQLite no valida PostgreSQL; Docker no será obligatorio; una base compartida mezcla disponibilidad y datos.

## Procesamiento de trabajos

**Decisión**: persistir trabajos en PostgreSQL y usar un único worker que reclama atómicamente el pendiente más antiguo. La transacción bloquea la fila con `FOR UPDATE SKIP LOCKED`, cambia a `processing` y registra `started_at`.

**Motivo**: evita reclamos dobles incluso si se inicia accidentalmente un segundo worker, sin agregar una cola externa.

**Recuperación**: al iniciar, el worker cambia trabajos `processing` a `failed`, fija `finished_at`, `failure_code=worker_interrupted` y una explicación segura. No los reintenta.

**Alternativas descartadas**: Redis/Celery suma instalación y estados duplicados; una cola en memoria pierde trabajos; reintentar contradice la aclaración aprobada.

## Estados y trazabilidad

**Decisión**: almacenar estado actual e historia de transiciones. Usar UUID y claves que incluyan el contexto de sesión. Separar `video_timestamp_seconds` de `created_at`, `started_at`, `finished_at` y `processing_duration_ms`.

**Motivo**: facilita consultas, conserva evidencia y evita que identificadores temporales mezclen sesiones.

## Datos sintéticos

**Decisión**: versionar un fixture JSON pequeño y determinista con dos sesiones, cámaras, frames, observaciones y eventos. Un servicio sintético usa un reloj inyectable y publica previews.

**Motivo**: prueba contratos, persistencia y aislamiento sin video, modelo ni GPU; el reloj controlable evita pruebas inestables.

## Previsualización

**Decisión**: usar WebSocket. Cada conexión posee una cola de capacidad uno; si está ocupada, se reemplaza la actualización pendiente. El mensaje usa JSON con metadatos y un JPEG sintético base64 de 320×180 y hasta 100 KiB, con límite de ejemplo de 5 actualizaciones por segundo. Al terminar, se entrega la última actualización pendiente antes del mensaje terminal. Las conexiones tardías consultan REST y no recuperan previews históricos.

**Motivo**: limita memoria y desacopla al worker. Desconectar elimina solo el slot de ese cliente.

**Alternativas descartadas**: una cola ilimitada acumula atraso; bloquear al productor altera el proceso; persistir previews las convierte en fuente de datos.

## Contratos, pruebas y CI

**Decisión**: REST crea y consulta sesiones/trabajos; WebSocket entrega preview. Pydantic valida configuración al inicio. pytest cubre dominio, PostgreSQL, API, worker y WebSocket; Vitest cubre unidades del frontend. Playwright se usa cuando exista una pantalla recorrible. GitHub Actions no requiere GPU, videos, pesos ni Azure.

**Motivo**: cada responsabilidad se prueba en su nivel y CI reproduce el mínimo común.

## Evidencia de equipos

**Decisión**: generar un informe JSON local con runtime, sistema, CPU, GPU detectada, modo, checks, duración y limitaciones. CPU siempre se evalúa; GPU es evidencia adicional y puede quedar `not_evaluated`. Solo un resumen anonimizado puede versionarse.

**Motivo**: separa capacidad detectada de rendimiento demostrado.

## Fuentes técnicas

- [Versiones de Node.js](https://nodejs.org/en/about/previous-releases)
- [Guía de Vite](https://vite.dev/guide/)
- [Versionado de FastAPI](https://fastapi.tiangolo.com/deployment/versions/)
- [PostgreSQL para Windows](https://www.postgresql.org/download/windows/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/en/latest/)
- [WebSockets en FastAPI](https://fastapi.tiangolo.com/advanced/websockets/)

Las versiones de paquetes aún no instalados son candidatas. Se fijarán en archivos de dependencias y lockfiles después de validar compatibilidad con autorización del usuario.
