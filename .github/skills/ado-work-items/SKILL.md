---
name: ado-work-items
description: Usar cuando el usuario quiera preparar o cargar en Azure Boards el backlog de FlowSight a partir de especificaciones y tareas aprobadas, mediante el MCP de Azure DevOps. No usar para crear issues de GitHub ni para implementar funcionalidades.
---

# Work items de FlowSight

Convertir planificación aprobada en work items trazables, sin un backlog fijo dentro de esta skill. Respetar [AGENTS.md](../../../AGENTS.md) y las [instrucciones de Copilot](../../copilot-instructions.md).

## Preparar y consultar

1. Identificar el alcance solicitado y leer los documentos correspondientes de Spec Kit: `spec.md`, `plan.md` y `tasks.md` cuando existan. Consultar la constitución si está definida. La existencia de un archivo no demuestra su aprobación. Si falta planificación aprobada, preparar una propuesta local y señalar qué falta; no inventar historias para completar el MVP.
2. Descubrir o listar las herramientas disponibles y leer sus esquemas. Seleccionar las del MCP de Azure DevOps para consultar proyectos, tipos, campos, work items y relaciones. No fijar nombres de herramientas en esta skill ni asumir que son iguales entre versiones. Si no están disponibles, informar el bloqueo y conservar la propuesta sin crear por otro canal.
3. Resolver organización y proyecto desde el contexto o la configuración existente. Consultar al usuario si el destino es ambiguo. Verificar los tipos, campos obligatorios y jerarquías admitidos por el proceso del proyecto; no asumir que siempre utiliza User Stories.
4. Consultar los work items existentes dentro del alcance, con sus padres y referencias a especificaciones. Completar la paginación pertinente. Comparar referencia de origen, contenido, título y padre para identificar coincidencias. No tratar una búsqueda fallida o incompleta como ausencia de duplicados. Ante coincidencias ambiguas, mostrarlas antes de crear.

## Mostrar la propuesta

Presentar el destino y un listado revisable de cada ítem con:

- Referencia al archivo y al identificador de historia o tarea de origen. Los IDs como `T001` se acompañan de la ruta de su especificación, porque pueden repetirse entre funcionalidades.
- Tipo, título, descripción y criterios de aceptación cuando correspondan.
- Padre existente con ID, o referencia provisional al padre que se propone crear.
- Campos obligatorios, asignaciones y relaciones adicionales propuestas, si corresponden. No inventar responsables, iteraciones ni estimaciones.
- Acción: crear, reutilizar sin cambios o consultar una posible coincidencia.

Mantener la jerarquía simple: Features, historias y tareas solo donde la planificación y el proceso del proyecto lo justifiquen. No convertir cada paso de una checklist en otro work item ni crear Epics automáticamente.

Esperar confirmación explícita de esta propuesta antes de cualquier creación o cambio de relaciones. Una solicitud general de cargar el backlog no reemplaza la revisión del contenido concreto. Si el usuario ya aprobó esa misma propuesta, ejecutar lo aprobado sin pedirlo otra vez. Consultar únicamente cambios de alcance o contenido posteriores.

## Crear y verificar

1. Reconsultar coincidencias antes de crear para detectar cambios desde la propuesta. Si apareció un ítem equivalente, no duplicarlo; informar la coincidencia y consultar si la relación prevista es ambigua.
2. Crear primero los padres y después sus hijos, usando los IDs devueltos por el MCP. Establecer solo las relaciones aprobadas y conservar las referencias al origen de Spec Kit en las descripciones. Nunca inventar IDs o URLs.
3. No borrar, cerrar, reasignar ni editar el contenido o estado de work items existentes con esta skill. Se permiten únicamente las relaciones explícitamente incluidas en la propuesta aprobada. Los demás cambios requieren una tarea separada.
4. Leer los ítems creados para verificar proyecto, tipo, contenido y relaciones. Si ocurre un error o timeout, consultar el resultado antes de reintentar. No repetir una creación cuyo resultado siga siendo incierto ni crear hijos si no se confirmó su padre. Detener el bloque afectado e informar lo que falta, sin borrar lo creado para simular una ejecución completa.

## Informar el resultado

Entregar una tabla con referencia de origen, tipo, título, ID, enlace, padre y resultado: creado y verificado, reutilizado, fallido o pendiente de verificar. Separar resultados confirmados de pendientes e indicar los errores de forma concreta.

Al retomar una ejecución parcial, consultar lo existente y continuar solo con lo aprobado que falta. No volver a cargar todo el backlog. Esta skill publica la planificación en Azure Boards; no implementa código, no crea issues de GitHub y no modifica los archivos generados por Spec Kit.
