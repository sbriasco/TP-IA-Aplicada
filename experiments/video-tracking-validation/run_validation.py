from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from detection import run_person_tracking, write_detections_jsonl
from detection_prep import describe_weight_approval, require_local_weights
from fragment_times import load_fragments_manifest, write_behavior_intervals_from_manual
from scene_config import load_scene_config, validate_scene_config
from overlay import render_fragment_overlays
from performance import build_performance_row, build_performance_summary_row, write_performance_csv
from spatial_events import events_from_detections, load_detections_jsonl, write_events_csv
from video_io import summarize_fragment_read

EXPERIMENT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
DEFAULT_FRAGMENTS_PATH = EXPERIMENT_ROOT / "references" / "fragments.csv"
EXAMPLE_FRAGMENTS_PATH = EXPERIMENT_ROOT / "references" / "fragments.example.csv"
DEFAULT_INVENTORY_PATH = EXPERIMENT_ROOT / "inputs" / "video-inventory.csv"
DEFAULT_SCENE_EXAMPLE_PATH = EXPERIMENT_ROOT / "config" / "scene.example.json"


def load_inventory(path: str | Path) -> list[dict[str, str]]:
    inventory_path = Path(path)
    with inventory_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_inventory_durations(path: str | Path) -> dict[str, float]:
    return {row["video_id"]: float(row["duration_seconds"]) for row in load_inventory(path)}


