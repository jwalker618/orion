"""Health, reset and reseed (SPEC §2.1, §6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models import Broker, BrokerSubmission, EntityPlan
from app.routers.ingest import RawPlanBatch, RawSubmissionBatch, post_broker_submissions, post_entity_plans
from app.services.demo_data import batched, generate_dataset

router = APIRouter(tags=["admin"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # pragma: no cover — exercised only when the DB is gone
        db_status = "error"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "records": {
            "plans": db.scalar(select(func.count()).select_from(EntityPlan)) or 0,
            "submissions": db.scalar(select(func.count()).select_from(BrokerSubmission)) or 0,
        },
    }


def load_demo_data(db: Session) -> dict:
    """Load the synthetic demo set through the same ingestion code path as
    the public POSTs, so validation and upserts stay exercised. Shared by
    POST /admin/reset?reseed=true and boot-time seeding (ORION_SEED_ON_START).
    """
    dataset = generate_dataset()
    accepted = {"plans": 0, "submissions": 0}
    rejected = {"plans": 0, "submissions": 0}
    for chunk in batched(dataset["plans"], 500):
        report = post_entity_plans(RawPlanBatch(records=chunk), db)
        accepted["plans"] += report.accepted + report.updated
        rejected["plans"] += len(report.rejected)
    for chunk in batched(dataset["submissions"], 1000):
        report = post_broker_submissions(RawSubmissionBatch(records=chunk), db)
        accepted["submissions"] += report.accepted + report.updated
        rejected["submissions"] += len(report.rejected)
    return {"accepted": accepted, "rejected": rejected}


@router.post("/admin/reset", dependencies=[Depends(require_permission("admin:reset"))])
def reset(
    reseed: bool = Query(default=False, description="Reload the synthetic demo set"),
    db: Session = Depends(get_db),
) -> dict:
    """Truncate all fact data (and the broker registry), optionally reseed."""
    db.execute(delete(BrokerSubmission))
    db.execute(delete(EntityPlan))
    db.execute(delete(Broker))
    db.commit()

    reports = load_demo_data(db) if reseed else {"plans": None, "submissions": None}
    return {"status": "reset", "reseeded": reseed, "report": reports}
