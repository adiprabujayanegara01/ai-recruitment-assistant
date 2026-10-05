"""Matching engine (bagian 8): hybrid eksak/alias + semantic embedding + skor berbobot.

Prinsip desain:
* Skor dihitung DETERMINISTIK dan dapat diaudit; LLM hanya menjelaskan, tidak menentukan skor.
* Setiap requirement mendapat evidence (kutipan dari CV) atau status "not_identified"; tidak ada tebakan.
* "Not identified" berarti tidak ditemukan di dokumen, bukan berarti kandidat tidak punya kemampuan tsb.
* Komponen yang tidak dapat dievaluasi (JD tidak menyebutnya) dikeluarkan dan bobot dinormalisasi ulang.
"""
from dataclasses import dataclass, field

import numpy as np

from app.ai.versions import MATCHING_ENGINE_VERSION
from app.core.config import get_settings
from app.services.embedding_service import Embedder, cosine_matrix
from app.services.privacy import redact, strip_injection
from app.services.skills import get_taxonomy, implied, related_skills

CREDIT = {"exact_demonstrated": 1.0, "implied": 0.9, "exact_declared": 0.85, "related": 0.5, "semantic_matched": 0.8, "semantic_related": 0.4}
OVERLAP_BONUS = 0.12  # hybrid retrieval: bonus bila requirement & evidence berbagi konsep taxonomy


@dataclass
class Unit:
    text: str
    section: str  # experience | projects | certifications | summary | skills
    skills: set[str] = field(default_factory=set)  # eksplisit disebut
    concepts: set[str] = field(default_factory=set)  # eksplisit + tersirat


def build_units(parsed: dict, name: str | None) -> list[Unit]:
    tax = get_taxonomy()
    raw: list[tuple[str, str]] = []
    for e in parsed.get("experience", []):
        for line in (e.get("description") or "").split("\n"):
            if line.strip():
                raw.append((line.strip(), "experience"))
    for p in parsed.get("projects", []):
        desc = (p.get("description") or "").replace("\n", " ")
        raw.append((f"{p['name']}: {desc}" if desc else p["name"], "projects"))
    for c in parsed.get("certifications", []):
        raw.append((f"{c['name']} ({c['issuer']})" if c.get("issuer") else c["name"], "certifications"))
    if parsed.get("summary"):
        raw.append((parsed["summary"], "summary"))
    if parsed.get("skills_declared"):
        raw.append(("Skills: " + ", ".join(parsed["skills_declared"]), "skills"))
    units = []
    for text, section in raw:
        text, _ = strip_injection(redact(text, name))
        if not text.strip():
            continue
        found = set(tax.find(text))
        concepts = set(found)
        for f in found:
            concepts.update(implied(f))
        units.append(Unit(text, section, found, concepts))
    return units


_FIELD_GROUPS = {
    "computing": r"informatic|informatika|computer|komputer|information (?:technology|system)|teknologi informasi|sistem informasi|software|rekayasa perangkat|data science|sains data|artificial intelligence|kecerdasan buatan",
    "stats_math": r"statistic|statistik|mathematic|matematika|actuarial|aktuaria",
    "engineering": r"engineering|teknik|elektro|electrical|industri|industrial",
}


def _field_groups(text: str) -> set[str]:
    import re as _re
    return {g for g, rx in _FIELD_GROUPS.items() if _re.search(rx, text or "", _re.IGNORECASE)}


def _status(sim: float, emb: Embedder) -> str:
    if sim >= emb.matched_threshold:
        return "matched"
    if sim >= emb.related_threshold:
        return "related"
    return "not_identified"


