# API (`/api/v1`) — dokumentasi interaktif di `/docs` (OpenAPI/Swagger)

Semua endpoint selain `/auth/login` dan `/health` memerlukan `Authorization: Bearer <token>`.

| Method | Endpoint | Fungsi | Role |
|---|---|---|---|
| POST | `/auth/login` | Login → JWT | – |
| GET | `/auth/me` | Profil | semua |
| POST/GET | `/auth/users` | Buat / daftar user | admin |
| POST | `/candidates/upload` | Upload & proses CV (`file`, opsional `job_id` → langsung dianalisis) | semua |
| GET | `/candidates?q=&skill=&min_years=` | Cari kandidat (skill dapat diulang = harus semua ada) | semua |
| GET | `/candidates/{id}` | Detail hasil ekstraksi | semua |
| GET | `/candidates/{id}/resume` | Unduh CV asli | admin / pengunggah |
| DELETE | `/candidates/{id}` | Hapus kandidat + file + hasil | admin / pengunggah |
| POST/GET | `/jobs` | Buat (ekstraksi requirement otomatis) / daftar | semua |
| GET/DELETE | `/jobs/{id}` | Detail / hapus | semua |
| GET | `/jobs/{id}/ranking` | Peringkat kandidat (hasil terbaru) | semua |
| POST | `/matching/analyze` | `{candidate_id, job_id}` → analisis | semua |
| POST | `/matching/batch` | `{job_id, candidate_ids?}` → analisis banyak + urut | semua |
| GET | `/matching`, `/matching/{id}` | Daftar / detail hasil | semua |
| POST | `/reports/{id}` | Laporan PDF | semua |
| POST/GET/DELETE | `/knowledge` | Kelola dokumen RAG | tulis: admin |
| POST | `/knowledge/ask` | Tanya jawab ber-sumber | semua |
| GET | `/admin/metrics`, `/admin/audit` | Monitoring, audit trail | admin |
| POST | `/admin/retention/purge?days=` | Hapus data lebih tua dari N hari | admin |
| GET | `/health` (tanpa prefix) | Status + versi model | – |

**Contoh respons `POST /matching/analyze`** (diringkas)
```json
{ "id": 7, "candidate_id": 1, "job_id": 1, "match_score": 65.5,
  "matched_skills": ["Python", "Machine Learning", "TensorFlow"],
  "missing_skills": ["Docker", "PostgreSQL", "NLP"],
  "breakdown": {"skill": {"score": 0.71, "applied_weight": 0.4, "note": "..."}, "experience": {...}, "education": {...}, "project": {...}},
  "details": [{"requirement": "FastAPI", "status": "matched", "method": "exact", "evidence": "Built REST API services with FastAPI ...", "evidence_section": "experience", "similarity": 1.0}],
  "analysis": {"explanation": "...", "relevant_experience": [...], "interview_questions": [...], "source": "rule_based", "warnings": []},
  "versions": {"embedding_model": "hashing-v1", "llm_model": "rule-based-v1", "prompt_version": "prompt-v2", "matching_engine": "matching-engine-v2"},
  "disclaimer": "Hasil ini adalah analisis pendukung keputusan ..." }
```
`missing_skills` = skill JD wajib yang **belum teridentifikasi pada dokumen**, bukan bukti kandidat tidak menguasainya.
