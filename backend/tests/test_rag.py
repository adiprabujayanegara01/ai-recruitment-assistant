from app.services.rag_service import chunk_text

API = "/api/v1"
POLICY = """Kerangka kompetensi AI Engineer

Level Junior: mampu membangun model machine learning dasar dan mengevaluasinya dengan metrik yang tepat.

Level Senior: memimpin desain sistem ML di produksi, mencakup monitoring, versioning model, dan deployment memakai Docker.

Kebijakan rekrutmen

Semua kandidat harus dievaluasi berdasarkan kompetensi yang relevan dengan pekerjaan. Atribut pribadi seperti usia dan agama tidak boleh digunakan.
Wawancara teknis dilakukan oleh minimal dua orang penilai."""


def test_chunking_respects_size_and_keeps_all_text():
    text = "\n\n".join(f"Paragraf nomor {i}. " + "kata " * 60 for i in range(10))
    chunks = chunk_text(text, size=500)
    assert all(len(c) <= 700 for c in chunks) and len(chunks) > 3
    assert "nomor 9" in chunks[-1]


def test_knowledge_base_lifecycle_and_grounded_answers(client, admin_headers, recruiter_headers):
    assert client.post(f"{API}/knowledge", headers=recruiter_headers, data={"title": "x", "text": POLICY}).status_code == 403
    r = client.post(f"{API}/knowledge", headers=admin_headers, data={"title": "Kompetensi & Kebijakan", "category": "policy", "text": POLICY})
    assert r.status_code == 201 and r.json()["chunks"] >= 1
    a = client.post(f"{API}/knowledge/ask", headers=recruiter_headers, json={"question": "Apa yang diharapkan dari level Senior AI Engineer?"}).json()
    assert a["found"] and a["sources"] and "Docker" in a["sources"][0]["text"] and a["mode"] == "extractive"
    n = client.post(f"{API}/knowledge/ask", headers=recruiter_headers, json={"question": "xyzzy qwerty plugh"}).json()
    assert n["found"] is False and "tidak ditemukan" in n["message"].lower()
    docs = client.get(f"{API}/knowledge", headers=recruiter_headers).json()
    assert docs and client.delete(f"{API}/knowledge/{docs[0]['id']}", headers=admin_headers).status_code == 204


def test_company_context_is_used_in_analysis(client, admin_headers):
    from tests.conftest import make_pdf, read_sample

    client.post(f"{API}/knowledge", headers=admin_headers, data={"title": "Standar AI Engineer", "text": POLICY})
    cid = client.post(f"{API}/candidates/upload", headers=admin_headers, files={"file": ("a.pdf", make_pdf(read_sample("sample_cvs", "adi_prabu")), "application/pdf")}).json()["id"]
    jid = client.post(f"{API}/jobs", headers=admin_headers, json={"title": "AI Engineer", "description": read_sample("sample_jobs", "ai_engineer")}).json()["id"]
    r = client.post(f"{API}/matching/analyze", headers=admin_headers, json={"candidate_id": cid, "job_id": jid}).json()
    assert r["analysis"]["context_sources"] and r["analysis"]["context_sources"][0]["title"] == "Standar AI Engineer"
