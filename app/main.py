"""FastAPI app assembly: routers, CORS, RFC-7807-style error handling."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Coverage, Entity
from app.routers import admin, dashboard, ingest
from app.services.demo_data import COVERAGES, ENTITIES


def seed_reference_data() -> None:
    """Entities and coverages are closed lists (SPEC §5.5–5.6), seeded at boot."""
    with SessionLocal() as db:
        known_entities = set(db.scalars(select(Entity.entity_code)))
        for e in ENTITIES:
            if e["entity_code"] not in known_entities:
                db.add(Entity(**e))
        known_coverages = set(db.scalars(select(Coverage.code)))
        for c in COVERAGES:
            if c["code"] not in known_coverages:
                db.add(Coverage(**c))
        db.commit()


def seed_demo_data_if_empty() -> None:
    """ORION_SEED_ON_START=true: load the demo set when no submissions exist.

    Makes ephemeral-filesystem deploys (e.g. Railway without a volume) come up
    demo-ready on every boot without a separate seed step.
    """
    from sqlalchemy import func

    from app.models import BrokerSubmission
    from app.routers.admin import load_demo_data

    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(BrokerSubmission)) or 0
        if count == 0:
            load_demo_data(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_reference_data()
    if get_settings().seed_on_start:
        seed_demo_data_if_empty()
    yield


app = FastAPI(
    title="Broker Intelligence Demo API",
    description="Project ORION demo backend — ingestion and dashboard read model. See SPEC.md.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Errors follow RFC-7807-style {type, title, detail, errors[]} (SPEC §4.2).


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "HTTP error",
            "detail": exc.detail,
            "errors": [],
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "type": "about:blank",
            "title": "Validation error",
            "detail": "Request failed validation",
            "errors": [
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            ],
        },
    )


API_PREFIX = "/api/v1"
app.include_router(ingest.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)

# Dashboard frontend (frontend/ — built from the Claude Design handoff).
# Mounted last so /api/v1 and /docs keep precedence.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
