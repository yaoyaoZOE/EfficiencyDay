from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkItemStatus = Literal["pending", "in_progress", "completed", "cancelled"]
ColorKey = Literal["gray", "blue", "green", "yellow", "orange", "red", "purple"]


class WorkItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    urgency: bool | None = None
    importance: bool | None = None
    color_key: ColorKey | None = None
    due_on: date | None = None
    background: str | None = None
    goal: str | None = None
    result: str | None = None
    reflection: str | None = None


class WorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: WorkItemStatus
    urgency: bool | None
    importance: bool | None
    color_key: ColorKey | None
    due_on: date | None
    started_on: date | None
    completed_on: date | None
    background: str | None
    goal: str | None
    result: str | None
    reflection: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkItemListResponse(BaseModel):
    items: list[WorkItemResponse]
    limit: int
    offset: int
