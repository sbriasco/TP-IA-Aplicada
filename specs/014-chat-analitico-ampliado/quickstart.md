# Quickstart: Chat analítico ampliado

Validar grounding y contraste **sin** depender de Azure de pago en CI.

## Prerrequisitos

- PostgreSQL de test y migraciones al head (igual que el resto del backend).
- Backend instalado en `backend/.venv` (deps ya fijadas; **no** agregar paquetes).
- Frontend con Vitest (`frontend/`).
- Sesiones sintéticas de archivo `result_complete` con métricas (y opcional funnel/patrones/posible compra) como en tests de 008/012/013.

## Backend (grounding + guards)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_chat_metrics.py tests/unit/test_chat_guard.py tests/contract/test_chat_api.py -q --basetemp=.pytest-tmp-chat014
```

Esperado:

- Catálogo ampliado: salidas / pasos / tasa presentes cuando están en DB; opcionales ausentes → unavailable (no cero).
- Contraste: pregunta con abierta + «última» o dos nombres → números = ensamblado comparison; eje sin grupos → sin columnas inventadas.
- Rechazo: compra confirmada / identidad / SQL / video → `refused` sin cifras.
- Webcam o incomplete → `unavailable`.
- Redactor falso: 100 % de números del mensaje ∈ figures/contraste (SC-001/002/005).
- `POST /comparisons` y GET métricas/funnel/patrones/possible-purchases sin cambio de cuerpo (regresión).

## Frontend

```powershell
cd frontend
npx vitest run tests/SessionChatPanel.test.tsx
```

(Ajustar el path al test del panel si el nombre difiere.) Esperado: espera/error/answered; limpieza al cambiar sesión; rótulos de estimación; contraste/aclaración visibles sin romper resultados.

## Manual (opcional, no bloquea)

Con Foundry configurado: una pregunta de catálogo y una de contraste sesión vs sesión; verificar que el texto no afirma venta y que coincide con el tablero/comparación. Medir cuotas sigue `not_measured`.

## Demo de materia (SC-006)

En &lt; 2 minutos: «El agente llama tools acotadas; las cifras salen de PostgreSQL vía analytics; no hay RAG ni SQL libre; el modelo solo redacta.»
