from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.models.schemas import UserPublic
from app.services.auth_service import get_current_user
from app.services.report_service import generate_word_report, generate_pdf_report, generate_preview_html
from app.services.data_service import DATA_DIR
import os

router = APIRouter(prefix="/api/report", tags=["report"])

@router.post("/generate")
def generate_report(report_data: dict, current_user: UserPublic = Depends(get_current_user)):
    try:
        fmt = report_data.get("format", "word")
        if fmt == "word":
            file_path = generate_word_report(report_data)
        elif fmt == "pdf":
            file_path = generate_pdf_report(report_data)
        else:
            raise ValueError("不支持的报告格式")
        filename = os.path.basename(file_path)
        return {
            "success": True,
            "download_url": f"/api/report/download/{filename}",
            "filename": filename,
            "preview_html": generate_preview_html(report_data),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{filename}")
def download_report(filename: str, current_user: UserPublic = Depends(get_current_user)):
    filename = os.path.basename(filename)
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(file_path, filename=filename, media_type=media_type)
