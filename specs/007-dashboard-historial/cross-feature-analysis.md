# Alignment Check: Dashboard e historial

**Feature**: `specs/007-dashboard-historial`
**Date**: 2026-09-30
**Analyzed Against**: 6 existing features (`001`, `002`, `003`, `004`, `005`, `006`)

---

## Impact Summary

**Cross-Feature Interactions**: Sí — `006` (cifras de la sesión y hechos por tramo), `005` (conteos parciales y muestra de posiciones), `004` (video ausente y frame de referencia). `002` aísla la sesión. `001` ya rotuló el tráfico como no identidad. `003` no muestra métricas.
**Conflict Risk**: Low
**Action Required**: No

---

## Questions to Resolve

1. Resuelta el 2026-09-30: los ocho indicadores son siempre los de toda la sesión. El tramo solo filtra los hechos y muestra, entero, cada minuto del flujo que se solapa con ese tramo.

---

## Issues Found

### ⚠️ With Feature 006-eventos-metricas

**Issue**: `007` pide que indicadores y flujo coincidan con cifras ya registradas para el tramo elegido; `006` registra las ocho métricas y el flujo de toda la sesión, y el intervalo solo filtra hechos.
**Impact**: Recalcular el tramo en el tablero crea una segunda verdad que el chat no va a leer.
**Fix**: Hecho. Los ocho indicadores quedan los de toda la sesión. El tramo no arma una segunda cifra.

### ⚠️ With Feature 005-procesamiento-tracking

**Issue**: `007` habla de una métrica parcial de un análisis que no terminó; `005` solo marca como parciales las entradas, las salidas y la ocupación visible, y `006` no publica las otras cinco hasta el cierre.
**Impact**: El tablero puede mostrar tráfico, tasa o permanencia como si ya existieran a mitad del análisis.
**Fix**: Hecho. Mientras corre, solo entradas, salidas y ocupación visible, marcadas como parciales. Las otras cinco aparecen al completar.

### ⚠️ With Feature 004-configuracion-escenas

**Issue**: `007` dice que, sin el video en este equipo, la previsualización no está disponible; `004` igual muestra metadatos y el frame de referencia.
**Impact**: El mapa de calor puede quedar sin escena aunque el frame sí esté guardado.
**Fix**: Hecho. «No disponible» es la reproducción del archivo. El frame de referencia sigue visible y el mapa, si hay muestra, se dibuja sobre ese frame.

---

## Recommendations

- [x] **Do**: Responder la pregunta 1 y dejar el filtro de tramo alineado con lo que `006` ya guarda.
- [ ] **Do**: Mostrar la versión de configuración que quedó en ese análisis, porque `004` sigue creando versiones nuevas de la cámara y `005` ya guardó la usada.
- [ ] **Avoid**: Tratar el historial como un alta de video. Registrar la sesión sigue en `004`.
- [ ] **Avoid**: Si el análisis más reciente no está completado, mostrar cifras de uno anterior como resultado final, porque `006` no las da por completas.
- [ ] **Avoid**: Armar el mapa de calor recalculando métricas desde la muestra, porque `005` la guardó para consulta y `006` no la usa como fuente de hechos.

---

## Feature Dependencies

**This feature depends on**:
- `004`: sesión, metadatos, frame de referencia y aviso de video ausente en este equipo.
- `005`: estado del análisis, motivo de fallo o cancelación, versión usada, tres conteos parciales y muestra de posiciones.
- `006`: ocho métricas, flujo, horario pico y hechos de una sesión completada, aislados de las demás.

**Features that will depend on this**:
- Chat mínimo (Feature #16, todavía sin spec): tiene que leer las mismas cifras que este tablero, no unas recalculadas.

---

## Potential Side Effects

- **Tramo más chico que un minuto**: el flujo de `006` ya viene en intervalos de un minuto. Un recorte adentro de un minuto no tiene una cifra propia → no partir ese intervalo en el tablero.

---

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [x] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

---

**Status**: ✅ Ready for planning
