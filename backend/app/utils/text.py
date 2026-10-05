import re

MONTHS = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2, "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4, "mei": 5, "may": 5, "jun": 6, "juni": 6, "june": 6, "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agt": 8, "aug": 8, "agustus": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "okt": 10, "oct": 10, "oktober": 10, "october": 10, "nov": 11, "november": 11, "des": 12, "dec": 12,
    "desember": 12, "december": 12,
}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_PRESENT = r"(?:present|now|current|sekarang|saat ini|sekarang ini|kini)"
_DATE = rf"(?:(?:{_MON})\.?\s+)?(?:19|20)\d{{2}}"
DATE_RANGE = re.compile(rf"(?P<s>{_DATE})\s*(?:-|–|—|to|sampai|s/d|hingga)\s*(?P<e>{_DATE}|{_PRESENT})", re.IGNORECASE)


def parse_date(token: str, now_year: int, now_month: int, is_end: bool = False) -> tuple[int, int]:
    token = token.strip().lower().rstrip(".")
    if re.fullmatch(_PRESENT, token):
        return now_year, now_month
    m = re.match(rf"(?:({_MON})\.?\s+)?((?:19|20)\d{{2}})", token)
    if m and m.group(1):
        month = MONTHS[m.group(1)]
    else:  # hanya tahun: awal = Januari, akhir = Desember
        month = 12 if is_end else 1
    return int(m.group(2)), month


def months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    return max(1, (end[0] * 12 + end[1]) - (start[0] * 12 + start[1]) + 1)


def sentences(text: str) -> list[str]:
    """Pecah teks menjadi kalimat/baris bermakna (dipakai sebagai unit evidence)."""
    out: list[str] = []
    for line in re.split(r"\n+", text):
        line = line.strip(" \t-•*▪●■·")
        if not line:
            continue
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line):
            part = part.strip()
            if len(part) >= 8:
                out.append(part)
    return out
