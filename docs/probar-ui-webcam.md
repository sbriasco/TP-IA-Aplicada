# Probar las mejoras de interfaz y pausa de webcam

Rama para pruebas: `fix/ui-y-pausa-webcam`. Incluye preparación de video/webcam, editor de escenas, reportes y pausa/reanudación del análisis en vivo.

## Actualizar una instalación existente

Desde la raíz del repositorio, con los cambios propios guardados:

```powershell
git fetch origin
git switch fix/ui-y-pausa-webcam
git pull --ff-only
npm --prefix frontend ci
& scripts\update-database.ps1
```

El script de migración carga el `.env` de la raíz y actualiza la base elegida hasta `0012_live_manual_pause`. Conservar el `.env` propio; no copiar credenciales de otro equipo. Para una instalación nueva, seguir primero los requisitos del [README](../README.md).

Reiniciar los procesos anteriores y abrir tres terminales desde la raíz:

```powershell
# Terminal 1
& scripts\start-api.ps1
```

```powershell
# Terminal 2
& scripts\start-worker.ps1
```

```powershell
# Terminal 3
Set-Location frontend
npm run dev
```

Abrir http://127.0.0.1:5173. La webcam debe estar conectada al equipo que ejecuta el worker. El identificador y la credencial local se generan automáticamente.

## Recorrido de prueba

1. **Video:** abrir o cargar un video, elegir configuración, procesar y consultar resultados. Revisar selector de zona, gráfico, eventos y chat según disponibilidad.
2. **Editor:** comprobar colores distintos por tipo de área; guardar sin modificar no debe crear una versión. Modificar una geometría y guardar sí debe crearla. Si existen resultados, «Continuar a resultados» debe abrirlos.
3. **Etiquetas:** preparar una webcam con «Entradas / Salidas», confirmar el sentido de la flecha y comprobar las mismas etiquetas en editor, monitoreo y reporte.
4. **Pausa:** iniciar la captura, pausar y esperar «Análisis pausado». Recargar la página: debe seguir pausada y conservar los conteos. Retomar, confirmar un encuadre nuevo y continuar en la misma sesión. Repetir y detener desde la pausa.
5. **Reporte:** verificar la pausa en el diagnóstico, el tiempo sin cobertura y los conteos conservados. El intervalo pausado no agrega estadía ni cruces.
6. **Temas y tamaños:** alternar claro/oscuro, revisar escritorio y móvil. Monitoreo y reportes deben usar los colores habituales de FlowSight.

Para informar un problema, anotar pantalla, pasos, resultado esperado/obtenido y si fue video o webcam. Adjuntar una captura sin credenciales cuando ayude a reproducirlo.

## Pendientes conocidos

Esta publicación conserva el estado actual para revisión; todavía no incorpora las correcciones propuestas por la auditoría de conteo:

- Una trayectoria que cae exactamente sobre la línea puede perder el cruce.
- El contador de archivos puede conservar continuidad de un ID tras una ausencia.
- Algunos cruces del video permanecen pendientes hasta otro cruce o el final del archivo.

Las pruebas sintéticas no certifican precisión ni latencia de una cámara física. Registrar por separado los resultados del ensayo real.
