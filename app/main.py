"""FastAPI entry point for the Eufisky browser simulation."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

app = FastAPI(title="Eufisky")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/api/health")
async def health() -> dict[str, bool]:
    """Return a dependency-free liveness response."""

    return {"ok": True}


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    """Serve the single-page browser simulation shell."""

    return FileResponse(WEB_DIR / "index.html")


__all__ = ["app", "settings"]
