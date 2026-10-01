# Validación del agente FlowSight — 2026-10-01

Revisión y correcciones con asistencia de IA en `fix/chat-grounding`, después del commit local `2f046d6`. Sin dependencias, cambios de modelo ni migraciones nuevas.

## Problemas encontrados

Azure responde: el rechazo reproducido provenía del filtro de cifras. El nombre del local seleccionado, `Local 1`, incluía un número que el filtro interpretaba como una métrica inventada. El rechazo también ocultaba las llamadas realizadas al modelo: devolvía `model_calls=0` aunque se hubiera consultado Azure.

La sesión histórica consultada tenía un análisis final con escena, pero no tenía métricas comerciales ni intervalos de tráfico guardados. Eso no permite deducir por qué faltan, ni afirmar que el video nunca fue procesado. El chat mostraba además un horario pico de cero a partir de un valor de respaldo, aunque no existieran intervalos.

## Correcciones

- La primera llamada exige `get_session_figures`; la segunda produce texto sin herramientas. El resultado de la herramienta contiene únicamente las cifras ya leídas para la sesión y el local resueltos por el backend. Si el proveedor omite la consulta obligatoria, su texto no se publica. Se mantienen dos llamadas como máximo, el presupuesto de 2048 tokens y `reasoning_effort=low`.
- La herramienta entrega nombres, alcances, unidades y motivos comprensibles. Los decimales conservan su precisión y omiten ceros finales. El modelo explica la falta de datos sin pedir comandos internos ni atribuirla a una causa desconocida.
- La interfaz ya cita el local y el alcance, por lo que se pide al modelo omitir nombres en su texto. Si los incluye, el filtro excluye únicamente referencias al nombre exacto entre comillas, precedidas por `local`, `sesión` o `para`. Sus dígitos nunca se agregan al conjunto de cifras permitidas. Nombres con delimitadores de comillas o caracteres no imprimibles no reciben esta excepción. El prefijo genérico `en` no se excluye porque también introduce mediciones como `se estimó en «123 visitas»`.
- Las cifras inventadas siguen bloqueadas. Se cubren nombres como `123 visitas` y `10 segundos`, nombres numéricos, prefijos parecidos y nombres que intentan cerrar comillas para ocultar una afirmación.
- Sin intervalos guardados, el horario pico queda no disponible en la API de chat y en su presentación. Cero sigue siendo un resultado válido cuando está registrado.
- `model_calls` conserva las llamadas realizadas cuando se rechaza una respuesta. Las preguntas rechazadas antes de consultar al modelo siguen devolviendo cero. Esto actualiza el comportamiento anterior de la especificación 006 que exigía cero también después de redactar.

El uso de herramientas forzadas está documentado en la [guía oficial de function calling](https://developers.openai.com/api/docs/guides/function-calling).

## Cómo revisarlo en la app

1. Abrir una sesión con resultados listos y seleccionar un local de su escena.
2. Preguntar `¿Cuál fue el tráfico total?`, `¿Cuántos ingresos hubo?`, `¿Cuál fue la ocupación visible?`, `¿Cuál fue la permanencia media?` y `¿Cuál fue el horario pico?`. Comparar las respuestas con los indicadores del mismo local y sesión; el alcance actual es toda la sesión, aunque cambie el tramo del gráfico.
3. Si una métrica falta, esperar una explicación de ausencia de datos. No aceptar cero como reemplazo. Si existe un cero registrado, debe citar cero.
4. Cambiar de sesión o local y comprobar que se limpia el chat. Las cifras de otro contexto no deben aparecer en la respuesta.
5. Preguntar `¿Confirmamos una compra?` o `¿Quién es esa persona?`: el sistema debe rechazarlo sin consultar Azure.

El historial visible es temporal y cada pregunta se resuelve independientemente. El MVP consulta tráfico, ingresos, ocupación visible, permanencia media/mediana y horario pico; no incorpora comparación aritmética entre sesiones ni métricas nuevas desde el LLM.

## Evidencia y límites

Se reprodujeron los fallos antes de corregirlos y se ejecutaron pruebas de regresión. Las verificaciones destructivas usan PostgreSQL local, separado de la base compartida. Las consultas a Azure de diagnóstico usan datos históricos en lectura o cifras sintéticas persistidas en una base local aislada; las transacciones de esas cifras se revierten.

El modelo real citó correctamente tráfico 17, ingresos 9, ocupación visible 2, permanencia media 3.125 segundos y pico desde 60 segundos con 5 tracks. También distinguió cero ingresos de permanencia no disponible. Tres preguntas sobre el análisis histórico sin métricas produjeron explicaciones de falta de datos, sin el falso rechazo por el identificador.

Frontend: 287 pruebas aprobadas y build de producción correcto. Playwright: 10 recorridos aprobados; utiliza un redactor de prueba y no mide la calidad del modelo. Suite backend local: 457 aprobadas, una omitida por permisos POSIX en Windows y dos deseleccionadas (GPU y chequeo de entorno). La batería final del chat, después de los ajustes adicionales del filtro, tiene 44 pruebas aprobadas; Ruff y `git diff --check` también pasan. El chequeo de entorno necesita acceso a Azure desde la configuración local; en el sandbox sin red fallaba, y con conectividad aprobada pasó. Logs y evaluaciones quedan ignorados en `.verification/frontend-redesign/`.

La API local se reinició con el arreglo. Las consultas reales a `/chat` sobre ingresos, tráfico y permanencia devolvieron `answered` y dos llamadas al modelo, con explicaciones de métricas no guardadas; tardaron entre 4.95 y 6.39 segundos en esas muestras. Compra e identidad se rechazaron antes del modelo, con cero llamadas. No se modificaron resultados históricos ni se ejecutaron nuevos análisis sobre los videos del usuario.

El filtro comprueba valores numéricos permitidos y algunas restricciones de alcance; no demuestra la corrección semántica de toda frase ni que un valor permitido se atribuya siempre a la métrica correcta. Las evaluaciones reales son muestras, no una garantía de disponibilidad, cuotas o calidad sostenida. La precisión de detección/tracking y de las métricas requiere comparar un video real con una referencia manual. La ausencia de métricas históricas no se rellena ni se repara con cifras inventadas.
