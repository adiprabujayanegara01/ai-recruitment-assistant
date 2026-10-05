"""Orkestrasi: parsing -> matching deterministik -> (RAG) -> LLM/rule-based -> simpan + monitoring."""
import logging
import time

from sqlalchemy.orm import Session

from app.ai.versions import MATCHING_ENGINE_VERSION, PARSER_VERSION, PROMPT_VERSION
from app.core.config import get_settings
from app.models import (Candidate, CandidateSkill, Certification, Education, Experience, InferenceLog, Job, JobSkill,
                        MatchingDetail, MatchingResult, Project, Resume, Skill)
from app.services import rag_service
from app.services.cv_parser import parse_cv
from app.services.embedding_service import get_embedder
from app.services.jd_parser import parse_jd
from app.services.llm_service import LLMError, get_llm, llm_analysis, llm_model_name
from app.services.matching_service import analyze_match
from app.services.privacy import detect_injection, redact, strip_injection
from app.services.rule_based_analyst import build_analysis
from app.services.skills import get_taxonomy

log = logging.getLogger(__name__)
DISCLAIMER = ("Hasil ini adalah analisis pendukung keputusan berbasis dokumen. Keputusan akhir ada pada recruiter; "
              "sistem tidak menerima atau menolak kandidat secara otomatis.")


def _skill_row(db: Session, name: str) -> Skill:
    sk = db.query(Skill).filter(Skill.name == name).first()
    if not sk:
        sk = Skill(name=name, category=get_taxonomy().category.get(name, "other"))
        db.add(sk)
        db.flush()
    return sk


def create_candidate_from_text(db: Session, *, text: str, filename: str, stored_path: str, file_type: str, user_id: int | None) -> Candidate:
    parsed = parse_cv(text)
    p = parsed["personal"]
    cand = Candidate(name=p["name"], email=p["email"], phone=p["phone"], location=p["location"],
                     total_experience_years=parsed["total_experience_years"], uploaded_by=user_id)
    cand.resume = Resume(original_filename=filename, stored_path=stored_path, file_type=file_type, raw_text=text,
                         parsed=parsed, parser_version=PARSER_VERSION)
    for e in parsed["education"]:
        cand.educations.append(Education(institution=e["institution"], degree=e["degree"], major=e["major"], level=e["level"]))
    for e in parsed["experience"]:
        cand.experiences.append(Experience(company=e["company"], position=e["position"], description=e["description"],
                                           start=e["start"], end=e["end"], months=e["months"]))
    for c in parsed["certifications"]:
        cand.certifications.append(Certification(name=c["name"], issuer=c["issuer"]))
    for pr in parsed["projects"]:
        cand.projects.append(Project(name=pr["name"], description=pr["description"]))
    for s in parsed["skills"]:
        cand.skills.append(CandidateSkill(skill=_skill_row(db, s)))
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def create_job(db: Session, title: str, description: str, user_id: int | None) -> Job:
    req = parse_jd(title, description)
    job = Job(title=title, description=description, requirements=req, created_by=user_id)
    required = set(req["required_skills"])
    for s in req["required_skills"]:
        job.job_skills.append(JobSkill(skill=_skill_row(db, s), required=True))
    for s in req["preferred_skills"]:
        if s not in required:
            job.job_skills.append(JobSkill(skill=_skill_row(db, s), required=False))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def cv_text_for_llm(parsed: dict, name: str | None) -> str:
    """Teks CV yang boleh dilihat LLM: tanpa nama/kontak/atribut sensitif, dan tanpa nama institusi
    (institusi dapat menjadi proxy bias; yang relevan adalah jenjang & bidang)."""
    lines: list[str] = []
    if parsed.get("summary"):
        lines += ["SUMMARY", parsed["summary"], ""]
    if parsed.get("experience"):
        lines.append("EXPERIENCE")
        for e in parsed["experience"]:
            lines.append(f"{e.get('position') or ''} | {e.get('company') or ''} | {e['start']} - {e['end']}")
            lines += [f"- {l}" for l in (e.get("description") or "").split("\n") if l.strip()]
        lines.append("")
    if parsed.get("education"):
        lines.append("EDUCATION")
        lines += [f"{e.get('degree') or ''} ({e.get('major') or 'bidang tidak teridentifikasi'})" for e in parsed["education"]]
        lines.append("")
    if parsed.get("skills_declared"):
        lines += ["SKILLS", ", ".join(parsed["skills_declared"]), ""]
    if parsed.get("certifications"):
        lines.append("CERTIFICATIONS")
        lines += [f"- {c['name']} ({c['issuer']})" if c.get("issuer") else f"- {c['name']}" for c in parsed["certifications"]]
        lines.append("")
    if parsed.get("projects"):
        lines.append("PROJECTS")
        for p in parsed["projects"]:
            lines.append(f"- {p['name']}: {p['description']}".strip())
    text = redact("\n".join(lines), name)
    return strip_injection(text)[0]


def _findings_text(outcome: dict) -> str:
    out = []
    for d in outcome["details"]:
        ev = f' | evidence: "{d["evidence"]}"' if d["evidence"] else ""
        out.append(f'- [{d["status"]}] ({"required" if d["required"] else "nice-to-have"}) {d["requirement"]}{ev}')
    b = outcome["breakdown"]
    out.append("Score components (computed by the system, do not change): " +
               ", ".join(f"{k}={v['score']}" for k, v in b.items() if v["evaluated"]))
    return "\n".join(out)


