<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.0.1
- Modified principles: ninguno; se aclara la evidencia pertinente a cada decisión y se omite la mención a aprobaciones de otros integrantes.
- Added sections: ninguna.
- Removed sections: ninguna.
- Follow-up TODOs: validar compatibilidad, rendimiento, tracker, previsualización, Azure y reproducibilidad según el documento de decisiones.
-->

# FlowSight Constitution

## Core Principles

### I. Procesamiento local y entorno reproducible
El procesamiento de video y la persistencia de sus resultados DEBEN poder ejecutarse
localmente. La configuración de ejemplo, las migraciones y los datos sintéticos mínimos
DEBEN permitir que los seis integrantes reproduzcan el entorno sin depender de servicios
cloud para procesar video. Las tecnologías y versiones se rigen por
[Decisiones técnicas](../../docs/decisiones-tecnicas.md), sin fijar aquí su catálogo.

### II. Separación de responsabilidades
La solución DEBE mantener separadas las responsabilidades de visión, tracking, reglas
espaciales, eventos, métricas, API y presentación. Un cambio en una responsabilidad DEBE
poder probarse sin convertir las demás en dependencias implícitas. La estructura concreta
se mantiene alineada con [Decisiones técnicas](../../docs/decisiones-tecnicas.md).

### III. Trazabilidad temporal y por sesión
Cada detección, evento y métrica DEBE poder vincularse con su sesión, cámara, frame y
timestamp del video cuando corresponda. Los tiempos de negocio DEBEN calcularse con los
timestamps del video, nunca con la duración del procesamiento. Las consultas y trabajos
DEBEN aislar los datos entre sesiones, y las métricas DEBEN documentar denominadores,
deduplicación, datos incompletos y divisiones por cero como no disponible.

### IV. Privacidad e interpretación prudente
Un `track_id` DEBE tratarse como temporal y limitado a una sesión/cámara; no representa una
identidad real ni garantiza una persona única. El sistema NO DEBE implementar reconocimiento
facial, identidad real, seguimiento entre cámaras ni confirmación de compras como parte del
alcance comprometido. La ocupación visible DEBE distinguirse de la ocupación total, y no
DEBE inferirse permanencia cuando se pierde el seguimiento.

### V. Estimaciones explícitas y eventos confiables
Los eventos de cruce DEBEN protegerse contra duplicados producidos por oscilaciones en
líneas o bordes. Las conversiones entre etapas DEBEN usar tracks vinculados y criterios
compatibles. La exposición, atención y posible compra DEBEN presentarse como estimaciones,
con sus supuestos y limitaciones; ninguna capacidad avanzada DEBE comprometerse antes de
validarla con los videos disponibles.

### VI. Analytics acotado y credenciales protegidas
El chat DEBE consultar herramientas o APIs acotadas de analytics y redactar respuestas a
partir de sus resultados. El modelo NO DEBE calcular métricas desde el video ni ejecutar SQL
arbitrario generado por el usuario o por el propio modelo. Las credenciales y las llamadas
al modelo DEBEN permanecer en el backend.

### VII. Evidencia, incrementos pequeños y colaboración trazable
Cada cambio DEBE ser pequeño, verificable y vinculado a una tarea. Las pruebas DEBEN
corresponder al componente afectado y cubrir especialmente cruces, duplicados, timestamps,
aislamiento por sesión y métricas; las pruebas de interfaz DEBEN verificar recorridos reales.
Las decisiones y validaciones relevantes realizadas con IA DEBEN registrarse brevemente.
GitHub DEBE alojar el código, ramas y pull requests; Azure Boards DEBE concentrar historias,
tareas y bugs.

## Decisiones técnicas pendientes

La selección tecnológica acordada, sus motivos y sus límites están en
[Decisiones técnicas](../../docs/decisiones-tecnicas.md). La constitución no fija versiones
ni duplica ese catálogo. Cada decisión DEBE validarse con la evidencia que le corresponda.
Según la decisión, esta evidencia comprende compatibilidad en CPU y GPU, rendimiento,
calidad de tracking, sincronización de previsualización, acceso al modelo de Azure o
reproducibilidad de migraciones y datos sintéticos.

## Flujo de trabajo y calidad

El trabajo DEBE organizarse en incrementos pequeños, sin refactors ajenos ni ampliaciones
de alcance. Los pull requests DEBEN indicar qué cambió, cómo se verificó y la tarea de
Azure Boards relacionada. La revisión DEBE comprobar el cumplimiento de esta constitución.
El equipo mantendrá una
gobernanza simple adecuada para dos o tres desarrolladores activos.

## Governance

Esta constitución define restricciones de gobierno del proyecto y complementa
[AGENTS.md](../../AGENTS.md), que contiene el contexto y las reglas operativas generales.
Si existe una contradicción, debe documentarse antes de modificar una decisión acordada.

Las enmiendas requieren una propuesta explícita, una justificación breve, la actualización
del informe de impacto y la verificación de los documentos afectados. Los cambios de
principios o secciones incrementan la versión MINOR; las eliminaciones o redefiniciones
incompatibles incrementan MAJOR; las aclaraciones sin cambio de obligación incrementan
PATCH. Cada revisión debe comprobar principios, fechas, enlaces y validaciones pendientes.

**Version**: 1.0.1 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-15
