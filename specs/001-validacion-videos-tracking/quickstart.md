# Guía de validación posterior

Esta guía describe cómo ejecutar el experimento después de aprobar su implementación.
No se ejecutó durante la planificación y no instala dependencias.

## Prerrequisitos

- Videos seleccionados disponibles en una ruta local y no versionados en Git.
- Python 3.11.x y las versiones de visión fijadas después de la validación de compatibilidad.
- Pesos del modelo disponibles localmente y con licencia documentada.
- Una escena JSON preconfigurada con una zona frontal y una línea de entrada.
- Una referencia manual CSV/JSON para los fragmentos elegidos.
- Una herramienta local de visualización anotada para revisar detecciones, tracks y eventos;
  no es una interfaz web.

La ubicación exacta de los videos debe ser indicada por el equipo al preparar la ejecución;
este plan no inspecciona ni inventa sus características.

## Preparación

1. Registrar cada video en el inventario con `video_id`, ruta, metadatos y condiciones de uso.
2. Seleccionar fragmentos por intervalo `[start_video_seconds, end_video_seconds)` del
  video original, en segundos, y documentar razón y casos cubiertos. Convertir cada
  timestamp original a tiempo relativo con `relative_seconds = video_timestamp_seconds -
  start_video_seconds`.
3. Configurar manualmente la zona frontal y la línea de entrada sobre un frame de referencia.
  Validar dimensiones positivas, puntos dentro del frame, polígono de al menos tres puntos
  con área no nula y línea de dos puntos distintos.
4. Preparar observaciones manuales de personas, permanencias, cruces, oclusiones y casos
  cubiertos. Revisar la visualización local y registrar correspondencias y errores en
  `outputs/review.csv`; no usar una asociación automática. Ampliar la muestra si faltan
  cruces u oclusiones.
5. Confirmar el equipo/dispositivo de la ejecución y la versión candidata usada.

## Ejecución posterior

El comando exacto se definirá al implementar el script. La forma prevista es:

```text
python experiments/video-tracking-validation/run_validation.py \
  --config <ruta-a-scene.json> \
  --input <ruta-a-video> \
  --manual-reference <ruta-a-referencia>
```

La ejecución debe producir detecciones y tracks, eventos de zona/línea, rendimiento por
fragmento y un informe. Las métricas de comportamiento usan timestamps del video; el tiempo
de procesamiento solo describe rendimiento operativo. La línea debe evaluarse en ambos
sentidos, A→B y B→A, según el mapeo declarado a entrada/salida.

## Verificaciones por historia

- **US1 / #17**: revisar que cada video y fragmento tenga identificación, intervalo, motivo,
  casos cubiertos y limitaciones.
- **US2 / #18**: comparar cruces por ocurrencia observable; clasificar coincidencias,
omisiones, espurios y duplicados; evaluar continuidad de tracks por separado.
- **US3 / #19**: comprobar detecciones, IDs temporales, zona frontal, línea de entrada,
dirección observable, oclusiones, pérdidas y oscilaciones.
- **US4 / #20**: revisar rendimiento por fragmento, timestamps de comportamiento, cobertura
directa de métricas y estado de viabilidad por medición.

## Criterio de cierre

El informe debe indicar para cada medición si es viable, viable con ajustes, no viable con
el material o configuración evaluados, o no evaluable por falta de evidencia. No se deben
inventar resultados, umbrales ni características de los videos. Una conclusión negativa
respaldada por evidencia completa el experimento.