def run_analysis(db: Session, candidate: Candidate, job: Job, user_id: int | None, request_id: str | None = None) -> MatchingResult:
    s = get_settings()
    t0 = time.perf_counter()
    emb = get_embedder()
    parsed, jd = candidate.resume.parsed, job.requirements
    warnings: list[str] = []
    if detect_injection(candidate.resume.raw_text):
        warnings.append("CV memuat kalimat yang tampak seperti instruksi kepada AI. Kalimat tersebut diabaikan dan tidak memengaruhi skor.")
    if not parsed.get("experience") and not parsed.get("skills"):
        warnings.append("Ekstraksi CV minim (bagian pengalaman/skill tidak terdeteksi). Periksa format dokumen.")

    outcome = analyze_match(parsed, jd, emb, candidate.name)

    # RAG: konteks perusahaan yang relevan dengan posisi (opsional)
    context, sources = "", []
    hits = rag_service.retrieve(db, f"{job.title}. " + ", ".join(jd.get("required_skills", [])[:8]), k=3, emb=emb)
    if hits:
        context = "\n".join(f"[{h['title']}] {h['text']}" for h in hits)
        sources = [{"title": h["title"], "score": h["score"]} for h in hits]

    src, in_tok, out_tok, unsupported, fallback, err = "rule_based", 0, 0, 0, False, None
    analysis = None
    if get_llm() is not None:
        try:
            skills = [d for d in outcome["details"] if d["kind"] == "skill"]
            matched = [d["requirement"] for d in skills if d["status"] in ("matched", "related")]
            missing = [d["requirement"] for d in skills if d["status"] == "not_identified"]
            job_text = (f"Required skills: {', '.join(jd.get('required_skills', []))}\nNice to have: {', '.join(jd.get('preferred_skills', []))}\n"
                        f"Minimum years: {jd.get('min_years')}\nEducation: {jd.get('education_text')}\n"
                        "Responsibilities:\n" + "\n".join(f"- {r}" for r in jd.get("responsibilities", [])))
            analysis, res, unsupported = llm_analysis(job.title, job_text, _findings_text(outcome),
                                                      cv_text_for_llm(parsed, candidate.name), context, matched, missing, s.output_language)
            src, in_tok, out_tok = "llm", res.input_tokens, res.output_tokens
        except LLMError as e:
            log.warning("LLM gagal, memakai analisis rule-based: %s", e)
            fallback, err = True, str(e)[:500]
            warnings.append("Layanan LLM tidak tersedia; penjelasan dibuat dengan analisis berbasis aturan.")
    if analysis is None:
        analysis = build_analysis(outcome, jd, job.title, s.output_language)
    analysis.update({"source": src, "unsupported_claims": unsupported, "warnings": warnings, "context_sources": sources})

    versions = {"embedding_model": emb.name, "llm_model": llm_model_name() if src == "llm" else "rule-based-v1",
                "prompt_version": PROMPT_VERSION, "matching_engine": MATCHING_ENGINE_VERSION,
                "parser_version": candidate.resume.parser_version}
    result = MatchingResult(candidate_id=candidate.id, job_id=job.id, match_score=outcome["match_score"],
                            summary=analysis["explanation"] or "", breakdown={**outcome["breakdown"], "_years": outcome["years"]},
                            analysis=analysis, versions=versions)
    for d in outcome["details"]:
        result.details.append(MatchingDetail(skill=d["requirement"], kind=d["kind"], required=d["required"], evidence=d["evidence"],
                                             similarity=d["similarity"], status=d["status"], method=d["method"],
                                             evidence_section=d["evidence_section"]))
    db.add(result)
    db.add(InferenceLog(request_id=request_id, candidate_id=candidate.id, job_id=job.id, embedding_model=emb.name,
                        llm_model=versions["llm_model"], matching_engine_version=MATCHING_ENGINE_VERSION,
                        prompt_version=PROMPT_VERSION, processing_ms=round((time.perf_counter() - t0) * 1000, 1),
                        input_tokens=in_tok, output_tokens=out_tok, unsupported_claims=unsupported, llm_fallback=fallback, error=err))
    db.commit()
    db.refresh(result)
    return result


def result_to_dict(r: MatchingResult, with_details: bool = True) -> dict:
    a = r.analysis or {}
    d = {
        "id": r.id, "candidate_id": r.candidate_id, "job_id": r.job_id,
        "candidate_name": r.candidate.name if r.candidate else None,
        "job_title": r.job.title if r.job else None,
        "match_score": r.match_score,
        "matched_skills": a.get("matched_skills", []), "missing_skills": a.get("missing_skills", []),
        "summary": r.summary, "created_at": r.created_at.isoformat() if r.created_at else None,
        "disclaimer": DISCLAIMER,
    }
    if with_details:
        d.update({
            "breakdown": {k: v for k, v in (r.breakdown or {}).items() if not k.startswith("_")},
            "years": (r.breakdown or {}).get("_years"),
            "details": [{"requirement": x.skill, "kind": x.kind, "required": x.required, "evidence": x.evidence,
                         "similarity": x.similarity, "status": x.status, "method": x.method,
                         "evidence_section": x.evidence_section} for x in r.details],
            "analysis": {k: a.get(k) for k in ("relevant_experience", "education_match", "explanation", "strengths", "gaps",
                                               "interview_questions", "source", "unsupported_claims", "warnings", "context_sources")},
            "versions": r.versions,
        })
    return d
