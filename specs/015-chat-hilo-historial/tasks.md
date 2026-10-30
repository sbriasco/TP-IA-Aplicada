# Tasks: Hilo de chat e historial

## Phase 1: Spec artifacts
- [X] T001 Crear specs/015 (spec, plan, research, data-model, contracts, quickstart)

## Phase 2: Persistencia
- [X] T002 Migración Alembic 0017 + modelos SQLAlchemy
- [X] T003 Servicio `chat_threads.py` (crear, listar, cargar, append, soft-delete)

## Phase 3: API + chat
- [X] T004 Schemas + rutas GET threads / GET thread + `thread_id` en POST /chat
- [X] T005 Extender `ask` con historial de texto y persistencia de turnos
- [X] T006 Tests unit/contract (seguimiento, listar, reabrir, aislamiento sesión/zona)

## Phase 4: UI
- [X] T007 Cliente API + SessionChatPanel (lista, nueva, reabrir, thread_id)
- [X] T008 Vitest SessionChatPanel

## Phase 5: Docs
- [X] T009 Quickstart verificado; puntero en 014 US3 → 015
