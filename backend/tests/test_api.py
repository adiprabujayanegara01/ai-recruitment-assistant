import io

from tests.conftest import make_docx, make_pdf, read_sample

API = "/api/v1"


def _upload(client, headers, name, kind="pdf", data=None, filename=None, **form):
    text = read_sample("sample_cvs", name)
    data = data if data is not None else (make_pdf(text) if kind == "pdf" else make_docx(text))
    fn = filename or f"{name}.{kind}"
    return client.post(f"{API}/candidates/upload", headers=headers, files={"file": (fn, data, "application/octet-stream")}, data=form)


def _job(client, headers, name, title):
    r = client.post(f"{API}/jobs", headers=headers, json={"title": title, "description": read_sample("sample_jobs", name)})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_docs(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["embedding_model"] == "hashing-v1"
    assert client.get("/openapi.json").status_code == 200


def test_auth_required_and_login_flow(client, admin_headers):
    assert client.get(f"{API}/candidates").status_code == 401
    assert client.get(f"{API}/candidates", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "wrong"}).status_code == 401
    assert client.get(f"{API}/auth/me", headers=admin_headers).json()["role"] == "admin"


def test_role_based_access(client, admin_headers, recruiter_headers):
    assert client.get(f"{API}/admin/metrics", headers=recruiter_headers).status_code == 403
    assert client.post(f"{API}/auth/users", headers=recruiter_headers, json={"name": "X Y", "email": "x@example.com", "password": "longenough1"}).status_code == 403
    assert client.get(f"{API}/admin/metrics", headers=admin_headers).status_code == 200


def test_upload_pdf_and_docx_parse_candidate(client, recruiter_headers):
    r = _upload(client, recruiter_headers, "adi_prabu", "pdf")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Adi Prabu" and "TensorFlow" in body["skills"] and body["education"][0]["level"] == 3
    r2 = _upload(client, recruiter_headers, "sari_wulandari", "docx")
    assert r2.status_code == 201 and r2.json()["experience"][0]["position"] == "Backend Engineer"


def test_upload_validation(client, recruiter_headers):
    assert _upload(client, recruiter_headers, "adi_prabu", data=b"%PDF-1.4 garbage", filename="a.pdf").status_code == 422   # PDF rusak
    assert _upload(client, recruiter_headers, "adi_prabu", data=b"MZ\x90 malware", filename="cv.pdf").status_code == 422     # magic bytes salah
    assert _upload(client, recruiter_headers, "adi_prabu", data=b"hello", filename="cv.exe").status_code == 422              # ekstensi
    assert _upload(client, recruiter_headers, "adi_prabu", data=b"", filename="cv.pdf").status_code == 422                   # kosong
    big = b"%PDF-" + b"0" * (2 * 1024 * 1024)
    r = _upload(client, recruiter_headers, "adi_prabu", data=big, filename="big.pdf")
    assert r.status_code == 422 and "MB" in r.json()["detail"]


def test_job_creation_extracts_requirements(client, recruiter_headers):
    j = _job(client, recruiter_headers, "ai_engineer", "AI Engineer")
    assert "Docker" in j["required_skills"] and j["min_years"] == 2
    assert client.post(f"{API}/jobs", headers=recruiter_headers, json={"title": "x", "description": "short"}).status_code == 422


