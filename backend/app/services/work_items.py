from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import local_today
from app.db.models import User, WorkItem
from app.schemas.work_items import WorkItemCreate, WorkItemStatus

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"in_progress", "completed", "cancelled"}),
    "in_progress": frozenset({"pending", "completed", "cancelled"}),
    "completed": frozenset({"pending", "in_progress"}),
    "cancelled": frozenset({"pending", "in_progress"}),
}


def create_work_item(session: Session, user: User, payload: WorkItemCreate) -> WorkItem:
    item = WorkItem(user_id=user.id, status="pending", **payload.model_dump())
    session.add(item)
    return item


def get_work_item(session: Session, user_id: int, work_item_id: int) -> WorkItem | None:
    return session.scalar(
        select(WorkItem).where(
            WorkItem.user_id == user_id,
            WorkItem.id == work_item_id,
        )
    )


def list_work_items(
    session: Session, user_id: int, *, limit: int, offset: int
) -> list[WorkItem]:
    return list(
        session.scalars(
            select(WorkItem)
            .where(WorkItem.user_id == user_id)
            .order_by(WorkItem.created_at.desc(), WorkItem.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def apply_status_transition(
    item: WorkItem,
    target_status: WorkItemStatus,
    timezone_name: str,
    *,
    now: datetime | None = None,
) -> None:
    allowed_targets = _ALLOWED_TRANSITIONS.get(item.status)
    if allowed_targets is None or target_status not in allowed_targets:
        raise ValueError(f"Invalid work item status transition: {item.status} -> {target_status}")

    current_status = item.status
    if target_status == "in_progress" and item.started_on is None:
        item.started_on = local_today(timezone_name, now=now)
    if target_status == "completed":
        item.completed_on = local_today(timezone_name, now=now)
    elif current_status == "completed":
        item.completed_on = None
    item.status = target_status
