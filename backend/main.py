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
    import os, subprocess, shutil
    deno_path = shutil.which("deno")
    try:
        deno_ver = subprocess.check_output(["deno", "--version"], timeout=5, stderr=subprocess.STDOUT).decode().split("\n")[0] if deno_path else "not installed"
    except Exception as e:
        deno_ver = f"error: {e}"
    return {
        "status": "ok",
        "version": os.environ.get("GIT_COMMIT_SHA") or os.environ.get("SOURCE_COMMIT", "unknown"),
        "deno": deno_ver,
        "cookie_file": os.path.exists("/root/yt_cookies.txt"),
        "cookie_size": os.path.getsize("/root/yt_cookies.txt") if os.path.exists("/root/yt_cookies.txt") else 0,
    }


app.include_router(translate_router)
app.include_router(leads_router)


@app.api_route("/", methods=["GET", "HEAD"])
def serve_frontend_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
