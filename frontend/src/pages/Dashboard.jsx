import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Empty, ErrorBox, Loading, ScoreChip } from "../components/ui.jsx";

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(async () => {
    const [c, j, r] = await Promise.all([api.candidates({ limit: 5 }), api.jobs(), api.results({ limit: 8 })]);
    return { c, j, r };
  });
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const { c, j, r } = data;
  return (
    <>
      <header className="page-head"><h1>Dashboard</h1></header>
      <section className="stats">
        <div className="stat"><span>{c.total}</span>Kandidat</div>
        <div className="stat"><span>{j.length}</span>Lowongan</div>
        <div className="stat"><span>{r.length}</span>Analisis terbaru</div>
      </section>
      <section className="card">
        <h2>Analisis terbaru</h2>
        {r.length === 0 ? <Empty title="Belum ada analisis">Buat lowongan, unggah CV, lalu jalankan analisis.</Empty> : (
          <table><thead><tr><th>Kandidat</th><th>Posisi</th><th>Skor</th><th>Skill belum teridentifikasi</th></tr></thead>
            <tbody>{r.map((x) => (
              <tr key={x.id}>
                <td><Link to={`/analysis/${x.id}`}>{x.candidate_name || `#${x.candidate_id}`}</Link></td>
                <td>{x.job_title}</td><td><ScoreChip score={x.match_score} /></td>
                <td className="muted">{x.missing_skills.slice(0, 4).join(", ") || "—"}</td>
              </tr>))}</tbody></table>)}
      </section>
      <p className="muted small note">Skor adalah indikator awal berbasis dokumen. Peringkat membantu menentukan prioritas peninjauan, bukan menerima atau menolak kandidat.</p>
    </>
  );
}
