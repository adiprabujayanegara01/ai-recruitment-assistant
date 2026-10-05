import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Empty, ErrorBox, Loading } from "../components/ui.jsx";

export default function Jobs() {
  const { data, error, loading, reload } = useAsync(api.jobs);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const create = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await api.createJob(title, desc); setTitle(""); setDesc(""); reload(); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <>
      <header className="page-head"><h1>Lowongan</h1></header>
      <div className="grid2">
        <section className="card">
          <h2>Buat lowongan</h2>
          <form onSubmit={create}>
            <label>Judul posisi<input value={title} onChange={(e) => setTitle(e.target.value)} required /></label>
            <label>Job description<textarea rows={12} value={desc} onChange={(e) => setDesc(e.target.value)} required
              placeholder={"Tanggung jawab\n- ...\n\nKualifikasi\n- Minimal S1 ...\n- 2+ tahun pengalaman ...\n\nNilai plus\n- ..."} /></label>
            <p className="muted small">Sistem mengekstrak skill wajib, nilai plus, pengalaman minimum, pendidikan, dan tanggung jawab. Gunakan judul bagian seperti Requirements / Kualifikasi / Nice to have / Nilai plus.</p>
            {err && <p className="error-text" role="alert">{err}</p>}
            <button className="btn" disabled={busy}>{busy ? "Memproses…" : "Simpan & ekstrak requirement"}</button>
          </form>
        </section>
        <section className="card">
          <h2>Daftar lowongan</h2>
          {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <Empty title="Belum ada lowongan">Buat lowongan pertama di samping.</Empty> : (
            <ul className="list">{data.map((j) => (
              <li key={j.id}>
                <Link to={`/jobs/${j.id}`}><strong>{j.title}</strong></Link>
                <div className="muted small">{j.required_skills.length} skill wajib · {j.min_years ? `min ${j.min_years} thn · ` : ""}{j.candidates_analyzed} kandidat dianalisis</div>
              </li>))}</ul>)}
        </section>
      </div>
    </>
  );
}
