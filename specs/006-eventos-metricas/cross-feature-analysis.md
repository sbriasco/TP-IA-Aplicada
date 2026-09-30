# Alignment Check: Eventos espaciales, métricas y persistencia

**Feature**: `specs/006-eventos-metricas`
**Date**: 2026-09-30
**Analyzed Against**: 5 existing features (`001`, `002`, `003`, `004`, `005`)

---

## Impact Summary

**Cross-Feature Interactions**: Sí — `004` (zona frontal, línea y zona interior opcional), `005` (números oficiales de entradas, salidas y ocupación visible, y la ventana de oscilación), `002` (sesión aislada y estado del análisis). `001` fija el rótulo de lo que no es viable. `003` no calcula métricas.
**Conflict Risk**: Low
**Action Required**: No

---

## Questions to Resolve

1. Resuelta el 2026-09-30: la permanencia observable es solo la de la zona frontal. Interior y vidriera no generan permanencia ni ocupación.

---

## Issues Found

### ⚠️ With Feature 004-configuracion-escenas

**Issue**: `006` genera una permanencia cuando el identificador «deja una zona»; `004` deja la zona interior opcional y prohíbe inferir permanencia o ocupación interior.
**Impact**: Un local sin interior, o con interior dibujado, puede mostrar una estadía que el experimento ya dio por no viable.
**Fix**: La permanencia observable es solo la de la zona frontal. Interior y vidriera no generan permanencia ni ocupación; si faltan, esas medidas siguen no disponibles.

### ⚠️ With Feature 005-procesamiento-tracking

**Issue**: `006` también registra entrada y salida del local, mientras `005` ya cerró esos dos conteos y la ocupación visible como números oficiales que no se recalculan.
**Impact**: Si los hechos confirmados no suman igual que esos oficiales, la consulta muestra dos verdades.
**Fix**: Entradas, salidas y ocupación visible de la consulta son los oficiales de `005`. Los hechos de cruce explican ese número y usan la misma ventana de oscilación; no son un segundo conteo.

---

## Recommendations

- [ ] **Do**: Responder la pregunta 1 y dejar en `006` que la permanencia observable es solo la zona frontal, porque `004` ya cerró el interior.
- [ ] **Do**: En el plan, leer entradas, salidas y ocupación visible del análisis completado, porque `005` ya lo exige y `006` FR-008 lo repite.
- [ ] **Avoid**: Contar el tráfico por identificador temporal como personas únicas, porque `001` lo dejó no viable y `006` ya lo rotula como estimación de visitas.
- [ ] **Avoid**: Publicar las ocho métricas como resultado completo si el análisis está pendiente, fallido o cancelado, porque `002` y `005` distinguen ese cierre.

---

## Feature Dependencies

**This feature depends on**:
- `004`: versión de escena con zona frontal y línea de entrada por local; interior y vidriera opcionales.
- `005`: análisis completado, ventana de oscilación, y los tres números oficiales.

**Features that will depend on this**:
- Tablero e historial, y el chat mínimo: leen esta consulta y no calculan desde el video (`003` solo validó el modelo).

---

## Potential Side Effects

- **Línea que no toca la zona frontal**: `004` la permite con aviso. La tasa (entradas oficiales / pasos en la zona frontal) puede quedar rara o no disponible → no inventar pasos para compensar.

---

**Status**: ✅ Ready for planning
