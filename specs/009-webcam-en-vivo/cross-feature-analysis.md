# Alignment Check: Análisis en vivo con webcam

**Feature**: `009-webcam-en-vivo`
**Date**: 2026-10-03
**Analyzed Against**: 8 specs (001–008), constitución 1.0.1, AGENTS.md y decisiones técnicas.

## Impact Summary

**Cross-Feature Interactions**: Directas con 002, 004–007; indirecta con 008; 001 aporta validación. 003 no requiere cambios.
**Conflict Risk**: Alto en semántica de métricas y cierre; medio en preparación y transporte.
**Action Required**: Aclaraciones incorporadas en 009; conservar comportamiento de archivos y concretar los parámetros técnicos en el plan.

## Questions Resolved · 2026-10-03

1. Cruces por minuto separados de visitas estimadas; sentidos A/B o entradas/salidas según encuadre (respuesta 1).
2. Detención normal produce completado con cobertura independiente; cancelación de archivos y fallo de worker conservan su significado (respuesta 2).
3. Se conserva muestra acotada y mapa de calor histórico (respuesta 3); el historial muestra las cifras acordadas sin indicadores comerciales adicionales (respuesta 4).

Resolución: CF-01 → FR-008/009; CF-02 → FR-003; CF-03 → US1/FR-002 y abandono de preparación; CF-04 → FR-004/007; CF-05 → FR-014/019/021; CF-06 → FR-013; CF-07 → FR-020. Parámetros de ventana, continuidad, guardado y muestreo se concretan en el plan, sin nuevas decisiones de producto pendientes.

## Issues Found

### CF-01 · Alto · Significado del flujo (006, 007 y 008)
**Issue**: 009 FR-009 agrupa entradas + salidas; 006 FR-007/010 agrupa tracks distintos y exige que el flujo sume tráfico estimado; 007 FR-006 y 008 FR-004 reutilizan ese significado.
**Impact**: Una visita con ida y vuelta podría representarse como dos unidades de tráfico y alterar el pico citado por el chat.
**Fix**: Separar «Total de cruces» y «Cruces por minuto» de tráfico, flujo de visitas y horario pico; no sobrescribir las métricas existentes.

### CF-02 · Alto · Detención y cierre oficial (002, 005 y 006)
**Issue**: 009 FR-003/013 no fija el estado al detener; 005 FR-014/016 distingue completado/cancelado y 006 FR-008 consulta medidas oficiales del cierre completado.
**Impact**: Cancelar para terminar la expo dejaría el resultado incompleto; completar sin marca de cobertura ocultaría pérdidas de captura.
**Fix**: Definir detención normal como cierre del intervalo observado y cobertura como atributo independiente; mantener cancelación de archivo y fallo de worker sin reanudación automática.

### CF-03 · Medio · Origen y preparación (004 y 007)
**Issue**: 004 FR-001/004/008 y 007 FR-001 presuponen archivo; 009 US1 crea sesión al iniciar, pero 004 FR-022 exige una sesión previa para guardar la escena sobre su frame.
**Impact**: Reutilizar el editor requiere resolver esa dependencia; pedir hash/ruta o mostrar «video perdido» sería incorrecto para webcam sin grabación.
**Fix**: Registrar sesión webcam y frame durante preparación, crear trabajo al iniciar y definir abandono de preparación; no exigir archivo/hash/duración anticipada y mostrar «Sin grabación» sin recarga/reanálisis de archivo.

### CF-04 · Alto · Reloj, continuidad e IDs (002, 005, 006; constitución III)
**Issue**: 009 FR-006/007 cambia el reloj sin fijar ventana temporal ni máximo intervalo entre observaciones; FR-004 reinicia tracks por segmento pero no concreta su identidad persistida.
**Impact**: Frames demasiado separados pueden producir cruces sin continuidad fiable; IDs reutilizados tras reconectar pueden colisionar con hechos anteriores.
**Fix**: Fijar ventana y máximo intervalo admisible en plan; distinguir sesión/cámara/segmento/track, invalidar continuidad al excederlo y conservar el timestamp original del cruce al confirmar. Documentar la extensión del tiempo de captura en constitución, AGENTS.md y decisiones técnicas, preservando archivos.

