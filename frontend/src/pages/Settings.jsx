import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { ErrorBox, Loading } from "../components/ui.jsx";

function Admin() {
  const m = useAsync(api.metrics);
  const a = useAsync(api.audit);
  if (m.loading) return <Loading />;
  if (m.error) return <ErrorBox message={m.error} onRetry={m.reload} />;
  const d = m.data;
  return (
    <>
      <section className="stats">
        <div className="stat"><span>{d.latency_ms.avg ?? "—"}</span>ms rata-rata / analisis</div>
        <div className="stat"><span>{d.latency_ms.p95 ?? "—"}</span>ms p95</div>
        <div className="stat"><span>{d.tokens.input + d.tokens.output}</span>token LLM</div>
        <div className="stat"><span>{d.llm_fallbacks}</span>fallback LLM</div>
        <div className="stat"><span>{d.unsupported_claims_removed}</span>klaim tak didukung dibuang</div>
      </section>
      <section className="card"><h2>Versi model yang dipakai</h2>
        <table><thead><tr><th>Embedding | LLM | Prompt | Engine</th><th>Analisis</th></tr></thead><tbody>{d.by_version.map((v) => <tr key={v.versions}><td className="small">{v.versions}</td><td>{v.count}</td></tr>)}</tbody></table></section>
      <section className="card"><h2>Audit trail</h2>
        {a.loading ? <Loading /> : a.error ? <ErrorBox message={a.error} /> : (
          <table><thead><tr><th>Waktu</th><th>Aksi</th><th>Entitas</th><th>User</th></tr></thead>
            <tbody>{a.data.map((x) => <tr key={x.id}><td className="small">{new Date(x.created_at).toLocaleString("id-ID")}</td><td>{x.action}</td><td className="small">{x.entity} {x.entity_id}</td><td>{x.user_id ?? "—"}</td></tr>)}</tbody></table>)}</section>
    </>
  );
}

export default function Settings({ user }) {
  return (
    <>
      <header className="page-head"><h1>Pengaturan & monitoring</h1></header>
      <section className="card">
        <h2>Prinsip penggunaan</h2>
        <ul className="small">
          <li>AI hanya memberi analisis dan evidence; keputusan seleksi sepenuhnya oleh manusia.</li>
          <li>Nama, kontak, dan atribut sensitif (gender, agama, usia, status pernikahan) dihapus sebelum dianalisis.</li>
          <li>"Belum teridentifikasi" berarti tidak ditemukan pada dokumen, bukan bukti kandidat tidak mampu.</li>
          <li>Hapus data kandidat bila tidak lagi diperlukan (kebijakan retensi).</li>
        </ul>
      </section>
      {user.role === "admin" ? <Admin /> : <p className="muted">Monitoring dan audit hanya tersedia untuk admin.</p>}
    </>
  );
}