def _best_unit(req_text: str, req_vec: np.ndarray, units: list[Unit], unit_vecs: np.ndarray, allowed: set[str] | None = None):
    """Unit dengan skor hybrid tertinggi. Mengembalikan (unit, cosine, hybrid)."""
    tax = get_taxonomy()
    req_concepts = set(tax.find(req_text))
    for c in list(req_concepts):
        req_concepts.update(implied(c))
    best, best_score, best_cos = None, -1.0, 0.0
    if not units:
        return None, 0.0, 0.0
    cos = cosine_matrix(req_vec[None, :], unit_vecs)[0]
    for i, u in enumerate(units):
        if allowed and u.section not in allowed:
            continue
        overlap = len(req_concepts & u.concepts)
        bonus = OVERLAP_BONUS * min(1.0, overlap / 2) if overlap else 0.0
        score = float(cos[i]) + bonus
        if score > best_score:
            best, best_score, best_cos = u, score, float(cos[i])
    return best, best_cos, best_score


def _union_months(spans: list[tuple[int, int]]) -> int:
    total, cur_s, cur_e = 0, None, None
    for s, e in sorted(spans):
        if cur_e is None or s > cur_e + 1:
            if cur_e is not None:
                total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s + 1
    return total


def relevant_years(parsed: dict, jd_skills: set[str]) -> float:
    """Tahun pengalaman yang deskripsinya menyentuh minimal satu skill JD (bukan sekadar total tahun kerja)."""
    tax = get_taxonomy()
    spans = []
    for e in parsed.get("experience", []):
        text = f"{e.get('position') or ''} {e.get('description') or ''}"
        found = set(tax.find(text))
        for f in list(found):
            found.update(implied(f))
        if not jd_skills or (found & jd_skills):
            sy, sm = map(int, e["start"].split("-"))
            ey, em = map(int, e["end"].split("-"))
            spans.append((sy * 12 + sm, ey * 12 + em))
    return round(_union_months(spans) / 12, 1)


def _skill_item(group: list[str], required: bool, cand_skills: set[str], units: list[Unit], unit_vecs, emb: Embedder) -> dict:
    tax = get_taxonomy()
    best = None  # (credit, member, method, unit, sim)
    for member in group:
        canon = tax.canonical(member) or member
        cred, method, unit, sim = 0.0, "none", None, 0.0
        cs = {tax.canonical(s) or s for s in cand_skills}
        if canon in cs or canon.lower() in {s.lower() for s in cs}:
            # Evidence terkuat = pengalaman kerja > proyek > sertifikasi. Ringkasan (summary) hanya klaim, bukan bukti.
            body = [u for u in units if u.section in ("experience", "projects", "certifications")]
            with_ctx = [u for u in body if canon in u.skills]
            implied_ctx = [u for u in body if canon in u.concepts and canon not in u.skills]
            if with_ctx:
                for sec in ("experience", "projects", "certifications"):
                    pick = [u for u in with_ctx if u.section == sec]
                    if pick:
                        unit = pick[0]
                        break
                cred, method = CREDIT["exact_demonstrated"], "exact"
            elif implied_ctx:  # mis. "Machine Learning" tersirat dari proyek scikit-learn
                unit, cred, method = implied_ctx[0], CREDIT["implied"], "implied"
            else:
                skills_unit = [u for u in units if u.section == "skills"]
                summary_unit = [u for u in units if u.section == "summary" and canon in u.skills]
                unit = skills_unit[0] if skills_unit else (summary_unit[0] if summary_unit else None)
                cred, method = CREDIT["exact_declared"], "declared"
            sim = 1.0
        else:
            rel = related_skills(canon) & cs
            if rel:
                pick = sorted(rel)[0]
                cand_units = [u for u in units if pick in u.skills and u.section != "skills"] or [u for u in units if pick in u.skills]
                unit = cand_units[0] if cand_units else None
                q = emb.encode([canon])[0]
                if unit is not None:
                    sim = float(cosine_matrix(q[None, :], emb.encode([unit.text]))[0, 0])
                cred, method = CREDIT["related"], f"related:{pick}"
            elif tax.canonical(member) is None and units:  # skill di luar taxonomy -> semantic + lexical
                lex = [u for u in units if member.lower() in u.text.lower()]
                if lex:
                    unit, sim, cred, method = lex[0], 1.0, CREDIT["exact_demonstrated"], "exact"
                else:
                    q = emb.encode([member])[0]
                    unit, sim, hybrid = _best_unit(member, q, units, unit_vecs)
                    st = _status(sim, emb)
                    if st == "matched":
                        cred, method = CREDIT["semantic_matched"], "semantic"
                    elif st == "related":
                        cred, method = CREDIT["semantic_related"], "semantic"
                    else:
                        unit = None
        if best is None or cred > best[0]:
            best = (cred, member, method, unit, sim)
    cred, member, method, unit, sim = best
    if cred >= 0.85:
        status = "matched"
    elif cred > 0:
        status = "related"
    else:
        status = "not_identified"
    label = member if cred > 0 else " / ".join(group)
    return {
        "requirement": label, "kind": "skill", "required": required, "status": status, "method": method,
        "similarity": round(max(sim, 0.0), 3), "credit": cred,
        "evidence": unit.text if unit and cred > 0 else None,
        "evidence_section": unit.section if unit and cred > 0 else None,
    }


