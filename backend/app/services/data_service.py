import json
import os
import secrets
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import pandas as pd

from app.models.schemas import DatasetInfo, VariableInfo, VariableType
from app.settings import DATA_DIR, DEMO_DATA_PATH

USERS_DIR = os.path.join(DATA_DIR, "users")

_datasets: Dict[str, pd.DataFrame] = {}
_dataset_meta: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def get_user_dir(user_id: str) -> str:
    return os.path.join(USERS_DIR, user_id)


def get_user_dataset_dir(user_id: str) -> str:
    return os.path.join(get_user_dir(user_id), "datasets")


def get_user_datasets_file(user_id: str) -> str:
    return os.path.join(get_user_dir(user_id), "datasets.json")


def _load_user_registry(user_id: str) -> List[Dict[str, Any]]:
    path = get_user_datasets_file(user_id)
    if not os.path.exists(path):
        os.makedirs(get_user_dataset_dir(user_id), exist_ok=True)
        _atomic_write_json(path, [])
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_user_registry(user_id: str, entries: List[Dict[str, Any]]) -> None:
    _atomic_write_json(get_user_datasets_file(user_id), entries)


def _upsert_user_dataset_meta(user_id: str, meta: Dict[str, Any]) -> None:
    entries = _load_user_registry(user_id)
    entries = [entry for entry in entries if entry.get("id") != meta["id"]]
    entries.append(meta)
    _save_user_registry(user_id, entries)


