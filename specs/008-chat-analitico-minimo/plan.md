# Implementation Plan: Chat analítico mínimo

**Branch**: `feature/008-chat-analitico-minimo` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-chat-analitico-minimo/spec.md`

**Azure Boards**: Feature #16 (Epic #1). User Stories #68, #69, #70, #71 y #72.

## Summary

El chat cita cinco cifras ya registradas de una sesión y un local. No calcula métricas ni guarda una conversación.

- Cinco lecturas internas leen `load_shop_metrics`. La herramienta ficticia de specs/003 no se usa para responder ([R1](./research.md#r1--cinco-lecturas-y-la-herramienta-ficticia-queda-aparte), [R2](./research.md#r2--qué-cifra-es-cada-lectura)).
- La sesión y el local se resuelven antes de redactar. Un análisis que no cerró no entrega las cinco cifras ([R3](./research.md#r3--sesión-local-y-análisis-incompleto)).
- Un filtro previo y otro posterior rechazan ventas, identidades y números que no salieron de una lectura. Una pregunta no hace más de dos llamadas al modelo ([R4](./research.md#r4--filtros-y-tope-de-llamadas)).
- `POST /chat` vive en el panel de resultados. Si el servicio no está o tarda más del tope, el tablero sigue ([R5](./research.md#r5--el-panel-y-el-pedido), [R6](./research.md#r6--espera-configuración-y-fallo)).
- La prueba de que no se inventan números no llama a Azure ([R7](./research.md#r7--prueba-sin-el-servicio-de-pago)).

## Technical Context

**Language/Version**: Python 3.11.16 en el backend. TypeScript 5.9 con `strict` y React 19.1 en el panel.

**Primary Dependencies**: FastAPI y Pydantic, los ya usados. El cliente `openai==1.109.1` y el deployment `gpt-5-mini` ya validados en specs/003. No hay otro SDK ni otra librería de interfaz.

**Storage**: Sin migración. Las cifras salen de `shop_metrics` y `traffic_buckets`. La sesión y el análisis salen de las tablas que ya lee el historial. El hilo del chat no se persiste.

**Testing**: Pytest de las cinco lecturas y del pedido de chat, con un redactor falso. Vitest del panel. Playwright del recorrido en resultados. La corrida de Azure queda manual y no bloquea.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Esta feature agrega una lectura para el modelo y un panel en la pantalla de resultados.

**Performance Goals**:

- No hay meta de tiempo real. La espera se muestra en cuanto se envía la pregunta.
- El tope de una pregunta es 20 segundos (`FLOWSIGHT_CHAT_TIMEOUT_SECONDS`). Pasado ese tiempo hay un mensaje y el tablero sigue.
- Una pregunta hace como máximo dos llamadas al modelo. Un rechazo, una aclaración o un análisis incompleto hace cero.
- SC-001 a SC-006 se demuestran sin el servicio de pago. SC-003 cubre el conjunto de preguntas prohibidas.

**Constraints**:

- Las cinco cifras son las de toda la sesión. Un tramo pedido en la pregunta no las cambia.
- No se citan salidas, pasos, tasa ni el detalle del flujo.
- La ocupación que se cita es la visible ya registrada. La permanencia es la observable. El pico es el tramo de video ya guardado.
- El análisis más reciente, si no está completo, no se reemplaza por uno anterior completo.
- Los secretos del servicio no salen en la respuesta, en el registro ni en el repositorio.
- Sin chat ampliado, sin comparaciones, sin grupos, sin atención, sin posible compra y sin el contraste manual de la historia #64.

**Scale/Scope**: seis integrantes y pocas sesiones. Un panel en la pantalla de resultados. Cinco lecturas y un listado de sesiones.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R7).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa PostgreSQL de test y un redactor falso. Azure no es requisito de CI | Aprobado |
| II. Responsabilidades separadas | Las lecturas no calculan métricas. El modelo no ve SQL. El panel no recalcula | Aprobado |
| III. Trazabilidad y aislamiento | Cada respuesta nombra sesión, local y alcance de toda la sesión. El pico sigue en tiempo de video | Aprobado |
| IV. Privacidad | El filtro rechaza identidad, seguimiento entre cámaras y confirmación de compra | Aprobado |
| V. Estimaciones explícitas | Tráfico como estimación de visitas, ocupación como visible, permanencia como observable | Aprobado |
| VI. Analytics acotado | Solo las cinco lecturas y el listado de sesiones. La clave queda en el backend | Aprobado |
| VII. Evidencia e incrementos | Historias #68 a #72. La prueba manual de Azure no bloquea | Aprobado |

**Revisión post-diseño**: se mantiene. `POST /chat` no agrega una métrica ni una tabla. La herramienta ficticia de specs/003 sigue solo en el script de validación.

## Project Structure

### Documentation (this feature)

```text
specs/008-chat-analitico-minimo/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── metric-tools.md
│   └── chat-ui.md
├── checklists/
│   └── requirements.md
├── cross-feature-analysis.md
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
backend/src/flowsight/
├── llm/fake_tools.py, llm/tool_loop.py     # no cambian; siguen la validación de specs/003
├── services/chat_metrics.py                # cinco lecturas sobre load_shop_metrics
├── services/chat.py                        # resuelve sesión y local, filtra, redacta
└── api/routes.py, api/schemas.py           # POST /chat