def analyze_match(parsed_cv: dict, jd: dict, emb: Embedder, name: str | None = None) -> dict:
    s = get_settings()
    tax = get_taxonomy()
    units = build_units(parsed_cv, name)
    unit_vecs = emb.encode([u.text for u in units])
    cand_skills = set(parsed_cv.get("skills", []))
    details: list[dict] = []

    # ---------- Skill ----------
    groups_req = jd.get("required_skill_groups") or [[x] for x in jd.get("required_skills", [])]
    for g in groups_req:
        details.append(_skill_item(g, True, cand_skills, units, unit_vecs, emb))
    for sk in jd.get("preferred_skills", []):
        details.append(_skill_item([sk], False, cand_skills, units, unit_vecs, emb))
    skill_items = [d for d in details if d["kind"] == "skill"]
    skill_score = None
    if skill_items:
        w = [1.0 if d["required"] else 0.5 for d in skill_items]
        skill_score = sum(wi * d["credit"] for wi, d in zip(w, skill_items)) / sum(w)

    # ---------- Responsibilities (evidence semantic) ----------
    resp_reqs = jd.get("responsibilities") or jd.get("experience_requirements") or []
    resp_reqs = resp_reqs[:12]
    resp_items: list[dict] = []
    if resp_reqs:
        rvecs = emb.encode(resp_reqs)
        for text, rv in zip(resp_reqs, rvecs):
            u, cos, hybrid = _best_unit(text, rv, units, unit_vecs, allowed={"experience", "projects", "summary", "certifications"})
            st = _status(hybrid, emb) if u else "not_identified"
            credit = 1.0 if st == "matched" else 0.5 if st == "related" else 0.0
            resp_items.append({
                "requirement": text, "kind": "responsibility", "required": True, "status": st, "method": "semantic",
                "similarity": round(min(max(hybrid, 0.0), 1.0), 3), "credit": credit,
                "evidence": u.text if u and credit > 0 else None,
                "evidence_section": u.section if u and credit > 0 else None,
            })
    details.extend(resp_items)

    # ---------- Experience ----------
    jd_skill_set = set(jd.get("required_skills", [])) | set(jd.get("preferred_skills", []))
    jd_concepts = set(jd_skill_set)
    total_years = float(parsed_cv.get("total_experience_years") or 0)
    rel_years = relevant_years(parsed_cv, jd_concepts)
    parts, exp_notes = [], []
    if jd.get("min_years"):
        ys = min(1.0, rel_years / jd["min_years"])
        parts.append(ys)
        exp_notes.append(f"{rel_years} thn relevan (total {total_years} thn) vs minimal {jd['min_years']} thn")
    if resp_items:
        rs = sum(d["credit"] for d in resp_items) / len(resp_items)
        parts.append(rs)
        exp_notes.append(f"{sum(d['status'] != 'not_identified' for d in resp_items)}/{len(resp_items)} tanggung jawab punya evidence")
    exp_score = sum(parts) / len(parts) if parts else None

    # ---------- Education ----------
    edu_score, edu_note = None, ""
    req_lv, cand_lv = jd.get("min_education_level", 0), int(parsed_cv.get("highest_education_level") or 0)
    if req_lv:
        edu_score = 1.0 if cand_lv >= req_lv else 0.5 if cand_lv == req_lv - 1 and cand_lv > 0 else 0.0
        edu_note = f"level kandidat {cand_lv or 'tidak teridentifikasi'} vs minimal {req_lv}"
        jd_fields = _field_groups(jd.get("education_text") or "")
        cand_text = " ".join(f"{e.get('degree') or ''} {e.get('major') or ''}" for e in parsed_cv.get("education", []))
        if edu_score and jd_fields and not (jd_fields & _field_groups(cand_text)):
            edu_score *= 0.5  # jenjang terpenuhi tetapi bidang studi tidak sejalan dengan yang disebut JD
            edu_note += "; bidang studi berbeda dari yang disebut JD"
        elif edu_score and jd_fields:
            edu_note += "; bidang studi relevan"

    # ---------- Project ----------
    proj_score, proj_note = None, ""
    if skill_items or resp_items:
        pu = [u for u in units if u.section in ("projects", "certifications")]
        pvecs = emb.encode([u.text for u in pu]) if pu else np.zeros((0, emb.dim))
        parts_p = []
        req_groups_only = [g for g in groups_req]
        if req_groups_only:
            hit = 0
            for g in req_groups_only:
                canon = {tax.canonical(m) or m for m in g}
                if any(canon & u.skills for u in pu):
                    hit += 1
            parts_p.append(hit / len(req_groups_only))
        if resp_reqs:
            rvecs = emb.encode(resp_reqs)
            cr = []
            for text, rv in zip(resp_reqs, rvecs):
                u, cos, hybrid = _best_unit(text, rv, pu, pvecs)
                st = _status(hybrid, emb) if u else "not_identified"
                cr.append(1.0 if st == "matched" else 0.5 if st == "related" else 0.0)
            parts_p.append(sum(cr) / len(cr))
        proj_score = sum(parts_p) / len(parts_p) if parts_p else 0.0
        proj_note = f"{len([u for u in pu if u.section == 'projects'])} proyek, {len([u for u in pu if u.section == 'certifications'])} sertifikasi dianalisis"
        if not pu:
            proj_score, proj_note = 0.0, "tidak ada proyek/sertifikasi teridentifikasi"

    comps = {
        "skill": (skill_score, s.w_skill, f"{sum(d['credit'] >= 0.85 for d in skill_items)}/{len(skill_items)} skill teridentifikasi"),
        "experience": (exp_score, s.w_experience, "; ".join(exp_notes)),
        "education": (edu_score, s.w_education, edu_note),
        "project": (proj_score, s.w_project, proj_note),
    }
    total_w = sum(w for sc, w, _ in comps.values() if sc is not None)
    breakdown, final = {}, 0.0
    for k, (sc, w, note) in comps.items():
        applied = (w / total_w) if (sc is not None and total_w) else 0.0
        breakdown[k] = {
            "score": None if sc is None else round(sc, 3), "weight": w, "applied_weight": round(applied, 3),
            "evaluated": sc is not None, "note": note or ("tidak disebut di JD" if sc is None else ""),
        }
        final += (sc or 0.0) * applied
    return {
        "match_score": round(final * 100, 1),
        "breakdown": breakdown,
        "details": details,
        "candidate_skills": sorted(cand_skills),
        "years": {"total": total_years, "relevant": rel_years},
        "engine_version": MATCHING_ENGINE_VERSION,
        "embedding_model": emb.name,
    }
