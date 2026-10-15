from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models.schemas import HistoryDetail, HistoryListItem, UserPublic
from app.services.auth_service import get_current_user
from app.services.history_service import delete_history, get_history, list_history

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=List[HistoryListItem])
def history_list(current_user: UserPublic = Depends(get_current_user)):
    return list_history(current_user.id)


@router.get("/{history_id}", response_model=HistoryDetail)
def history_detail(history_id: str, current_user: UserPublic = Depends(get_current_user)):
    try:
        return get_history(current_user.id, history_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{history_id}")
def history_delete(history_id: str, current_user: UserPublic = Depends(get_current_user)):
    try:
        delete_history(current_user.id, history_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
