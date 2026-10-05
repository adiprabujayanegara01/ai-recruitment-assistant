"""CV parser: teks mentah -> data terstruktur (bagian 7 dokumen).
Berbasis aturan + taxonomy sehingga deterministik, cepat, dan dapat diuji. Mendukung Bahasa Indonesia & Inggris."""
import re
from datetime import date

from app.services.privacy import EMAIL, PHONE
from app.services.skills import get_taxonomy
from app.utils.text import DATE_RANGE, months_between, parse_date

SECTION_PATTERNS = {
    "summary": r"summary|professional summary|profile|about me|about|ringkasan|profil|tentang saya|objective|tujuan karir",
    "experience": r"(?:work |professional |relevant )?experience|employment(?: history)?|work history|"
    r"pengalaman(?: kerja| profesional)?|riwayat pekerjaan|riwayat kerja",
    "education": r"education(?:al background)?|academic background|pendidikan|riwayat pendidikan|latar belakang pendidikan",
    "skills": r"(?:technical |key |core )?skills|technical skills|keahlian|keterampilan|kemampuan|kompetensi|tech stack|technologies",
    "certifications": r"certifications?|certificates?|licenses?|sertifikasi|sertifikat|pelatihan|training|courses?|kursus",
    "projects": r"(?:personal |selected |academic )?projects?|proyek|portfolio|portofolio",
    "other": r"languages?|bahasa|interests?|hobbies|hobi|references?|referensi|awards?|achievements?|penghargaan|"
    r"prestasi|organi[sz]ations?|organisasi|volunteer|publications?",
}
_HEADING_RES = {k: re.compile(rf"^(?:{v})$", re.IGNORECASE) for k, v in SECTION_PATTERNS.items()}
BULLET = "•-*▪●■·–—"

EDU_LEVELS = [  # (level, regex)
    (5, r"\bph\.?\s?d\b|\bdoctor(?:ate)?\b|\bs-?3\b|\bdoktor\b"),
    (4, r"\bmaster(?:'s)?\b|\bmagister\b|\bs-?2\b|\bm\.?sc\b|\bm\.?eng\b|\bmba\b"),
    (3, r"\bbachelor(?:'s)?\b|\bsarjana\b|\bs-?1\b|\bb\.?sc\b|\bb\.?eng\b|\bundergraduate\b|\bb\.?s\b|\bs\.?kom\b|\bs\.?t\b|\bs\.?ti\b"),
    (2, r"\bdiploma\b|\bd-?3\b|\bd-?4\b|\bassociate\b|\bd\.?iii\b"),
    (1, r"\bsma\b|\bsmk\b|\bhigh school\b|\bvocational\b|\bsenior high\b"),
]
INSTITUTION = re.compile(
    r"\b(universitas|university|institut|institute|politeknik|polytechnic|college|akademi|academy|sekolah|school|stmik|stikom)\b",
    re.IGNORECASE,
)
MAJOR_AFTER_DEGREE = re.compile(
    r"(?:bachelor(?:'s)?|master(?:'s)?|sarjana|magister|diploma|s-?[123]|d-?[34]|b\.?sc|m\.?sc|ph\.?d)\b"
    r"(?:\s+of\s+(?:science|engineering|arts|applied science)|\s+degree)?"
    r"(?:\s*(?:in|of|dalam|,|-|–|:)\s*|\s+)"
    r"(?P<major>[A-Za-z][A-Za-z&/ ]{2,45}?)(?=\s*(?:[,|(–—\-]|\bgpa\b|\bipk\b|\d|$))",
    re.IGNORECASE,
)
COMPANY_HINT = re.compile(
    r"\b(pt|cv|inc|ltd|llc|corp|co\.|company|startup|tbk|gmbh|group|labs?|technolog(?:y|ies)|solutions?|bank|"
    r"university|universitas|studio|systems|digital|indonesia|consulting|agency|institute)\b\.?",
    re.IGNORECASE,
)
ROLE_HINT = re.compile(
    r"(engineer|developer|analyst|scientist|manager|intern|magang|lead|officer|specialist|consultant|designer|"
    r"architect|administrator|programmer|staff|associate|head|director|researcher|assistant|asisten|peneliti|"
    r"koordinator|supervisor|technician|teknisi|freelance)",
    re.IGNORECASE,
)
LOCATION_LABEL = re.compile(r"^(?:location|lokasi|alamat|address|domisili|kota)\s*[:\-]\s*(.+)$", re.IGNORECASE)
CITIES = (
    "Jakarta|Bandung|Surabaya|Yogyakarta|Jogja|Medan|Semarang|Bekasi|Depok|Tangerang|Bogor|Malang|Denpasar|Bali|"
    "Makassar|Palembang|Batam|Solo|Balikpapan|Singapore|Kuala Lumpur"
)


def _is_bullet(line: str) -> bool:
    return bool(line) and line[0] in BULLET and (len(line) == 1 or line[1] in " \t" or line[0] in "•▪●■·")


