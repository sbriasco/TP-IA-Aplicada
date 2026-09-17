# Contrato de configuración local

La aplicación carga `.env` en desarrollo y valida antes de aceptar solicitudes o trabajos. `.env` no se versiona; `.env.example` contiene valores locales sin secretos reales.

| Variable | Componente | Regla |
|---|---|---|
| `FLOWSIGHT_ENV` | API/worker | `development` o `test` |
| `FLOWSIGHT_DATABASE_URL` | API/worker | URL PostgreSQL; nunca se imprime completa |
| `FLOWSIGHT_API_HOST` | API | por defecto `127.0.0.1` |
| `FLOWSIGHT_API_PORT` | API/frontend | entero 1–65535 |
| `FLOWSIGHT_WORKER_ID` | worker | identificador diagnóstico no secreto |
| `FLOWSIGHT_PREVIEW_MAX_FPS` | worker | positivo y hasta 5 en el ejemplo; limita transporte, no timestamps |
| `VITE_API_BASE_URL` | frontend | URL HTTP local |
| `VITE_WS_BASE_URL` | frontend | URL WS local |

Cada error indica variable, causa (`missing`, `empty`, `invalid_format`, `unreachable`) y corrección, sin mostrar valores secretos.

Se excluyen de Git `.env`, entornos, bases, videos, pesos, outputs e informes con rutas privadas. Se versionan `.env.example`, fixtures y esquemas.

## Dependencias de inicio

PostgreSQL debe estar disponible antes de API y worker. Ambos validan configuración y conexión y se detienen antes de operar ante un error. El frontend puede iniciar sin la API y muestra su indisponibilidad sin inventar datos. El script de verificación informa el componente y la corrección correspondiente.
