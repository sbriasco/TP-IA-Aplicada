# Alignment Check: Patrones de visita y grupos estimados

**Feature**: `011-patrones-visita-grupos`
**Date**: 2026-10-24
**Analyzed Against**: 10 specs (001–010)

## Impact Summary

**Cross-Feature Interactions**: Sí, con 004, 005, 006, 007, 008, 009 y 010. 001 aporta el protocolo de diferencias. 002 y 003 no exigen cambios.
**Conflict Risk**: Medio, ya resuelto en la spec
**Action Required**: No. Las dos decisiones quedaron en la sesión 2026-10-24.

## Questions to Resolve

1. Resuelta: si el pie está en dos áreas a la vez, no hay transición. El paso se cuenta cuando sale de una y, en no más de 1 segundo de video y sin perder el seguimiento, queda en la otra.
2. Resuelta: los patrones y los grupos se cierran durante el análisis, con las mismas observaciones de los hechos. Se guarda el resultado. La muestra del mapa de calor no es la fuente.

## Issues Found

### ⚠️ With Feature 004-configuracion-escenas

**Issue**: Una escena válida puede tener zonas superpuestas, y 011 solo define la transición cuando se sale de un área y se entra en otra.
**Impact**: El mismo pie puede generar un cambio de local que no ocurrió, u omitir un recorrido real.
**Fix**: Hecho. La spec cuenta el paso al salir de un área y quedar en la otra.

### ⚠️ With Feature 005-procesamiento-tracking

**Issue**: El grupo exige cercanía y dirección durante 2 segundos de video, pero 005 solo conserva una muestra de trayectorias, no cada instante.
**Impact**: Calcular el grupo después, desde el mapa de calor, puede inventar o perder esos 2 segundos.
**Fix**: Hecho. Se cierran durante el análisis y se guarda el resultado. La muestra del mapa no es la fuente.

## Recommendations

- [x] **Do**: Resolver las dos preguntas en `/speckit-clarify` porque cambian conteos de secuencias y de grupos.
- [ ] **Avoid**: Sumar una transición de áreas al funnel, a las entradas oficiales o a la permanencia de 006 y 010, porque el interior y la vidriera no son exposición ni entrada.
- [ ] **Avoid**: Agregar patrones o grupos a las cinco cifras del chat mínimo de 008, ni mostrarlos en un resultado de webcam de 009.

## Feature Dependencies

**This feature depends on**:

- 004: áreas y locales ya configurados. El frente es obligatorio; interior y vidriera, no.
- 005: identificador temporal, pies, instante de video y corte de continuidad al reaparecer después de 1 segundo.
- 006: entradas y salidas de zona ya registradas, sin reescribirlas. Las ocho métricas y la tasa de ingreso quedan iguales.
- 007: el tramo del video filtra hechos y no cambia las cifras de toda la sesión.
- 010: el funnel no se alimenta con estas secuencias. Estar en el interior no es exposición ni atención.

**Features that will depend on this**:

- Las features de posible compra, comparaciones y chat ampliado todavía no tienen spec. Cuando existan, deben leer estas cifras y no calcularlas desde el video.

## Potential Side Effects

- **Pantalla de resultados**: 007 y 010 ya muestran cifras de toda la sesión junto a un tramo que solo filtra hechos. Un bloque nuevo no debe recalcular ni ocultar esos bloques.

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [x] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

**Status**: Resuelto en la spec el 2026-10-26
