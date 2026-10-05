import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Empty, ErrorBox, Loading, ScoreChip } from "../components/ui.jsx";

export default function JobDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const job = useAsync(() => api.job(id), [id]);
  const rank = useAsync(() => api.ranking(id), [id]);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const file = useRef();

  const run = async (label, fn) => {
    setBusy(label); setMsg(null);
    try { await fn(); rank.reload(); job.reload(); } catch (e) { setMsg(e.message); } finally { setBusy(null); }
  };
  const uploadMany = (e) => run("upload", async () => {
    for (const f of e.target.files) await api.upload(f, id);
    e.target.value = "";
  });

  if (job.loading) return <Loading />;
  if (job.error) return <ErrorBox message={job.error} onRetry={job.reload} />;
  const j = job.data;
  return (
    <>
      <header className="page-head">
        <div><Link to="/jobs" className="muted small">← Lowongan</Link><h1>{j.title}</h1></div>
        <div className="actions">
          <input ref={file} type="file" accept=".pdf,.docx" multiple hidden onChange={uploadMany} />
          <button className="btn" disabled={!!busy} onClick={() => file.current.click()}>{busy === "upload" ? "Memproses CV…" : "Unggah CV & analisis"}</button>
          <button className="btn ghost" disabled={!!busy} onClick={() => run("batch", () => api.batch(id))}>{busy === "batch" ? "Menganalisis…" : "Analisis ulang semua kandidat"}</button>
          <button className="btn ghost danger" onClick={async () => { if (confirm("Hapus lowongan beserta hasil analisisnya?")) { await api.deleteJob(id); nav("/jobs"); } }}>Hapus</button>
        </div>
      </header>
      {msg && <ErrorBox message={msg} />}
      <div className="grid2">
        <section className="card">
          <h2>Requirement hasil ekstraksi</h2>
          <h3>Skill wajib</h3>
          <div className="tags">{(j.required_skill_groups?.length ? j.required_skill_groups : j.required_skills.map((s) => [s])).map((g) => <span className="tag" key={g.join()}>{g.join(" / ")}</span>)}</div>
          {j.preferred_skills.length > 0 && <><h3>Nilai plus</h3><div className="tags">{j.preferred_skills.map((s) => <span className="tag soft" key={s}>{s}</span>)}</div></>}
          <h3>Lainnya</h3>
          <p className="small">Pengalaman minimum: {j.min_years ? `${j.min_years} tahun` : "tidak disebut"}<br />Pendidikan: {j.education_text || "tidak disebut"}</p>
          {j.responsibilities.length > 0 && <><h3>Tanggung jawab</h3><ul className="small">{j.responsibilities.map((r) => <li key={r}>{r}</li>)}</ul></>}
        </section>
        <section className="card">
          <h2>Peringkat kandidat</h2>
          {rank.loading ? <Loading /> : rank.error ? <ErrorBox message={rank.error} onRetry={rank.reload} /> : rank.data.items.length === 0 ? (
            <Empty title="Belum ada kandidat dianalisis">Unggah CV (PDF/DOCX) untuk lowongan ini.</Empty>) : (
            <table><thead><tr><th>#</th><th>Kandidat</th><th>Skor</th><th>Belum teridentifikasi</th></tr></thead>
              <tbody>{rank.data.items.map((r) => (
                <tr key={r.result_id}>
                  <td>{r.rank}</td>
                  <td><Link to={`/analysis/${r.result_id}`}>{r.candidate_name || `#${r.candidate_id}`}</Link>{r.warnings?.length > 0 && <span title={r.warnings[0]} className="warn"> ⚠</span>}</td>
                  <td><ScoreChip score={r.match_score} /></td>
                  <td className="muted small">{r.missing_skills.slice(0, 3).join(", ") || "—"}</td>
                </tr>))}</tbody></table>)}
          <p className="muted small note">Peringkat adalah alat prioritas peninjauan. Keputusan seleksi tetap oleh recruiter.</p>
        </section>
      </div>
    </>
  );
}
