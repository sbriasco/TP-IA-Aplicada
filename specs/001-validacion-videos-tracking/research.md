# Investigación y decisiones: validación de videos y tracking

## Alcance de la investigación

Este plan cubre un experimento local acotado para la Feature #4 y sus User Stories #17 a
#20. No se inspeccionaron los videos ni se ejecutó código; las características del material
son entradas que deberán registrarse durante la prueba.

## Decisiones

### Runtime local

- **Decisión**: proponer Python 3.11.x sobre Windows como runtime inicial.
- **Rationale**: la [documentación oficial de Python 3.11](https://docs.python.org/3.11/)
documenta la versión y su instalación de módulos, y coincide con el entorno Python acordado.
Permite un script local reproducible y deja abierta la ejecución en CPU y GPU.
- **Alternativas consideradas**: Python 3.12.x; se deja como alternativa si la matriz de
PyTorch y la GPU de referencia lo exige, pero no se adopta antes de validarla.

### Detección y tracking

- **Decisión**: iniciar con Ultralytics YOLO 8.3.x, PyTorch 2.7.x, OpenCV 4.10.x y
ByteTrack, como versiones candidatas y no como dependencias aprobadas.
- **Rationale**: la [documentación oficial de tracking de Ultralytics](https://docs.ultralytics.com/modes/track/)
documenta tracking persistente y ByteTrack; la [página oficial de versiones de PyTorch](https://pytorch.org/get-started/previous-versions/)
documenta combinaciones de instalación; la [documentación oficial de OpenCV 4.10.0](https://docs.opencv.org/4.10.0/)
incluye video I/O y análisis de video. Esto justifica las capacidades y los candidatos,
no la compatibilidad final de nuestro entorno.
- **Alternativas consideradas**: BoT-SORT, solo si los resultados de ByteTrack justifican
compararlo; no se agrega otro tracker por anticipado.
- **Validación pendiente**: compatibilidad real con Windows, CPU, RTX 5080, CUDA, pesos,
licencias y el material seleccionado. Las versiones se deben fijar después de esa prueba.

La compatibilidad documentada es la existencia de documentación oficial para Python 3.11,
las combinaciones publicadas de PyTorch, la API de video de OpenCV 4.10.0 y ByteTrack en
Ultralytics. La compatibilidad pendiente es la ejecución efectiva de esa combinación en
los equipos del grupo, con los pesos seleccionados y los videos reales. No se instala nada
durante la planificación.

### Fragmentos y tiempos

- **Decisión**: recibir un manifest CSV/JSON con `start_video_seconds` y
	`end_video_seconds`, en segundos del video original, usando `[inicio, fin)`.
- **Rationale**: hace explícitos los límites y evita confundir tiempo relativo con timestamp
	original. Para cada frame, `relative_seconds = video_timestamp_seconds -
	start_video_seconds`.
- **Validación pendiente**: comprobar que el lector respeta los límites y documentar si el
	video solo permite aproximarlos por frame.

### Escenas de evaluación

- **Decisión**: usar una configuración manual local con una zona frontal y una línea de
entrada, sin construir el editor visual.
- **Rationale**: permite validar detección, paso y cruces sin duplicar el componente del MVP.
- **Alternativas consideradas**: esperar al editor visual; se descarta para esta validación
porque aumentaría el alcance y no es necesario para probar la hipótesis técnica.

### Comparación con referencia manual

- **Decisión**: documentar cantidad observada y casos cubiertos, ampliar la muestra si faltan
cruces u oclusiones, comparar cruces por ocurrencia observable y evaluar continuidad de tracks
por separado.
- **Rationale**: evita confundir cambios de ID con duplicados y evita conclusiones sobre casos
que no aparecen en la muestra.
- **Alternativas consideradas**: exigir un tamaño numérico fijo o comparar solo por `track_id`;
se descartan porque todavía no hay evidencia para fijar umbrales ni porque un ID temporal no
representa identidad real.

La revisión será humana y asistida por una visualización local de detecciones, tracks y
eventos. El revisor registrará correspondencias y errores en `outputs/review.csv`; no se
construirá una interfaz web ni un algoritmo automático de asociación. Solo se comparará la
muestra manual revisada: la ausencia de una anotación fuera de esa muestra no es un resultado
espurio.

### Cruces y configuración geométrica

- **Decisión**: evaluar ambos sentidos de la línea, de A hacia B y de B hacia A. La escena
	declarará explícitamente cuál sentido se interpreta como `entry` y cuál como `exit`; si no
	puede observarse, será `unknown`.
- **Validación mínima**: dimensiones positivas del frame; puntos dentro del frame; polígono
	con al menos tres puntos distintos y área no nula; línea con dos puntos distintos y
	longitud no nula.
- **Rationale**: una configuración inválida no debe producir conclusiones sobre eventos.

### Rendimiento y timestamps

- **Decisión**: registrar por fragmento duración según el video, frames procesados, tiempo de
procesamiento y equipo/dispositivo, con resumen global opcional.
- **Rationale**: conserva trazabilidad de rendimiento sin mezclarla con timestamps de
permanencia o comportamiento, que siempre provienen del video.
- **Alternativas consideradas**: una única media global; se descarta porque ocultaría
variaciones entre fragmentos o equipos.

### Informe de viabilidad

- **Decisión**: usar por medición los estados `viable`, `viable con ajustes`, `no viable con
el material o configuración evaluados` y `no evaluable por falta de evidencia`.
- **Rationale**: una conclusión negativa respaldada por evidencia completa la validación y no
obliga a implementar una capacidad que el material no soporte.
- **Alternativas consideradas**: declarar éxito solo si todas las métricas del MVP funcionan;
se descarta porque el experimento no debe implementar todas las métricas ni ocultar límites
del material.

## Validaciones técnicas pendientes

1. Comprobar la matriz de versiones, GPU/CPU, CUDA y licencias sin instalar nada durante
esta fase de planificación.
2. Inspeccionar los videos seleccionados al iniciar la prueba y documentar resolución,
duración, perspectiva, entradas, frentes, circulación y oclusiones reales.
3. Medir detecciones, continuidad, pérdidas, oclusiones, duplicados y cruces contra la
referencia manual.
4. Determinar qué métricas se pueden comprobar directamente con la zona y línea disponibles;
las demás deben quedar como no evaluables o pendientes con evidencia.
5. Registrar cualquier ajuste de configuración o decisión técnica en el informe y en las
decisiones del proyecto.
