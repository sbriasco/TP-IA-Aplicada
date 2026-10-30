# Panel de chat ampliado

Mismo panel en la pantalla de resultados de la sesión abierta (supersede el chat mínimo). No reemplaza indicadores ni la pantalla de comparación.

## Envío

- Campo de pregunta con etiqueta visible; botón de envío con nombre accesible.
- Al enviar: estado de espera; no pintar respuesta vacía como definitiva.
- El pedido lleva `session_id` de la página y el local/zona elegido (`shop_id` vacío si no hay selección).
- Cada envío es una pregunta independiente (sin historial de cifras hacia el backend).

## Respuesta

| Estado | Qué se ve |
|---|---|
| `answered` | Texto; sesión/zona o contraste usado; cifras/rótulos que respaldan; si hubo contraste, eje y columnas en lenguaje cotidiano |
| `refused` | Rechazo (compra, identidad, fuera de alcance, SQL/video). Sin cifras |
| `needs_clarification` | Pedido de aclaración (sesión/zona/par de contraste ambiguo). Sin cifras inventadas |
| `unavailable` | Sin resultado final (incompleto, vivo, etc.). Sin catálogo comercial como cierre |
| `error` | Mensaje claro (timeout, modelo no configurado). Tablero y comparación siguen |

Rótulos alineados al tablero: estimación de visitas, visible, observable, posible compra estimada, no disponible. Pico en segundos de video. Día de contraste = fecha UTC de cierre de análisis (como en comparación).

## Sesión y contraste

- Por defecto las cifras de una sesión son las de la abierta, salvo que nombre otra o «la última».
- Contraste: requiere indicar con qué comparar (otro nombre y/o «la última») y, si aplica, el eje; si falta, se pide aclaración.
- Al abrir otra sesión o cambiar zona, el panel limpia el hilo local. No se presentan cifras de la selección anterior como si fueran de la nueva.

## Accesibilidad

- Controles nativos; estados anunciables (espera/error/respuesta).
- Sin depender solo del color para no disponible vs cero.
