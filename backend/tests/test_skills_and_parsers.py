from datetime import date

from app.services.cv_parser import parse_cv
from app.services.jd_parser import parse_jd
from app.services.skills import get_taxonomy
from tests.conftest import read_sample

TODAY = date(2026, 9, 30)


def test_taxonomy_normalises_aliases_and_avoids_false_positives():
    t = get_taxonomy()
    found = t.find("Trained ML models with Keras, deployed with Docker containers. Go to market. CV parsing pipeline.")
    assert {"Machine Learning", "TensorFlow", "Docker"} <= set(found)
    assert "Go" not in found            # kata biasa "Go"
    assert "Computer Vision" not in found  # "CV" = resume dalam konteks rekrutmen
    assert t.find("pemrosesan bahasa alami dan k8s") == ["NLP", "Kubernetes"]
    assert "Machine Learning" not in t.find("the ml prefix in html")  # akronim hanya HURUF BESAR


def test_cv_parser_english_cv():
    cv = parse_cv(read_sample("sample_cvs", "adi_prabu"), today=TODAY)
    assert cv["personal"]["name"] == "Adi Prabu"
    assert cv["personal"]["email"] == "adi.prabu@example.com"
    assert cv["experience"][0]["position"] == "AI Engineer"
    assert cv["experience"][0]["company"].startswith("PT Nusantara")
    assert cv["experience"][0]["end"] == "2026-09"          # "Present" -> tanggal hari ini
    assert cv["highest_education_level"] == 3
    assert {"Python", "TensorFlow", "Computer Vision", "CNN"} <= set(cv["skills"])
    assert len(cv["projects"]) == 2 and len(cv["certifications"]) == 2
    assert 5.0 <= cv["total_experience_years"] <= 5.5


def test_cv_parser_indonesian_cv():
    cv = parse_cv(read_sample("sample_cvs", "sari_wulandari"), today=TODAY)
    assert cv["experience"][0]["position"] == "Backend Engineer"
    assert cv["education"][0]["level"] == 3 and "Bandung" in cv["education"][0]["institution"]
    assert "PostgreSQL" in cv["skills_declared"] and "Pytest" in cv["skills_inferred"]  # "unit testing" tersirat
    assert cv["certifications"][0]["issuer"] == "Amazon Web Services"
    assert cv["total_experience_years"] > 9


def test_cv_parser_overlapping_experience_not_double_counted():
    text = ("Nama Contoh\n\nExperience\nDev A | PT Satu | Jan 2020 - Dec 2021\n- x\nDev B | PT Dua | Jan 2021 - Dec 2022\n- y\n")
    assert parse_cv(text, today=TODAY)["total_experience_years"] == 3.0


def test_cv_without_sections_does_not_crash():
    cv = parse_cv("Just some random text without any structure at all, nothing to parse here really.", today=TODAY)
    assert cv["experience"] == [] and cv["skills"] == []


def test_jd_parser_required_preferred_and_alternatives():
    jd = parse_jd("AI Engineer", read_sample("sample_jobs", "ai_engineer"))
    assert jd["min_years"] == 2 and jd["min_education_level"] == 3
    assert ["TensorFlow", "PyTorch"] in jd["required_skill_groups"]   # "or" = alternatif, bukan dua kewajiban
    assert "Docker" in jd["required_skills"]
    assert set(jd["preferred_skills"]) >= {"LLM", "RAG", "Kubernetes"}
    assert "LLM" not in jd["required_skills"]
    assert len(jd["responsibilities"]) == 4


def test_jd_parser_indonesian():
    jd = parse_jd("Backend Engineer", read_sample("sample_jobs", "backend_engineer"))
    assert jd["min_years"] == 3 and jd["min_education_level"] == 3
    assert ["FastAPI", "Django"] in jd["required_skill_groups"]
    assert "Kubernetes" in jd["preferred_skills"]
