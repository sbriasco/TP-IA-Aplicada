# Implementation Plan: Hilo de chat e historial

**Branch**: `feature/015-chat-hilo-historial` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)

**Azure Boards**: Feature #11 cerrada; esta entrega extiende el chat (seguimiento US3 + historial). Sin Feature Boards nueva obligatoria.

## Summary

Persistir conversaciones por sesión de análisis en PostgreSQL; `POST /chat` acepta `thread_id`, carga historial de texto acotado y sigue grounding con tools. El panel lista, reabre y crea hilos. Supersede el diferido US3 de 014.

## Technical Context

**Language/Version**: Python 3.11 / TypeScript strict (stack existente).  
**Dependencies**: Sin paquetes nuevos.  
**Storage**: Alembic `0017_chat_threads` — tablas `chat_threads`, `chat_messages`.  
**Testing**: pytest unit/contract; Vitest panel.  
**Constraints**: ≤2 llamadas modelo; historial no es fuente de cifras; webcam sin chat comercial.

## Constitution Check

| Principio | Estado |
|---|---|
| I Local | Suite con DB de test |
| II Separación | Persistencia + chat service + UI |
| III Aislamiento | Hilos por session_id; zona explícita |
| IV Privacidad | Guards existentes |
| V Estimaciones | Sin cambio de rótulos |
| VI Analytics acotado | Tools + historial solo texto |
| VII Evidencia | Tests + quickstart |

## Structure

```text
specs/015-chat-hilo-historial/
backend/.../alembic/versions/0017_chat_threads.py
backend/.../db/models.py
backend/.../services/chat_threads.py
backend/.../services/chat.py  (thread_id + history)
backend/.../api/schemas.py, routes.py
frontend/.../api/chat.ts
frontend/.../components/SessionChatPanel.tsx
```

## Complexity Tracking

Ninguna violación. Migración justificada por historial persistente pedido explícitamente.
