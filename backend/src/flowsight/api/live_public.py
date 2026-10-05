"""Live observer stream and same-machine monotonic-clock calibration."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from flowsight.db.models import JobStatus, LiveAnalysisState, ProcessingJob


class ClockPing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["clock.ping"]
    client_sent_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    nonce: str = Field(min_length=1, max_length=64)


async def preview_live_job(websocket, job_id: uuid.UUID, session_id: uuid.UUID):
    broker = websocket.app.state.live_broker
    try:
        subscription = broker.subscribe(job_id)
    except ValueError:
        await websocket.close(code=1013)
        return
    send_lock = asyncio.Lock()

    async def send(message):
        async with send_lock:
            await websocket.send_json(message)

    async def clock_reader():
        pings = 0
        last_ping = time.monotonic()
        while True:
            raw = await websocket.receive_json()
            received = time.monotonic() * 1000
            ping = ClockPing.model_validate(raw)
            now = time.monotonic()
            if pings >= 8 and now - last_ping < 30:
                continue
            pings += 1
            last_ping = now
            async with send_lock:
                await asyncio.wait_for(
                    websocket.send_json(
                        {
                            "type": "clock.pong",
                            "nonce": ping.nonce,
                            "client_sent_ms": ping.client_sent_ms,
                            "server_received_monotonic_ms": received,
                            "server_sent_monotonic_ms": time.monotonic() * 1000,
                        }
                    ),
                    1,
                )

    def read_state():
        with websocket.app.state.session_factory() as database:
            job = database.get(ProcessingJob, job_id)
            state = database.get(LiveAnalysisState, job_id)
            if job is None or state is None:
                return None
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return {
                    "type": "job.terminal",
                    "schema_version": "1",
                    "job_id": str(job_id),
                    "session_id": str(session_id),
                    "status": job.status.value,
                }
            return {
                "type": "live.status",
                "schema_version": "3",
                "source_kind": "webcam",
                "job_id": str(job_id),
                "session_id": str(session_id),
                "revision": state.revision,
                "status": job.status.value,
                "capture_status": state.capture_status,
                "capture_timestamp_seconds": float(state.elapsed_capture_seconds),
                "coverage_complete": state.coverage_complete,
                "unknown_tail": state.unknown_tail,
            }

    reader = asyncio.create_task(clock_reader())
    last_status = None
    try:
        while True:
            if reader.done():
                reader.result()
            # Expire broker JPEGs even when no producer is publishing.
            broker.latest(job_id)
            try:
                message = await asyncio.wait_for(subscription.receive(), 0.2)
            except TimeoutError:
                message = None
            if message is not None:
                await asyncio.wait_for(send(message), 1)
            state = await run_in_threadpool(read_state)
            if state is None:
                await websocket.close(code=4404)
                return
            if state["type"] == "job.terminal":
                broker.status(job_id, state, terminal=True)
                await asyncio.wait_for(send(state), 1)
                return
            if message is None and state != last_status:
                await asyncio.wait_for(send(state), 1)
                last_status = state
    except WebSocketDisconnect:
        pass
    except ValidationError:
        await websocket.close(code=1008)
    except TimeoutError:
        await websocket.close(code=1013)
    finally:
        reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)
        broker.unsubscribe(job_id, subscription)
