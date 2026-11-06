# Top 5 de secuencias en el resumen

Pedido del usuario (2026-11-06): en el resumen al terminar, volver a mostrar
las secuencias de visita y dejar solo las cinco con más visitas. El resto se
ve al ampliar. Los nombres usan la forma corta que aprobó.

## Diseño

El cálculo no cambia y no se vuelven a procesar las sesiones. La API sigue
devolviendo todas las secuencias. La pantalla las ordena y recorta.

El bloque aparece en el resultado de un video terminado y en el de una cámara
ya detenida. La vista mientras la cámara corre no lo muestra.

Arriba van las secuencias. Abajo sigue el conteo de grupos estimados, como
está ahora. No vuelven las transiciones ni los cambios de local.

### Orden y recorte

Se ordenan por cantidad de visitas, de mayor a menor. Si empatan, queda
primero la que ya venía antes en la respuesta. Se muestran cinco. Si hay cinco
o menos, no hay control para ampliar. Si hay más, el control cerrado dice
«Ver el resto de las secuencias» y el abierto dice «Ocultar el resto de las
secuencias». Cerrado, esas secuencias no están en la página. Abierto, siguen
el mismo orden. Cada cadena distinta sigue siendo una tarjeta aunque el texto
corto coincida.

Si no hay secuencias, el bloque dice «No hay secuencias.». El conteo de
grupos no cambia.

### Nombres

El nombre sale de las zonas ya cargadas en ese resultado, unidas por el
identificador de la zona. La respuesta de patrones no trae el nombre. El
número es el entero al final del nombre de la zona. «Zona 1» aporta `1`. Si
ese identificador no está en la lista, el texto lleva solo el rol.
El rol se escribe `Frente`, `Interior` o `Vidriera`, pegado al número:
`Frente1`. Si el nombre no termina en un entero, el rol y el nombre completo
van separados por un espacio: `Frente Kiosco`.

| Recorrido | Texto |
| --- | --- |
| Solo el frente de la zona 1 | Frente1 |
| Solo el interior de la zona 1 | Interior1 |
| Frente y después interior | Frente1 → Interior1 |
| Interior y después frente | Interior1 → Frente1 |
| Ida y vuelta, termina donde empezó | Frente1 ⇄ Interior1 |
| Ida, vuelta y otra ida | Frente1 ⇄ Interior1 (X2) |
| Cada ida de más | Frente1 ⇄ Interior1 (X3) |

`⇄` se usa solo cuando la cadena alterna entre dos áreas. Una ida es cada
paso que sale del área inicial hacia la otra. Una sola ida con vuelta se
escribe `⇄` y no lleva `(X1)`. Desde la segunda ida se escribe `(X2)`,
`(X3)` y así. Una vuelta que no inicia otra ida no aumenta ese número: `A B A
B` y `A B A B A` se leen igual, `(X2)`, y siguen en tarjetas distintas.

Si entra una tercera área, el texto usa flechas y no se abrevia el recorrido:
`Frente1 → Interior1 → Frente2`.

El número grande de la tarjeta sigue siendo la cantidad de visitas.

## Aceptación

- Con más de cinco secuencias, el resumen muestra las cinco de mayor cantidad
  de visitas y el conteo de grupos. El resto aparece solo al ampliar.
- Con cinco o menos, se ven todas y no hay control de ampliar.
- Un empate no salta una secuencia que ya venía antes.
- Los ejemplos de la tabla de nombres se leen así, incluida la vidriera como
  `Vidriera1`.
- Dos cadenas distintas con el mismo texto corto no se suman.
- Una sesión ya terminada se ve con esta pantalla sin reprocesar el video ni
  la cámara.
- La vista en vivo, mientras corre, no gana este bloque.
