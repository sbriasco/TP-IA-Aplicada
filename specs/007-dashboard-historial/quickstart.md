# Quickstart: Dashboard e historial

Validación de la feature. No incluye la implementación.

## Precondiciones

- Backend y frontend como en el README. PostgreSQL de test, sin la base compartida de Azure.
- Dependencia ya acordada, todavía no instalada: Recharts `3.10.1`.
- El detector de prueba de specs/005. No hace falta GPU ni un clip real.

## Qué tiene que quedar verde

Contrato del historial, contra [contracts/openapi.yaml](./contracts/openapi.yaml):

```powershell
cd backend
.\.venv\Scripts\pytest tests\contract\test_processed_sessions_api.py
```

- Una sesión sin análisis no aparece.
- Una completada trae nombre, archivo, estado, `finished_at` y `version_number` de la versión guardada en ese análisis, no el número de una versión posterior de la cámara.
- Una fallida trae el motivo y `result_complete` en false.
- Otra sesión no aparece en la fila de la primera.

Filtro de minutos, puro, en el frontend:

```powershell
cd frontend
npm test
```

Un minuto de 0–60 se muestra entero si el tramo es 50–70. No se parte. Los ocho indicadores de la prueba no cambian al mover el tramo.

Recorrido de interfaz, junto a los que ya existen:

```powershell
cd frontend
npm run test:e2e
```

El recorrido abre el historial, entra a una sesión completada y ve los ocho indicadores iguales a los del pedido de métricas. Una segunda sesión no se mezcla. Con el archivo marcado como ausente, el frame de referencia sigue y el texto dice que el video no está en este equipo. El mapa puede faltar: el recorrido igual termina.

## Fuera de esta corrida

- El contraste manual del clip (historia #64).
- El chat.
- Una medición nueva de velocidad del detector.