def _strip_bullet(line: str) -> str:
    return line.lstrip(BULLET + " \t").strip()


def detect_heading(line: str) -> str | None:
    clean = re.sub(r"[:\-–—_|#*]+", " ", line).strip().rstrip(":")
    clean = re.sub(r"\s+", " ", clean)
    if not clean or len(clean) > 40:
        return None
    for name, rx in _HEADING_RES.items():
        if rx.match(clean):
            return name
    return None


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            if current:
                sections[current].append("")
            continue
        h = detect_heading(line)
        if h:
            current = h
            sections.setdefault(current, [])
            continue
        (sections[current] if current else header).append(line)
    return header, sections


def parse_personal(header: list[str], full_text: str) -> dict:
    email_m = EMAIL.search(full_text)
    email = email_m.group(0) if email_m else None
    phone_m = PHONE.search("\n".join(header) or full_text)
    phone = phone_m.group(0).strip() if phone_m else None
    name = None
    for line in header[:6]:
        clean = line.strip()
        if EMAIL.search(clean) or re.search(r"\d{4,}", clean) or "http" in clean.lower():
            continue
        if re.fullmatch(r"(curriculum vitae|resume|cv|daftar riwayat hidup)", clean, re.IGNORECASE):
            continue
        words = clean.replace(",", " ").split()
        if 1 < len(words) <= 5 and all(re.fullmatch(r"[A-Za-z.'\-]+", w) for w in words):
            name = clean
            break
    location = None
    for line in header[:10]:
        m = LOCATION_LABEL.match(line)
        if m:
            location = m.group(1).strip()
            break
        m = re.search(rf"\b({CITIES})\b(?:,\s*[A-Za-z ]+)?", line)
        if m and len(line) < 140:
            location = m.group(0).strip()
            break
    return {"name": name, "email": email, "phone": phone, "location": location}


