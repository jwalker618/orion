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
from app.models import Coverage, Entity, User
from app.routers import admin, auth, dashboard, ingest
from app.services import security
from app.services.demo_data import COVERAGES, ENTITIES

# Demo identities — one per role (initials match the dashboard fixtures).
# Every account starts with ORION_DEMO_PASSWORD (default "orion-demo").
DEMO_USERS = [
    {
        "user_id": "usr-ki", "email": "kenji.ito@msad.example",
        "display_name": "Kenji Ito", "job_title": "Group Distribution Lead",
        "organisation": "MS&AD Group", "role": "group_admin",
    },
    {
        "user_id": "usr-ao", "email": "amara.osei@msad.example",
        "display_name": "Amara Osei", "job_title": "Broker Relations Manager",
        "organisation": "MS&AD Group", "role": "broker_relations",
    },
    {
        "user_id": "usr-rn", "email": "rin.nakamura@msad.example",
        "display_name": "Rin Nakamura", "job_title": "Senior Underwriter",
        "organisation": "MS Reinsurance", "role": "entity_underwriter",
        "entity_scope": "MSRE",
    },
    {
        "user_id": "usr-kt", "email": "keiko.tanaka@msad.example",
        "display_name": "Keiko Tanaka", "job_title": "Underwriting Manager",
        "organisation": "MS Amlin", "role": "entity_underwriter",
        "entity_scope": "AMLIN",
    },
    {
        "user_id": "usr-cr", "email": "casey.reid@partner.example",
        "display_name": "Casey Reid", "job_title": "External Reviewer",
        "organisation": "Group Audit Partner", "role": "reviewer",
    },
]


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


def seed_demo_users() -> None:
    """Create any missing demo accounts (never overwrites changed passwords)."""
    from datetime import datetime, timezone

    settings = get_settings()
    with SessionLocal() as db:
        known = set(db.scalars(select(User.email)))
        for spec in DEMO_USERS:
            if spec["email"] not in known:
                db.add(
                    User(
                        **spec,
                        password_hash=security.hash_password(settings.demo_password),
                        joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )
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
    seed_demo_users()
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
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(ingest.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)

# Dashboard frontend (frontend/ — built from the Claude Design handoff).
# Mounted last so /api/v1 and /docs keep precedence.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
