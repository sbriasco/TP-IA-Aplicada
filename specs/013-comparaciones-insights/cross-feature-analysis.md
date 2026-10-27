# Alignment Check: Comparaciones e insights

**Feature**: `013-comparaciones-insights`
**Date**: 2026-10-27
**Analyzed Against**: 12 existing features (001–012)

---

## Impact Summary

**Cross-Feature Interactions**: Yes — 006 (métricas), 007 (historial/resultados), 008 (chat mínimo), 009 (webcam), 010–012 (funnel/patrones/posible compra; lectura opcional), Feature #11 futura (chat ampliado)
**Conflict Risk**: Low — FR-004/FR-005 y preguntas de alineación resueltas; queda respetar «no disponible ≠ cero» en implementación
**Action Required**: No blocking — proceder a plan; mantener que comparación no altera consultas de una sola sesión

---

## Questions Resolved (2026-10-27)

1. Zona (P2): misma cámara + mismo nombre; `shop_id` puede diferir entre versiones de escena; no unificar solo por nombre entre cámaras.
2. Horario (P2): tiempo del video (timestamps del archivo), no registro ni procesamiento.
3. Familia opcional ausente en un lado: fila visible; lado = no disponible; sin diferencia inventada.

---

## Issues Found

### ⚠️ With Feature 006-eventos-metricas

**Issue**: Diferencias mal armadas si un lado «no disponible» se trata como 0 (tasa, permanencia).
**Impact**: Insights falsos («más tasa») y contradicción con FR-011/SC-004 de 006.
**Fix**: Diferencia solo con ambos lados disponibles; si no, celda/insight no disponible.

### ⚠️ With Feature 007-dashboard-historial

**Issue**: El historial es por sesión; la comparación es multi-sesión y puede competir por el mismo recorrido de UI.
**Impact**: Confusión si se presenta como «otro resultado de una sola sesión» o si el tramo de 007 parece recalcular la comparación.
**Fix**: Pantalla/flujo de comparación aparte; tramo de una sesión no redefine cifras de comparación (solo lectura de totales ya guardados).

### ⚠️ With Feature 008-chat-analitico-minimo

**Issue**: El chat mínimo solo cita cinco cifras de una sesión/local; la comparación es otra fuente.
**Impact**: Si el mínimo responde comparaciones, se rompe el alcance de 008 y SC-007 de 013.
**Fix**: Mantener FR-008/SC-007: el mínimo no narra comparación ni insights; eso es Feature #11.

### ⚠️ With Feature 009-webcam-en-vivo

**Issue**: 013 excluye webcam como columna completa; 009 tiene métricas parciales/en vivo distintas.
**Impact**: Incluir vivo como si fuera archivo completado inventa comparabilidad.
**Fix**: Rechazar o etiquetar no comparable (alineado a FR-002).

### ⚠️ With Features 010–012 (funnel / patrones / posible compra)

**Issue**: (Resuelto) Familias opcionales de lectura sin dependencia de bolsas.
**Impact**: Sesiones sin 010–012 muestran no disponible en esas filas; no rompen la comparación base.
**Fix**: Aplicado — filas visibles con no disponible; nunca recalcular.

---

## Recommendations

- [x] **Do**: Resolver FR-004 y FR-005 (y las 3 preguntas de arriba) en `/speckit-clarify` antes de plan.
- [ ] **Do**: Reutilizar semántica de disponibilidad y rótulos de estimación de 006/007/010–012 sin nuevos cálculos desde video.
- [ ] **Avoid**: Agregar herramientas de comparación al chat mínimo (008); dejar lectura al chat ampliado (#11).
- [ ] **Consider**: Entrada a la comparación desde el historial (007) eligiendo N sesiones, sin mutar la pantalla de resultado individual.

---

## Feature Dependencies

**This feature depends on**:
- 006: ocho métricas, tasa, pico, no disponible vs cero
- 007: historial y sesiones completadas identificables
- 004 (indirecto): zonas/locales de escena si hay eje por zona
- 010–012 (opcional): solo si FR-005 las incluye como lectura

**Features that will depend on this**:
- Feature #11 chat ampliado: debe leer comparación/insights ya armados, no calcularlos desde el video

---

## Potential Side Effects

- **UI de resultados**: un bloque multi-sesión no debe ocultar ni recalcular el resultado de una sesión (007/010–012).
- **Lenguaje**: insights que mencionen tráfico/atención/posible compra deben conservar «estimación».

---

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [x] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

---

**Status**: ✅ Clarified — ready for `/speckit-plan`
