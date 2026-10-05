"""RAM-only preview fanout and bounded request/reply channel to the local worker."""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass, field

from flowsight.capture.contracts import CaptureError, CaptureProbeResult
from flowsight.preview.live_messages import LiveUpdate


@dataclass
class LiveSubscription:
    pending: dict | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def pending_count(self) -> int:
        return int(self.pending is not None)

    async def receive(self) -> dict:
        while self.pending is None:
            self.changed.clear()
            await self.changed.wait()
        message, self.pending = self.pending, None
        return message


class LiveBroker:
    def __init__(self, *, clock=time.monotonic) -> None:
        self.clock = clock
        self._latest: dict[uuid.UUID, tuple[float, dict]] = {}
        self._observers: dict[uuid.UUID, list[LiveSubscription]] = {}

    @property
    def observer_count(self) -> int:
        return sum(map(len, self._observers.values()))

    def subscribe(self, job_id: uuid.UUID) -> LiveSubscription:
        observers = self._observers.setdefault(job_id, [])
        if len(observers) >= 8:
            raise ValueError("observer_limit")
        observer = LiveSubscription()
        observers.append(observer)
        observer.pending = self.latest(job_id)
        return observer

    def unsubscribe(self, job_id: uuid.UUID, observer: LiveSubscription) -> None:
        observers = self._observers.get(job_id, [])
        if observer in observers:
            observers.remove(observer)
        observer.pending = None
        if not observers:
            self._observers.pop(job_id, None)

    def latest(self, job_id: uuid.UUID) -> dict | None:
        self._prune()
        latest = self._latest.get(job_id)
        return latest[1] if latest is not None else None

    def _prune(self) -> None:
        for job_id, (created, _) in list(self._latest.items()):
            if self.clock() - created > 10:
                del self._latest[job_id]
                for observer in self._observers.get(job_id, []):
                    if observer.pending is not None and observer.pending.get("type") in {
                        "live.update",
                        "live.reconnect-check",
                    }:
                        observer.pending = None

    def publish(self, update: LiveUpdate) -> bool:
        previous = self.latest(update.job_id)
        if previous is not None and (
            update.revision <= previous["revision"]
            or update.capture_sequence < previous.get("capture_sequence", 0)
        ):
            return False
        message = update.model_dump(mode="json")
        self._latest[update.job_id] = (self.clock(), message)
        for observer in self._observers.get(update.job_id, []):
            observer.pending = message
            observer.changed.set()
        return True

    def reconnect_check(self, job_id: uuid.UUID, message: dict) -> None:
        self._latest[job_id] = (self.clock(), message)
        for observer in self._observers.get(job_id, []):
            observer.pending = message
            observer.changed.set()

    def status(self, job_id: uuid.UUID, message: dict, *, terminal=False) -> None:
        if terminal:
            self._latest.pop(job_id, None)
        for observer in self._observers.get(job_id, []):
            observer.pending = message
            observer.changed.set()


class LiveChannel:
    def __init__(self, broker: LiveBroker) -> None:
        self.broker = broker
        self.websocket = None
        self.machine_id: str | None = None
        self.owner_epoch: uuid.UUID | None = None
        self._pending: dict[uuid.UUID, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self.websocket is not None

    def attach(self, websocket, machine_id: str, owner_epoch: uuid.UUID) -> None:
        if self.available:
            raise ValueError("producer_exists")
        self.websocket, self.machine_id, self.owner_epoch = websocket, machine_id, owner_epoch

    def detach(self, websocket) -> None:
        if self.websocket is not websocket:
            return
        self.websocket = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(CaptureError("worker_unavailable"))

    async def probe(self, *, machine_id, owner_epoch, reservation_id, device_index):
        if not self.available or machine_id != self.machine_id or owner_epoch != self.owner_epoch:
            raise CaptureError("worker_unavailable")
        if len(self._pending) >= 8:
            raise CaptureError("machine_busy")
        request_id = uuid.uuid4()
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with self._send_lock:
                await asyncio.wait_for(
                    self.websocket.send_json(
                        {
                            "type": "capture.probe",
                            "request_id": str(request_id),
                            "reservation_id": str(reservation_id),
                            "device_index": device_index,
                            "max_timeout_s": 5,
                        }
                    ),
                    0.5,
                )
            return await asyncio.wait_for(future, 5)
        except TimeoutError:
            raise CaptureError("capture_open_timeout") from None
        finally:
            self._pending.pop(request_id, None)

    def probe_result(self, message: dict) -> None:
        request_id = uuid.UUID(message["request_id"])
        future = self._pending.get(request_id)
        if future is None or future.done():
            return
        if message.get("error") is not None:
            code = message["error"]
            if code not in {
                "device_unavailable",
                "capture_open_timeout",
                "machine_busy",
                "capture_read_timeout",
                "capture_process_failed",
            }:
                code = "device_unavailable"
            future.set_exception(CaptureError(code))
            return
        width, height, index = message["width"], message["height"], message["device_index"]
        if not (
            type(width) is int
            and type(height) is int
            and type(index) is int
            and 1 <= width <= 1920
            and 1 <= height <= 1080
            and 0 <= index <= 32
        ):
            raise ValueError("Invalid probe dimensions")
        jpeg = base64.b64decode(message["image_base64"], validate=True)
        if not jpeg or len(jpeg) > 200 * 1024:
            raise ValueError("Probe too large")
        backend = message["backend"]
        if backend not in {"auto", "dshow", "msmf", "fake"}:
            raise ValueError("Invalid backend")
        future.set_result(CaptureProbeResult(jpeg, width, height, backend, index))
