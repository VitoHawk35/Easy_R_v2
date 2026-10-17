from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.models.schemas import UserPublic
from app.services.auth_service import get_current_user
from app.services.report_service import (
    REPORT_FILENAME_RE,
    generate_word_report,
    generate_pdf_report,
    generate_preview_html,
    get_user_reports_dir,
)
import os

router = APIRouter(prefix="/api/report", tags=["report"])

@router.post("/generate")
def generate_report(report_data: dict, current_user: UserPublic = Depends(get_current_user)):
    try:
        fmt = report_data.get("format", "word")
        if fmt == "word":
            file_path = generate_word_report(report_data, current_user.id)
        elif fmt == "pdf":
            file_path = generate_pdf_report(report_data, current_user.id)
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
    # 只允许本用户 reports 目录下、符合新命名规则的文件；其余一律 404。
    if not REPORT_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    reports_dir = os.path.realpath(get_user_reports_dir(current_user.id))
    file_path = os.path.realpath(os.path.join(reports_dir, filename))
    if not file_path.startswith(reports_dir + os.sep) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(file_path, filename=filename, media_type=media_type)
