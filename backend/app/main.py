from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, datasets, history, ml, diagnostics, eval, report

app = FastAPI(title="EasyR Clinical Data Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
