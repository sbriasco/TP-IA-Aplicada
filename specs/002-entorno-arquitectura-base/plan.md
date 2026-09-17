# Implementation Plan: Entorno local reproducible y arquitectura base

**Branch**: `feature/entorno-arquitectura-base` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-entorno-arquitectura-base/spec.md`

## Summary

Construir la base local de FlowSight como una aplicación web pequeña con frontend React, API FastAPI, un worker Python separado y PostgreSQL local. La primera ejecución usa datos sintéticos deterministas para probar migraciones, sesiones, estados, aislamiento, trazabilidad y previsualización sin videos, pesos ni servicios cloud. El worker reclama un trabajo persistido por vez; un trabajo interrumpido se recupera como fallido y no se reintenta. La previsualización WebSocket mantiene como máximo una actualización pendiente por cliente.

## Technical Context

**Language/Version**: Python 3.11.16; Node.js 22.20.0; TypeScript 5.x con `strict`

**Primary Dependencies**: FastAPI y Pydantic; SQLAlchemy 2.x, Alembic y psycopg 3.x; React 19 y Vite 7

**Storage**: PostgreSQL local; archivos privados y resultados pesados en disco fuera de Git

**Testing**: pytest para dominio, persistencia, API, worker y WebSocket; Vitest para unidades del frontend; Playwright cuando exista un recorrido visual

**Target Platform**: Windows 10/11; CPU obligatoria y GPU NVIDIA opcional como evidencia adicional

**Project Type**: aplicación web monorepo con dos procesos Python y un frontend

**Performance Goals**: mediana menor a 30 segundos para tres ejecuciones consecutivas del fixture base con PostgreSQL local y un worker; mediana menor a 1 segundo para tres consultas locales consecutivas a `/health`; equipo CPU y versiones registrados; máximo una actualización pendiente por cliente

**Constraints**: local; sin Docker obligatorio, Redis, cola distribuida, videos, pesos ni Azure; un trabajo concurrente; timestamps del video separados del tiempo operativo

**Scale/Scope**: seis integrantes, dos o tres desarrolladores activos, una instalación y base por equipo, un worker y pocos trabajos sintéticos

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | PostgreSQL local, configuración de ejemplo, migraciones, fixture sintético y CPU obligatoria | Aprobado |
| II. Responsabilidades separadas | API y worker tienen entradas distintas; dominio, persistencia y preview son módulos separados | Aprobado |
| III. Trazabilidad | Claves incluyen sesión, cámara, frame y timestamp; tiempos operativos están separados | Aprobado |
| IV. Privacidad | `track_id` limitado por sesión/cámara; no se modela identidad real | Aprobado |
| V. Eventos confiables | Solo contratos sintéticos; no se afirma precisión de visión | Aprobado |
| VI. Analytics acotado | Chat, Azure y credenciales quedan fuera del alcance | Aprobado |
| VII. Evidencia e incrementos | Verificaciones por historia; implementación vinculada luego a tareas de Azure | Aprobado |

La revisión posterior al diseño conserva todos los principios. No hay excepciones constitucionales.

## Project Structure

### Documentation (this feature)

```text
specs/002-entorno-arquitectura-base/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── preview-websocket.md
│   └── configuration.md
└── tasks.md                 # se crea recién con /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/versions/
├── src/flowsight/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── domain/
│   ├── preview/
│   ├── services/
│   ├── synthetic/
│   └── worker/
└── tests/{contract,integration,unit}/

frontend/
├── package.json
├── package-lock.json
├── tsconfig.json
├── vite.config.ts
├── src/{api,components,pages,types}/
└── tests/

scripts/
├── check-environment.ps1
├── start-api.ps1
├── start-worker.ps1
└── verify-base.ps1

fixtures/synthetic/base-flow.json
.github/workflows/ci.yml
.env.example
.node-version
README.md
```

**Structure Decision**: un único paquete Python comparte modelos y reglas entre API y worker, pero cada proceso tiene su propio punto de entrada. Esto evita duplicación sin mezclar el trabajo con el servidor HTTP. El frontend queda separado por su toolchain. El fixture vive fuera de los tests para reutilizarlo en verificaciones manuales y automáticas.

## Implementation Phases

1. Preparar versiones, configuración de ejemplo, verificación de requisitos y guía raíz.
2. Crear paquete Python, configuración validada, PostgreSQL, migraciones y fixture determinista.
3. Implementar REST y persistencia de sesiones, trabajos, transiciones y recuperación.
4. Implementar el worker de a un trabajo, trazabilidad sintética y reclamo exclusivo.
5. Implementar WebSocket con un slot pendiente por cliente y frontend mínimo de supervisión.
6. Agregar pruebas, evidencia CPU/GPU, scripts y CI sin GPU ni secretos.

## Verification Strategy

- **US1**: ejecutar preparación y verificación desde valores de ejemplo; provocar faltantes y revisar mensajes.
- **US2**: migrar dos veces; crear trabajos exitoso, fallido e interrumpido; reiniciar y consultar persistencia.
- **US3**: usar dos sesiones con iguales `camera_id`, `frame_index` y `track_id`; comprobar aislamiento y trazabilidad.
- **US4**: conectar clientes normal, lento y desconectado; comprobar un solo pendiente y finalización independiente.
- **US5**: ejecutar el mismo flujo en CPU y, cuando esté disponible, en la PC de referencia; registrar resultado y límites.

## Complexity Tracking

No hay violaciones que justificar.
