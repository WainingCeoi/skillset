"""FastAPI application factory.

Run with:  uv run uvicorn <app>_api.main:app --reload

One <EngineClass> is built at startup and shared by every request (single-user, on-device).
Routers mount under ``/api`` so the Vite dev proxy can forward ``/api/*`` here. In single-origin
production (``make start`` / ``make host``) the built frontend in ``frontend/dist`` is served
from this same server, so the whole app runs on one port.

Replace <app>_api, <engine>, and <EngineClass> with your names.
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException

if TYPE_CHECKING:
    from <engine> import <EngineClass>

# Dev origins for the Vite frontend. Override with a comma-separated env var. In single-origin
# production the UI is same-origin, so CORS is only exercised when hitting the API directly.
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Keep shell-provided settings authoritative, while making backend/.env work for every launcher.
load_dotenv(_BACKEND_DIR / ".env", override=False)


def _build_engine() -> <EngineClass>:
    """Import the project-specific builder after dotenv has populated import-time config."""
    from .deps import build_engine

    return build_engine()


class SPAStaticFiles(StaticFiles):
    """Serve index.html only for HTML navigation to an otherwise unknown SPA route."""

    async def get_response(self, path: str, scope: dict[str, object]):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            accepts_html = "text/html" in Headers(scope=scope).get("accept", "")
            is_api_path = path == "api" or path.startswith("api/")
            is_asset_path = path.startswith("assets/") or bool(Path(path).suffix)
            if (
                exc.status_code == 404
                and scope["method"] in {"GET", "HEAD"}
                and accepts_html
                and not is_api_path
                and not is_asset_path
            ):
                return await super().get_response("index.html", scope)
            raise


def _cors_origins() -> list[str]:
    raw = os.environ.get("APP_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def _frontend_dist() -> Path | None:
    """Location of the built frontend, if present (APP_STATIC_DIR or ../frontend/dist)."""
    override = os.environ.get("APP_STATIC_DIR")
    dist = Path(override) if override else _BACKEND_DIR.parent / "frontend" / "dist"
    return dist if dist.is_dir() else None


def create_app(engine: <EngineClass> | None = None) -> FastAPI:
    """Build the app. Pass ``engine`` to inject a fake (tests); otherwise a real one is built
    at startup and any expensive resource warmed in the background."""
    provided = engine is not None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine if engine is not None else _build_engine()
        if not provided:
            # Warm expensive resources now, not inside the first request. Use a daemon thread
            # if warm-up is slow so the server can start binding immediately.
            warm = getattr(app.state.engine, "warm", None)
            if callable(warm):
                threading.Thread(target=warm, daemon=True).start()
        yield

    app = FastAPI(title="<PROJECT> API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import project-local routers only after dotenv is loaded above. Each router may import the
    # engine or dependency builder while defining routes.
    # from .routers import ...   # one module per resource, each with an APIRouter
    # app.include_router(<resource>.router, prefix="/api")   # repeat per resource

    # Serve the built frontend from the same server, if present (make start / make host).
    # Mounted LAST (after /api and /docs) so it only catches unmatched paths, and skipped in
    # tests (which inject an engine and only exercise /api).
    if not provided:
        dist = _frontend_dist()
        if dist is not None:
            app.mount("/", SPAStaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
