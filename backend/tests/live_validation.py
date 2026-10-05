"""Wall-clock capture/sampling soak. Reports limits, never claims hardware acceptance.

Optional --process-id monitors API/worker RSS too; run with an active live session.
No image, video, credentials or process command line is written to the report.
"""

import argparse
import ctypes
import json
import os
import statistics
import time
from collections import deque
from ctypes import wintypes
from pathlib import Path

from flowsight.capture.contracts import CaptureSettings
from flowsight.capture.fake import FakeCaptureOptions
from flowsight.capture.process import ProcessFrameSource
from flowsight.vision.live_sampling import LivePositionSampler


def working_set(pid):
    class Counters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak",
                "rss",
                "quota_peak",
                "quota",
                "nonpaged_peak",
                "nonpaged",
                "pagefile",
                "pagefile_peak",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    handle = kernel.OpenProcess(0x0410, False, pid)
    if not handle:
        return None
    try:
        counters = Counters()
        counters.size = ctypes.sizeof(counters)
        return (
            counters.rss
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.size)
            else None
        )
    finally:
        kernel.CloseHandle(handle)


def disk_size(directory):
    if directory is None:
        return None
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["Overload", "Stability"], required=True)
    parser.add_argument("--duration", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--process-id", type=int, action="append", default=[])
    parser.add_argument("--storage-directory", type=Path)
    args = parser.parse_args()
    if args.duration < 1 or args.duration > 86400:
        parser.error("duration must be between 1 and 86400 seconds")
    os.environ["FLOWSIGHT_ENV"] = "test"
    source = ProcessFrameSource(
        CaptureSettings(0, "fake", 320, 240), fake_options=FakeCaptureOptions(frame_rate=30)
    )
    sampler = LivePositionSampler()
    baseline, recent = [], deque(maxlen=120)
    initial_disk = disk_size(args.storage_directory)
    sequence = analyzed = dropped = pending_peak = 0
    ages = deque(maxlen=2000)
    source.start()
    started = time.monotonic()
    next_sample = started
    pids = [os.getpid(), source._process.pid, *args.process_id]
    try:
        while time.monotonic() - started < args.duration:
            frame = source.read_latest(sequence, 0.5)
            if frame is None:
                continue
            dropped += max(0, frame.sequence - sequence - 1)
            sequence = frame.sequence
            analyzed += 1
            for track in range(20):
                sampler.observe(
                    segment_index=0,
                    track_id=track,
                    sequence=sequence,
                    timestamp_s=frame.timestamp_seconds,
                    foot=(0.5, 0.5),
                )
            sampler.drain_changes()
            ages.append((time.monotonic_ns() - frame.captured_monotonic_ns) / 1e6)
            pending_peak = max(pending_peak, source.pending_count)
            if args.scenario == "Overload" and time.monotonic() - started < args.duration * 0.8:
                time.sleep(0.1)  # 30 fps capture versus at most 10 analyses per second.
            if time.monotonic() >= next_sample:
                point = {
                    "seconds": round(time.monotonic() - started, 2),
                    "rss_bytes": [working_set(pid) for pid in pids],
                    "samples": len(sampler.samples),
                }
                recent.append(point)
                if 600 <= point["seconds"] < 1200:
                    baseline.append(point)
                next_sample = time.monotonic() + 5
        elapsed = time.monotonic() - started
    finally:
        source.stop()
    final_disk = disk_size(args.storage_directory)
    ordered = sorted(ages)
    growth = []
    for index in range(len(pids)):
        before = [
            point["rss_bytes"][index] for point in baseline if point["rss_bytes"][index] is not None
        ]
        after = [
            point["rss_bytes"][index] for point in recent if point["rss_bytes"][index] is not None
        ]
        growth.append(
            statistics.median(after) / statistics.median(before) - 1 if before and after else None
        )
    report = {
        "scenario": args.scenario,
        "duration_seconds": elapsed,
        "scope": "capture process and sampler; optional external process RSS only",
        "physical_camera": False,
        "full_application_acceptance": "not_measured",
        "analyzed": analyzed,
        "dropped": dropped,
        "pending_peak": pending_peak,
        "sample_count": len(sampler.samples),
        "capacity": sampler.capacity,
        "recent_capture_to_read_p95_ms": ordered[int((len(ordered) - 1) * 0.95)]
        if ordered
        else None,
        "capture_to_first_paint_p95_ms": None,
        "rss_growth_after_warmup": growth,
        "recent_resource_samples": list(recent),
        "storage_growth_bytes": final_disk - initial_disk if initial_disk is not None else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "recent_resource_samples"}
        )
    )
    if pending_peak > 1 or len(sampler.samples) > 20000 or source.running:
        raise SystemExit("Capture/sampler bound violated")


if __name__ == "__main__":
    main()
