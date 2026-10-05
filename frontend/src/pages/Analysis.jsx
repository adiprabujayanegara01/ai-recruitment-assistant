import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Badge, ErrorBox, Loading, ScoreBar, methodLabel, scoreClass } from "../components/ui.jsx";

const EDU = { match: "Sesuai", partial: "Sebagian sesuai", not_identified: "Belum teridentifikasi" };

function Evidence({ d }) {
  return (
    <li className="req">
      <div className="req-head">
        <strong>{d.requirement}</strong>
        {!d.required && <span className="muted small"> nilai plus</span>}
        <Badge status={d.status} />
      </div>
      {d.evidence ? (
        <blockquote><mark>{d.evidence}</mark>
          <footer className="muted small">
            {d.evidence_section && <>bagian {d.evidence_section} · </>}{methodLabel(d.method)}
            {d.kind === "responsibility" && <> · kemiripan {d.similarity.toFixed(2)}</>}
          </footer></blockquote>
      ) : <p className="muted small">Tidak ditemukan pada dokumen. Ini bukan bukti bahwa kandidat tidak menguasainya; konfirmasi saat wawancara.</p>}
    </li>
  );
}

export default function Analysis() {
  const { id } = useParams();
  const { data: r, error, loading, reload } = useAsync(() => api.result(id), [id]);
  const [busy, setBusy] = useState(false);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const a = r.analysis;
  const skills = r.details.filter((d) => d.kind === "skill");
  const resp = r.details.filter((d) => d.kind === "responsibility");
  const download = async () => {
    setBusy(true);
    try { const blob = await api.report(r.id); const u = URL.createObjectURL(blob); const el = document.createElement("a"); el.href = u; el.download = `laporan-${r.id}.pdf`; el.click(); URL.revokeObjectURL(u); }
    catch (e) { alert(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <header className="page-head">
        <div>
          <Link to={`/jobs/${r.job_id}`} className="muted small">← {r.job_title}</Link>
          <h1><Link to={`/candidates/${r.candidate_id}`}>{r.candidate_name || `Kandidat #${r.candidate_id}`}</Link></h1>
          <p className="muted">Posisi: {r.job_title}</p>
        </div>
        <div className="actions"><button className="btn" disabled={busy} onClick={download}>{busy ? "Membuat…" : "Unduh laporan PDF"}</button></div>
      </header>

      {a.warnings?.map((w, i) => <div className="notice" key={i} role="status">⚠ {w}</div>)}

      <section className="card hero">
        <div className={`bigscore ${scoreClass(r.match_score)}`}><span>{Math.round(r.match_score)}</span><small>% kecocokan</small></div>
        <div className="hero-body">
          <ScoreBar breakdown={r.breakdown} />
          <p className="summary">{a.explanation}</p>
        </div>
      </section>

      <div className="grid2">
        <section className="card">
          <h2>Skill wajib & nilai plus</h2>
          <p className="small"><span className="ok-text">✓ {r.matched_skills.length} teridentifikasi</span> · <span className="muted">{r.missing_skills.length} belum teridentifikasi</span></p>
          <ul className="reqlist">{skills.map((d, i) => <Evidence key={i} d={d} />)}</ul>
        </section>
        <div>
          {resp.length > 0 && (
            <section className="card"><h2>Tanggung jawab pekerjaan</h2><ul className="reqlist">{resp.map((d, i) => <Evidence key={i} d={d} />)}</ul></section>)}
          <section className="card">
            <h2>Pendidikan</h2>
            <p>{EDU[a.education_match?.status] || "Tidak dinilai"}<span className="muted small"> — {a.education_match?.explanation}</span></p>
            {r.years && <p className="small muted">Pengalaman: {r.years.relevant} thn relevan dari total {r.years.total} thn.</p>}
          </section>
          {(a.strengths?.length > 0 || a.gaps?.length > 0) && (
            <section className="card">
              {a.strengths?.length > 0 && <><h2>Kekuatan</h2><ul className="small">{a.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></>}
              {a.gaps?.length > 0 && <><h2>Perlu dikonfirmasi</h2><ul className="small">{a.gaps.map((s, i) => <li key={i}>{s}</li>)}</ul></>}
            </section>)}
          {a.interview_questions?.length > 0 && (
            <section className="card"><h2>Pertanyaan wawancara</h2><ol className="small">{a.interview_questions.map((q, i) => <li key={i}>{q}</li>)}</ol></section>)}
        </div>
      </div>

      <p className="muted small note">{r.disclaimer}</p>
      <details className="small muted trace">
        <summary>Jejak versi & sumber analisis</summary>
        <p>Sumber penjelasan: {a.source === "llm" ? "LLM (tervalidasi groundedness)" : "analisis berbasis aturan"}{a.unsupported_claims > 0 && ` · ${a.unsupported_claims} klaim tidak didukung CV dibuang`}</p>
        <p>{Object.entries(r.versions).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
        {a.context_sources?.length > 0 && <p>Konteks perusahaan (RAG): {a.context_sources.map((s) => s.title).join(", ")}</p>}
      </details>
    </>
  );
}