def test_analyze_response_matches_documented_contract_and_is_explainable(client, recruiter_headers):
    cid = _upload(client, recruiter_headers, "adi_prabu").json()["id"]
    jid = _job(client, recruiter_headers, "ai_engineer", "AI Engineer")["id"]
    r = client.post(f"{API}/matching/analyze", headers=recruiter_headers, json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("candidate_id", "job_id", "match_score", "matched_skills", "missing_skills"):
        assert k in d
    assert "Python" in d["matched_skills"] and "Docker" in d["missing_skills"]
    assert d["analysis"]["relevant_experience"] and d["analysis"]["interview_questions"]
    assert d["versions"]["prompt_version"] and d["versions"]["embedding_model"] == "hashing-v1"
    assert "keputusan akhir" in d["disclaimer"].lower()
    assert all(x["evidence"] for x in d["details"] if x["status"] == "matched")
    assert client.get(f"{API}/matching/{d['id']}", headers=recruiter_headers).json()["match_score"] == d["match_score"]


def test_batch_ranking_and_search(client, recruiter_headers):
    for n in ("sari_wulandari", "budi_santoso", "rendra_pratama"):
        _upload(client, recruiter_headers, n)
    jid = _job(client, recruiter_headers, "backend_engineer", "Backend Engineer")["id"]
    b = client.post(f"{API}/matching/batch", headers=recruiter_headers, json={"job_id": jid}).json()
    scores = [x["match_score"] for x in b["items"]]
    assert b["count"] >= 4 and scores == sorted(scores, reverse=True)
    assert b["items"][0]["candidate_name"] == "Sari Wulandari"
    rk = client.get(f"{API}/jobs/{jid}/ranking", headers=recruiter_headers).json()
    assert rk["items"][0]["rank"] == 1 and rk["items"][0]["candidate_name"] == "Sari Wulandari"
    s = client.get(f"{API}/candidates", headers=recruiter_headers, params={"skill": ["Docker", "Kubernetes"]}).json()
    assert s["total"] >= 1 and all({"Docker", "Kubernetes"} <= set(c["skills"]) for c in s["items"])
    assert client.get(f"{API}/candidates", headers=recruiter_headers, params={"min_years": 8}).json()["total"] >= 1


def test_upload_with_job_id_runs_analysis_immediately(client, recruiter_headers):
    jid = _job(client, recruiter_headers, "data_analyst", "Data Analyst")["id"]
    r = _upload(client, recruiter_headers, "budi_santoso", job_id=str(jid))
    assert r.status_code == 201 and r.json()["analysis"]["match_score"] > 0


def test_report_pdf(client, recruiter_headers):
    cid = _upload(client, recruiter_headers, "dewi_lestari").json()["id"]
    jid = _job(client, recruiter_headers, "ai_engineer", "AI Engineer")["id"]
    rid = client.post(f"{API}/matching/analyze", headers=recruiter_headers, json={"candidate_id": cid, "job_id": jid}).json()
    assert any("instruksi" in w for w in rid["analysis"]["warnings"])     # prompt injection ditandai
    r = client.post(f"{API}/reports/{rid['id']}", headers=recruiter_headers)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 2000
    assert client.post(f"{API}/reports/999999", headers=recruiter_headers).status_code == 404


def test_resume_access_control_and_deletion(client, admin_headers, recruiter_headers):
    cid = _upload(client, admin_headers, "rendra_pratama").json()["id"]
    assert client.get(f"{API}/candidates/{cid}/resume", headers=recruiter_headers).status_code == 403   # bukan pengunggah
    dl = client.get(f"{API}/candidates/{cid}/resume", headers=admin_headers)
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")
    assert client.delete(f"{API}/candidates/{cid}", headers=recruiter_headers).status_code == 403
    assert client.delete(f"{API}/candidates/{cid}", headers=admin_headers).status_code == 204
    assert client.get(f"{API}/candidates/{cid}", headers=admin_headers).status_code == 404


def test_audit_trail_records_key_actions(client, admin_headers):
    actions = {a["action"] for a in client.get(f"{API}/admin/audit", headers=admin_headers, params={"limit": 500}).json()}
    assert {"login_success", "login_failed", "cv_uploaded", "analysis_run", "report_generated", "candidate_deleted"} <= actions
    assert "raw_text" not in str(client.get(f"{API}/admin/audit", headers=admin_headers).json())


def test_monitoring_metrics_and_request_id(client, admin_headers):
    m = client.get(f"{API}/admin/metrics", headers=admin_headers).json()
    assert m["totals"]["analyses"] > 0 and m["latency_ms"]["avg"] is not None and m["by_version"]
    r = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers["X-Request-ID"] == "trace-123"


def test_retention_purge(client, admin_headers, recruiter_headers):
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from app.models import Candidate

    cid = _upload(client, recruiter_headers, "rendra_pratama").json()["id"]
    with SessionLocal() as db:
        db.get(Candidate, cid).created_at = datetime.now(timezone.utc) - timedelta(days=400)
        db.commit()
    r = client.post(f"{API}/admin/retention/purge", headers=admin_headers).json()
    assert r["deleted"] >= 1
    assert client.get(f"{API}/candidates/{cid}", headers=admin_headers).status_code == 404
