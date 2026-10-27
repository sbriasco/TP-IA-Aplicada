# Alignment Check: Evaluación de posible compra

**Feature**: `012-posible-compra`
**Date**: 2026-10-26
**Analyzed Against**: 11 specs (001–011)

## Impact Summary

**Cross-Feature Interactions**: Sí, con 005, 006, 007, 008, 009, 010 y 011. 001 aporta el contraste. 002–004 no exigen cambios.
**Conflict Risk**: Medio, ya resuelto en la spec
**Action Required**: No. Las dos decisiones quedaron en la sesión 2026-10-26.

## Questions to Resolve

1. Resuelta: la bolsa queda atada solo si su recuadro se solapa con el de exactamente una visita. Si se solapa con dos o con ninguna, no cuenta.
2. Resuelta: se cierra durante el mismo análisis que hechos, funnel y patrones, y se guarda solo el resultado. No hay otra pasada sobre el video.

## Issues Found

### ⚠️ With Feature 005-procesamiento-tracking

**Issue**: 005 solo produce visitas y pies; no define bolsas ni la regla para atarlas a un identificador.
**Impact**: Sin esa regla, el mismo video puede contar visitas distintas o inventar una bolsa repartida.
**Fix**: Hecho. Solape exclusivo del recuadro; si hay dos visitas o ninguna, no cuenta.

### ⚠️ With Feature 008-chat-analitico-minimo

**Issue**: 008 rechaza confirmar compras; 012 muestra «posible compra estimada» y prohíbe que el chat mínimo cite la cifra.
**Impact**: Una pregunta «¿hubo compras?» sigue rechazada, pero el panel puede confundirse con una venta si el rótulo no queda claro.
**Fix**: Mantener el rechazo del chat mínimo y el rótulo de estimación en resultados; no agregar bolsas a las cinco cifras.

### ⚠️ With Feature 010-exposicion-atencion-funnel

**Issue**: El ingreso vinculado no es una compra; 012 no debe sumar una sexta etapa ni reinterpretar entrada/atención como compra.
**Impact**: Mezclar la bolsa con el funnel cambiaría conteos ya cerrados.
**Fix**: Ya está en la spec: la bolsa no se atribuye a un local y no entra al funnel. No reabrir 010.

## Recommendations

- [x] **Do**: Resolver las dos preguntas en `/speckit-clarify` porque cambian el conteo y el momento de cierre.
- [ ] **Avoid**: Agregar la cifra a las ocho métricas de 006, a las cinco del chat de 008 o a las etapas del funnel de 010.
- [ ] **Avoid**: Calcular o mostrar esta estimación en resultados de webcam de 009.
- [ ] **Avoid**: Tratar un grupo estimado de 011 como compra ni exigir atención/entrada previas para contar la bolsa.

## Feature Dependencies

**This feature depends on**:

- 005: visita vinculada, instante de video y corte al perder el seguimiento.
- 006: las ocho métricas y la tasa de ingreso quedan iguales; esta cifra no entra en esa consulta.
- 007: el tramo del video no recalcula cifras de toda la sesión.
- 010: entrada, detención y atención no se reinterpretan; el funnel no gana etapa.
- 011: patrones y grupos quedan iguales; estar juntos no es compra.

**Features that will depend on this**:

- Comparaciones e insights (Feature #10) y chat ampliado (Feature #11): deben leer esta cifra y no calcularla desde el video.

## Potential Side Effects

- **Pantalla de resultados**: 007, 010 y 011 ya muestran bloques de toda la sesión; un bloque nuevo no debe ocultarlos ni recalcularlos.
- **Lenguaje**: «posible compra» junto al rechazo de compras del chat mínimo exige el rótulo de estimación en cada lectura.

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [x] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

**Status**: Resuelto en la spec el 2026-10-26
