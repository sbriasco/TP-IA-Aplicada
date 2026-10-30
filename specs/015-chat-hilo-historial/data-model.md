# Data Model: Hilo de chat e historial

## chat_threads

| Campo | Tipo | Regla |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK sessions | sesión de análisis |
| shop_id | UUID \| null | zona al crear/usar |
| title | string | auto desde 1ª pregunta (recortada) |
| created_at / updated_at | timestamptz | |
| deleted_at | timestamptz \| null | baja lógica |

## chat_messages

| Campo | Tipo | Regla |
|---|---|---|
| id | UUID PK | |
| thread_id | UUID FK | |
| role | user \| assistant | |
| content | text | mensaje mostrado |
| created_at | timestamptz | |
| answer_payload | text JSON \| null | solo assistant: status, message, scope, figures, comparison, model_calls |

## ChatRequest ampliado

| Campo | Tipo | Regla |
|---|---|---|
| question | string | |
| session_id | UUID | |
| shop_id | UUID \| null | |
| thread_id | UUID \| null | omitido → crear hilo nuevo |

## ChatResponse ampliado

Incluye `thread_id` cuando hay conversación asociada.
