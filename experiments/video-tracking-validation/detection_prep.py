from __future__ import annotations

from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHTS_PATH = EXPERIMENT_ROOT / "weights" / "yolov8n.pt"
DEFAULT_TRACKER_PATH = (
    EXPERIMENT_ROOT
    / ".venv"
    / "Lib"
    / "site-packages"
    / "ultralytics"
    / "cfg"
    / "trackers"
    / "bytetrack.yaml"
)

PROPOSED_WEIGHTS = {
    "name": "yolov8n.pt",
    "approximate_size": "6.53 MB",
    "origin": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt",
    "docs": "https://docs.ultralytics.com/models/yolov8/",
    "license": "AGPL-3.0 (alternativa Enterprise de Ultralytics para uso comercial)",
    "class_filter": "person (COCO class 0)",
    "tracker": "ByteTrack vía ultralytics/cfg/trackers/bytetrack.yaml",
}


class WeightsNotApprovedError(RuntimeError):
    """Raised when local YOLO weights are missing or download was not approved."""


def describe_weight_approval(weights_path: Path | None = None) -> str:
    path = weights_path or DEFAULT_WEIGHTS_PATH
    command = (
        "Invoke-WebRequest -Uri "
        f"'{PROPOSED_WEIGHTS['origin']}' "
        f"-OutFile '{path}'"
    )
    yolo_command = (
        f'"{EXPERIMENT_ROOT / ".venv" / "Scripts" / "python.exe"}" '
        "-c \"from ultralytics import YOLO; YOLO(r'"
        f"{path}"
        "')\""
    )
    return "\n".join(
        [
            f"nombre: {PROPOSED_WEIGHTS['name']}",
            f"tamaño aproximado: {PROPOSED_WEIGHTS['approximate_size']}",
            f"origen: {PROPOSED_WEIGHTS['origin']}",
            f"documentación: {PROPOSED_WEIGHTS['docs']}",
            f"licencia: {PROPOSED_WEIGHTS['license']}",
            f"tracker: {PROPOSED_WEIGHTS['tracker']}",
            f"destino local: {path}",
            "comando de descarga (solo tras aprobación):",
            command,
            "comando que Ultralytics ejecutaría al cargar el peso (descarga implícita si falta el archivo; no usarlo todavía):",
            yolo_command,
        ]
    )


def require_local_weights(path: str | Path) -> Path:
    weights_path = Path(path)
    if not weights_path.is_file():
        raise WeightsNotApprovedError(
            "Los pesos YOLO no están en disco y no se descargarán sin aprobación. "
            + describe_weight_approval(weights_path)
        )
    return weights_path
