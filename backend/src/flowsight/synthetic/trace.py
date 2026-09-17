"""Validated, deterministic records for the versioned synthetic flow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class SyntheticTraceError(ValueError):
    """Raised when a synthetic trace cannot be trusted."""


@dataclass(frozen=True)
class FrameRecord:
    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    camera_id: str
    frame_index: int
    video_timestamp_seconds: Decimal


@dataclass(frozen=True)
class ObservationRecord:
    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    frame_id: uuid.UUID
    camera_id: str
    track_id: int
    kind: str


@dataclass(frozen=True)
class EventRecord:
    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    frame_id: uuid.UUID
    observation_id: uuid.UUID | None
    camera_id: str
    video_timestamp_seconds: Decimal
    event_type: str


@dataclass(frozen=True)
class SyntheticTrace:
    frames: tuple[FrameRecord, ...]
    observations: tuple[ObservationRecord, ...]
    events: tuple[EventRecord, ...]


def generate_synthetic_trace(
    payload: dict[str, Any],
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    camera_id: str,
) -> SyntheticTrace:
    """Validate a fixture and generate records scoped to one job."""
    if payload.get("schema_version") != 1 or not isinstance(payload.get("frames"), list):
        raise SyntheticTraceError("El fixture sintético tiene un formato no compatible.")

    frames: list[FrameRecord] = []
    observations: list[ObservationRecord] = []
    events: list[EventRecord] = []
    frame_keys: set[str] = set()
    observation_keys: set[str] = set()
    event_keys: set[str] = set()
    previous_timestamp: Decimal | None = None

    for frame_data in payload["frames"]:
        frame_key = _required_text(frame_data, "key", "frame")
        if frame_key in frame_keys:
            raise SyntheticTraceError(f"La clave de frame está duplicada: {frame_key}.")
        frame_keys.add(frame_key)

        frame_index = frame_data.get("frame_index")
        if not isinstance(frame_index, int) or isinstance(frame_index, bool) or frame_index < 0:
            raise SyntheticTraceError("Cada frame requiere un índice entero no negativo.")
        timestamp = _timestamp(frame_data.get("video_timestamp_seconds"))
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise SyntheticTraceError("Los timestamps del video deben ser monótonos crecientes.")
        previous_timestamp = timestamp

        frame_id = _stable_id(job_id, f"frame:{frame_key}")
        frames.append(FrameRecord(frame_id, session_id, job_id, camera_id, frame_index, timestamp))

        frame_observations: dict[str, uuid.UUID] = {}
        for observation_data in _required_list(frame_data, "observations"):
            observation_key = _required_text(observation_data, "key", "observación")
            if observation_key in observation_keys:
                raise SyntheticTraceError(
                    f"La clave de observación está duplicada: {observation_key}."
                )
            observation_keys.add(observation_key)
            observation_id = _stable_id(job_id, f"observation:{observation_key}")
            frame_observations[observation_key] = observation_id
            track_id = observation_data.get("track_id")
            if not isinstance(track_id, int) or isinstance(track_id, bool):
                raise SyntheticTraceError("Cada observación requiere un track_id entero.")
            observations.append(
                ObservationRecord(
                    observation_id,
                    session_id,
                    job_id,
                    frame_id,
                    camera_id,
                    track_id,
                    _required_text(observation_data, "kind", "observación"),
                )
            )

        for event_data in _required_list(frame_data, "events"):
            event_key = _required_text(event_data, "key", "evento")
            if event_key in event_keys:
                raise SyntheticTraceError(f"La clave de evento está duplicada: {event_key}.")
            event_keys.add(event_key)
            reference = event_data.get("observation_key")
            if reference is not None and reference not in frame_observations:
                raise SyntheticTraceError(
                    f"El evento {event_key} contiene una referencia de observación inválida."
                )
            events.append(
                EventRecord(
                    _stable_id(job_id, f"event:{event_key}"),
                    session_id,
                    job_id,
                    frame_id,
                    frame_observations.get(reference),
                    camera_id,
                    timestamp,
                    _required_text(event_data, "event_type", "evento"),
                )
            )

    return SyntheticTrace(tuple(frames), tuple(observations), tuple(events))


def _stable_id(job_id: uuid.UUID, key: str) -> uuid.UUID:
    return uuid.uuid5(job_id, key)


def _timestamp(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise SyntheticTraceError("Cada frame requiere un timestamp de video válido.")
    try:
        timestamp = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SyntheticTraceError("Cada frame requiere un timestamp de video válido.") from None
    if not timestamp.is_finite() or timestamp < 0:
        raise SyntheticTraceError("El timestamp del video debe ser finito y no negativo.")
    return timestamp


def _required_text(data: dict[str, Any], field: str, owner: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SyntheticTraceError(f"Cada {owner} requiere {field}.")
    return value


def _required_list(data: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SyntheticTraceError(f"El campo {field} debe ser una lista.")
    return value
