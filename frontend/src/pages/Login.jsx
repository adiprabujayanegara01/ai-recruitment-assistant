import { useState } from "react";
import { api, setToken } from "../services/api.js";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { const r = await api.login(email, password); setToken(r.access_token); onLogin(r.user); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="login">
      <form onSubmit={submit} className="card login-card">
        <h1>AI Recruitment Assistant</h1>
        <p className="muted">Alat bantu analisis kandidat. Hasil AI adalah saran untuk ditinjau recruiter, bukan keputusan seleksi.</p>
        <label>Email<input type="text" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {error && <p className="error-text" role="alert">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? "Masuk…" : "Masuk"}</button>
      </form>
    </div>
  );
}
