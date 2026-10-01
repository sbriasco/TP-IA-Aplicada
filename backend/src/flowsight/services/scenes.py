"""Immutable, numbered scene versions per camera (specs/004, T032).

A version is validated completely before anything is written: rules that need
the database (reference session, `shop_id` of the camera) are checked here, and
range and geometry go through `flowsight.scene.validation.validate_scene`. The
caller commits.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.core.config import Settings
from flowsight.db.models import (
    Camera,
    EntryDirection,
    ReferenceFrame,
    SceneEntryLine,
    SceneVersion,
    SceneVersionShop,
    SceneZone,
    Shop,
    ZoneRole,
)
from flowsight.scene.geometry import NORMALIZED_DECIMALS
from flowsight.scene.validation import ELEMENT_SHOP, ELEMENT_VERSION, SceneIssue, validate_scene
from flowsight.services.cameras import normalize_name_key
from flowsight.services.sessions import get_active_session

SceneErrorCode = Literal["camera_not_found"]


class SceneError(LookupError):
    """Scene request refused; `code` is translated by the API."""

    def __init__(self, code: SceneErrorCode) -> None:
        super().__init__(code)
        self.code = code


class InvalidSceneConfiguration(ValueError):
    """The version was rejected; `errors` lists every problem, nothing was written."""

    def __init__(self, errors: Sequence[SceneIssue]) -> None:
        super().__init__("invalid_scene_configuration")
        self.errors = list(errors)


@dataclass(frozen=True)
class CreatedSceneVersion:
    id: uuid.UUID
    warnings: list[SceneIssue]


@dataclass(frozen=True)
class SceneVersionSummaryRow:
    id: uuid.UUID
    camera_id: uuid.UUID
    version_number: int
    reference_session_id: uuid.UUID
    frame_width: int
    frame_height: int
    created_by_machine_id: str | None
    created_at: datetime
    shop_count: int


@dataclass(frozen=True)
class SceneVersionShopRow:
    shop_id: uuid.UUID
    name: str
    zones: dict[str, list[list[float]]]
    entry_line: dict[str, Any]


@dataclass(frozen=True)
class SceneVersionDetail(SceneVersionSummaryRow):
    shops: list[SceneVersionShopRow]


def _round(value: float) -> float:
    # `+ 0.0` turns -0.0 into 0.0 and integers into floats.
    return round(value, NORMALIZED_DECIMALS) + 0.0


def _round_point(point: Sequence[float]) -> list[float]:
    return [_round(point[0]), _round(point[1])]


def _rounded_shop(shop: Mapping[str, Any]) -> dict[str, Any]:
    """The shop as `validate_scene` expects it, with coordinates rounded as stored.

    Validating the rounded values guarantees that what is saved is what passed.
    """

    zones = {
        role: None if polygon is None else [_round_point(point) for point in polygon]
        for role, polygon in shop["zones"].items()
    }
    line = shop.get("entry_line")
    return {
        "shop_id": shop.get("shop_id"),
        "name": shop["name"],
        "zones": zones,
        "entry_line": None
        if line is None
        else {
            "start": _round_point(line["start"]),
            "end": _round_point(line["end"]),
            "entry_direction": line["entry_direction"],
        },
    }


def _version_issue(rule: str, message: str) -> SceneIssue:
    return SceneIssue(rule, ELEMENT_VERSION, None, None, f"{message} ({rule}).")


def _require_camera(database_session: DatabaseSession, camera_id: uuid.UUID) -> None:
    if database_session.get(Camera, camera_id) is None:
        raise SceneError("camera_not_found")


def _reference_frame(
    database_session: DatabaseSession, camera_id: uuid.UUID, session_id: uuid.UUID
) -> tuple[ReferenceFrame | None, SceneIssue | None]:
    # Looked up by id and camera: an unknown session reads as "of another camera".
    reference = get_active_session(database_session, session_id, lock=True)
    if reference is None or reference.registered_camera_id != camera_id:
        return None, _version_issue(
            "reference_session_other_camera",
            "La sesión de referencia no existe o no pertenece a esta cámara",
        )
    frame = database_session.get(ReferenceFrame, session_id)
    if frame is None:
        return None, _version_issue(
            "reference_frame_missing",
            "La sesión de referencia no tiene frame de referencia; elegí una sesión de video",
        )
    return frame, None


def _foreign_shop_issues(
    database_session: DatabaseSession, camera_id: uuid.UUID, shops: Sequence[Mapping[str, Any]]
) -> list[SceneIssue]:
    requested = {shop["shop_id"] for shop in shops if shop["shop_id"] is not None}
    if not requested:
        return []
    own = set(
        database_session.scalars(
            select(Shop.id).where(Shop.id.in_(requested), Shop.camera_id == camera_id)
        )
    )
    issues = []
    for index, shop in enumerate(shops):
        if shop["shop_id"] is not None and shop["shop_id"] not in own:
            message = (
                f'Local "{shop["name"]}", el local: el identificador no corresponde a un local '
                "de esta cámara (shop_other_camera)."
            )
            issues.append(
                SceneIssue("shop_other_camera", ELEMENT_SHOP, index, shop["name"], message)
            )
    return issues


def create_scene_version(
    database_session: DatabaseSession,
    settings: Settings,
    camera_id: uuid.UUID,
    *,
    reference_session_id: uuid.UUID,
    base_version_id: uuid.UUID | None,
    shops: Sequence[Mapping[str, Any]],
) -> CreatedSceneVersion:
    """Validate and insert a new version of the camera's scene; the caller commits.

    `shops` are plain dicts with the API's shop shape (`shop_id`, `name`, `zones`
    keyed by role, `entry_line`), so the service does not depend on the API layer.

    Raises `SceneError("camera_not_found")` or `InvalidSceneConfiguration` with
    every problem found; in both cases nothing is written.
    """

    _require_camera(database_session, camera_id)

    # The reference session lock prevents removal until this save commits.
    # Validation still runs before the camera lock to avoid blocking other
    # scene saves during geometry validation.
    frame, reference_issue = _reference_frame(database_session, camera_id, reference_session_id)
    errors: list[SceneIssue] = [] if reference_issue is None else [reference_issue]
    errors.extend(_foreign_shop_issues(database_session, camera_id, shops))
    shops_input = [_rounded_shop(shop) for shop in shops]
    warnings: list[SceneIssue] = []
    if frame is not None:
        # Without a reference frame there is no resolution to measure geometry in.
        geometry_errors, warnings = validate_scene(shops_input, frame.width, frame.height)
        errors.extend(geometry_errors)
    if errors:
        # Stable sort: version-level issues first, then by shop in request order.
        errors.sort(key=lambda issue: -1 if issue.shop_index is None else issue.shop_index)
        raise InvalidSceneConfiguration(errors)
    assert frame is not None

    # Serializes saves of the same camera until commit. NO KEY UPDATE, unlike
    # UPDATE, does not block inserts of rows whose foreign key points at the camera.
    database_session.execute(
        select(Camera.id).where(Camera.id == camera_id).with_for_update(key_share=True)
    )
    latest = database_session.execute(
        select(SceneVersion.id, SceneVersion.version_number)
        .where(SceneVersion.camera_id == camera_id)
        .order_by(SceneVersion.version_number.desc())
        .limit(1)
    ).first()
    version_number = 1 if latest is None else latest.version_number + 1

    version = SceneVersion(
        id=uuid.uuid4(),
        camera_id=camera_id,
        version_number=version_number,
        reference_session_id=reference_session_id,
        frame_width=frame.width,
        frame_height=frame.height,
        created_by_machine_id=settings.machine_id,
    )
    database_session.add(version)
    database_session.flush()

    for position, shop in enumerate(shops_input):
        shop_id = shop["shop_id"]
        if shop_id is None:
            shop_id = uuid.uuid4()
            database_session.add(Shop(id=shop_id, camera_id=camera_id))
            database_session.flush()
        version_shop = SceneVersionShop(
            id=uuid.uuid4(),
            scene_version_id=version.id,
            shop_id=shop_id,
            camera_id=camera_id,
            position=position,
            name=shop["name"].strip(),
            name_key=normalize_name_key(shop["name"]),
        )
        database_session.add(version_shop)
        database_session.flush()
        for role, polygon in shop["zones"].items():
            if polygon is not None:
                database_session.add(
                    SceneZone(version_shop_id=version_shop.id, role=ZoneRole(role), polygon=polygon)
                )
        line = shop["entry_line"]
        database_session.add(
            SceneEntryLine(
                version_shop_id=version_shop.id,
                start_x=line["start"][0],
                start_y=line["start"][1],
                end_x=line["end"][0],
                end_y=line["end"][1],
                entry_direction=EntryDirection(line["entry_direction"]),
            )
        )
    database_session.flush()

    if base_version_id is not None and (latest is None or base_version_id != latest.id):
        warnings.insert(
            0,
            _version_issue(
                "newer_version_exists",
                "Existe una versión más nueva que la que se cargó en el editor; "
                f"esta se guardó igual como versión {version_number}",
            ),
        )
    return CreatedSceneVersion(version.id, warnings)


def _shop_count_subquery():
    return (
        select(
            SceneVersionShop.scene_version_id,
            func.count(SceneVersionShop.id).label("shop_count"),
        )
        .group_by(SceneVersionShop.scene_version_id)
        .subquery()
    )


def _summary(version: SceneVersion, shop_count: int) -> SceneVersionSummaryRow:
    return SceneVersionSummaryRow(
        id=version.id,
        camera_id=version.camera_id,
        version_number=version.version_number,
        reference_session_id=version.reference_session_id,
        frame_width=version.frame_width,
        frame_height=version.frame_height,
        created_by_machine_id=version.created_by_machine_id,
        created_at=version.created_at,
        shop_count=shop_count,
    )


def list_scene_versions(
    database_session: DatabaseSession, camera_id: uuid.UUID
) -> list[SceneVersionSummaryRow]:
    """Versions of the camera, newest first; raises `SceneError` if it does not exist."""

    _require_camera(database_session, camera_id)
    counts = _shop_count_subquery()
    rows = database_session.execute(
        select(SceneVersion, func.coalesce(counts.c.shop_count, 0))
        .outerjoin(counts, counts.c.scene_version_id == SceneVersion.id)
        .where(SceneVersion.camera_id == camera_id)
        .order_by(SceneVersion.version_number.desc())
    )
    return [_summary(version, shop_count) for version, shop_count in rows]


def get_scene_version(
    database_session: DatabaseSession, scene_version_id: uuid.UUID
) -> SceneVersionDetail | None:
    """Full content of a version, shops in request order; `None` if it does not exist."""

    version = database_session.get(SceneVersion, scene_version_id)
    if version is None:
        return None
    version_shops = list(
        database_session.scalars(
            select(SceneVersionShop)
            .where(
                SceneVersionShop.scene_version_id == version.id,
                SceneVersionShop.camera_id == version.camera_id,
            )
            .order_by(SceneVersionShop.position)
        )
    )
    shop_ids = [shop.id for shop in version_shops]
    zones: dict[uuid.UUID, dict[str, list[list[float]]]] = {id_: {} for id_ in shop_ids}
    for zone in database_session.scalars(
        select(SceneZone).where(SceneZone.version_shop_id.in_(shop_ids))
    ):
        zones[zone.version_shop_id][zone.role.value] = zone.polygon
    lines = {
        line.version_shop_id: line
        for line in database_session.scalars(
            select(SceneEntryLine).where(SceneEntryLine.version_shop_id.in_(shop_ids))
        )
    }

    shops = []
    for shop in version_shops:
        line = lines[shop.id]
        shops.append(
            SceneVersionShopRow(
                shop_id=shop.shop_id,
                name=shop.name,
                zones=zones[shop.id],
                entry_line={
                    "start": [line.start_x, line.start_y],
                    "end": [line.end_x, line.end_y],
                    "entry_direction": line.entry_direction,
                },
            )
        )
    summary = _summary(version, len(shops))
    return SceneVersionDetail(**vars(summary), shops=shops)
