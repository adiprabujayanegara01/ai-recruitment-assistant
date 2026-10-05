"""Isi data demo: lowongan, kandidat (PDF dibuat dari sample teks), knowledge base, lalu analisis batch.
Jalankan dari folder backend/:  python -m scripts.seed"""
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.main import init_db  # noqa: E402
from app.models import Candidate, Job, KnowledgeDocument  # noqa: E402
from app.services import analysis_service as svc  # noqa: E402
from app.services import rag_service  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data"
TITLES = {"ai_engineer": "AI Engineer", "backend_engineer": "Backend Engineer", "data_analyst": "Data Analyst"}


def pdf_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            c.showPage(); y = 800
        c.setFont("Helvetica", 9); c.drawString(40, y, line[:130]); y -= 12
    c.save()
    return buf.getvalue()


def main() -> None:
    init_db()
    up = get_settings().upload_path
    with SessionLocal() as db:
        if db.query(Candidate).count() or db.query(Job).count():
            print("Database sudah berisi data; seed dilewati."); return
        jobs = [svc.create_job(db, TITLES[p.stem], p.read_text(encoding="utf-8"), None) for p in sorted((DATA / "sample_jobs").glob("*.txt"))]
        cands = []
        for p in sorted((DATA / "sample_cvs").glob("*.txt")):
            text = p.read_text(encoding="utf-8")
            path = up / f"{uuid.uuid4().hex}.pdf"
            path.write_bytes(pdf_bytes(text))
            cands.append(svc.create_candidate_from_text(db, text=text, filename=f"{p.stem}.pdf", stored_path=str(path), file_type="pdf", user_id=None))
        for k in (DATA / "knowledge").glob("*.md"):
            if not db.query(KnowledgeDocument).filter_by(title=k.stem).first():
                rag_service.ingest(db, k.stem.replace("_", " ").title(), "policy", k.read_text(encoding="utf-8"), None)
        for j in jobs:
            for c in cands:
                svc.run_analysis(db, c, j, None)
        print(f"Seed selesai: {len(jobs)} lowongan, {len(cands)} kandidat, {len(jobs) * len(cands)} analisis.")


if __name__ == "__main__":
    main()
