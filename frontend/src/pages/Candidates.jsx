import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Empty, ErrorBox, Loading, ScoreChip } from "../components/ui.jsx";

export default function Candidates() {
  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [minYears, setMinYears] = useState("");
  const list = useAsync(() => api.candidates({ q, skill, min_years: minYears }), [q, skill, minYears]);
  const jobs = useAsync(api.jobs);
  const [jobId, setJobId] = useState("");
  const [state, setState] = useState({ busy: false, msgs: [] });
  const file = useRef();

  const upload = async (e) => {
    const files = [...e.target.files]; e.target.value = "";
    setState({ busy: true, msgs: [] });
    const msgs = [];
    for (const f of files) {
      try { const r = await api.upload(f, jobId); msgs.push({ ok: true, text: `${f.name}: ${r.name || "nama tidak terdeteksi"} diproses${r.analysis ? ` (skor ${Math.round(r.analysis.match_score)}%)` : ""}` }); }
      catch (err) { msgs.push({ ok: false, text: `${f.name}: ${err.message}` }); }
    }
    setState({ busy: false, msgs }); list.reload();
  };
  return (
    <>
      <header className="page-head"><h1>Kandidat</h1></header>
      <section className="card">
        <h2>Unggah CV</h2>
        <div className="row">
          <select value={jobId} onChange={(e) => setJobId(e.target.value)} aria-label="Analisis otomatis untuk lowongan">
            <option value="">Tanpa analisis otomatis</option>
            {jobs.data?.map((j) => <option key={j.id} value={j.id}>Analisis untuk: {j.title}</option>)}
          </select>
          <input ref={file} type="file" accept=".pdf,.docx" multiple hidden onChange={upload} />
          <button className="btn" disabled={state.busy} onClick={() => file.current.click()}>{state.busy ? "Memproses…" : "Pilih file PDF / DOCX"}</button>
        </div>
        {state.msgs.map((m, i) => <p key={i} className={m.ok ? "ok-text small" : "error-text small"}>{m.text}</p>)}
        <p className="muted small">Maksimal 5 MB per file. PDF hasil scan (gambar) belum didukung.</p>
      </section>
      <section className="card">
        <div className="row filters">
          <input placeholder="Cari nama, email, atau skill…" value={q} onChange={(e) => setQ(e.target.value)} />
          <input placeholder="Skill persis (mis. Docker)" value={skill} onChange={(e) => setSkill(e.target.value)} />
          <input type="number" min="0" step="0.5" placeholder="Min. tahun pengalaman" value={minYears} onChange={(e) => setMinYears(e.target.value)} />
        </div>
        {list.loading ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> : list.data.items.length === 0 ? <Empty title="Tidak ada kandidat">Unggah CV atau ubah filter.</Empty> : (
          <table><thead><tr><th>Nama</th><th>Pengalaman</th><th>Skill</th><th>Skor terbaru</th></tr></thead>
            <tbody>{list.data.items.map((c) => (
              <tr key={c.id}>
                <td><Link to={`/candidates/${c.id}`}>{c.name || `Kandidat #${c.id}`}</Link><div className="muted small">{c.location}</div></td>
                <td>{c.total_experience_years} thn</td>
                <td className="small">{c.skills.slice(0, 6).join(", ")}{c.skills.length > 6 && ` +${c.skills.length - 6}`}</td>
                <td>{c.latest_scores.slice(-2).map((s) => <Link key={s.result_id} to={`/analysis/${s.result_id}`}><ScoreChip score={s.match_score} /> </Link>)}</td>
              </tr>))}</tbody></table>)}
      </section>
    </>
  );
}
