from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id
from app.core.database import get_db
from app.models import MatchingResult, User
from app.services.audit import audit
from app.services.report_service import build_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/{rid}")
def generate(rid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(MatchingResult, rid)
    if not r:
        raise HTTPException(404, "Hasil matching tidak ditemukan.")
    pdf = build_report_pdf(r)
    audit(db, user.id, "report_generated", "matching_result", rid, request_id=request_id(request))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="report-{rid}.pdf"'})
