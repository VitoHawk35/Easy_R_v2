import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, datasets, history, ml, diagnostics, eval, report


def _cors_origins() -> list[str]:
    """CORS 白名单，逗号分隔；默认空。

    默认空列表适用于生产经 nginx 同源访问（浏览器不发送跨域请求）。
    需要跨域时通过 EASYR_CORS_ORIGINS 显式列出，例如
    "https://example.org,http://localhost:5173"。不要把生产域名写死在代码里。
    """
    raw = os.getenv("EASYR_CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="EasyR Clinical Data Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(history.router)
app.include_router(ml.router)
app.include_router(diagnostics.router)
app.include_router(eval.router)
app.include_router(report.router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
