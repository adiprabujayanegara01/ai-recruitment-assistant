from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_user, request_id, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import KnowledgeDocument, User
from app.schemas import AskIn
from app.services import rag_service
from app.services.audit import audit
from app.services.document_reader import FileValidationError, extract_text, extract_text_from_plain, validate_upload

router = APIRouter(prefix="/knowledge", tags=["knowledge-base (RAG)"])


@router.post("", status_code=201)
async def add_document(request: Request, title: str = Form(...), category: str = Form("general"), text: str | None = Form(None),
                       file: UploadFile | None = File(None), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Tambah dokumen ke knowledge base (competency framework, kebijakan rekrutmen, standar job requirement)."""
    if file is not None:
        data = await file.read()
        name = (file.filename or "").lower()
        try:
            if name.endswith((".txt", ".md")):
                if len(data) > get_settings().max_upload_mb * 1024 * 1024:
                    raise FileValidationError("Ukuran file terlalu besar.")
                content = extract_text_from_plain(data)
            else:
                content = extract_text(data, validate_upload(name, data))
        except FileValidationError as e:
            raise HTTPException(422, str(e))
    elif text:
        content = text
    else:
        raise HTTPException(422, "Sertakan file atau text.")
    if len(content.strip()) < 30:
        raise HTTPException(422, "Isi dokumen terlalu pendek.")
    doc = rag_service.ingest(db, title.strip(), category.strip() or "general", content, user.id)
    audit(db, user.id, "knowledge_added", "knowledge_document", doc.id, {"chunks": len(doc.chunks)}, request_id(request))
    return {"id": doc.id, "title": doc.title, "category": doc.category, "chunks": len(doc.chunks)}


@router.get("")
def list_documents(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "title": d.title, "category": d.category, "chunks": len(d.chunks), "created_at": d.created_at.isoformat()}
            for d in db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()]


@router.delete("/{did}", status_code=204)
def delete_document(did: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, did)
    if not d:
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    db.delete(d)
    db.commit()
    audit(db, user.id, "knowledge_deleted", "knowledge_document", did, request_id=request_id(request))


@router.post("/ask")
def ask(body: AskIn, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Tanya jawab berbasis knowledge base. Jawaban selalu disertai sumber; bila tidak ada, dinyatakan tidak ditemukan."""
    out = rag_service.ask(db, body.question, get_settings().output_language)
    if not out["found"]:
        out["message"] = "Informasi ini tidak ditemukan di knowledge base perusahaan."
    return out
