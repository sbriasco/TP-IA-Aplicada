"""Non-blocking latest-frame preview delivery."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class PreviewUpdate:
    session_id: uuid.UUID
    job_id: uuid.UUID
    frame_index: int
    video_timestamp_seconds: Decimal
    progress_percent: float
    image_base64: str

    def as_message(self) -> dict[str, object]:
        return {
            "type": "preview.update",
            "schema_version": "1",
            "session_id": str(self.session_id),
            "job_id": str(self.job_id),
            "frame_index": self.frame_index,
            "video_timestamp_seconds": float(self.video_timestamp_seconds),
            "progress_percent": self.progress_percent,
            "image_media_type": "image/jpeg",
            "image_base64": self.image_base64,
        }


@dataclass
class PreviewSubscription:
    pending: PreviewUpdate | None = None
    terminal: dict[str, object] | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    async def receive(self) -> dict[str, object]:
        while True:
            if self.pending is not None:
                update, self.pending = self.pending, None
                return update.as_message()
            if self.terminal is not None:
                return self.terminal
            self.changed.clear()
            await self.changed.wait()


class PreviewBroker:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[PreviewSubscription]] = {}

    def subscribe(self, job_id: uuid.UUID) -> PreviewSubscription:
        subscription = PreviewSubscription()
        self._subscribers.setdefault(job_id, []).append(subscription)
        return subscription

    def unsubscribe(self, job_id: uuid.UUID, subscription: PreviewSubscription) -> None:
        subscribers = self._subscribers.get(job_id, [])
        if subscription in subscribers:
            subscribers.remove(subscription)
        if not subscribers:
            self._subscribers.pop(job_id, None)

    def publish(self, update: PreviewUpdate) -> None:
        for subscription in self._subscribers.get(update.job_id, []):
            subscription.pending = update
            subscription.changed.set()

    def finish(self, session_id: uuid.UUID, job_id: uuid.UUID, status: str) -> None:
        message: dict[str, object] = {
            "type": "job.terminal",
            "schema_version": "1",
            "session_id": str(session_id),
            "job_id": str(job_id),
            "status": status,
        }
        for subscription in self._subscribers.get(job_id, []):
            subscription.terminal = message
            subscription.changed.set()
