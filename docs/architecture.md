# Arsitektur

```
Browser (React) ──/api/v1──▶ FastAPI (middleware: request-id, timing, security headers)
   routers: auth · candidates · jobs · matching · reports · knowledge · admin
      │
      ├─ document_reader   validasi magic-bytes + ekstraksi teks (PyMuPDF / python-docx)
      ├─ cv_parser         section detection → personal/education/experience/skills/certs/projects
      ├─ jd_parser         requirement: skill wajib (grup alternatif), nilai plus, tahun, pendidikan, tanggung jawab
      ├─ skills            taxonomy + alias + IMPLIES (konsep tersirat) + RELATED_GROUPS (setara)
      ├─ privacy           redaksi PII/atribut sensitif, penghapusan kalimat prompt-injection
      ├─ embedding_service SentenceTransformer | HashingEmbedder (fallback offline)
      ├─ matching_service  hybrid exact/alias + semantic → skor berbobot + evidence
      ├─ rag_service       chunk → embed → retrieve → jawaban ber-sitasi
      ├─ llm_service       Anthropic / OpenAI-compatible, validasi JSON, groundedness guard
      ├─ rule_based_analyst  analisis terstruktur tanpa LLM (fallback)
      ├─ analysis_service  orkestrasi + penyimpanan + inference log
      └─ report_service    PDF (reportlab)
PostgreSQL (SQLite untuk dev): users, candidates, resumes, educations, experiences, skills, candidate_skills,
certifications, projects, jobs, job_skills, matching_results, matching_details,
knowledge_documents, knowledge_chunks, audit_logs, inference_logs
```

**Keputusan desain utama**
1. *Skor deterministik, LLM hanya menjelaskan* → hasil dapat diaudit & direproduksi, tahan terhadap manipulasi lewat teks CV.
2. *Provider embedding/LLM pluggable dengan fallback* → sistem tidak pernah mati karena layanan eksternal.
3. *Setiap hasil membawa versi* (`embedding`, `llm`, `prompt-v*`, `matching-engine-v*`, `parser-v*`) → perubahan model dapat dibandingkan lewat `scripts/evaluate.py`.
4. *Hasil analisis disimpan sebagai snapshot* (detail + evidence + analysis JSON) sehingga laporan lama tidak berubah saat model diperbarui.
