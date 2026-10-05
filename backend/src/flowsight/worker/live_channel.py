"""A background sender owns networking; inference only replaces one RAM message."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import threading
import time
import uuid
from datetime import UTC, datetime

from websockets.asyncio.client import connect

from flowsight.capture.contracts import CaptureError, CaptureSettings
from flowsight.capture.process import ProcessFrameSource
from flowsight.db.models import WorkerMachine
from flowsight.vision.overlay import render_overlay_jpeg

logger = logging.getLogger("flowsight.capture")


class WorkerLiveChannel:
    def __init__(self, settings, factory, lease, *, clock=time.monotonic) -> None:
        self.settings, self.factory, self.lease = settings, factory, lease
        self.clock = clock
        self._pending: tuple[float, dict] | None = None
        self._lock = threading.Lock()
        self._probe_lock = threading.Lock()
        self._stop = threading.Event()
        self._loop = None
        self._changed = None
        self._socket = None
        self._probe_source = None
        self._thread = threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True)

    @property
    def pending_message(self) -> dict | None:
        with self._lock:
            if self._pending is None:
                return None
            timestamp, message = self._pending
            if self.clock() - timestamp > 10:
                self._pending = None
                return None
            return message

    @property
    def pending_count(self) -> int:
        return int(self.pending_message is not None)

    def publish(self, message: dict) -> None:
        with self._lock:
            self._pending = (self.clock(), message)
        if self._loop is not None and self._changed is not None:
            self._loop.call_soon_threadsafe(self._changed.set)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._probe_source is not None:
            self._probe_source.stop()
        if self._loop is not None and self._socket is not None:
            asyncio.run_coroutine_threadsafe(self._socket.close(), self._loop)
        if self._thread.ident is not None:
            self._thread.join(3)
        with self._lock:
            self._pending = None

    async def _send_updates(self, socket, send_lock):
        last_message = None
        while not self._stop.is_set():
            message = self.pending_message
            if message is not None and message is not last_message:
                raw = json.dumps(message, allow_nan=False)
                if len(raw.encode()) <= 1048576:
                    async with send_lock:
                        await asyncio.wait_for(socket.send(raw), 0.5)
                last_message = message
            self._changed.clear()
            try:
                await asyncio.wait_for(self._changed.wait(), 0.2)
            except TimeoutError:
                pass

    async def _run(self):
        self._loop = asyncio.get_running_loop()
        self._changed = asyncio.Event()
        delay_index = 0
        while not self._stop.is_set():
            sender = None
            receiver = None
            probe_tasks = set()
            try:
                url = (
                    f"ws://127.0.0.1:{self.settings.api_port}/ws/internal/live/"
                    f"{self.settings.machine_id}"
                )
                async with connect(
                    url,
                    additional_headers={
                        "Authorization": "Bearer "
                        + self.settings.live_channel_token.get_secret_value(),
                        "X-FlowSight-Worker": self.settings.worker_id,
                        "X-FlowSight-Owner": str(self.lease.owner_epoch),
                    },
                    proxy=None,
                    open_timeout=2,
                    close_timeout=0.5,
                    max_size=1048576,
                    max_queue=1,
                ) as socket:
                    self._socket = socket
                    send_lock = asyncio.Lock()
                    sender = asyncio.create_task(self._send_updates(socket, send_lock))
                    receiver = asyncio.create_task(
                        self._receive_requests(socket, send_lock, probe_tasks)
                    )
                    delay_index = 0
                    done, _ = await asyncio.wait(
                        {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
            except Exception:
                # No credential, camera data or frame is logged. Reconnect does not stop capture.
                pass
            finally:
                self._socket = None
                if sender is not None:
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
                if receiver is not None:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
                for task in probe_tasks:
                    task.cancel()
                await asyncio.gather(*probe_tasks, return_exceptions=True)
            delay = (1, 2, 5)[min(delay_index, 2)]
            delay_index += 1
            until = time.monotonic() + delay
            while not self._stop.is_set() and time.monotonic() < until:
                await asyncio.sleep(0.1)

    async def _receive_requests(self, socket, send_lock, probe_tasks):
        async for raw in socket:
            message = json.loads(raw)
            if message.get("type") == "capture.probe" and len(probe_tasks) < 8:
                task = asyncio.create_task(self._answer_probe(socket, send_lock, message))
                probe_tasks.add(task)

                def finished(task):
                    probe_tasks.discard(task)
                    if not task.cancelled():
                        task.exception()

                task.add_done_callback(finished)

    async def _answer_probe(self, socket, send_lock, message):
        started = time.monotonic()
        try:
            result = await asyncio.to_thread(self._probe, message)
        except Exception as error:
            result = {"error": getattr(error, "code", "device_unavailable")}
            logger.info(
                "Capture probe failed: %s (%.3f s)", result["error"], time.monotonic() - started
            )
        result.update(type="capture.probe.result", request_id=message["request_id"])
        async with send_lock:
            await asyncio.wait_for(socket.send(json.dumps(result, allow_nan=False)), 0.5)

    def _probe(self, message):
        if not self._probe_lock.acquire(blocking=False):
            raise CaptureError("machine_busy")
        source = None
        try:
            reservation = uuid.UUID(message["reservation_id"])
            index = message["device_index"]
            if type(index) is not int or not 0 <= index <= 32:
                raise CaptureError("device_unavailable")
            with self.factory() as database:
                machine = database.get(WorkerMachine, self.settings.machine_id)
                if machine is None or (
                    machine.owner_epoch != self.lease.owner_epoch
                    or machine.reservation_id != reservation
                    or machine.reserved_until is None
                    or machine.reserved_until <= datetime.now(UTC)
                ):
                    raise CaptureError("machine_busy")
            backend = (
                "fake"
                if self.settings.live_capture_source == "fake"
                else "dshow"
                if sys.platform == "win32"
                else "auto"
            )
            source = ProcessFrameSource(CaptureSettings(index, backend))
            self._probe_source = source
            source.start()
            frame = source.read_latest(0, 0.5)
            if frame is None:
                raise CaptureError("device_unavailable")
            jpeg = render_overlay_jpeg(frame.image, [], [], None)
            return {
                "image_base64": base64.b64encode(jpeg).decode(),
                "width": frame.width,
                "height": frame.height,
                "backend": source.status().backend,
                "device_index": index,
            }
        finally:
            if source is not None:
                source.stop()
            self._probe_source = None
            self._probe_lock.release()
