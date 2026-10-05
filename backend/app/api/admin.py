from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.candidates import delete_candidate_files
from app.api.deps import request_id, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AuditLog, Candidate, InferenceLog, Job, MatchingResult, User
from app.services.audit import audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
def metrics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(InferenceLog).order_by(InferenceLog.id.desc()).limit(1000).all()
    ms = [l.processing_ms for l in logs]
    by_ver: dict[str, int] = {}
    for l in logs:
        key = f"{l.embedding_model} | {l.llm_model} | {l.prompt_version} | {l.matching_engine_version}"
        by_ver[key] = by_ver.get(key, 0) + 1
    return {
        "totals": {"candidates": db.query(func.count(Candidate.id)).scalar(), "jobs": db.query(func.count(Job.id)).scalar(),
                   "analyses": db.query(func.count(MatchingResult.id)).scalar()},
        "latency_ms": {"avg": round(float(np.mean(ms)), 1) if ms else None, "p95": round(float(np.percentile(ms, 95)), 1) if ms else None},
        "tokens": {"input": sum(l.input_tokens for l in logs), "output": sum(l.output_tokens for l in logs)},
        "llm_fallbacks": sum(1 for l in logs if l.llm_fallback),
        "unsupported_claims_removed": sum(l.unsupported_claims for l in logs),
        "errors": sum(1 for l in logs if l.error),
        "by_version": [{"versions": k, "count": v} for k, v in by_ver.items()],
        "recent": [{"request_id": l.request_id, "candidate_id": l.candidate_id, "job_id": l.job_id, "processing_ms": l.processing_ms,
                    "embedding_model": l.embedding_model, "llm_model": l.llm_model, "prompt_version": l.prompt_version,
                    "tokens": l.input_tokens + l.output_tokens, "error": l.error, "created_at": l.created_at.isoformat()} for l in logs[:15]],
    }


@router.get("/audit")
def audit_log(limit: int = 100, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)).all()
    return [{"id": r.id, "user_id": r.user_id, "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
             "detail": r.detail, "request_id": r.request_id, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/retention/purge")
def purge(days: int | None = None, request: Request = None, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Kebijakan retensi: hapus kandidat (beserta file CV & hasil analisis) yang lebih tua dari N hari."""
    days = days or get_settings().retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old = db.query(Candidate).filter(Candidate.created_at < cutoff).all()
    for c in old:
        delete_candidate_files(c)
        db.delete(c)
    db.commit()
    audit(db, admin.id, "retention_purge", "candidate", None, {"days": days, "deleted": len(old)}, request_id(request))
    return {"deleted": len(old), "older_than_days": days}
