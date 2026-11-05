# Cierre de analítica y chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Ejecutar tareas verificables sin detener el alcance ya autorizado.

**Goal:** Corregir los defectos detectados y dejar un asistente conversacional de FlowSight funcional.

**Architecture:** Mantener API, worker y frontend existentes. Conversación y ayuda con contexto de producto; cifras mediante las herramientas del backend y guardas de salida. Regresiones de visión independientes del chat.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy/Alembic, Azure Foundry/openai 1.109.1, React/TypeScript estricto, pytest, Vitest y Playwright.

**Spec:** `docs/superpowers/specs/2026-11-04-cierre-analitica-chat-design.md`

## Global Constraints

- No instalar dependencias; mantener contratos históricos y vocabulario de zonas de análisis.
- Timestamps de video/captura; pérdida de continuidad >1 s corta visitas.
- LLM sin SQL libre ni acciones; credenciales en backend, máximo dos llamadas por turno.
- Datos destructivos de tests solo en PostgreSQL temporal local; preservar datos compartidos.
- No ejecutar los ensayos físicos de demo aplazados por el usuario.

## Review Focus

- Un saludo sin zona elegida o sin resultados no debe quedar bloqueado.
- Explicar una limitación no equivale a intentar identificar personas o confirmar compras.
- Repreguntas, zonas con nombres numéricos y cambios de sesión no deben mezclar métricas.
- Un fallo de historial no debe perder la respuesta ni producir una promesa sin manejar.
- Personas nuevas/ocultas y grupos numerosos deben conservar las reglas de medición.

## Task 1: Visión

Files: `backend/src/flowsight/vision/{ultralytics_tracker,events,visit_patterns}.py` y tests unitarios asociados.

- [x] Escribir y observar fallar regresiones de callbacks reales, huecos y más de doce candidatos.
- [x] Separar la inferencia de bolsas del estado de ByteTrack, cortar visitas y calcular grupos sin truncar candidatos.
- [x] Ejecutar pruebas afectadas y Ruff, revisar el diff.

## Task 2: UI, regresión y CI

Files: `frontend/src/components/SessionChatPanel.tsx`, tests del panel, `frontend/e2e/{results-dashboard,live,session-chat}.spec.ts`, `.github/workflows/ci.yml`.

- [x] Regresión de fallo al refrescar historial: escribir, comprobar rojo y corregir.
- [x] Permitir envío sin zona elegida; mantener aislamiento al cambiar zona/sesión.
- [x] Actualizar expectativas/mocks de chat ampliado y ejecutar la suite UI en CI.
- [x] Ejecutar Vitest/build y recorridos afectados con los puertos configurados coherentemente.

## Task 3: Conversación y analytics

Files: `backend/src/flowsight/services/chat*.py`, contexto de producto nuevo si hace falta, tests unitarios/contract del chat.

- [x] Pruebas rojas de saludo, ayuda, límites, repregunta, consulta compleja y formatos numéricos.
- [x] Sustituir el filtro cerrado por guardas de alcance y contexto de producto; cargar resultados solo donde correspondan.
- [x] Resolver zona/sesión con contexto y aclaraciones; ampliar datos de funnel/flujo y validar cifras/porcentajes.
- [x] Conservar tools y dos llamadas en Azure; probar errores/timeout y redactor de suite.
- [x] Actualizar expectativas obsoletas del catálogo de cifras y pasar tests afectados.

## Task 4: Cierre

Files: README, decisiones técnicas y guía de chat; scripts de diagnóstico cuando corresponda.

- [x] Alinear documentación con funciones y límites actuales.
- [x] Ejecutar Ruff, pytest completo, Vitest/build y las dos suites de Playwright en bases aisladas.
- [x] Revisar el cambio con un agente independiente y resolver hallazgos importantes.
- [x] Aplicar migraciones oficiales a la base configurada y verificar revisión/datos conservados.
- [x] Validar conversaciones reales con Foundry sin presentar eso como un ensayo físico de demo.

## Evidencia de cierre

- Ruff y build del frontend aprobaron. Vitest aprobó 380 pruebas en la repetición con un worker.
- La suite completa de pytest aprobó 787 pruebas y mostró un fixture de permanencia con un hueco. El fixture corregido y los otros dos casos del archivo aprobaron la repetición. Se omitió una prueba POSIX en Windows y se mantuvieron las exclusiones habituales de GPU y migraciones históricas.
- Playwright aprobó 15 recorridos de UI y 13 integrados. La repetición integrada usó una base nueva y corrió por separado de la suite de UI.
- Se verificaron conversación, guía y consultas con Foundry usando datos sintéticos. La guía actual describe los casos. Se aplicó la migración compartida y se comprobó la conservación de los conteos.
- La selección de grupos se resolvió con una heurística determinista que conserva los criterios de compatibilidad y la prioridad de grupos activos. La especificación 011 registra el alcance de esa estimación.