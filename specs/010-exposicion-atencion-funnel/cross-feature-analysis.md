# Alignment Check: Exposición, detención, atención estimada y funnel comercial

**Feature**: `010-exposicion-atencion-funnel`
**Date**: 2026-10-23
**Analyzed Against**: 9 specs (001–009)

## Impact Summary

**Cross-Feature Interactions**: Directas con 004, 005, 006, 007, 008 y 009. 001 aporta el protocolo de diferencias. 002 y 003 no exigen cambios.
**Conflict Risk**: Medio. El choque está en el significado de paso, tasa, hechos de zona y en qué pantalla se muestran las etapas.
**Action Required**: No. Las tres preguntas quedaron resueltas en la spec el 2026-10-23.

## Questions Resolved · 2026-10-23

1. El funnel es de toda la sesión. El tramo no lo cambia.
2. La exposición es la entrada de zona de vidriera ya existente, sin un segundo hecho.
3. Cada tasa del funnel se nombra por sus dos etapas. La tasa de ingreso ya existente queda igual.

## Issues Found

### CF-01 · Medio · Hechos de vidriera (006)

**Issue**: Entrar a la vidriera ya es una entrada de zona; 010 FR-003 agrega otro hecho de exposición por el mismo pie.
**Impact**: La lista de hechos puede mostrar dos eventos de una sola entrada, y la etapa del funnel puede no coincidir con esas entradas de zona.
**Fix**: Resuelto. La exposición es la entrada de zona ya registrada. No se agrega ni se borra un hecho. El funnel cuenta la visita una sola vez.

### CF-02 · Medio · Oscilación (005 y 006)

**Issue**: La ventana de oscilación de 005 FR-015 y 006 FR-004 vale para la línea de entrada, no para el borde de una zona. 010 FR-005 la aplica a la vidriera.
**Impact**: Las entradas de zona de vidriera pueden seguir duplicadas mientras el funnel cuenta una sola exposición.
**Fix**: No cambiar los cruces ni las entradas de zona ya definidos. La deduplicación de 010 vale solo para sus etapas.

### CF-03 · Medio · Tasa e indicadores (006 y 007)

**Issue**: La tasa de ingreso de 006 es entradas oficiales divididas por pasos frente al local, que excluyen a quienes entraron. 010 usa otro paso y otras tasas.
**Impact**: Un mismo rótulo haría creer que el ingreso vinculado reemplazó las entradas o la tasa ya mostrada en 007.
**Fix**: Resuelto. Cada tasa del funnel se nombra por sus dos etapas. La tasa de ingreso conserva nombre y valor.

### CF-04 · Medio · Misma consulta para tablero y chat (006 y 008)

**Issue**: 006 FR-012 entrega las mismas cifras al tablero y al chat. 008 FR-001 solo admite cinco cifras y 010 FR-014 prohíbe responder el funnel en el chat mínimo.
**Impact**: Si el funnel entra en esa consulta, el chat mínimo pasa a ver cifras que debe rechazar.
**Fix**: Dejar intacta la consulta de las ocho métricas y de las cinco cifras. Leer el funnel por una consulta distinta, que el chat mínimo no usa.

### CF-05 · Medio · Cuándo se muestra (007 y 009)

**Issue**: 007 FR-008 no muestra tráfico ni tasa hasta el cierre. 009 FR-013 prohíbe las métricas comerciales en webcam y comparte la lectura de resultados.
**Impact**: El funnel puede aparecer en un análisis incompleto o en una sesión en vivo, al lado de entradas parciales.
**Fix**: Mostrarlo solo en una sesión de archivo con análisis completado. No presentarlo como cifra parcial en la vista de 005 ni en el historial de webcam.

### CF-06 · Bajo · Tramo del video (007)

**Issue**: 007 FR-006 y FR-007 impiden armar indicadores nuevos al recortar el tramo. 010 no dice si el funnel obedece ese recorte.
**Impact**: Recalcular el funnel por el tramo rompe la regla de los ocho indicadores; dejarlo fijo sin decirlo confunde al analista.
**Fix**: Resuelto. El funnel es de toda la sesión, igual que los ocho indicadores. El tramo no lo recalcula.

## Recommendations

- [ ] **Do**: Resolver las preguntas 1 y 2 en `/speckit-clarify` y ajustar FR-003, FR-012 y FR-014.
- [ ] **Do**: Mantener entradas oficiales, paso frente al local, permanencia y ocupación como están en 005 y 006.
- [ ] **Avoid**: Aplicar los umbrales de 3 s y 8 s a la permanencia frontal o a la estadía de webcam.
- [ ] **Avoid**: Hacer que el chat mínimo cite exposición, detención, atención o ingreso vinculado.

## Feature Dependencies

**This feature depends on**:

- 004: local con zona frontal obligatoria y vidriera opcional; las zonas pueden superponerse.
- 005: pie, identificador temporal, entradas oficiales y ventana de oscilación de la línea.
- 006: hechos de zona, paso frente al local, ocho métricas y permanencia solo en el frente.
- 007: resultado por local, tramo que no cambia los ocho indicadores.
- 008: rechazo de toda cifra fuera de las cinco.
- 009: sesión de webcam sin este funnel.
- 001: clasificar diferencias del contraste manual sin declarar exactitud.

**Features that will depend on this**:

- Chat ampliado (Feature #11): tendrá que leer estas etapas y no calcularlas desde el video.
- Comparaciones (Feature #10): no forman parte de este funnel.

## Potential Side Effects

- **Métricas de archivo**: un umbral de vidriera aplicado a la zona frontal cambiaría permanencia y ocupación → vigilar que sigan solo en el frente.
- **Vista durante el análisis**: los hechos recientes de 005 no deben rotularse como etapa del funnel → no mostrar atención ni ingreso vinculado antes del cierre.
- **Webcam**: reutilizar la estadía por zona del vivo para la detención de 3 s contaría un funnel que 009 no admite → calcular estas etapas solo en archivo.

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [x] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

**Status**: ✅ Ready for planning