def _as_numeric(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        cleaned = series.astype(str).str.strip().str.replace(",", "", regex=False)
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def _infer_type(series: pd.Series) -> VariableType:
    s = series.dropna()
    if len(s) == 0:
        return VariableType.CATEGORICAL
    numeric = _as_numeric(s)
    numeric_ratio = numeric.notna().mean()
    if series.dtype == bool or set(s.unique()).issubset({0, 1, True, False}):
        return VariableType.LOGICAL
    if numeric_ratio >= 0.9:
        return VariableType.CONTINUOUS
    return VariableType.CATEGORICAL


def _range_str(series: pd.Series, vtype: VariableType) -> str:
    s = series.dropna()
    if len(s) == 0:
        return "无数据"
    if vtype == VariableType.CATEGORICAL or vtype == VariableType.LOGICAL:
        uniq = s.unique()
        if len(uniq) <= 10:
            return f"{len(uniq)}分类"
        else:
            return f"{len(uniq)}分类(多)"
    else:
        numeric = _as_numeric(s).dropna()
        if len(numeric) == 0:
            return "无数据"
        mn, mx = numeric.min(), numeric.max()
        return f"{mn:.2f}-{mx:.2f}连续"


def load_demo_data():
    if "demo" in _datasets:
        return
    if os.path.exists(DEMO_DATA_PATH):
        df = pd.read_csv(DEMO_DATA_PATH)
        _datasets["demo"] = df
        _dataset_meta["demo"] = {
            "id": "demo",
            "name": "demo.csv",
            "rows": len(df),
            "cols": len(df.columns),
            "path": DEMO_DATA_PATH,
            "owner_user_id": None,
            "global": True,
        }


def make_user_dataset_id(prefix: str = "upload") -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def register_dataframe(dataset_id: str, df: pd.DataFrame, name: str, transform_meta: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> DatasetInfo:
    file_name = name if name.lower().endswith(".csv") else f"{name}.csv"
    if user_id:
        os.makedirs(get_user_dataset_dir(user_id), exist_ok=True)
        file_path = os.path.join(get_user_dataset_dir(user_id), f"{dataset_id}.csv")
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, file_name)

    df.to_csv(file_path, index=False)
    _datasets[dataset_id] = df
    meta = {
        "id": dataset_id,
        "name": file_name,
        "rows": len(df),
        "cols": len(df.columns),
        "path": file_path,
        "owner_user_id": user_id,
        "created_at": _now(),
        "transform_meta": transform_meta or {},
    }
    _dataset_meta[dataset_id] = meta
    if user_id:
        _upsert_user_dataset_meta(user_id, meta)
    return DatasetInfo(**meta)


def load_dataset(dataset_id: str, file_path: str, user_id: Optional[str] = None, display_name: Optional[str] = None) -> DatasetInfo:
    df = pd.read_csv(file_path)
    name = display_name or os.path.basename(file_path)
    if user_id:
        return register_dataframe(dataset_id, df, name, {"source_path": file_path}, user_id)
    _datasets[dataset_id] = df
    meta = {
        "id": dataset_id,
        "name": name,
        "rows": len(df),
        "cols": len(df.columns),
        "path": file_path,
        "owner_user_id": None,
        "created_at": _now(),
        "transform_meta": {"source_path": file_path},
    }
    _dataset_meta[dataset_id] = meta
    return DatasetInfo(**meta)


def import_uploaded_file(temp_path: str, original_name: str, user_id: str) -> DatasetInfo:
    dataset_id = make_user_dataset_id("upload")
    df = pd.read_csv(temp_path)
    return register_dataframe(dataset_id, df, original_name, {"source_path": original_name}, user_id)


def list_datasets(user_id: Optional[str] = None) -> List[DatasetInfo]:
    load_demo_data()
    if user_id:
        for meta in _load_user_registry(user_id):
            _dataset_meta[meta["id"]] = meta
        metas = [m for m in _dataset_meta.values() if m.get("global") or m.get("owner_user_id") == user_id]
    else:
        metas = list(_dataset_meta.values())
    return [DatasetInfo(**m) for m in metas]


def _load_user_dataset_from_disk(dataset_id: str, user_id: str) -> bool:
    for meta in _load_user_registry(user_id):
        if meta.get("id") == dataset_id and os.path.exists(meta.get("path", "")):
            _datasets[dataset_id] = pd.read_csv(meta["path"])
            meta["rows"] = len(_datasets[dataset_id])
            meta["cols"] = len(_datasets[dataset_id].columns)
            _dataset_meta[dataset_id] = meta
            return True
    return False


def get_dataset(dataset_id: str, user_id: Optional[str] = None) -> pd.DataFrame:
    load_demo_data()
    if dataset_id not in _datasets and user_id:
        _load_user_dataset_from_disk(dataset_id, user_id)
    if dataset_id not in _datasets:
        raise ValueError(f"Dataset {dataset_id} not found")
    if user_id:
        assert_dataset_access(dataset_id, user_id)
    return _datasets[dataset_id]


def get_dataset_meta(dataset_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    get_dataset(dataset_id, user_id)
    return _dataset_meta[dataset_id]


def assert_dataset_access(dataset_id: str, user_id: str) -> None:
    load_demo_data()
    if dataset_id not in _dataset_meta:
        _load_user_dataset_from_disk(dataset_id, user_id)
    meta = _dataset_meta.get(dataset_id)
    if not meta:
        raise ValueError(f"Dataset {dataset_id} not found")
    if meta.get("global") or meta.get("owner_user_id") == user_id:
        return
    raise ValueError("无权访问该数据集")


def get_variables(dataset_id: str, user_id: Optional[str] = None) -> List[VariableInfo]:
    df = get_dataset(dataset_id, user_id)
    variables = []
    for col in df.columns:
        series = df[col]
        vtype = _infer_type(series)
        levels = []
        min_value = None
        max_value = None
        if vtype in (VariableType.CATEGORICAL, VariableType.LOGICAL):
            levels = sorted(set(series.dropna().astype(str).unique()))[:100]
        else:
            numeric = _as_numeric(series).dropna()
            if len(numeric):
                min_value = float(numeric.min())
                max_value = float(numeric.max())
        info = VariableInfo(
            name=col,
            type=vtype,
            range_str=_range_str(series, vtype),
            missing_count=int(series.isna().sum()),
            unique_count=int(series.nunique()),
            levels=levels,
            min_value=min_value,
            max_value=max_value,
        )
        variables.append(info)
    return variables


def _apply_filters(df: pd.DataFrame, filters: Optional[List[Dict[str, Any]]]) -> pd.DataFrame:
    if not filters:
        return df
    for f in filters:
        col = f.get("column")
        op = f.get("op")
        val = f.get("value")
        if col and op and col in df.columns:
            if op == "eq":
                df = df[df[col] == val]
            elif op == "ne":
                df = df[df[col] != val]
            elif op == "gt":
                df = df[df[col] > val]
            elif op == "lt":
                df = df[df[col] < val]
            elif op == "ge":
                df = df[df[col] >= val]
            elif op == "le":
                df = df[df[col] <= val]
            elif op == "in":
                df = df[df[col].isin(val)]
    return df


def get_raw_data(dataset_id: str, columns: List[str],
                 filters: Optional[List[Dict[str, Any]]] = None,
                 user_id: Optional[str] = None) -> pd.DataFrame:
    """按筛选条件取原始数据：保留缺失行，不 dropna（E3e 缺失值诊断专用）。

    与 get_data_for_ml 的区别：这里不做任何缺失值删除，因此缺失计数真实反映
    上传数据；缺失诊断不应受建模阶段的行删除影响。
    """
    df = get_dataset(dataset_id, user_id).copy()
    df = _apply_filters(df, filters)
    keep = [c for c in columns if c in df.columns]
    return df[keep]


def get_data_for_ml(dataset_id: str, y_variable: str, x_variables: List[str],
                    is_survival: bool = False, time_variable: Optional[str] = None,
                    filters: Optional[List[Dict[str, Any]]] = None,
                    extra_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """建模用数据：只删除结局（及生存时间）缺失的行。

    E3f 约定：X 的缺失不再整行删除，交由 Pipeline 内的 ClinicalPreprocessor
    用训练集中位数/参照水平填补；报告 summary 由调用方注明删除行数。
    """
    df = get_dataset(dataset_id).copy()
    df = _apply_filters(df, filters)
    needed = [y_variable] + list(x_variables)
    if is_survival and time_variable:
        needed.append(time_variable)
    keep = needed + [c for c in (extra_cols or []) if c and c in df.columns and c not in needed]
    # 仅结局与生存时间缺失才删行；X 缺失保留给预处理填补
    outcome_cols = [y_variable]
    if is_survival and time_variable:
        outcome_cols.append(time_variable)
    outcome_cols = [c for c in outcome_cols if c in df.columns]
    df = df[keep].dropna(subset=outcome_cols)
    return df


def outcome_missing_note(dataset_id: str, y_variable: str, x_variables: List[str],
                         is_survival: bool = False, time_variable: Optional[str] = None,
                         filters: Optional[List[Dict[str, Any]]] = None,
                         user_id: Optional[str] = None) -> str:
    """生成 E3f 的统一 summary 说明（删除行数 + X 缺失处理方式）。"""
    outcome_cols = [y_variable] + ([time_variable] if is_survival and time_variable else [])
    outcome_cols = [c for c in outcome_cols if c]
    raw = get_raw_data(dataset_id, outcome_cols, filters, user_id)
    n_raw = len(raw)
    n_kept = len(raw.dropna(subset=outcome_cols)) if outcome_cols else n_raw
    n_drop = max(n_raw - n_kept, 0)
    return (f"数据准备：删除了 {n_drop} 行结局缺失；"
            f"X 缺失用训练集中位数/参照水平填补。")
