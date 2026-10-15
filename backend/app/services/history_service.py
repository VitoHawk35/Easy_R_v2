import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models.schemas import HistoryDetail, HistoryListItem, MLRequest, MLResult
from app.services.data_service import get_dataset_meta, get_user_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_dir(user_id: str) -> str:
    path = os.path.join(get_user_dir(user_id), "history")
    os.makedirs(path, exist_ok=True)
    return path


def _atomic_write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _history_path(user_id: str, history_id: str) -> str:
    return os.path.join(_history_dir(user_id), f"{history_id}.json")


def record_history(user_id: str, algorithm: str, request: MLRequest, result: MLResult) -> HistoryDetail:
    history_id = f"h_{secrets.token_urlsafe(10)}"
    try:
        dataset_meta = get_dataset_meta(request.dataset_id, user_id)
        dataset_name = dataset_meta.get("name", "")
    except Exception:
        dataset_name = ""
    item = {
        "id": history_id,
        "user_id": user_id,
        "created_at": _now(),
        "algorithm": algorithm,
        "dataset_id": request.dataset_id,
        "dataset_name": dataset_name,
        "y_variable": request.y_variable,
        "feature_count": len(request.x_variables),
        "summary": result.summary,
        "chart_count": len(result.charts),
        "table_count": len(result.tables),
        "request": request.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "wizard_snapshot": request.wizard_snapshot or {},
    }
    _atomic_write_json(_history_path(user_id, history_id), item)
    return HistoryDetail(**item)


def list_history(user_id: str) -> List[HistoryListItem]:
    items = []
    for file_name in os.listdir(_history_dir(user_id)):
        if not file_name.endswith(".json"):
            continue
        try:
            with open(os.path.join(_history_dir(user_id), file_name), "r", encoding="utf-8") as f:
                data = json.load(f)
            items.append(HistoryListItem(**data))
        except Exception:
            continue
    return sorted(items, key=lambda item: item.created_at, reverse=True)


def get_history(user_id: str, history_id: str) -> HistoryDetail:
    path = _history_path(user_id, history_id)
    if not os.path.exists(path):
        raise ValueError("历史记录不存在")
    with open(path, "r", encoding="utf-8") as f:
        return HistoryDetail(**json.load(f))


def delete_history(user_id: str, history_id: str) -> None:
    path = _history_path(user_id, history_id)
    if not os.path.exists(path):
        raise ValueError("历史记录不存在")
    os.remove(path)
