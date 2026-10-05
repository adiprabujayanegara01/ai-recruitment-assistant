import io
import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="airecruit-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "UPLOAD_DIR": f"{_tmp}/uploads", "EMBEDDING_BACKEND": "hashing",
    "LLM_PROVIDER": "none", "ADMIN_EMAIL": "admin@example.com", "ADMIN_PASSWORD": "admin-pass-123", "MAX_UPLOAD_MB": "1",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data"


def read_sample(kind: str, name: str) -> str:
    return (DATA / kind / f"{name}.txt").read_text(encoding="utf-8")


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            c.showPage(); y = 800
        c.setFont("Helvetica", 9)
        c.drawString(40, y, line[:130])
        y -= 12
    c.save()
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    from docx import Document

    d = Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def recruiter_headers(client, admin_headers):
    client.post("/api/v1/auth/users", headers=admin_headers,
                json={"name": "Rina Recruiter", "email": "rina@example.com", "password": "recruiter-pass-1", "role": "recruiter"})
    r = client.post("/api/v1/auth/login", json={"email": "rina@example.com", "password": "recruiter-pass-1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
