# Alignment Check: Chat analítico mínimo

**Feature**: `specs/008-chat-analitico-minimo`
**Date**: 2026-09-30
**Analyzed Against**: 7 existing features (`001`–`007`)

---

## Impact Summary

**Cross-Feature Interactions**: Sí — `006` y `007` (cifras ya registradas, sesión completa, parciales), `005` (las tres cifras parciales), `004` (video ausente, resultados igual), `003` (servicio de redacción y herramienta ficticia), `002` (aislamiento por sesión), `001` (tráfico no es identidad).
**Conflict Risk**: Low
**Action Required**: No

---

## Recommendations

- [ ] **Avoid**: Contestar el chat con la herramienta ficticia de `003`, porque esa cifra no es la de la sesión y desmentiría el tablero.
- [ ] **Avoid**: Calcular una ocupación máxima nueva o una cifra para un tramo, porque `006` y `007` ya fijaron la ocupación visible y las cifras de toda la sesión.

---

## Feature Dependencies

**This feature depends on**:

- `006` / `007`: las cinco cifras son las ya registradas del local para toda la sesión. Un tramo no las cambia. No disponible sigue siendo no disponible.
- `005` / `007`: mientras el análisis no terminó, solo hay tres cifras parciales. El chat no las presenta como las cinco finales.
- `004`: si el video no está en este equipo, las cifras registradas se pueden citar igual.
- `003`: el servicio de redacción ya validado. La prueba de que no se inventan números no llama a ese servicio. La herramienta ficticia queda solo en esa validación.
- `002` / `001`: una respuesta no mezcla sesiones ni trata el tráfico como una persona.

**Features that will depend on this**:

- El chat ampliado (feature #11, sin spec todavía) va a partir de estas cinco cifras y de estos rechazos.

---

## Potential Side Effects

- **Misma pantalla**: el tablero muestra salidas, pasos y tasa, y el chat no las cita. → No es un fallo del tablero; la respuesta tiene que decir que no puede citarlas, sin inventarlas.
- **Análisis a medias**: el tablero muestra tres cifras parciales y el chat dice que no hay resultado final. → Las dos pantallas tienen que poder verse juntas sin que el chat copie esas tres como cierre.

---

## Quick Checklist

- [x] All clarification questions answered
- [x] High/Medium risk issues addressed in spec
- [ ] Recommendations reviewed and incorporated as needed
- [x] Dependencies documented in spec
- [x] Clarification line removed from spec.md when complete

---

**Status**: ✅ Ready for planning

*No hay conflicto abierto con las specs existentes. La línea de aclaración en `spec.md` apunta a este archivo.*
