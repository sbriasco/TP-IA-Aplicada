# Verificación integral de la base

Fecha: 16 de septiembre de 2026. Equipo CPU local con Windows, Python 3.11.16, Node.js 22.20.0 y PostgreSQL 17.11.

## Recorrido ejecutado

- `scripts/check-environment.ps1`: entorno `ready`, configuración y PostgreSQL disponibles.
- Alembic `upgrade head` y `check`: esquema aplicado sin operaciones nuevas pendientes.
- Flujo sintético: tres ejecuciones consecutivas exitosas, con mediana de 1471,14 ms.
- API `/health`: tres solicitudes contra una API iniciada localmente, con mediana de 2,41 ms.
- Backend: `pytest -q`, 43 pruebas aprobadas; `ruff check` y `ruff format --check`, aprobados.
- Frontend: `npm run lint`, `npm test` y `npm run build`, aprobados; 4 pruebas Vitest y build Vite exitoso.
- Navegador: `npm run test:e2e`, 4 pruebas Playwright aprobadas contra API, worker y PostgreSQL
  reales; se verificaron preview JPEG, estado terminal, cliente lento, desconexión, reconexión
  tardía y trabajo inexistente. Los selectores se
  contrastaron previamente con el snapshot de accesibilidad del MCP de Playwright.
- Los comandos locales que usa CI quedaron aprobados. La ejecución remota de GitHub Actions se comprobará al publicar el pull request.

## Hallazgos y correcciones

El recorrido detectó que faltaban `scripts/start-api.ps1` y `scripts/start-worker.ps1`, aunque estaban nombrados en el quickstart. Se agregaron ambos scripts y se alineó el README. También se corrigió la medición de `/health` para medir solicitudes contra una API ya iniciada, sin incluir el arranque de Python.

La convergencia posterior conectó worker y API mediante frames persistidos, incorporó una preview
JPEG versionada de 320×180 y hasta 100 KiB, y agregó el recorrido real de navegador. También se
impidió que la API informe disponibilidad cuando PostgreSQL no responde. En Windows, el runner E2E
inicia directamente los CLI de Vite y Playwright para cerrar sus procesos sin dejar servicios
locales activos.

El worker E2E resuelve `Scripts/python.exe` en Windows y `bin/python` en Linux; ambas rutas están
cubiertas por pruebas unitarias. La ejecución real del job E2E en Ubuntu permanece pendiente de la
primera corrida de GitHub Actions del PR, porque este equipo no dispone de WSL accesible ni Docker
Linux. Por esa razón T020 continúa abierta hasta obtener esa evidencia remota.

## Límites

La evidencia corresponde al flujo sintético y no demuestra rendimiento de video. La PC RTX 5080 no estuvo disponible y permanece `not_evaluated`. El informe completo del equipo queda en `.verification/`, excluido de Git; solo se versiona el resumen anonimizado.

## Trazabilidad en Azure Boards

Consulta de solo lectura mediante el MCP de Azure DevOps el 16 de septiembre de 2026. No se modificaron estados.

| Tipo | ID | Título | Padre |
|---|---:|---|---:|
| Feature | 6 | Entorno local reproducible y arquitectura base | 2 |
| User Story | 29 | Reproducir el entorno local | 6 |
| User Story | 30 | Persistir sesiones y trabajos sintéticos | 6 |
| User Story | 31 | Mantener trazabilidad y aislamiento por sesión | 6 |
| User Story | 32 | Previsualizar sin bloquear el trabajo | 6 |
| User Story | 33 | Validar equipos de referencia | 6 |
| Task | 34 | Preparar estructura, dependencias y configuración local | 29 |
| Task | 35 | Verificar reproducción del entorno desde un clon limpio | 29 |
| Task | 36 | Crear esquema, migraciones y datos sintéticos | 30 |
| Task | 37 | Implementar API y ciclo de vida de trabajos | 30 |
| Task | 38 | Implementar trazabilidad y aislamiento sintético | 31 |
| Task | 39 | Implementar previsualización y supervisión mínima | 32 |
| Task | 40 | Registrar evidencia reproducible en CPU y GPU | 33 |

La consulta devolvió todos los elementos en estado `New`. La actualización de estados se realizará como una acción separada sobre Azure Boards.
