export const STATUS = {
  matched: { label: "Teridentifikasi", cls: "ok" },
  related: { label: "Setara / terkait", cls: "rel" },
  not_identified: { label: "Belum teridentifikasi", cls: "no" },
};
const METHOD = { exact: "disebut langsung", declared: "hanya di daftar skill", implied: "tersirat dari teknologi", semantic: "kemiripan makna" };
export const methodLabel = (m) => (m?.startsWith("related:") ? `setara dengan ${m.split(":")[1]}` : METHOD[m] || "");

export function Badge({ status }) {
  const s = STATUS[status] || STATUS.not_identified;
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

export function Loading({ text = "Memuat…" }) { return <p className="muted pad">{text}</p>; }
export function ErrorBox({ message, onRetry }) {
  return (
    <div className="error" role="alert">
      <p>{message}</p>
      {onRetry && <button className="btn ghost" onClick={onRetry}>Coba lagi</button>}
    </div>
  );
}
export function Empty({ title, children }) {
  return <div className="empty"><h3>{title}</h3><p className="muted">{children}</p></div>;
}

/** Bilah skor bersegmen: lebar tiap segmen = bobot efektif, isi = skor komponen. */
export function ScoreBar({ breakdown }) {
  const names = { skill: "Skill", experience: "Pengalaman", education: "Pendidikan", project: "Proyek" };
  const parts = Object.entries(breakdown || {}).filter(([, v]) => v.evaluated);
  return (
    <div>
      <div className="scorebar" role="img" aria-label="Rincian skor per komponen">
        {parts.map(([k, v]) => (
          <div key={k} className="seg" style={{ flexGrow: v.applied_weight * 100 }} title={`${names[k]}: ${Math.round(v.score * 100)}%`}>
            <div className="fill" style={{ width: `${v.score * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="seglegend">
        {parts.map(([k, v]) => (
          <div key={k} style={{ flexGrow: v.applied_weight * 100, flexBasis: 0 }}>
            <strong>{names[k]}</strong> {Math.round(v.score * 100)}%
            <span className="muted"> · bobot {Math.round(v.applied_weight * 100)}%</span>
            {v.note && <div className="muted small">{v.note}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

export function scoreClass(s) { return s >= 70 ? "hi" : s >= 45 ? "mid" : "lo"; }
export function ScoreChip({ score }) { return <span className={`chip ${scoreClass(score)}`}>{Math.round(score)}%</span>; }
