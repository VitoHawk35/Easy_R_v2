from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
import os
import tempfile

from app.models.schemas import DatasetInfo, VariableListResponse, DataTransformRequest, DataTransformResponse, UserPublic
from app.services.auth_service import get_current_user
from app.services.data_service import list_datasets, get_variables, import_uploaded_file, get_dataset, assert_dataset_access
from app.services.transform_service import run_data_transform

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

_UPLOAD_CHUNK_SIZE = 1024 * 1024
_DEFAULT_MAX_UPLOAD_MB = 50


def _max_upload_bytes() -> int:
    """上传大小上限（字节），由 EASYR_MAX_UPLOAD_MB 配置，默认 50 MB。"""
    raw = os.getenv("EASYR_MAX_UPLOAD_MB", str(_DEFAULT_MAX_UPLOAD_MB))
    try:
        max_mb = int(raw)
    except (TypeError, ValueError):
        max_mb = _DEFAULT_MAX_UPLOAD_MB
    return max(max_mb, 1) * 1024 * 1024


def _copy_upload_with_limit(src, dst, max_bytes: int) -> int:
    """分块复制上传内容，累计超过 max_bytes 时抛 413。返回总字节数。"""
    total = 0
    while True:
        chunk = src.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            return total
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过大小限制（最大 {max_bytes // (1024 * 1024)} MB）",
            )
        dst.write(chunk)


@router.get("", response_model=List[DatasetInfo])
def list_all_datasets(current_user: UserPublic = Depends(get_current_user)):
    return list_datasets(current_user.id)


@router.post("/transform", response_model=DataTransformResponse)
def transform_dataset(request: DataTransformRequest, current_user: UserPublic = Depends(get_current_user)):
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        return run_data_transform(request, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")


@router.get("/{dataset_id}/variables", response_model=VariableListResponse)
def dataset_variables(dataset_id: str, current_user: UserPublic = Depends(get_current_user)):
    try:
        vars_info = get_variables(dataset_id, current_user.id)
        return VariableListResponse(
            total=len(vars_info),
            selected=0,
            variables=vars_info
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/upload", response_model=DatasetInfo)
def upload_dataset(file: UploadFile = File(...), current_user: UserPublic = Depends(get_current_user)):
    temp_path = None
    try:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(status_code=400, detail="仅支持 CSV 或 Excel 文件")
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name
            _copy_upload_with_limit(file.file, tmp, _max_upload_bytes())
        if ext in [".xlsx", ".xls"]:
            df = __import__("pandas").read_excel(temp_path)
            csv_path = f"{temp_path}.csv"
            df.to_csv(csv_path, index=False)
            os.remove(temp_path)
            temp_path = csv_path
        return import_uploaded_file(temp_path, file.filename or "uploaded.csv", current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/{dataset_id}/preview")
def preview_dataset(dataset_id: str, limit: int = 20, current_user: UserPublic = Depends(get_current_user)):
    try:
        df = get_dataset(dataset_id, current_user.id)
        preview = df.head(limit)
        return {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": df.columns.tolist(),
            "data": preview.fillna("").to_dict(orient="records")
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
