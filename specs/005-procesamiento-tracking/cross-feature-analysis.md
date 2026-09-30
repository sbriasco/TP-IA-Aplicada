# Alignment Check: Procesamiento y seguimiento con vista en vivo

**Feature**: `specs/005-procesamiento-tracking`
**Date**: 2026-09-29
**Analyzed Against**: 4 existing features (`001`, `002`, `003`, `004`)

---

## Impact Summary

**Cross-Feature Interactions**: Sí — `002` (trabajos, un análisis a la vez, vista, interrupción), `004` (video, versión de escena y compuerta de inicio), `001` (reglas de conteo y de identificador temporal). `003` no interviene: no procesa video ni define métricas.
**Conflict Risk**: Low
**Action Required**: No

---

## Questions to Resolve

1. Resuelta el 2026-09-29: entradas, salidas y ocupación visible al completar son los números oficiales. Las features posteriores los leen y no los recalculan.
2. Resuelta el 2026-09-29: cancelar deja el estado «cancelado». Los demás estados son pendiente, procesando, completado y fallido. Una caída del proceso sigue en fallido.

---

## Issues Found

### ⚠️ With Feature 002-entorno-arquitectura-base

**Issue**: `005` dice «en curso», «terminado» y «cancelado»; `002` fija pendiente, procesando, completado y fallido.
**Impact**: Una máquina de estados paralela rompe el flujo sintético y el recupero tras interrupción.
**Fix**: Reusar los cuatro estados de `002`; si se agrega `cancelado`, que sea solo por acción del operador y que un proceso caído siga en `fallido` sin reintento.

### ⚠️ With Feature 002-entorno-arquitectura-base

**Issue**: `002` limita la vista sintética a 320×180, 100 KiB y una sola actualización pendiente; `005` pide recuadros, zonas y línea sobre el instante del video.
**Impact**: Aplicar el tope sintético al video real deja la escena ilegible; frenar por un cliente lento viola `002`.
**Fix**: El tope de tamaño queda en la prueba sintética; la vista real muestra el instante declarado, descarta imágenes viejas y no detiene el análisis.

### ⚠️ With Feature 004-configuracion-escenas

**Issue**: `005` FR-001 pide «una escena válida» y no exige preselección, elección de una versión anterior ni el bloqueo si la proporción difiere más de 1 %.
**Impact**: El análisis puede usar otra escena que la elegida, o una dibujada para otra proporción.
**Fix**: El inicio cumple FR-025 a FR-028 de `004` y el trabajo guarda la versión elegida; `005` no los redefine.

### ⚠️ With Feature 001-validacion-videos-tracking

**Issue**: `001` exige que un cambio de identificador no sea por sí solo otra persona, un cruce duplicado ni una salida; `005` cuenta entradas y salidas.
**Impact**: Un identificador que cambia sobre la línea duplica una entrada o inventa una salida.
**Fix**: Un cambio de identificador no suma un cruce ni confirma una salida; si se pierde el seguimiento no se infiere permanencia.

---

## Recommendations

- [ ] **Do**: Alinear los nombres de estado con `002` y tratar `cancelado` solo después de responder la pregunta 2, porque las pruebas sintéticas ya afirman pendiente → procesando → completado o fallido.
- [ ] **Do**: Declarar en `005` que la compuerta de inicio es la de `004` (versión elegida, misma cámara, proporción dentro del 1 %), porque si no el plan la vuelve a inventar.
- [ ] **Consider**: Fijar que entradas, salidas y ocupación visible de `005` son la fuente que #14 consulta, para que no existan dos definiciones.
- [ ] **Avoid**: Romper sesiones sintéticas, trabajos sintéticos o versiones de escena ya guardadas al agregar el análisis de video real, porque `002` y `004` siguen siendo el recorrido reproducible sin el equipo de referencia.
- [ ] **Avoid**: Prometer que la vista iguala la velocidad del video; `002` y `005` ya dejan esa velocidad como medición.

---

**Status**: ✅ Ready for planning
