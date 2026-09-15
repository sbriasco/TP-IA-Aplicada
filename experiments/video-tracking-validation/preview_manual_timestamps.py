"""Visor local de timestamps del video original. No usa detecciones ni overlays."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mostrar el video original con segundos del video, sin resultados automáticos."
    )
    parser.add_argument(
        "--video",
        default=str(REPO_ROOT / "Videos" / "EnterExitCrossingPaths1front.mpg"),
    )
    parser.add_argument("--start", type=float, default=8.0)
    parser.add_argument("--end", type=float, default=15.32)
    parser.add_argument("--fps", type=float, default=25.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    capture = cv2.VideoCapture(args.video)
    if not capture.isOpened():
        raise SystemExit(f"No se pudo abrir {args.video}")
    fps = args.fps
    frames: list = []
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        timestamp = frame_index / fps
        if args.start <= timestamp < args.end:
            frames.append((frame_index, timestamp, frame.copy()))
        if timestamp >= args.end:
            break
        frame_index += 1
    capture.release()
    if not frames:
        raise SystemExit("No hay frames en el intervalo del fragmento.")

    paused = False
    position = 0
    window = "manual-timestamps"
    print("Espacio: pausa | E: frame siguiente | D: frame anterior | Q: salir")
    print(f"Fragmento [{args.start}, {args.end}) s. relative = video_timestamp - {args.start}")
    while True:
        frame_index, video_timestamp, frame = frames[position]
        view = frame.copy()
        relative = video_timestamp - args.start
        label = f"video={video_timestamp:.2f}s  relative={relative:.2f}s  frame={frame_index}"
        cv2.putText(view, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.imshow(window, view)
        delay = 0 if paused else max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key in {ord("q"), 27}:
            break
        if key == ord(" "):
            paused = not paused
        if key in {ord("e"), ord("E")} or not paused:
            position = min(position + 1, len(frames) - 1)
            if position == len(frames) - 1:
                paused = True
        if key in {ord("d"), ord("D")}:
            paused = True
            position = max(position - 1, 0)
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
