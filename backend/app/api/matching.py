from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id
from app.core.database import get_db
from app.models import Candidate, Job, MatchingResult, User
from app.schemas import AnalyzeIn, BatchIn
from app.services import analysis_service as svc
from app.services.audit import audit

router = APIRouter(prefix="/matching", tags=["matching"])


def _pair(db: Session, cid: int, jid: int) -> tuple[Candidate, Job]:
    c, j = db.get(Candidate, cid), db.get(Job, jid)
    if not c:
        raise HTTPException(404, "Kandidat tidak ditemukan.")
    if not j:
        raise HTTPException(404, "Job tidak ditemukan.")
    return c, j


@router.post("/analyze")
def analyze(body: AnalyzeIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, j = _pair(db, body.candidate_id, body.job_id)
    r = svc.run_analysis(db, c, j, user.id, request_id(request))
    audit(db, user.id, "analysis_run", "matching_result", r.id, {"candidate_id": c.id, "job_id": j.id}, request_id(request))
    return svc.result_to_dict(r)


@router.post("/batch")
def batch(body: BatchIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Analisis banyak kandidat sekaligus untuk satu job lalu urutkan (prioritas peninjauan)."""
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "Job tidak ditemukan.")
    q = db.query(Candidate)
    if body.candidate_ids is not None:
        q = q.filter(Candidate.id.in_(body.candidate_ids))
    cands = q.all()
    if len(cands) > 200:
        raise HTTPException(422, "Maksimal 200 kandidat per batch.")
    results = [svc.run_analysis(db, c, job, user.id, request_id(request)) for c in cands]
    audit(db, user.id, "batch_analysis_run", "job", job.id, {"count": len(results)}, request_id(request))
    results.sort(key=lambda r: -r.match_score)
    return {"job_id": job.id, "count": len(results), "items": [svc.result_to_dict(r, with_details=False) for r in results]}


@router.get("")
def list_results(job_id: int | None = None, candidate_id: int | None = None, limit: int = 50,
                 _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(MatchingResult)
    if job_id:
        q = q.filter(MatchingResult.job_id == job_id)
    if candidate_id:
        q = q.filter(MatchingResult.candidate_id == candidate_id)
    return [svc.result_to_dict(r, with_details=False) for r in q.order_by(MatchingResult.id.desc()).limit(min(limit, 200)).all()]


@router.get("/{rid}")
def get_result(rid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(MatchingResult, rid)
    if not r:
        raise HTTPException(404, "Hasil matching tidak ditemukan.")
    return svc.result_to_dict(r)
