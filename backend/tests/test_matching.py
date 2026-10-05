from datetime import date

import pytest

from app.services.cv_parser import parse_cv
from app.services.embedding_service import HashingEmbedder, cosine_matrix
from app.services.jd_parser import parse_jd
from app.services.matching_service import analyze_match
from tests.conftest import read_sample

EMB = HashingEmbedder()
CVS = ["adi_prabu", "sari_wulandari", "budi_santoso", "dewi_lestari", "rendra_pratama"]
JDS = {"ai_engineer": "AI Engineer", "backend_engineer": "Backend Engineer", "data_analyst": "Data Analyst"}


@pytest.fixture(scope="module")
def world():
    cvs = {k: parse_cv(read_sample("sample_cvs", k), today=date(2026, 9, 30)) for k in CVS}
    jds = {k: parse_jd(t, read_sample("sample_jobs", k)) for k, t in JDS.items()}
    return cvs, jds


def score(world, cv, jd):
    cvs, jds = world
    return analyze_match(cvs[cv], jds[jd], EMB, cvs[cv]["personal"]["name"])


def test_embedding_vectors_are_normalised_and_similar_text_is_close():
    v = EMB.encode(["Python programming", "Python development", "menyusun kampanye media sosial"])
    assert abs(float((v[0] * v[0]).sum()) - 1) < 1e-4
    sims = cosine_matrix(v[:1], v[1:])[0]
    assert sims[0] > sims[1] + 0.3


def test_each_candidate_ranks_best_for_their_own_field(world):
    assert score(world, "sari_wulandari", "backend_engineer")["match_score"] > score(world, "adi_prabu", "backend_engineer")["match_score"]
    assert score(world, "budi_santoso", "data_analyst")["match_score"] > score(world, "sari_wulandari", "data_analyst")["match_score"]
    assert score(world, "dewi_lestari", "ai_engineer")["match_score"] > score(world, "rendra_pratama", "ai_engineer")["match_score"] + 40


def test_missing_skills_are_reported_as_not_identified_without_evidence(world):
    r = score(world, "adi_prabu", "ai_engineer")
    by = {d["requirement"]: d for d in r["details"]}
    assert by["Docker"]["status"] == "not_identified" and by["Docker"]["evidence"] is None
    assert by["NLP"]["status"] == "not_identified"


def test_matched_skill_has_verbatim_evidence_from_experience(world):
    cvs, _ = world
    r = score(world, "adi_prabu", "ai_engineer")
    d = next(x for x in r["details"] if x["requirement"] == "FastAPI")
    assert d["status"] == "matched" and d["evidence_section"] == "experience"
    assert "FastAPI" in d["evidence"]
    assert d["evidence"].split(":")[0][:20] in cvs["adi_prabu"]["experience"][0]["description"] or "FastAPI" in d["evidence"]


def test_alternative_skill_group_satisfied_by_either(world):
    r = score(world, "adi_prabu", "ai_engineer")  # punya TensorFlow, tidak PyTorch
    d = next(x for x in r["details"] if x["requirement"] in ("TensorFlow", "TensorFlow / PyTorch"))
    assert d["status"] == "matched" and d["requirement"] == "TensorFlow"


def test_related_skill_gets_partial_credit(world):
    cvs, jds = world
    cv = {**cvs["sari_wulandari"], "skills": ["MySQL", "Python"], "skills_declared": ["MySQL", "Python"]}
    r = analyze_match(cv, jds["backend_engineer"], EMB, None)
    d = next(x for x in r["details"] if x["requirement"] == "PostgreSQL")
    assert d["status"] == "related" and d["method"].startswith("related:") and d["credit"] == 0.5


def test_relevant_years_ignore_unrelated_jobs(world):
    r = score(world, "rendra_pratama", "ai_engineer")   # 5 tahun marketing
    assert r["years"]["total"] == 5.0 and r["years"]["relevant"] == 0.0


def test_weights_renormalise_when_component_not_in_jd(world):
    cvs, jds = world
    jd = {**jds["ai_engineer"], "min_education_level": 0, "education_text": None}
    r = analyze_match(cvs["adi_prabu"], jd, EMB, "Adi Prabu")
    b = r["breakdown"]
    assert b["education"]["evaluated"] is False and b["education"]["applied_weight"] == 0
    assert abs(sum(v["applied_weight"] for v in b.values()) - 1.0) < 0.01


def test_score_bounds_and_breakdown_consistency(world):
    for cv in CVS:
        for jd in JDS:
            r = score(world, cv, jd)
            assert 0 <= r["match_score"] <= 100
            recomputed = sum((v["score"] or 0) * v["applied_weight"] for v in r["breakdown"].values()) * 100
            assert abs(recomputed - r["match_score"]) < 0.2


def test_education_field_mismatch_lowers_education_score(world):
    r = score(world, "rendra_pratama", "ai_engineer")
    assert r["breakdown"]["education"]["score"] == 0.5
