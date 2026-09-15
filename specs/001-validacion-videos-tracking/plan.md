# Implementation Plan: Validación técnica de videos y tracking

**Branch**: `001-validacion-videos-tracking` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)

**Azure Boards**: Feature #4; User Stories #17, #18, #19 y #20

**Input**: Feature specification from `specs/001-validacion-videos-tracking/spec.md`

## Summary

Determinar, mediante un experimento local reproducible y acotado, qué mediciones
comerciales pueden evaluarse con los videos seleccionados, una zona frontal y una línea
de entrada preconfiguradas. El experimento usará un script Python, YOLO y ByteTrack,
registrará resultados por fragmento y producirá un informe de viabilidad. No construirá
componentes del MVP ni persistirá resultados en PostgreSQL.

## Technical Context

**Language/Version**: Python 3.11.x propuesta; validar en Windows y en CPU/GPU antes de fijar.

**Primary Dependencies**: Ultralytics YOLO 8.3.x, PyTorch 2.7.x y OpenCV 4.10.x como
versiones candidatas. La documentación oficial de [Ultralytics tracking](https://docs.ultralytics.com/modes/track/)
documenta ByteTrack; [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/)
publica combinaciones de instalación; [OpenCV 4.10.0](https://docs.opencv.org/4.10.0/)
documenta video I/O y análisis de video. Estas fuentes no validan nuestra combinación
concreta: hay que comprobar Python/PyTorch/CUDA/GPU, pesos y licencias antes de fijar.

**Storage**: Archivos locales: videos de entrada fuera de Git, configuraciones JSON,
referencias manuales CSV/JSON, resultados JSONL/CSV e informe Markdown. PostgreSQL no
participa en este experimento.

**Testing**: Pruebas manuales y scripts de validación sobre fragmentos; pytest queda
propuesto para formatos y reglas puras si se implementa junto con el experimento. No se
ejecutan pruebas durante esta etapa de planificación.

**Target Platform**: Windows local; registrar por fragmento el equipo/dispositivo y
considerar una ejecución de referencia en CPU y otra en la RTX 5080 cuando estén disponibles.

**Project Type**: Experimento local de línea de comandos y análisis offline de archivos.

**Performance Goals**: Medir por fragmento duración según el video, frames procesados,
tiempo de procesamiento y equipo/dispositivo. Comparar esos valores como rendimiento
operativo, sin usarlos como timestamps de permanencia o comportamiento.

Cada fragmento se recibe mediante `start_video_seconds` y `end_video_seconds`, ambos en
segundos del video original, con intervalo semiabierto `[inicio, fin)`. El manifest de
fragmentos es la entrada única del experimento. Para un frame con timestamp original
`video_timestamp_seconds`, el tiempo relativo es `relative_seconds = video_timestamp_seconds
- start_video_seconds`; no se redondea a frames para calcular permanencia.

**Constraints**: No inventar umbrales de precisión ni velocidad. Usar escenas manuales
preconfiguradas, separar continuidad de tracks y cruces por ocurrencia, conservar videos
y pesos fuera de Git, y no exigir implementar todas las métricas del MVP. La comparación
se hará mediante revisión humana asistida por una visualización local anotada; no habrá
interfaz web ni algoritmo de asociación automático.

**Scale/Scope**: Videos ya seleccionados por el equipo y fragmentos representativos
documentados; muestra manual acotada que se amplía si faltan cruces u oclusiones. No se
construyen frontend, API, chat, editor visual ni persistencia completa.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passes:

- El procesamiento y los archivos de evidencia son locales; los videos, pesos y datos
generados permanecen fuera de Git.
- La separación se respeta porque el experimento mantiene lectura de video, detección y
tracking, reglas de evaluación, métricas y reporte como responsabilidades diferenciadas,
sin crear la API ni la presentación del producto.
- Los timestamps de comportamiento se mantienen separados de las mediciones de rendimiento
y cada resultado se referencia a video, fragmento, configuración y sesión de prueba.
- Los IDs se tratan como temporales; no se infiere identidad real ni continuidad entre cámaras.
- Las conclusiones se expresan como viable, viable con ajustes, no viable con el material o
configuración evaluados, o no evaluable por falta de evidencia.
- La evidencia y las decisiones asistidas por IA se documentan en los artefactos del plan y
del experimento.

No se detectan violaciones que requieran Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-validacion-videos-tracking/
├── plan.md              # Este plan
├── research.md          # Decisiones y validaciones técnicas
├── data-model.md        # Entidades y estados del experimento
├── quickstart.md        # Guía de ejecución posterior
├── contracts/           # Formatos de configuración, referencia y resultados
└── tasks.md             # Se generará después con /speckit-tasks
```

### Source Code (repository root)

```text
experiments/video-tracking-validation/
├── README.md                 # Propósito, alcance y limitaciones
├── requirements.txt          # Versiones candidatas, a fijar tras validación
├── run_validation.py         # Entrada del experimento; no se crea en esta etapa
├── config/
│   └── scene.example.json    # Zona frontal y línea de entrada de ejemplo
├── inputs/                   # Rutas locales ignoradas; no contiene videos versionados
├── references/
│   ├── fragments.example.csv # Plantilla sintética versionada
│   ├── fragments.csv         # Manifest local de ejecución, excluido de Git
│   └── manual.example.csv     # Observaciones manuales y revisión
├── outputs/                  # Resultados locales ignorados
│   ├── detections.jsonl
│   ├── events.csv
│   ├── performance.csv
│   ├── review.csv
│   ├── overlays/              # Visualización local para revisión humana
│   └── viability-report.md
└── tests/                    # Validaciones del experimento, si se implementan
```

**Structure Decision**: Se propone un experimento aislado bajo
`experiments/video-tracking-validation/`, con entradas y salidas locales excluidas de
Git. Sus formatos contractuales se documentan en `contracts/`; los documentos de diseño
permanecen en esta Feature de Spec Kit. La implementación de esos archivos se difiere
hasta una aprobación y un paso posterior; este plan no crea código.

## Complexity Tracking

No aplica: la propuesta usa un único experimento local, archivos y escenas preconfiguradas;
no agrega servicios, capas de aplicación ni persistencia compartida.
