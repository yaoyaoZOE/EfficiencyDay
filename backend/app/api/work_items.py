from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.db.models import User
from app.db.session import get_db
from app.schemas.work_items import WorkItemCreate, WorkItemListResponse, WorkItemResponse
from app.services.work_items import create_work_item, get_work_item, list_work_items

router = APIRouter(prefix="/work-items", tags=["work-items"])


@router.post(
    "",
    response_model=WorkItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_work_item_route(
    payload: WorkItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkItemResponse:
    item = create_work_item(db, current_user, payload)
    db.commit()
    return WorkItemResponse.model_validate(item)


@router.get("", response_model=WorkItemListResponse)
def list_work_items_route(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkItemListResponse:
    items = list_work_items(db, current_user.id, limit=limit, offset=offset)
    return WorkItemListResponse(
        items=[WorkItemResponse.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
    )


@router.get("/{work_item_id}", response_model=WorkItemResponse)
def get_work_item_route(
    work_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkItemResponse:
    item = get_work_item(db, current_user.id, work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found.")
    return WorkItemResponse.model_validate(item)
