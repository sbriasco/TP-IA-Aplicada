# Feature Specification: Hilo de chat e historial

**Feature Branch**: `feature/015-chat-hilo-historial`  
**Created**: 2026-10-30  
**Status**: Draft  
**Input**: Plan aprobado opción C — hilo con contexto + historial persistente por sesión de análisis.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seguimiento sin repetir contexto (Priority: P1)

Como analista, quiero preguntar «¿y la permanencia?» después de una respuesta sobre la zona abierta y recibir cifras ancladas a lecturas, para conversar con menos fricción.

**Independent Test**: Tras una respuesta en un hilo, un seguimiento sin nombrar otra sesión usa la misma sesión/zona del hilo y solo cifras consultadas en ese turno.

**Acceptance Scenarios**:

1. **Given** un hilo abierto con una respuesta sobre la sesión/zona, **When** el analista hace un seguimiento que no nombra otra sesión, **Then** el chat mantiene ese contexto y no mezcla otra sesión.
2. **Given** un seguimiento que pide una cifra nueva, **When** se responde, **Then** esa cifra proviene de una lectura de ese turno (no de memoria inventada del modelo).
3. **Given** un seguimiento ambiguo, **When** se envía, **Then** el chat pide aclaración en lugar de adivinar.

### User Story 2 - Historial de conversaciones de la sesión (Priority: P1)

Como analista, quiero ver conversaciones anteriores de esta sesión de análisis, reabrir una y seguir escribiendo, o empezar una nueva, para no perder el trabajo del chat al recargar.

**Independent Test**: Tras varias conversaciones en una sesión, la lista las muestra; reabrir restaura mensajes; «Nueva conversación» empieza vacía; otra sesión no lista esos hilos.

**Acceptance Scenarios**:

1. **Given** al menos una conversación guardada en la sesión abierta, **When** el analista abre resultados, **Then** ve la lista de esas conversaciones.
2. **Given** una conversación elegida, **When** la reabre, **Then** ve los mensajes previos y puede seguir preguntando en el mismo hilo.
3. **Given** «Nueva conversación», **When** pregunta, **Then** se crea un hilo nuevo sin el texto de los anteriores.
4. **Given** el analista cambia de sesión de análisis, **When** mira el chat, **Then** solo ve hilos de la sesión actual.
5. **Given** el analista cambia de zona con un hilo de otra zona activo, **When** mira el chat, **Then** ese hilo no se presenta como contexto activo de la nueva zona.

### User Story 3 - Grounding y límites (Priority: P1)

Como equipo, quiero que el historial no permita inventar cifras ni ampliar el alcance prohibido, para conservar las garantías del chat ampliado.

**Independent Test**: Un número solo del historial sin lectura del turno no se muestra; compra/identidad/SQL siguen rechazados; webcam sin chat comercial.

**Acceptance Scenarios**:

1. **Given** un borrador que copia un número del historial no presente en las figures del turno, **When** se filtra, **Then** no se muestra esa respuesta.
2. **Given** webcam, **When** se usa el chat, **Then** sigue indisponible como hoy.

### Edge Cases

- Pregunta vacía: error claro.
- Hilo inexistente o de otra sesión: no encontrado / aclaración.
- Sesión incompleta o sin zona: mismos comportamientos de no disponibilidad / aclaración del chat ampliado.
- Fallo del modelo: mensaje de error; el hilo puede conservar el turno de usuario según política de persistencia segura (no inventar respuesta).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir conversaciones persistentes asociadas a una sesión de análisis, con título (auto desde la primera pregunta si falta) y zona (`shop_id`) asociada.
- **FR-002**: El sistema MUST listar las conversaciones de la sesión abierta y permitir reabrirlas o crear una nueva.
- **FR-003**: Cada pregunta MUST poder enviarse en el contexto de un hilo; el backend MUST usar un historial acotado de texto para interpretar seguimientos.
- **FR-004**: Todo número mostrado MUST provenir de una lectura/contraste del turno actual. El historial MUST NOT ser fuente de verdad de cifras.
- **FR-005**: Al cambiar de sesión, MUST mostrarse solo el historial de esa sesión. Al cambiar de zona, MUST NOT presentar un hilo de otra zona como contexto activo.
- **FR-006**: Credenciales y llamadas al modelo MUST permanecer en el backend; presupuesto máximo de llamadas por pregunta MUST ser el del chat ampliado (2).
- **FR-007**: Webcam, compra confirmada, identidad y multi-cámara MUST conservar las mismas exclusiones/rechazos del chat ampliado.
- **FR-008**: Esta feature supersede el diferido US3 de specs/014: el hilo con memoria pasa a estar comprometido.

### Key Entities

- **Conversación (hilo)**: agrupación de mensajes de una sesión (y zona) con título y timestamps.
- **Mensaje**: turno usuario o asistente; el asistente puede guardar el payload de cifras del turno para reabrir la UI.
- **Contexto de seguimiento**: texto reciente del hilo usado solo para interpretar la pregunta.

## Success Criteria *(mandatory)*

- **SC-001**: El 100 % de los números citados en respuestas de seguimiento proviene de lecturas del turno.
- **SC-002**: Tras recargar resultados de la misma sesión, el analista recupera al menos una conversación previa y puede continuar.
- **SC-003**: Cambiar de sesión no muestra hilos de la sesión anterior como activos.
- **SC-004**: Demostración de grounding sin servicio de pago sigue siendo posible (redactor falso).

## Assumptions

- Sin autenticación de usuarios: el historial es del entorno/base compartida.
- Historial acotado al enviarse al modelo (últimos N turnos de texto).
- No hay página global de chat aparte del panel de resultados.