def parse_education(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    cur: dict | None = None
    for raw in lines:
        line = _strip_bullet(raw)
        if not line:
            continue
        level = 0
        for lv, rx in EDU_LEVELS:
            if re.search(rx, line, re.IGNORECASE):
                level = lv
                break
        inst = INSTITUTION.search(line)
        if not level and not inst:
            continue
        deg_m = MAJOR_AFTER_DEGREE.search(line)
        major = deg_m.group("major").strip(" ,-") if deg_m else None
        if major and INSTITUTION.search(major):
            major = None
        institution = None
        if inst:
            # ambil frasa institusi (kata kunci + kata kapital di sekitarnya)
            m = re.search(
                r"((?:universitas|university|institut|institute|politeknik|polytechnic|college|akademi|academy|stmik|stikom|sekolah|school)"
                r"(?:\s+(?:of\s+)?[A-Z][\w&.]*)+|[A-Z][\w&.]*(?:\s+[A-Z][\w&.]*)*\s+(?:University|Institute|College|Polytechnic))",
                line,
                re.IGNORECASE,
            )
            institution = m.group(1).strip() if m else line
        new_needed = cur is None or (institution and cur.get("institution")) or (level and cur.get("level") and not institution)
        if new_needed:
            cur = {"institution": None, "degree": None, "major": None, "level": 0}
            entries.append(cur)
        if institution and not cur["institution"]:
            cur["institution"] = institution
        if level and not cur["level"]:
            cur["level"] = level
            cur["degree"] = re.split(r"\s+[|–—]\s+|\s*\(", line)[0].strip()[:120]
        if major and not cur["major"]:
            cur["major"] = major
    return entries


def _split_header(line: str) -> list[str]:
    line = re.sub(r"\s+(?:at|di|@)\s+", " | ", line, flags=re.IGNORECASE)
    parts = re.split(r"\s*[|•·@,]\s*|\s+[–—-]\s+", line)
    return [p.strip(" ()-–—") for p in parts if p and p.strip(" ()-–—")]


def parse_experience(lines: list[str], today: date) -> list[dict]:
    idxs = [i for i, l in enumerate(lines) if DATE_RANGE.search(l)]
    if not idxs:
        return []
    starts: list[int] = []
    for i in idxs:
        rest = DATE_RANGE.sub("", lines[i]).strip(" ()|,-–—")
        start = i
        if len(rest) < 3:  # baris hanya tanggal -> judul di baris sebelumnya
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and j not in idxs and not _is_bullet(lines[j].strip()):
                start = j
        starts.append(start)
    entries = []
    for n, i in enumerate(idxs):
        line = lines[i]
        m = DATE_RANGE.search(line)
        s = parse_date(m.group("s"), today.year, today.month)
        e = parse_date(m.group("e"), today.year, today.month, is_end=True)
        title_line = DATE_RANGE.sub("", line).strip(" ()|,-–—")
        title_parts = _split_header(title_line)
        if starts[n] != i:
            title_parts = _split_header(lines[starts[n]].strip()) + title_parts
        position = company = None
        for p in title_parts:
            if not position and ROLE_HINT.search(p) and not (COMPANY_HINT.search(p) and not ROLE_HINT.search(p)):
                position = p
            elif not company and COMPANY_HINT.search(p):
                company = p
        rest_parts = [p for p in title_parts if p not in (position, company)]
        if not position and rest_parts:
            position = rest_parts.pop(0)
        if not company and rest_parts:
            company = rest_parts.pop(0)
        end_idx = (starts[n + 1] if n + 1 < len(idxs) else len(lines))
        desc = [_strip_bullet(l) for l in lines[i + 1:end_idx] if l.strip()]
        entries.append(
            {
                "position": position,
                "company": company,
                "description": "\n".join(desc),
                "start": f"{s[0]}-{s[1]:02d}",
                "end": f"{e[0]}-{e[1]:02d}",
                "months": months_between(s, e),
                "_range": (s, e),
            }
        )
    return entries


def total_years(entries: list[dict]) -> float:
    spans = sorted((e["_range"][0][0] * 12 + e["_range"][0][1], e["_range"][1][0] * 12 + e["_range"][1][1]) for e in entries)
    total, cur_s, cur_e = 0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e + 1:
            if cur_e is not None:
                total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s + 1
    return round(total / 12, 1)


def parse_skills(lines: list[str]) -> list[str]:
    tax = get_taxonomy()
    out: list[str] = []
    for raw in lines:
        line = _strip_bullet(raw)
        if not line:
            continue
        line = re.sub(r"^[A-Za-z &/]{2,30}:\s*", "", line)  # buang label kategori "Languages:"
        for tok in re.split(r"[,;|•·/]|\s{2,}", line):
            tok = tok.strip(" .-")
            if not tok or len(tok) > 40:
                continue
            canon = tax.canonical(tok)
            if canon:
                out.append(canon)
            else:
                found = tax.find(tok)
                if found:
                    out.extend(found)
                elif len(tok.split()) <= 3 and re.search(r"[A-Za-z]", tok):
                    out.append(tok)
    seen, uniq = set(), []
    for s in out:
        if s.lower() not in seen:
            seen.add(s.lower())
            uniq.append(s)
    return uniq


def parse_certifications(lines: list[str]) -> list[dict]:
    out = []
    for raw in lines:
        line = _strip_bullet(raw)
        if len(line) < 4:
            continue
        line = re.sub(r"\(?\b(?:19|20)\d{2}\)?", "", line).strip(" ,-–—|")
        parts = re.split(r"\s+[–—|-]\s+|\s*\|\s*|,\s+|\s+by\s+|\s+oleh\s+|\s+\(", line, maxsplit=1)
        name = parts[0].strip()
        issuer = parts[1].strip(" )") if len(parts) > 1 else None
        if name:
            out.append({"name": name, "issuer": issuer or None})
    return out


def parse_projects(lines: list[str]) -> list[dict]:
    projects: list[dict] = []
    for raw in lines:
        if not raw.strip():
            continue
        line = raw.strip()
        if _is_bullet(line) and projects:
            projects[-1]["description"] += ("\n" if projects[-1]["description"] else "") + _strip_bullet(line)
            continue
        line = _strip_bullet(line)
        if projects and not projects[-1]["description"] and len(line) > 70:
            projects[-1]["description"] = line
            continue
        m = re.split(r"\s+[–—]\s+|\s*:\s+|\s+-\s+", line, maxsplit=1)
        projects.append({"name": m[0].strip()[:200], "description": m[1].strip() if len(m) > 1 else ""})
    return projects


def parse_cv(text: str, today: date | None = None) -> dict:
    today = today or date.today()
    tax = get_taxonomy()
    header, sections = split_sections(text)
    personal = parse_personal(header, text)
    experience = parse_experience(sections.get("experience", []), today)
    education = parse_education(sections.get("education", []))
    declared = parse_skills(sections.get("skills", []))
    certifications = parse_certifications(sections.get("certifications", []))
    projects = parse_projects(sections.get("projects", []))

    # Skill yang tersirat dari pengalaman/proyek/sertifikasi (bukan hanya daftar skill)
    body = "\n".join(
        ["\n".join(e["description"] + " " + (e["position"] or "") for e in [x]) for x in experience]
        + [p["name"] + " " + p["description"] for p in projects]
        + [c["name"] for c in certifications]
        + sections.get("summary", [])
    )
    inferred = [s for s in tax.find(body) if s.lower() not in {d.lower() for d in declared}]
    skills = declared + inferred

    for e in experience:
        e.pop("_range", None)
    exp_for_total = parse_experience(sections.get("experience", []), today)
    return {
        "personal": personal,
        "summary": " ".join(l for l in sections.get("summary", []) if l).strip(),
        "education": education,
        "experience": experience,
        "skills": skills,
        "skills_declared": declared,
        "skills_inferred": inferred,
        "certifications": certifications,
        "projects": projects,
        "total_experience_years": total_years(exp_for_total) if exp_for_total else 0.0,
        "highest_education_level": max([e["level"] for e in education], default=0),
        "sections_found": [k for k, v in sections.items() if any(x.strip() for x in v)],
    }