### CF-05 · Medio · Persistencia y memoria (002, 005; decisiones técnicas)
**Issue**: 009 FR-010/014 prohíbe previews persistentes; el camino actual guarda snapshots, persiste cada 15 frames y conserva muestras de trayectorias (005 FR-005).
**Impact**: Reutilizarlo literalmente guardaría imágenes, demoraría persistencia a baja tasa y podría acumular tracks/muestras durante horas aunque la cola de frames sea acotada.
**Fix**: Definir vivo sin snapshots persistentes, guardado con cadencia temporal y entrega conjunta de imagen/cifras; acotar tracks inactivos y muestras. Decidir si vivo conserva trayectorias; sin muestra, mapa vacío explicado (007 FR-011).

### CF-06 · Alto · Dashboard e historial reducido (005–008)
**Issue**: 009 FR-008/013 compromete cuatro cifras; 005 FR-013 incluye ocupación parcial, 007 FR-008 limita parciales a tres medidas y FR-005 espera indicadores comerciales al completar.
**Impact**: El dashboard podría ocultar el gráfico nuevo, exigir cifras ausentes o habilitar herramientas de chat que esta entrega no respalda.
**Fix**: Declarar pantalla de vivo como extensión por origen; concretar inclusión de ocupación y cifras históricas; mantener dashboard de archivos y no habilitar respuestas del chat para cifras no producidas.

### CF-07 · Medio · Minutos y cobertura (006 y 007)
**Issue**: 009 FR-009 marca el minuto actual parcial, pero confirmar tarde un cruce puede modificar el minuto anterior; no define cobertura parcial de intervalos con interrupción.
**Impact**: Congelar minutos al cambio de reloj omite cruces pendientes; completar huecos con ceros simula ausencia de tránsito.
**Fix**: Admitir corrección de buckets pendientes; separar intervalo abierto de cobertura incompleta y registrar tiempo observado/perdido. Definir agregación por local sin presentar sumas de líneas como personas únicas.

## Recommendations

- [x] Resolver CF-01/02/06 mediante `/speckit-clarify` y ajustar la spec 009.
- [x] Completar preparación y contrato histórico por origen (CF-03).
- [x] Delimitar ventana, continuidad, identidad por segmento, cadencia y límites de memoria como obligaciones del plan (CF-04/05/07).
- [ ] Añadir regresiones de archivos para métricas, cancelación, timestamps, snapshots y chat; comprobar vivo sin grabación y sin herencia de datos tras reconectar.
- [ ] Vincular Azure Boards antes de implementar y registrar decisiones como evolución explícita.

## Feature Dependencies

- **001**: Comparación manual por ocurrencia; 40 cruces no prueban precisión en una multitud no ensayada.
- **002**: Persistencia, recuperación tras caída, exclusión del worker y reemplazo de actualizaciones pendientes.
- **004**: Cámara, escena inmutable, editor y frame compartido; conservar validación de proporción y referencias tras bajas lógicas.
- **005**: Visión aprobada y fuente oficial de entradas/salidas; registrar también versiones y parámetros en vivo.
- **006/007**: Hechos e historial con extensión explícita por origen que preserve métricas de archivos.
- **008**: Compatibilidad de consultas; sin ampliar chat ni depender de Foundry para la demo.

## Quick Checklist

- [x] Preguntas de cierre, métricas y alcance histórico respondidas.
- [x] Riesgos incorporados en spec o delimitados para plan.
- [x] Dependencias e impactos documentados en este informe.
- [x] Checklist de requisitos revalidada tras aclarar.
- [x] Marcador de aclaración retirado de spec.md al resolver el informe.

**Status**: Listo para planificación. Revisión documental asistida por IA; sin cambios de código ni pruebas de funcionamiento. Regresiones, Azure Boards y actualización de documentos de gobierno siguen como trabajo previo a implementación.
