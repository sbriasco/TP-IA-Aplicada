from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from flowsight.preview.broker import PreviewBroker, PreviewUpdate


def update(job_id: uuid.UUID, frame: int) -> PreviewUpdate:
    return PreviewUpdate(
        session_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        job_id=job_id,
        frame_index=frame,
        video_timestamp_seconds=Decimal(frame) / 5,
        progress_percent=float(frame * 10),
        image_base64="/9j/2Q==",
    )


def test_slow_client_keeps_only_latest_pending_preview() -> None:
    async def scenario() -> None:
        broker = PreviewBroker()
        job_id = uuid.uuid4()
        client = broker.subscribe(job_id)
        broker.publish(update(job_id, 1))
        broker.publish(update(job_id, 2))
        broker.publish(update(job_id, 3))

        assert (await client.receive())["frame_index"] == 3

    asyncio.run(scenario())


def test_last_preview_is_delivered_before_terminal() -> None:
    async def scenario() -> None:
        broker = PreviewBroker()
        job_id = uuid.uuid4()
        item = update(job_id, 9)
        client = broker.subscribe(job_id)
        broker.publish(item)
        broker.finish(item.session_id, job_id, "completed")

        assert (await client.receive())["frame_index"] == 9
        assert (await client.receive())["type"] == "job.terminal"

    asyncio.run(scenario())


def test_disconnected_and_reconnected_clients_have_independent_slots() -> None:
    async def scenario() -> None:
        broker = PreviewBroker()
        job_id = uuid.uuid4()
        disconnected = broker.subscribe(job_id)
        broker.unsubscribe(job_id, disconnected)
        broker.publish(update(job_id, 1))
        reconnected = broker.subscribe(job_id)
        broker.publish(update(job_id, 2))

        assert (await reconnected.receive())["frame_index"] == 2

    asyncio.run(scenario())
