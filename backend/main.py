from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.routers.translate import router as translate_router
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from routers.translate import router as translate_router


app = FastAPI(title="SubTrad Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(translate_router)
