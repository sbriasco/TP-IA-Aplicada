# Grupos estimados con membresía exclusiva

Pedido del usuario (2026-11-05): después de ajustar la distancia a 0,12 del
ancho y el ángulo a 60 grados, el conteo de grupos sigue alto. Un id que ya
pertenece a un grupo confirmado no puede formar parte de otro. Aprobó
reservarlo recién al cumplir 1 segundo y congelar los miembros de ese grupo.

## Diseño

El conteo sigue siendo de episodios que duraron al menos 1 segundo de video.
La distancia, el ángulo, el corte de movimiento y la entrada de quien no tiene
dirección no cambian: 0,12 del ancho, 60 grados, 0,005 del ancho, y la cercanía
alcanza si falta una dirección. El salto de un frame del análisis queda fuera
de este cambio.

Antes de cumplir 1 segundo el grupo es provisorio. Sus integrantes pueden
cambiar. Si el conjunto cambia o se interrumpe, ese tramo no se emite y esos
ids siguen libres. El conjunto nuevo empieza su propio tiempo en el frame en
que aparece.

Cuando un mismo conjunto cumple 1 segundo, sus ids quedan reservados hasta el
fin del análisis. El episodio conserva exactamente esos miembros: nadie se
suma. Sigue abierto mientras el conjunto se mantiene junto. Una ausencia de
hasta 1 segundo lo conserva y no inventa posiciones. Una ausencia de más de 1
segundo lo cierra. Los ids reservados no abren otro episodio, ni entre sí ni
con alguien libre.

Quien no está reservado puede formar grupos solo con otros que tampoco lo
estén. En un mismo instante, un id pertenece a un solo conjunto. Cada id
aparece como máximo en un episodio emitido, así que la cantidad de grupos no
supera a la de personas observadas en ese análisis. Varios `track_id` de un
mismo cuerpo siguen siendo ids distintos.

Los informes ya guardados no se recalculan. La exclusividad no agrega una
columna ni un umbral: no hay migración. Resultados sigue mostrando solo la
cantidad de grupos estimados.

## Aceptación

- Una pareja junta al menos 1 segundo, que después se separa más de 1 segundo
  y se reencuentra, cuenta como un solo grupo.
- Un acercamiento de menos de 1 segundo no reserva. Esos ids pueden confirmar
  después otro conjunto.
- Un tercero que se acerca a un grupo ya confirmado no entra. El episodio
  conserva a los miembros originales.
- Dos parejas distintas, simultáneas y suficientes en tiempo, siguen siendo
  dos grupos.
- Un informe ya guardado conserva su conteo hasta que se vuelva a analizar.
- Ruff y las pruebas de patrones de visita que cubren estos casos pasan.
