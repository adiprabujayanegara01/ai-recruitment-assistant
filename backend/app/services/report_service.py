"""Laporan kandidat (PDF) dengan reportlab."""
import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import MatchingResult
from app.services.analysis_service import DISCLAIMER

INK, MUTED, RULE = colors.HexColor("#17212b"), colors.HexColor("#5b6773"), colors.HexColor("#d5dbe1")
STATUS = {"matched": "Teridentifikasi", "related": "Setara / terkait", "not_identified": "Belum teridentifikasi"}
LABEL = {"skill": "Skill", "experience": "Pengalaman", "education": "Pendidikan", "project": "Proyek & sertifikasi"}


def _p(text, style):
    return Paragraph(escape(str(text)) if text is not None else "-", style)


def build_report_pdf(r: MatchingResult) -> bytes:
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=0, textColor=INK, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=INK, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11.5, textColor=MUTED)
    cell = ParagraphStyle("c", parent=body, fontSize=8.5, leading=11)
    a = r.analysis or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Laporan kandidat #{r.candidate_id}", author="AI Recruitment Assistant")
    el = [_p(r.candidate.name or f"Kandidat #{r.candidate_id}", h1),
          _p(f"Posisi: {r.job.title}  |  Dibuat {datetime.now():%d %b %Y %H:%M}", small), Spacer(1, 4),
          HRFlowable(width="100%", thickness=0.6, color=RULE), Spacer(1, 6)]

    el.append(_p(f"Skor kecocokan: {r.match_score:.1f}%", ParagraphStyle("sc", parent=h2, fontSize=15, spaceBefore=4)))
    rows = [[_p(h, small) for h in ("Komponen", "Skor", "Bobot efektif", "Catatan")]]
    for k, v in (r.breakdown or {}).items():
        if k.startswith("_"):
            continue
        rows.append([_p(LABEL.get(k, k), cell), _p("-" if v["score"] is None else f"{v['score'] * 100:.0f}%", cell),
                     _p(f"{v['applied_weight'] * 100:.0f}%", cell), _p(v.get("note"), cell)])
    t = Table(rows, colWidths=[32 * mm, 16 * mm, 24 * mm, 102 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    el += [t, Spacer(1, 4), _p("Bobot dokumentasi awal (skill 40, pengalaman 30, pendidikan 15, proyek 15) adalah indikator, bukan ukuran objektif kualitas kandidat.", small)]

    el += [_p("Ringkasan", h2), _p(a.get("explanation") or r.summary, body)]
    if a.get("warnings"):
        el += [_p("Catatan sistem", h2)] + [_p("• " + w, body) for w in a["warnings"]]

    el.append(_p("Requirement dan evidence", h2))
    rows = [[_p(h, small) for h in ("Requirement", "Status", "Evidence dari CV")]]
    for d in r.details:
        rows.append([_p(("" if d.required else "(nilai plus) ") + d.skill, cell), _p(STATUS.get(d.status, d.status), cell),
                     _p(d.evidence or "Tidak ditemukan pada dokumen", cell)])
    t = Table(rows, colWidths=[52 * mm, 30 * mm, 92 * mm], repeatRows=1)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    el.append(t)

    for title, key in (("Kekuatan", "strengths"), ("Hal yang perlu dikonfirmasi", "gaps"), ("Pertanyaan wawancara", "interview_questions")):
        if a.get(key):
            el.append(KeepTogether([_p(title, h2)] + [_p("• " + x, body) for x in a[key]]))

    v = r.versions or {}
    el += [Spacer(1, 10), HRFlowable(width="100%", thickness=0.6, color=RULE), Spacer(1, 4),
           _p("Jejak versi: " + ", ".join(f"{k}={val}" for k, val in v.items()), small), Spacer(1, 3), _p(DISCLAIMER, small)]
    doc.build(el)
    return buf.getvalue()
