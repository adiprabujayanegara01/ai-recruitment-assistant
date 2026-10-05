import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Candidate, CandidateSkill, Job, MatchingResult, Skill, User
from app.services import analysis_service as svc
from app.services.audit import audit
from app.services.document_reader import FileValidationError, extract_text, validate_upload

router = APIRouter(prefix="/candidates", tags=["candidates"])


def candidate_dict(c: Candidate, full: bool = False) -> dict:
    latest = {}
    for r in sorted(c.results, key=lambda x: x.created_at):
        latest[r.job_id] = r
    d = {
        "id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "location": c.location,
        "total_experience_years": c.total_experience_years,
        "skills": [cs.skill.name for cs in c.skills],
        "created_at": c.created_at.isoformat(),
        "latest_scores": [{"job_id": j, "result_id": r.id, "match_score": r.match_score} for j, r in latest.items()],
    }
    if full:
        d.update({
            "education": [{"institution": e.institution, "degree": e.degree, "major": e.major, "level": e.level} for e in c.educations],
            "experience": [{"position": e.position, "company": e.company, "description": e.description,
                            "start": e.start, "end": e.end, "months": e.months} for e in c.experiences],
            "certifications": [{"name": x.name, "issuer": x.issuer} for x in c.certifications],
            "projects": [{"name": p.name, "description": p.description} for p in c.projects],
            "resume": {"filename": c.resume.original_filename, "type": c.resume.file_type,
                       "sections_found": c.resume.parsed.get("sections_found", []), "parser_version": c.resume.parser_version},
        })
    return d


@router.post("/upload", status_code=201)
async def upload_cv(request: Request, file: UploadFile = File(...), job_id: int | None = Form(None),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = await file.read()
    try:
        kind = validate_upload(file.filename or "", data)
        text = extract_text(data, kind)
    except FileValidationError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(422, "File tidak dapat dibaca. Pastikan dokumen tidak rusak atau terkunci password.")
    stored = get_settings().upload_path / f"{uuid.uuid4().hex}.{kind}"  # nama acak: tidak memakai nama dari pengguna
    stored.write_bytes(data)
    cand = svc.create_candidate_from_text(db, text=text, filename=Path(file.filename or "cv").name[:200],
                                          stored_path=str(stored), file_type=kind, user_id=user.id)
    audit(db, user.id, "cv_uploaded", "candidate", cand.id, {"type": kind, "size": len(data)}, request_id(request))
    out = candidate_dict(cand, full=True)
    if job_id is not None:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job tidak ditemukan.")
        r = svc.run_analysis(db, cand, job, user.id, request_id(request))
        audit(db, user.id, "analysis_run", "matching_result", r.id, {"candidate_id": cand.id, "job_id": job.id}, request_id(request))
        out["analysis"] = svc.result_to_dict(r, with_details=False)
    return out


@router.get("")
def list_candidates(q: str | None = None, skill: list[str] = Query(default=[]), min_years: float | None = None,
                    limit: int = Query(50, le=200), offset: int = 0, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Pencarian kandidat: teks bebas (nama/email/skill/posisi), skill (semua harus ada), minimal tahun pengalaman."""
    query = db.query(Candidate)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(func.lower(Candidate.name).like(like), func.lower(Candidate.email).like(like),
                                 Candidate.id.in_(db.query(CandidateSkill.candidate_id).join(Skill).filter(func.lower(Skill.name).like(like)))))
    for s in skill:
        query = query.filter(Candidate.id.in_(db.query(CandidateSkill.candidate_id).join(Skill).filter(func.lower(Skill.name) == s.lower())))
    if min_years is not None:
        query = query.filter(Candidate.total_experience_years >= min_years)
    total = query.count()
    rows = query.order_by(Candidate.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [candidate_dict(c) for c in rows]}


def _get(db: Session, cid: int) -> Candidate:
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "Kandidat tidak ditemukan.")
    return c


@router.get("/{cid}")
def get_candidate(cid: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return candidate_dict(_get(db, cid), full=True)


@router.get("/{cid}/resume")
def download_resume(cid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _get(db, cid)
    if user.role != "admin" and c.uploaded_by != user.id:  # akses dokumen CV dibatasi: admin atau pengunggah
        raise HTTPException(403, "Anda tidak memiliki akses ke dokumen CV ini.")
    path = Path(c.resume.stored_path)
    if not path.exists():
        raise HTTPException(404, "File CV sudah dihapus.")
    audit(db, user.id, "resume_downloaded", "candidate", cid, request_id=request_id(request))
    return FileResponse(path, filename=c.resume.original_filename)


def delete_candidate_files(c: Candidate) -> None:
    try:
        Path(c.resume.stored_path).unlink(missing_ok=True)
    except Exception:
        pass


@router.delete("/{cid}", status_code=204)
def delete_candidate(cid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _get(db, cid)
    if user.role != "admin" and c.uploaded_by != user.id:
        raise HTTPException(403, "Hanya admin atau pengunggah yang dapat menghapus kandidat.")
    delete_candidate_files(c)
    db.delete(c)
    db.commit()
    audit(db, user.id, "candidate_deleted", "candidate", cid, request_id=request_id(request))
