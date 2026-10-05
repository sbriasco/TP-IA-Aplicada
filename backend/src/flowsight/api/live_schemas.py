"""Validated live controls; devices are local integer indices, never arbitrary URLs."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, Strict

from flowsight.api.schemas import TrimmedName


class LiveSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: TrimmedName
    registered_camera_id: uuid.UUID
    device_index: Annotated[int, Strict(), Field(ge=0, le=32)]
    label_mode: Literal["directions", "access"] = "directions"


class LiveStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_version_id: uuid.UUID
    check_token: str = Field(min_length=1, max_length=128)
    frame_confirmed: Annotated[bool, Strict()]


class LiveResume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_token: str = Field(min_length=1, max_length=128)
    frame_confirmed: Annotated[bool, Strict()]
