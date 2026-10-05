import pytest

from app.services import analysis_service, llm_service
from app.services.llm_service import LLMError, LLMResult, parse_json_object, validate_analysis

CV = "Developed a CNN-based tomato classification system using TensorFlow. Built REST API services with FastAPI."


def test_parse_json_object_handles_fences_and_noise():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        parse_json_object("no json here")


def test_groundedness_guard_drops_fabricated_evidence_and_skills():
    raw = {
        "matched_skills": ["TensorFlow", "Kubernetes"],  # Kubernetes tidak didukung
        "missing_skills": ["Docker"],
        "relevant_experience": [
            {"requirement": "Computer Vision", "evidence": "Developed a CNN-based tomato classification system using TensorFlow", "explanation": "ok"},
            {"requirement": "Leadership", "evidence": "Led a team of 20 engineers at Google", "explanation": "fabricated"},
        ],
        "education_match": {"status": "match", "explanation": "ok"},
        "explanation": "Kandidat cocok.", "strengths": ["a"], "gaps": [], "interview_questions": ["q?"],
    }
    out, bad = validate_analysis(raw, CV, matched=["TensorFlow"], missing=["Docker"])
    assert len(out["relevant_experience"]) == 1 and "tomato" in out["relevant_experience"][0]["evidence"]
    assert bad == 2                                    # 1 kutipan palsu + 1 skill tanpa dukungan
    assert out["matched_skills"] == ["TensorFlow"]      # daftar skill selalu dari hasil deterministik


def test_invalid_education_status_is_dropped():
    out, _ = validate_analysis({"education_match": {"status": "genius"}, "explanation": "x"}, CV, [], [])
    assert out["education_match"]["status"] is None


def test_llm_failure_falls_back_to_rule_based(client, admin_headers, monkeypatch):
    from tests.conftest import make_pdf, read_sample

    monkeypatch.setattr(analysis_service, "get_llm", lambda: object())
    def boom(*a, **k):
        raise LLMError("timeout")
    monkeypatch.setattr(analysis_service, "llm_analysis", boom)
    files = {"file": ("cv.pdf", make_pdf(read_sample("sample_cvs", "adi_prabu")), "application/pdf")}
    cid = client.post("/api/v1/candidates/upload", headers=admin_headers, files=files).json()["id"]
    jid = client.post("/api/v1/jobs", headers=admin_headers, json={"title": "AI Engineer", "description": read_sample("sample_jobs", "ai_engineer")}).json()["id"]
    r = client.post("/api/v1/matching/analyze", headers=admin_headers, json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 200
    a = r.json()["analysis"]
    assert a["source"] == "rule_based" and any("LLM" in w for w in a["warnings"])
    m = client.get("/api/v1/admin/metrics", headers=admin_headers).json()
    assert m["llm_fallbacks"] >= 1


def test_llm_success_path_validates_output(client, admin_headers, monkeypatch):
    from tests.conftest import make_pdf, read_sample

    def fake(job_title, job_text, findings, cv_text, ctx, matched, missing, language="id"):
        assert "adi.prabu@example.com" not in cv_text and "Adi Prabu" not in cv_text   # PII tidak sampai ke LLM
        assert "Universitas Gadjah Mada" not in cv_text                               # institusi tidak dikirim
        return ({"matched_skills": matched, "missing_skills": missing, "relevant_experience": [],
                 "education_match": {"status": "match", "explanation": "ok"}, "explanation": "Ringkasan LLM.",
                 "strengths": [], "gaps": [], "interview_questions": ["q?"]}, LLMResult("{}", 900, 300), 1)
    monkeypatch.setattr(analysis_service, "get_llm", lambda: object())
    monkeypatch.setattr(analysis_service, "llm_analysis", fake)
    files = {"file": ("cv.pdf", make_pdf(read_sample("sample_cvs", "adi_prabu")), "application/pdf")}
    cid = client.post("/api/v1/candidates/upload", headers=admin_headers, files=files).json()["id"]
    jid = client.post("/api/v1/jobs", headers=admin_headers, json={"title": "AI Engineer", "description": read_sample("sample_jobs", "ai_engineer")}).json()["id"]
    a = client.post("/api/v1/matching/analyze", headers=admin_headers, json={"candidate_id": cid, "job_id": jid}).json()
    assert a["analysis"]["source"] == "llm" and a["analysis"]["unsupported_claims"] == 1
    assert client.get("/api/v1/admin/metrics", headers=admin_headers).json()["tokens"]["input"] >= 900
