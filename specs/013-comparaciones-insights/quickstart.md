# Quickstart: validar comparaciones e insights

Esta guía valida la feature. No la implementa. Modelo en [data-model.md](./data-model.md), API en [contracts/openapi.yaml](./contracts/openapi.yaml), UI en [contracts/comparison-ui.md](./contracts/comparison-ui.md).

## Prerrequisitos

- Entorno de specs/002–012 con `alembic upgrade head` desde `backend/`. No hace falta migración nueva de esta feature.
- Al menos dos sesiones sintéticas de archivo `completed` con `result_complete`, misma o distinta cámara, con métricas de un `zone_name` conocido.
- Opcional: una sesión sin funnel/patrones/posible compra y otra con ellos, para filas opcionales.

## Ensamblado y contrato

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests/unit/test_comparison.py tests/contract/test_comparison_api.py -q
```

Cubrir:

- Dos sesiones elegibles + `zone_name` → 200 con columnas, cifras base y relación/delta solo si ambos lados available.
- Cifra unavailable en un lado → celda no disponible, sin delta inventado, sin cero inventado.
- Familia opcional solo en una sesión → fila presente; lado ausente unavailable.
- Menos de dos elegibles (webcam, incompleta, id duplicado) → 409 `comparison_insufficient_sessions`.
- Misma petición dos veces → mismo cuerpo.
- `GET` métricas / funnel / patrones / possible-purchases / chat de cada sesión: cuerpo sin cambio.

## Regresión de lecturas existentes

```powershell
.\.venv\Scripts\pytest tests/contract/test_metrics_api.py tests/contract/test_funnel_api.py tests/contract/test_visit_patterns_api.py tests/contract/test_possible_purchase_api.py tests/contract/test_chat_api.py -q
```

## Pantalla

Desde `frontend/`:

```powershell
npm test -- Comparison
```

- Selector de ≥2 sesiones completadas + zona; rechazo claro si faltan.
- Tabla con no disponible y insights verificables o «sin diferencias».
- No aparece en vista webcam; el chat mínimo no muestra estos textos.
