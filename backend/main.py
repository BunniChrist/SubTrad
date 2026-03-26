from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from backend.routers.leads import router as leads_router
    from backend.routers.translate import router as translate_router
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from routers.leads import router as leads_router
    from routers.translate import router as translate_router


app = FastAPI(title="SubTrad Backend API")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict:
    try:
        from config import get_settings
    except ModuleNotFoundError:
        from backend.config import get_settings
    s = get_settings()
    import os
    return {
        "status": "ok",
        "yt_key_len": len(s.youtube_api_key),
        "yt_key_prefix": s.youtube_api_key[:8] if s.youtube_api_key else "EMPTY",
        "openai_key_len": len(s.openai_api_key),
        "env_yt_key": os.environ.get("SUBTRAD_YOUTUBE_API_KEY", "NOT_SET")[:8],
        "env_keys": [k for k in os.environ if k.startswith("SUBTRAD_")],
    }


app.include_router(translate_router)
app.include_router(leads_router)


@app.api_route("/", methods=["GET", "HEAD"])
def serve_frontend_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
