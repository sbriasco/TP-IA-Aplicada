# Research: Chat analítico mínimo

## R1 — Cinco lecturas y la herramienta ficticia queda aparte

**Decision**: El chat del producto usa cinco lecturas nuevas en `services/chat_metrics.py`. Cada una llama a `load_shop_metrics` y devuelve una sola cifra ya guardada. `llm/fake_tools.py` y `run_tool_loop` no se modifican y siguen sirviendo solo al script de validación de specs/003.

**Rationale**: Esa herramienta devuelve un tráfico fijo (`total_entries: 42`) y no lee la sesión. Si el chat la reutilizara, la respuesta desmentiría el tablero. El ciclo de validación ya está demostrado; cambiarlo arriesga esa evidencia.

**Alternatives considered**: Reemplazar la herramienta ficticia por las lecturas reales (el script de specs/003 dejaría de ser reproducible sin PostgreSQL). Hacer que el modelo arme SQL sobre `shop_metrics` (la constitución lo prohíbe).

## R2 — Qué cifra es cada lectura

**Decision**: Las lecturas son `traffic_total`, `entries`, `visible_occupancy`, la pareja `dwell_mean_seconds` y `dwell_median_seconds`, y el pico ya guardado (`bucket_index`, `start_seconds`, `track_count`). Los rótulos son los de specs/006: estimación de visitas, visible y observable. El pico se cita como tramo del video, en segundos, no como hora de reloj. No hay parámetro de tramo: si el pedido trae uno, se ignora y el alcance sigue siendo toda la sesión. Salidas, pasos, tasa y los minutos del flujo no se exponen.

**Rationale**: La spec ya igualó «ocupación máxima» con la ocupación visible guardada y «ingresos por local» con las entradas oficiales. El producto no guarda una fecha real del video. Un máximo nuevo o una hora de reloj serían cifras que el tablero no muestra.

**Alternatives considered**: Elegir solo la media de permanencia y esconder la mediana (las dos están registradas y las dos son observables). Convertir el pico a hora local (no hay fecha real que lo justifique).

## R3 — Sesión, local y análisis incompleto

**Decision**: Antes de redactar se elige una sesión y un local. La sesión abierta del panel gana, salvo que la pregunta diga «la última» o un nombre. «La última» es la de `finished_at` mayor; si empatan, gana el análisis de `id` mayor. Un nombre elige la sesión procesada cuyo nombre coincide, sin distinguir mayúsculas. Si coincide más de una, se pregunta y no se llama al modelo. El local es el elegido en resultados, salvo que la pregunta nombre otro de esa escena. Si hay varios y ninguno está elegido ni nombrado, se pregunta. Si el análisis más reciente no tiene `result_complete`, la respuesta dice que no hay resultado final, puede incluir el motivo de falla o cancelación, y no entrega las cinco cifras ni las tres parciales. No se sustituye por un análisis anterior completo.

**Rationale**: Es la misma regla del historial: se muestra el análisis más reciente. Las tres parciales no son el cierre. Elegir en silencio una sesión o un local mezclaría cifras.

**Alternatives considered**: Usar el orden de `created_at` del historial como «la última» (no es la fecha de procesamiento). Caer a un análisis viejo completo cuando el último falló.

## R4 — Filtros y tope de llamadas

**Decision**: Un filtro de la pregunta, sin modelo, rechaza confirmar una compra, identificar a una persona, seguirla entre cámaras y responder fuera de las sesiones y de las cinco cifras. También corta, sin número, un pedido de salidas, pasos, tasa o flujo. Recién después se consulta. El borrador se muestra solo si cada número que contiene está en las lecturas de esa pregunta y si no afirma una venta, una identidad ni trata una estimación como observación. Si no pasa, se reemplaza por un rechazo. Una pregunta hace como máximo dos llamadas al modelo, el mismo tope de rondas que la validación. Un rechazo, una aclaración o un análisis incompleto hace cero. El registro anota cuántas llamadas hubo y el código de error. No anota la clave, el texto de la pregunta ni el borrador.

**Rationale**: El crédito de estudiantes no está medido. El filtro previo evita gastar una llamada en una pregunta que igual hay que rechazar. El posterior cubre un borrador que se saltea el filtro. Comparar números no necesita el servicio de pago.

**Alternatives considered**: Dejar que el modelo decida el rechazo (puede consultar cifras igual y afirmar una venta). Guardar el texto completo para auditarlo (la spec deja los secretos y lo anotado de la pregunta fuera de ese registro).

## R5 — El panel y el pedido

**Decision**: `POST /chat` recibe la pregunta, la sesión abierta y el local elegido. La respuesta trae un estado (`answered`, `refused`, `needs_clarification`, `unavailable`, `error`), el texto, la sesión y el local usados, el alcance `whole_session` y las cifras que respaldan. El panel está en la pantalla de resultados. Al enviar se ve espera. Al cambiar de sesión se borra el hilo. El hilo vive en la página: no hay tabla ni migración.

**Rationale**: La spec no pide historial de chat. Persistirlo mezclaría sesiones si el cambio de pantalla no lo limpia, y obligaría a una migración que las cifras no necesitan.

**Alternatives considered**: Guardar cada turno en PostgreSQL. Un chat flotante fuera de resultados, sin sesión abierta.

## R6 — Espera, configuración y fallo

**Decision**: El tope es 20 segundos, en `FLOWSIGHT_CHAT_TIMEOUT_SECONDS`. La espera del panel empieza al enviar, no a los 20 segundos. Si falta la configuración de Azure, la llamada vence, el servicio falla o el contenido vuelve vacío, `POST /chat` responde `error` con un mensaje claro y sin cifras. Ese resultado no cambia el tablero ni los otros pedidos. La clave sigue en el entorno, con los nombres que ya documenta specs/003.

**Rationale**: La validación midió respuestas del orden de varios segundos y dejó las cuotas sin medir. Diez segundos corta una respuesta lenta que todavía es usable; veinte cubre dos rondas sin dejar el panel colgado. Un error HTTP de toda la aplicación haría parecer que el tablero también falló.

**Alternatives considered**: Sin tope, hasta que Azure conteste. Reutilizar el mensaje de configuración inválida del script de validación tal cual, incluyendo la guía de `.env` (no es lo que tiene que leer quien mira resultados).

## R7 — Prueba sin el servicio de pago

**Decision**: La suite inyecta un redactor falso que devuelve un borrador y, si corresponde, pide lecturas. Las lecturas se prueban contra PostgreSQL de test, comparando con lo ya guardado. El recorrido de interfaz usa ese falso. Una corrida manual con `gpt-5-mini` queda descripta en el quickstart y no es requisito para dar por válida la feature.

**Rationale**: La spec exige demostrar que no se inventan números sin el servicio de pago. CI no tiene la clave, igual que specs/003.

**Alternatives considered**: Marcar la feature como válida solo si Azure contesta. Llamar al modelo real desde pytest.