frontend/src/
├── pages/SessionResultsPage.tsx           # monta el panel; no saca los indicadores
├── components/SessionChatPanel.tsx
└── api/chat.ts

frontend/e2e/session-chat.spec.ts
backend/tests/contract/test_chat_api.py
backend/tests/unit/test_chat_metrics.py
```

**Structure Decision**: se mantiene el monorepo. No hay worker nuevo, migración ni SDK nuevo. El panel se agrega a la pantalla de resultados que ya existe.

## Implementation Phases

1. **Lecturas (#68)**: las cinco cifras y el listado de sesiones, sin llamar al modelo. Una cifra no disponible vuelve no disponible. Un análisis incompleto no devuelve las cinco.
2. **Respuesta respaldada (#69)**: `POST /chat` con el servicio ya validado, el tope de dos llamadas y el de 20 segundos. El redactor falso alcanza para la suite.
3. **Límites (#70)**: el filtro previo no consulta cifras. El filtro posterior no muestra una venta, una identidad ni un número que no esté en las lecturas de esa pregunta.
4. **Panel (#72)**: espera, error y cifras que respaldan la respuesta, en la sesión abierta. Cambiar de sesión limpia el panel.
5. **Sesión anterior (#71)**: «la última» y un nombre. Si no se distingue una sola, el chat pregunta y no llama al modelo.

#68 bloquea a #69. #69 bloquea a #70 y a #72. #71 se apoya en #69 y no bloquea el panel de la sesión abierta.

## Verification Strategy

- **#68**: cada lectura coincide con la cifra ya registrada de ese local para toda la sesión. No disponible no se vuelve cero. Otra sesión no se cuela. Salidas, pasos y tasa no tienen lectura.
- **#69**: en el conjunto de preguntas, todo número de la respuesta está en las lecturas de esa pregunta. Sin configuración, con tiempo agotado o con texto vacío, hay un mensaje y el resto de la API sigue.
- **#70**: el conjunto documentado de compras, identidad y temas ajenos se rechaza sin lecturas. Un borrador que igual afirmaría una venta o trataría una estimación como observación no se muestra así.
- **#72**: desde resultados se pregunta sin salir. Se ven la espera o el error, el local, el alcance y los valores. La sesión siguiente no muestra el hilo anterior.
- **#71**: «la última» es la de `finished_at` más reciente. Un nombre que coincide con dos sesiones no elige una.
