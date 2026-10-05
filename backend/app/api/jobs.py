from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id
from app.core.database import get_db
from app.models import Job, MatchingResult, User
from app.schemas import JobCreate
from app.services import analysis_service as svc
from app.services.audit import audit

router = APIRouter(prefix="/jobs", tags=["jobs"])


def job_dict(j: Job, full: bool = False) -> dict:
    r = j.requirements or {}
    d = {"id": j.id, "title": j.title, "created_at": j.created_at.isoformat(),
         "required_skills": r.get("required_skills", []), "preferred_skills": r.get("preferred_skills", []),
         "min_years": r.get("min_years"), "min_education_level": r.get("min_education_level"),
         "candidates_analyzed": len({x.candidate_id for x in j.results})}
    if full:
        d.update({"description": j.description, "responsibilities": r.get("responsibilities", []),
                  "education_text": r.get("education_text"), "required_skill_groups": r.get("required_skill_groups", [])})
    return d


@router.post("", status_code=201)
def create_job(body: JobCreate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = svc.create_job(db, body.title.strip(), body.description, user.id)
    audit(db, user.id, "job_created", "job", job.id, request_id=request_id(request))
    return job_dict(job, full=True)


@router.get("")
def list_jobs(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [job_dict(j) for j in db.query(Job).order_by(Job.id.desc()).all()]


@router.get("/{jid}")
def get_job(jid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Job tidak ditemukan.")
    return job_dict(j, full=True)


@router.delete("/{jid}", status_code=204)
def delete_job(jid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Job tidak ditemukan.")
    db.delete(j)
    db.commit()
    audit(db, user.id, "job_deleted", "job", jid, request_id=request_id(request))


@router.get("/{jid}/ranking")
def ranking(jid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Peringkat kandidat untuk satu job (hasil analisis terbaru per kandidat). Peringkat = alat bantu prioritas
    peninjauan, bukan keputusan seleksi."""
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Job tidak ditemukan.")
    latest: dict[int, MatchingResult] = {}
    for r in sorted(j.results, key=lambda x: x.created_at):
        latest[r.candidate_id] = r
    rows = sorted(latest.values(), key=lambda r: -r.match_score)
    return {"job": job_dict(j), "items": [
        {"rank": i + 1, "result_id": r.id, "candidate_id": r.candidate_id, "candidate_name": r.candidate.name,
         "match_score": r.match_score, "matched_skills": r.analysis.get("matched_skills", []),
         "missing_skills": r.analysis.get("missing_skills", []),
         "warnings": r.analysis.get("warnings", [])} for i, r in enumerate(rows)]}
