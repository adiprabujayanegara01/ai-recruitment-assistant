from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, user_id: int | None, action: str, entity: str | None = None, entity_id: int | None = None,
          detail: dict | None = None, request_id: str | None = None) -> None:
    """Catat aktivitas penting (upload, analysis, report, delete, login). Tidak menyimpan isi CV."""
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail or {}, request_id=request_id))
    db.commit()
