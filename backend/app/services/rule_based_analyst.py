"""Analisis tanpa LLM: menyusun output terstruktur yang sama dari hasil matching deterministik.
Dipakai saat LLM tidak dikonfigurasi atau gagal (fallback), sehingga sistem tetap berfungsi penuh offline."""

T = {
    "id": {
        "summary": "Kandidat memenuhi {m} dari {t} skill yang disebut pada JD ({req} wajib teridentifikasi: {rm}/{rt}). "
                   "Pengalaman relevan sekitar {ry} tahun (total {ty} tahun). {edu} Skor {score}% adalah indikator awal berbasis dokumen dan perlu ditinjau recruiter.",
        "edu_ok": "Jenjang pendidikan sesuai dengan kebutuhan JD.",
        "edu_part": "Jenjang pendidikan mendekati kebutuhan JD.",
        "edu_no": "Kesesuaian pendidikan belum teridentifikasi dari CV.",
        "edu_none": "JD tidak menyebutkan syarat pendidikan.",
        "sem": "Kalimat CV memiliki kemiripan semantik {sim} dengan kebutuhan ini.",
        "exact": "Skill disebut langsung dalam pengalaman/proyek kandidat.",
        "declared": "Skill hanya tercantum di daftar skill, belum terlihat pada uraian pengalaman.",
        "implied": "Skill tidak disebut langsung, tetapi tersirat dari teknologi/proyek yang digunakan kandidat.",
        "related": "Kandidat memiliki skill setara ({pick}); perlu dikonfirmasi apakah dapat menggantikan.",
        "strength": "{x}: ditunjukkan pada pengalaman/proyek.",
        "gap": "{x}: belum teridentifikasi pada CV (bukan berarti tidak dikuasai; konfirmasi saat wawancara).",
        "q_matched": "Ceritakan proyek konkret saat Anda memakai {x}. Apa tantangan terbesarnya dan bagaimana Anda mengukur hasilnya?",
        "q_missing": "CV belum menyebut {x}. Apakah Anda punya pengalaman di area ini, atau bagaimana rencana Anda mempelajarinya?",
        "q_related": "Anda berpengalaman dengan {pick}. Bagaimana Anda akan menerapkan pengalaman itu untuk {x}?",
        "q_gen": "Dari pengalaman Anda, hasil apa yang paling relevan dengan posisi {t} dan bagaimana dampaknya bisa diukur?",
    },
    "en": {
        "summary": "The candidate covers {m} of {t} skills named in the JD ({rm}/{rt} required identified). "
                   "Relevant experience is about {ry} years (total {ty}). {edu} The {score}% score is a document-based indicator for recruiter review.",
        "edu_ok": "Education level meets the JD requirement.",
        "edu_part": "Education level is close to the JD requirement.",
        "edu_no": "Education fit could not be identified from the CV.",
        "edu_none": "The JD states no education requirement.",
        "sem": "The CV sentence has {sim} semantic similarity to this requirement.",
        "exact": "The skill is mentioned directly in the candidate's experience/projects.",
        "declared": "The skill only appears in the skills list, not in experience descriptions.",
        "implied": "Not named directly, but implied by the technologies/projects the candidate used.",
        "related": "The candidate has an equivalent skill ({pick}); confirm whether it can substitute.",
        "strength": "{x}: demonstrated in experience/projects.",
        "gap": "{x}: not identified in the CV (not proof of absence; confirm in interview).",
        "q_matched": "Describe a concrete project where you used {x}. What was the hardest challenge and how did you measure the result?",
        "q_missing": "The CV does not mention {x}. Do you have experience here, or how would you plan to learn it?",
        "q_related": "You have experience with {pick}. How would you apply it to {x}?",
        "q_gen": "Which achievement is most relevant to the {t} role, and how was its impact measured?",
    },
}


def build_analysis(outcome: dict, jd: dict, job_title: str, language: str = "id") -> dict:
    t = T.get(language, T["id"])
    det = outcome["details"]
    skills = [d for d in det if d["kind"] == "skill"]
    matched = [d["requirement"] for d in skills if d["status"] == "matched"]
    related = [d for d in skills if d["status"] == "related"]
    missing = [d["requirement"] for d in skills if d["status"] == "not_identified" and d["required"]]

    rel_exp = []
    for d in det:
        if d["evidence"] and d.get("evidence_section") in ("experience", "projects", "certifications", "summary"):
            if d["kind"] == "responsibility":
                expl = t["sem"].format(sim=f"{d['similarity']:.2f}")
            elif d["method"] == "exact":
                expl = t["exact"]
            elif d["method"] == "implied":
                expl = t["implied"]
            elif d["method"].startswith("related"):
                expl = t["related"].format(pick=d["method"].split(":", 1)[1])
            else:
                continue
            rel_exp.append({"requirement": d["requirement"], "evidence": d["evidence"], "explanation": expl})
    rel_exp = sorted(rel_exp, key=lambda x: 0 if x["explanation"] != t["exact"] else 1)[:8]

    edu_b = outcome["breakdown"]["education"]
    if not edu_b["evaluated"]:
        edu_status, edu_txt = None, t["edu_none"]
    elif edu_b["score"] >= 1:
        edu_status, edu_txt = "match", t["edu_ok"]
    elif edu_b["score"] > 0:
        edu_status, edu_txt = "partial", t["edu_part"]
    else:
        edu_status, edu_txt = "not_identified", t["edu_no"]

    req_total = sum(1 for d in skills if d["required"])
    req_hit = sum(1 for d in skills if d["required"] and d["status"] == "matched")
    explanation = t["summary"].format(
        m=len(matched), t=len(skills), req="", rm=req_hit, rt=req_total, ry=outcome["years"]["relevant"],
        ty=outcome["years"]["total"], edu=edu_txt, score=round(outcome["match_score"]),
    )
    strengths = [t["strength"].format(x=d["requirement"]) for d in skills if d["status"] == "matched" and d["method"] in ("exact", "implied")][:5]
    gaps = [t["gap"].format(x=x) for x in missing][:5]
    qs = [t["q_missing"].format(x=x) for x in missing[:3]]
    qs += [t["q_related"].format(pick=d["method"].split(":", 1)[1], x=d["requirement"]) for d in related[:1] if ":" in d["method"]]
    qs += [t["q_matched"].format(x=x) for x in matched[:2]]
    qs.append(t["q_gen"].format(t=job_title))
    return {
        "matched_skills": matched, "missing_skills": missing, "relevant_experience": rel_exp,
        "education_match": {"status": edu_status, "explanation": edu_txt},
        "explanation": explanation, "strengths": strengths, "gaps": gaps, "interview_questions": qs[:6],
    }
