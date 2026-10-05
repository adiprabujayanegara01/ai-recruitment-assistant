import { useState } from "react";
import { api } from "../services/api.js";
import { useAsync } from "../hooks/useAsync.js";
import { Empty, ErrorBox, Loading } from "../components/ui.jsx";

export default function Knowledge({ user }) {
  const docs = useAsync(api.knowledge);
  const [form, setForm] = useState({ title: "", category: "policy", text: "" });
  const [q, setQ] = useState("");
  const [ans, setAns] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const isAdmin = user.role === "admin";
  const add = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await api.addKnowledge(form.title, form.category, form.text); setForm({ ...form, title: "", text: "" }); docs.reload(); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  const ask = async (e) => { e.preventDefault(); setErr(null); setAns(null); try { setAns(await api.ask(q)); } catch (x) { setErr(x.message); } };
  return (
    <>
      <header className="page-head"><h1>Knowledge base perusahaan</h1></header>
      <p className="muted">Competency framework, kebijakan rekrutmen, atau standar job requirement. Dokumen ini dipakai sebagai konteks (RAG) saat analisis kandidat, dan dapat ditanyai langsung dengan jawaban ber-sumber.</p>
      <div className="grid2">
        <section className="card">
          <h2>Tanya knowledge base</h2>
          <form onSubmit={ask} className="row"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="mis. Apa standar kompetensi AI Engineer senior?" required /><button className="btn">Tanya</button></form>
          {err && <p className="error-text">{err}</p>}
          {ans && (ans.found ? (
            <div className="answer"><p className="pre">{ans.answer}</p>
              <h3>Sumber</h3>{ans.sources.map((s) => <p key={s.chunk_id} className="small muted"><strong>{s.title}</strong> (relevansi {s.score}) — {s.text.slice(0, 160)}…</p>)}
              {ans.mode === "extractive" && <p className="small muted">LLM belum dikonfigurasi; menampilkan potongan dokumen paling relevan.</p>}</div>
          ) : <p className="muted">{ans.message}</p>)}
        </section>
        <section className="card">
          <h2>Dokumen</h2>
          {docs.loading ? <Loading /> : docs.error ? <ErrorBox message={docs.error} onRetry={docs.reload} /> : docs.data.length === 0 ? <Empty title="Belum ada dokumen">{isAdmin ? "Tambahkan dokumen di bawah." : "Minta admin menambahkan dokumen."}</Empty> : (
            <ul className="list">{docs.data.map((d) => (
              <li key={d.id}><strong>{d.title}</strong> <span className="tag soft">{d.category}</span><div className="muted small">{d.chunks} potongan</div>
                {isAdmin && <button className="btn ghost sm" onClick={async () => { await api.deleteKnowledge(d.id); docs.reload(); }}>Hapus</button>}</li>))}</ul>)}
          {isAdmin && (
            <form onSubmit={add}>
              <h3>Tambah dokumen</h3>
              <label>Judul<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></label>
              <label>Kategori<input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></label>
              <label>Isi<textarea rows={6} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} required /></label>
              <button className="btn" disabled={busy}>{busy ? "Mengindeks…" : "Simpan & indeks"}</button>
            </form>)}
        </section>
      </div>
    </>
  );
}
