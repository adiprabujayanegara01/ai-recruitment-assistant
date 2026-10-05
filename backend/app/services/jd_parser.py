"""Job Description parser: requirement, skill wajib vs nilai tambah, pengalaman, pendidikan, tanggung jawab."""
import re

from app.services.cv_parser import EDU_LEVELS, _strip_bullet
from app.services.skills import get_taxonomy
from app.utils.text import sentences

JD_SECTIONS = {
    "responsibilities": r"responsibilities|key responsibilities|job description|job desc|what you(?:'ll| will) do|"
    r"the role|role overview|tanggung jawab|deskripsi pekerjaan|tugas|lingkup pekerjaan",
    "requirements": r"requirements?|qualifications?|minimum qualifications|what we(?:'re| are) looking for|"
    r"who you are|kualifikasi|persyaratan|syarat|yang kami cari|kriteria",
    "preferred": r"nice to have|preferred(?: qualifications| skills)?|bonus(?: points)?|good to have|plus|"
    r"nilai (?:tambah|plus)|diutamakan|keunggulan|lebih disukai",
    "benefits": r"benefits?|what we offer|perks|kami menawarkan|fasilitas|tentang perusahaan|about us|about the company",
}
_RES = {k: re.compile(rf"^(?:{v})$", re.IGNORECASE) for k, v in JD_SECTIONS.items()}
YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|–\s*\d{1,2})?\s*(?:years?|yrs?|tahun|thn)", re.IGNORECASE)


def _heading(line: str) -> str | None:
    clean = re.sub(r"[:\-–—_|#*]+", " ", line).strip()
    clean = re.sub(r"\s+", " ", clean)
    if not clean or len(clean) > 50:
        return None
    for k, rx in _RES.items():
        if rx.match(clean):
            return k
    return None


_OR = re.compile(r"\s+(?:or|atau|and/or|/)\s+|/", re.IGNORECASE)


def _skill_groups(text: str) -> list[list[str]]:
    """Skill yang dipisah 'or/atau' dianggap alternatif (satu grup): 'TensorFlow or PyTorch'."""
    tax = get_taxonomy()
    singles: list[str] = []
    groups: list[list[str]] = []
    for line in text.split("\n"):
        found = tax.find(line)
        if not found:
            continue
        segs = [tax.find(seg) for seg in re.split(r"\s+(?:or|atau)\s+", line, flags=re.IGNORECASE)]
        in_group: set[str] = set()
        if len(segs) > 1:
            chain: list[str] = []
            for i in range(len(segs) - 1):
                if segs[i] and segs[i + 1]:
                    left, right = segs[i][-1], segs[i + 1][0]
                    if left != right:
                        chain = chain if (chain and chain[-1] == left) else [left]
                        chain.append(right)
                        continue
                if len(chain) > 1:
                    groups.append(chain)
                chain = []
            if len(chain) > 1:
                groups.append(chain)
            for g in groups:
                in_group.update(g)
        singles += [s for s in found if s not in in_group]
    singles = list(dict.fromkeys(singles))
    groups = [list(dict.fromkeys(g)) for g in groups if not any(m in singles for m in g)]
    uniq: list[list[str]] = []
    for g in groups:
        if g not in uniq:
            uniq.append(g)
    return [[s] for s in singles] + uniq


def parse_jd(title: str, text: str) -> dict:
    tax = get_taxonomy()
    sections: dict[str, list[str]] = {"intro": []}
    cur = "intro"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        h = _heading(line)
        if h:
            cur = h
            sections.setdefault(cur, [])
            continue
        sections.setdefault(cur, []).append(line)

    join = lambda k: "\n".join(sections.get(k, []))  # noqa: E731
    preferred_text = join("preferred")
    core_text = "\n".join([title, join("intro"), join("responsibilities"), join("requirements")])
    if not sections.get("requirements") and not sections.get("responsibilities"):
        core_text = "\n".join([title, text])

    preferred_skills = tax.find(preferred_text)
    required_groups = _skill_groups(core_text)
    required_skills = list(dict.fromkeys(s for g in required_groups for s in g))
    preferred_skills = [s for s in preferred_skills if s not in required_skills]

    # Skill non-taxonomy yang ditulis eksplisit: "Skills: X, Y"
    extra: list[str] = []
    for line in sections.get("requirements", []):
        m = re.match(r"^(?:[-•*]\s*)?(?:skills?|tech stack|keahlian)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            for tok in re.split(r"[,;/]", m.group(1)):
                tok = tok.strip(" .")
                if tok and not tax.canonical(tok) and not tax.find(tok) and len(tok.split()) <= 3:
                    extra.append(tok)
    for e in extra:
        if e not in required_skills:
            required_skills.append(e)
            required_groups.append([e])

    req_lines = [_strip_bullet(l) for l in sections.get("requirements", [])]
    min_years = None
    for line in req_lines or [text]:
        m = YEARS.search(line)
        if m:
            min_years = int(m.group(1))
            break

    min_level, edu_text = 0, None
    for line in req_lines or text.split("\n"):
        levels = [lv for lv, rx in EDU_LEVELS if re.search(rx, line, re.IGNORECASE)]
        if levels and re.search(r"degree|sarjana|bachelor|master|diploma|s-?[123]|d-?3|pendidikan|education|lulusan|graduate|ph\.?d|gelar", line, re.IGNORECASE):
            min_level, edu_text = min(levels), line
            break

    responsibilities = [s for l in sections.get("responsibilities", []) for s in sentences(l)]
    # Baris requirement yang bersifat pengalaman/kemampuan (bukan pendidikan murni) ikut jadi unit evidence
    experience_reqs = [
        l for l in req_lines
        if len(l) > 15 and l != edu_text and not re.match(r"^(?:skills?|tech stack)\s*:", l, re.IGNORECASE)
    ]
    return {
        "title": title,
        "required_skills": required_skills,
        "required_skill_groups": required_groups,  # [["TensorFlow","PyTorch"], ["Docker"]] -> salah satu dalam grup cukup
        "preferred_skills": preferred_skills,
        "min_years": min_years,
        "min_education_level": min_level,
        "education_text": edu_text,
        "responsibilities": responsibilities,
        "experience_requirements": experience_reqs,
        "sections_found": [k for k, v in sections.items() if v and k != "intro"],
    }
