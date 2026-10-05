import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { ErrorBox, Loading, ScoreChip } from "../components/ui.jsx";

export default function CandidateDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const c = useAsync(() => api.candidate(id), [id]);
  const jobs = useAsync(api.jobs);
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  if (c.loading) return <Loading />;
  if (c.error) return <ErrorBox message={c.error} onRetry={c.reload} />;
  const d = c.data;
  const run = async () => {
    setBusy(true); setErr(null);
    try { const r = await api.analyze(d.id, jobId); nav(`/analysis/${r.id}`); } catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <>
      <header className="page-head">
        <div><Link to="/candidates" className="muted small">← Kandidat</Link><h1>{d.name || `Kandidat #${d.id}`}</h1>
          <p className="muted">{[d.email, d.phone, d.location].filter(Boolean).join(" · ")}</p></div>
        <button className="btn ghost danger" onClick={async () => { if (confirm("Hapus kandidat beserta file CV dan hasil analisis? Tindakan ini permanen.")) { await api.deleteCandidate(d.id); nav("/candidates"); } }}>Hapus data kandidat</button>
      </header>
      <section className="card">
        <h2>Jalankan analisis</h2>
        <div className="row">
          <select value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">Pilih lowongan…</option>{jobs.data?.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select>
          <button className="btn" disabled={!jobId || busy} onClick={run}>{busy ? "Menganalisis…" : "Analisis"}</button>
        </div>
        {err && <p className="error-text" role="alert">{err}</p>}
        {d.latest_scores.length > 0 && <p className="small">Analisis sebelumnya: {d.latest_scores.map((s) => <Link key={s.result_id} to={`/analysis/${s.result_id}`}><ScoreChip score={s.match_score} /> </Link>)}</p>}
      </section>
      <div className="grid2">
        <section className="card">
          <h2>Hasil ekstraksi CV</h2>
          <p className="muted small">Total pengalaman {d.total_experience_years} tahun · bagian terdeteksi: {d.resume.sections_found.join(", ")}</p>
          <h3>Pengalaman</h3>
          {d.experience.map((e, i) => <div key={i} className="item"><strong>{e.position || "—"}</strong> · {e.company || "—"}<div className="muted small">{e.start} → {e.end}</div><p className="small pre">{e.description}</p></div>)}
          <h3>Pendidikan</h3>
          {d.education.map((e, i) => <div key={i} className="item small">{e.degree || "—"} · {e.institution || "—"} {e.major && `(${e.major})`}</div>)}
        </section>
        <section className="card">
          <h2>Skill</h2><div className="tags">{d.skills.map((s) => <span className="tag" key={s}>{s}</span>)}</div>
          {d.certifications.length > 0 && <><h3>Sertifikasi</h3><ul className="small">{d.certifications.map((x, i) => <li key={i}>{x.name}{x.issuer && ` — ${x.issuer}`}</li>)}</ul></>}
          {d.projects.length > 0 && <><h3>Proyek</h3>{d.projects.map((p, i) => <div key={i} className="item small"><strong>{p.name}</strong><div className="muted">{p.description}</div></div>)}</>}
        </section>
      </div>
    </>
  );
}
