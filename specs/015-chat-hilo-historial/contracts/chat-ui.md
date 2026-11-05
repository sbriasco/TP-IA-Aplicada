# Chat UI — hilo e historial

- Panel de resultados: lista de conversaciones de la sesión + «Nueva conversación».
- Reabrir un hilo restaura mensajes (texto + figures del assistant si hay payload).
- Cada envío incluye `thread_id` del hilo activo (salvo nueva conversación, que omite hasta la primera respuesta).
- Cambio de `sessionId`: limpia selección y recarga lista.
- Cambio de `shopId` con hilo de otra zona: deselecciona el hilo (no lo usa como activo).
- Webcam: panel de chat comercial sigue no ofreciendo cifras (mismo 409/unavailable).
