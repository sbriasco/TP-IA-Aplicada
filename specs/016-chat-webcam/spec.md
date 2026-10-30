# Feature Specification: Chat unificado para reportes de webcam

**Feature Branch**: `feature/016-chat-webcam`  
**Created**: 2026-10-30  
**Status**: Draft  
**Input**: Chat de IA disponible sobre reportes de webcam guardados, reutilizando hilos 015 y el mismo panel que video.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar un reporte de webcam guardado (Priority: P1)

Como analista, quiero preguntar al asistente sobre cruces, permanencia, cobertura y duración de una captura de webcam ya finalizada, para interpretar el reporte sin recalcular a mano.

**Independent Test**: Con un job live en estado terminal y fake drafter, `POST /chat` responde `answered` con figures del canal live; funnel/compra aparecen no disponibles.

**Acceptance Scenarios**:

1. **Given** un análisis de webcam `completed`/`failed`/`cancelled` con checkpoint, **When** pregunto por entradas o cruces, **Then** el chat cita cifras del resumen live de esa sesión/zona.
2. **Given** el mismo reporte, **When** pregunto por funnel o posible compra, **Then** esas figures quedan no disponibles (no se inventan).
3. **Given** un job live aún `pending`/`processing`, **When** llamo al chat, **Then** responde `409 live_chat_unavailable`.

### User Story 2 - Mismo panel e historial que video (Priority: P1)

Como analista, quiero usar el mismo `SessionChatPanel` e historial de hilos (015) en la vista de resultados de webcam guardados.

**Independent Test**: `LiveResultsPage` monta el panel solo cuando el status es terminal; los hilos se listan por `session_id`.

**Acceptance Scenarios**:

1. **Given** un reporte webcam terminal, **When** abro resultados, **Then** veo el chat con sugerencias propias de live.
2. **Given** una captura aún en vivo, **When** miro resultados/diagnóstico, **Then** el chat no se monta.
3. **Given** conversaciones previas de esa sesión, **When** abro el historial, **Then** aplican las mismas reglas de 015.

## Requirements *(mandatory)*

- **FR-001**: El chat MUST permitirse solo con reporte webcam guardado (job live terminal).
- **FR-002**: Las figures de webcam MUST leerse del canal live (`live_*` / checkpoint), no de `shop_metrics`/funnel de archivo.
- **FR-003**: Periodo MUST ser toda la sesión; grounding, tope de 2 model calls y `draft_refusal` MUST conservarse.
- **FR-004**: Hilos 015 (`chat_threads` por `session_id`) MUST aplicar también a webcam.
- **FR-005**: Contrastes comerciales entre archivos MUST seguir excluyendo sesiones webcam.
- **FR-006**: La UI MUST montar el mismo panel en resultados webcam terminales.

## Success Criteria *(mandatory)*

- **SC-001**: 100 % de cifras citadas en webcam provienen de figures live del turno.
- **SC-002**: Un job en ejecución no obtiene respuesta del modelo.
- **SC-003**: Demostración con redactor falso sin Azure.
