# Fairness & security

**Fairness.** Matching hanya memakai skills/experience/education/projects/certifications. Sebelum analisis AI, `privacy.redact` menghapus email/telepon/URL, nama kandidat, baris atribut sensitif (jenis kelamin, agama, status nikah, tanggal lahir, usia, foto, dll.) dan kata sensitif inline. Nama institusi tidak dikirim ke LLM (proxy bias). Test `test_counterfactual_*` memastikan skor identik saat atribut sensitif/nama diganti. Hasil dilabeli saran; "belum teridentifikasi" dirumuskan netral; peringkat = prioritas peninjauan.
**Yang belum dicakup:** redaksi berbasis aturan bisa lolos untuk bentuk penulisan tak terduga; proxy bias tidak langsung (mis. celah karier, lokasi) belum diuji; belum ada audit bias per kelompok. Lakukan sebelum penggunaan nyata.

**Prompt injection.** CV diperlakukan sebagai data (di dalam `<candidate_cv>`), kalimat instruksi dibuang, system prompt melarang mengikuti instruksi dalam CV, skor dihitung di luar LLM.

**Security.** Lihat bagian Security di README. Menambahkan: kunci API LLM hanya dari env; error 500 tidak membocorkan detail (hanya `request_id`); log audit tidak memuat isi CV.
