"""Fairness by design (bagian 13): matching & LLM tidak boleh melihat atribut sensitif.

Pendekatan berlapis:
1. Matching hanya memakai bagian skills / experience / education / projects / certifications.
2. Sebelum teks dikirim ke embedding atau LLM, PII & atribut sensitif dihapus (redaksi).
"""
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?62|0)[\s-]?8\d[\d\s-]{6,12}\d|\+?\d[\d\s().-]{8,}\d")
URL = re.compile(r"(?:https?://|www\.)\S+|linkedin\.com/\S+|github\.com/\S+", re.IGNORECASE)

# Label/baris yang memuat atribut sensitif (bukan kompetensi kerja).
SENSITIVE_LINE = re.compile(
    r"^\s*(?:jenis kelamin|gender|sex|agama|religion|status (?:pernikahan|perkawinan)|marital status|"
    r"tempat,? tanggal lahir|tanggal lahir|date of birth|dob|birth ?date|umur|usia|age|kewarganegaraan|"
    r"nationality|suku|ras|ethnicity|tinggi badan|berat badan|height|weight|foto|photo|nama ayah|nama ibu|"
    r"jumlah anak|number of children|religion)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
SENSITIVE_INLINE = re.compile(
    r"\b(?:laki-laki|perempuan|pria|wanita|male|female|single|married|menikah|belum menikah|"
    r"islam|kristen|katolik|hindu|buddha|budha|konghucu|muslim|christian)\b",
    re.IGNORECASE,
)


def redact(text: str, candidate_name: str | None = None) -> str:
    """Hapus kontak, nama, dan atribut sensitif dari teks sebelum dianalisis AI."""
    out = SENSITIVE_LINE.sub("", text)
    out = EMAIL.sub("[email]", out)
    out = URL.sub("[link]", out)
    out = PHONE.sub("[phone]", out)
    out = SENSITIVE_INLINE.sub("[redacted]", out)
    if candidate_name:
        for part in {candidate_name.strip(), *candidate_name.split()}:
            if len(part) >= 3:
                out = re.sub(re.escape(part), "[nama]", out, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", out)


# ---------------------------------------------------------------------------
# Pertahanan prompt injection: CV adalah input tidak tepercaya.
# ---------------------------------------------------------------------------
INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions?|prompts?)|"
    r"disregard (?:all |any |the )?(?:previous|prior|above)|abaikan (?:semua |seluruh )?(?:instruksi|perintah)|"
    r"(?:give|assign|rate) (?:this candidate|me|them) (?:a )?(?:score|rating|grade)|"
    r"(?:berikan|beri) (?:kandidat ini )?(?:skor|nilai) (?:\d+|tertinggi|sempurna)|"
    r"note to the (?:ai|llm|reviewer|model|system)|system prompt|you are now|"
    r"(?:hire|recommend) this candidate|score (?:of )?100",
    re.IGNORECASE,
)


def strip_injection(text: str) -> tuple[str, bool]:
    """Hapus kalimat yang tampak seperti instruksi kepada AI. Mengembalikan (teks_bersih, ada_injeksi)."""
    found = False
    kept = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        if INJECTION.search(sent):
            found = True
            continue
        kept.append(sent)
    return " ".join(kept).strip() if "\n" not in text else "\n".join(kept).strip(), found


def detect_injection(text: str) -> list[str]:
    return [m.group(0) for m in INJECTION.finditer(text)]
