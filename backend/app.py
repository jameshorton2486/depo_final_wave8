from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.api import ai_review as ai_review_router
from backend.api import cases as cases_router
from backend.api import corrections as corrections_router
from backend.api import depo_meta as depo_meta_router
from backend.api import exhibits as exhibits_router
from backend.api import intake as intake_router
from backend.api import nod as nod_router
from backend.api import packaging as packaging_router
from backend.api import reporters as reporters_router
from backend.api import sessions as sessions_router
from backend.api import snapshots as snapshots_router
from backend.api import transcripts as transcripts_router
from backend.config import settings
from backend.database.init_db import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    try:
        initialize_database()
    except Exception as exc:  # noqa: BLE001 - log then re-raise so startup fails loudly
        logger.exception(f"Database initialization failed: {exc}")
        raise
    try:
        from backend.transcript.audio_retention import prune_audio

        prune_audio()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Audio retention sweep failed (non-fatal): {exc}")
    logger.info("Backend ready.")
    yield
    logger.info("Backend shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled errors.

    FastAPI handles HTTPException (400/404/422 etc.) on its own; this
    only fires for genuinely unexpected errors. It writes the full
    traceback to the log (loguru) and returns a clean JSON `detail` so
    the frontend can surface a message instead of failing silently.
    """
    logger.exception(
        f"Unhandled error on {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "application": settings.app_name,
        "version": settings.app_version,
    }


# Register API routers. Order matters: all /api/* routes must be
# attached before the catch-all static mount, otherwise the static
# handler swallows API requests.
app.include_router(cases_router.router)
app.include_router(sessions_router.router)
app.include_router(reporters_router.router)
app.include_router(nod_router.router)
app.include_router(intake_router.router)
app.include_router(transcripts_router.router)
app.include_router(exhibits_router.router)
app.include_router(corrections_router.router)
app.include_router(ai_review_router.router)
app.include_router(snapshots_router.router)
app.include_router(packaging_router.router)
app.include_router(depo_meta_router.router)


app.mount(
    "/",
    StaticFiles(directory=str(settings.frontend_root), html=True),
    name="frontend",
)
