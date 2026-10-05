# AI pipeline

**CV:** file → validasi (ekstensi, ukuran, magic bytes) → ekstraksi teks → deteksi bagian (EN/ID) → ekstraksi entitas → skill (daftar + tersirat dari pengalaman) → simpan.
**JD:** teks → bagian (responsibilities / requirements / preferred) → skill wajib (grup "or"), nilai plus, tahun, jenjang pendidikan, tanggung jawab.
**Matching:** CV dipecah jadi unit evidence (baris pengalaman, proyek, sertifikasi, ringkasan, daftar skill) → PII/sensitif dihapus + kalimat injeksi dibuang → embedding → per requirement:
1. skill: exact/alias → implied → declared-only → related (keluarga teknologi) → (skill di luar taxonomy) semantic;
2. tanggung jawab: kemiripan kosinus unit terbaik + bonus overlap konsep (hybrid), ambang `matched`/`related` per embedder;
3. komponen → skor berbobot dengan normalisasi bobot.
**Analisis:** temuan deterministik + CV terredaksi + konteks RAG → LLM (JSON) → validasi skema → groundedness guard → simpan. Gagal ⇒ rule-based.

**Evaluasi** (`scripts/evaluate.py`): extraction P/R/F1, ranking P@K/Recall@K/NDCG@K, evidence verbatim rate, counterfactual fairness, latensi; riwayat per versi di `data/eval/results.json`. Untuk LLM nyata ukur juga JSON validity dan `unsupported_claims` (halaman monitoring). Setiap perubahan model/prompt: naikkan versi di `app/ai/versions.py`, jalankan evaluasi, bandingkan.