def load_experiment_fragments(
    fragments_path: str | Path | None = None,
    inventory_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    path = Path(fragments_path) if fragments_path else DEFAULT_FRAGMENTS_PATH
    durations: Mapping[str, float] | None = None
    if inventory_path is not None:
        durations = load_inventory_durations(inventory_path)
    return load_fragments_manifest(path, video_durations=durations)


def resolve_video_path(inventory_row: Mapping[str, str]) -> Path:
    raw_path = Path(inventory_row["path"])
    if raw_path.is_absolute():
        return raw_path
    return REPO_ROOT / raw_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experimento local de validación de videos y tracking."
    )
    parser.add_argument(
        "--fragments",
        default=str(DEFAULT_FRAGMENTS_PATH),
        help="Manifest local de fragmentos en segundos del video original.",
    )
    parser.add_argument(
        "--inventory",
        default=None,
        help="Inventario local opcional para validar intervalos contra la duración.",
    )
    parser.add_argument(
        "--scene",
        default=str(DEFAULT_SCENE_EXAMPLE_PATH),
        help="Configuración de escena JSON.",
    )
    parser.add_argument(
        "--read-first-fragment",
        action="store_true",
        help="Leer el primer fragmento del manifest sin ejecutar YOLO.",
    )
    parser.add_argument(
        "--prepare-detect",
        action="store_true",
        help="Mostrar origen, licencia y comando del peso YOLO sin descargarlo.",
    )
    parser.add_argument(
        "--weights",
        default=str(EXPERIMENT_ROOT / "weights" / "yolov8n.pt"),
        help="Ruta local del peso YOLO; no se descarga implícitamente.",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Ejecutar detección YOLO y tracking ByteTrack sobre un fragmento.",
    )
    parser.add_argument(
        "--measure-detect",
        action="store_true",
        help="Reejecutar YOLO+ByteTrack solo para medir tiempo, sin escribir detections.jsonl.",
    )
    parser.add_argument(
        "--fragment-id",
        default=None,
        help="Identificador del fragmento a procesar.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Dispositivo Ultralytics (cpu por defecto).",
    )
    parser.add_argument(
        "--session-id",
        default="session-enterexit-crossing-001",
        help="Identificador temporal de la sesión de ejecución.",
    )
    parser.add_argument(
        "--detections-out",
        default=str(EXPERIMENT_ROOT / "outputs" / "detections.jsonl"),
        help="Ruta de salida JSONL de observaciones automáticas.",
    )
    parser.add_argument(
        "--events-from-detections",
        action="store_true",
        help="Derivar eventos de zona y línea desde detections.jsonl existente.",
    )
    parser.add_argument(
        "--detections-in",
        default=str(EXPERIMENT_ROOT / "outputs" / "detections.jsonl"),
        help="JSONL de detecciones de entrada para T022.",
    )
    parser.add_argument(
        "--events-out",
        default=str(EXPERIMENT_ROOT / "outputs" / "events.csv"),
        help="CSV de eventos espaciales.",
    )
    parser.add_argument(
        "--annotate-overlays",
        action="store_true",
        help="Generar overlays locales anotados en outputs/overlays.",
    )
    parser.add_argument(
        "--overlays-out",
        default=str(EXPERIMENT_ROOT / "outputs" / "overlays"),
        help="Directorio de overlays locales.",
    )
    parser.add_argument(
        "--write-performance",
        action="store_true",
        help="Registrar performance.csv del fragmento procesado.",
    )
    parser.add_argument(
        "--performance-out",
        default=str(EXPERIMENT_ROOT / "outputs" / "performance.csv"),
        help="CSV de rendimiento por fragmento.",
    )
    parser.add_argument(
        "--write-behavior-intervals",
        action="store_true",
        help="Calcular duraciones observables desde timestamps del video en manual.csv.",
    )
    parser.add_argument(
        "--manual-in",
        default=str(EXPERIMENT_ROOT / "references" / "manual.csv"),
        help="Referencia manual con timestamps del video original.",
    )
    parser.add_argument(
        "--behavior-intervals-out",
        default=str(EXPERIMENT_ROOT / "outputs" / "behavior-intervals.csv"),
        help="CSV de duraciones de comportamiento (no usa tiempo de procesamiento).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.prepare_detect:
        print(describe_weight_approval(Path(args.weights)))
        try:
            require_local_weights(args.weights)
        except Exception as error:
            print(error)
            return 2
        return 0

    scene = validate_scene_config(load_scene_config(args.scene))
    print(f"Escena válida: {scene.get('scene_id')} video_id={scene.get('video_id')}")
    directions = scene["entry_line"]["directions"]
    print(f"A_to_B={directions['A_to_B']} B_to_A={directions['B_to_A']}")

    fragments = load_experiment_fragments(args.fragments, args.inventory)
    print(f"Fragmentos válidos: {len(fragments)}")
    for fragment in fragments:
        print(
            f"{fragment['fragment_id']} "
            f"[{fragment['start_video_seconds']}, {fragment['end_video_seconds']})"
        )

    detect_time = 0.0
    detect_frames = 0
    if args.read_first_fragment:
        if args.inventory is None:
            raise SystemExit(" --read-first-fragment requiere --inventory")
        first = fragments[0]
        inventory = {row["video_id"]: row for row in load_inventory(args.inventory)}
        video_row = inventory[first["video_id"]]
        summary = summarize_fragment_read(
            resolve_video_path(video_row),
            first,
            fps=float(video_row["fps"]),
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    detect_time = 0.0
    detect_frames = 0
    if args.detect or args.measure_detect:
        if args.inventory is None:
            raise SystemExit("--detect/--measure-detect requiere --inventory")
        fragment_id = args.fragment_id or fragments[0]["fragment_id"]
        selected = next(
            (item for item in fragments if item["fragment_id"] == fragment_id),
            None,
        )
        if selected is None:
            raise SystemExit(f"No se encontró el fragmento {fragment_id}")
        inventory = {row["video_id"]: row for row in load_inventory(args.inventory)}
        video_row = inventory[selected["video_id"]]
        observations, detect_summary = run_person_tracking(
            video_path=resolve_video_path(video_row),
            fragment=selected,
            weights_path=args.weights,
            session_id=args.session_id,
            fps=float(video_row["fps"]),
            device=args.device,
        )
        detect_time = float(detect_summary["detection_tracking_time_seconds"])
        detect_frames = int(detect_summary["frames_processed"])
        if args.detect:
            written = write_detections_jsonl(args.detections_out, observations)
            detect_summary["written"] = written
            detect_summary["detections_out"] = args.detections_out
        else:
            detect_summary["written"] = 0
            detect_summary["detections_out"] = None
        print(json.dumps(detect_summary, ensure_ascii=False, indent=2))

    if args.events_from_detections or args.annotate_overlays or args.write_performance:
        started = time.perf_counter()
        detections = load_detections_jsonl(args.detections_in)
        events = events_from_detections(detections, scene)
        if args.events_from_detections:
            written = write_events_csv(args.events_out, events)
            counts: dict[str, int] = {}
            for event in events:
                key = str(event["event_type"])
                counts[key] = counts.get(key, 0) + 1
            print(
                json.dumps(
                    {
                        "detections_in": args.detections_in,
                        "events_out": args.events_out,
                        "event_count": written,
                        "by_type": counts,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        overlay_count = 0
        if args.annotate_overlays:
            if args.inventory is None:
                raise SystemExit("--annotate-overlays requiere --inventory")
            fragment_id = args.fragment_id or (
                detections[0]["fragment_id"] if detections else fragments[0]["fragment_id"]
            )
            selected = next(
                (item for item in fragments if item["fragment_id"] == fragment_id),
                None,
            )
            if selected is None:
                raise SystemExit(f"No se encontró el fragmento {fragment_id}")
            inventory = {row["video_id"]: row for row in load_inventory(args.inventory)}
            video_row = inventory[selected["video_id"]]
            overlay_summary = render_fragment_overlays(
                video_path=resolve_video_path(video_row),
                fragment=selected,
                scene=scene,
                detections=detections,
                events=events,
                output_dir=args.overlays_out,
                fps=float(video_row["fps"]),
            )
            overlay_count = int(overlay_summary["overlay_count"])
            print(json.dumps(overlay_summary, ensure_ascii=False, indent=2))
        elapsed = time.perf_counter() - started
        if args.write_performance:
            if args.inventory is None:
                raise SystemExit("--write-performance requiere --inventory")
            fragment_id = args.fragment_id or (
                detections[0]["fragment_id"] if detections else fragments[0]["fragment_id"]
            )
            selected = next(
                (item for item in fragments if item["fragment_id"] == fragment_id),
                None,
            )
            if selected is None:
                raise SystemExit(f"No se encontró el fragmento {fragment_id}")
            inventory = {row["video_id"]: row for row in load_inventory(args.inventory)}
            video_row = inventory[selected["video_id"]]
            duration = (
                float(selected["end_video_seconds"]) - float(selected["start_video_seconds"])
            )
            frames_processed = detect_frames or overlay_count or len(
                {int(item["frame_index"]) for item in detections}
            )
            total = detect_time + elapsed
            row = build_performance_row(
                session_id=args.session_id,
                video_id=str(selected["video_id"]),
                fragment_id=str(selected["fragment_id"]),
                device=args.device,
                video_duration_seconds=duration,
                frames_processed=frames_processed,
                processing_time_seconds=total,
                detection_tracking_time_seconds=detect_time,
                postprocess_time_seconds=elapsed,
                notes=(
                    "processing_time_seconds es el total operativo "
                    "(detección/tracking + eventos/overlays). "
                    "No sustituye timestamps de comportamiento del video. "
                    "detections.jsonl y events.csv no se reescribieron en la medición T025."
                ),
            )
            write_performance_csv(args.performance_out, [row])
            print(json.dumps(row, ensure_ascii=False, indent=2))

    if args.write_behavior_intervals:
        written = write_behavior_intervals_from_manual(
            args.manual_in,
            args.behavior_intervals_out,
        )
        print(
            json.dumps(
                {
                    "manual_in": args.manual_in,
                    "behavior_intervals_out": args.behavior_intervals_out,
                    "rows": written,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
