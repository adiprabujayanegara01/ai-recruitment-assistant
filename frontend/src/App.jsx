import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, hasToken, setToken } from "./services/api.js";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Jobs from "./pages/Jobs.jsx";
import JobDetail from "./pages/JobDetail.jsx";
import Candidates from "./pages/Candidates.jsx";
import CandidateDetail from "./pages/CandidateDetail.jsx";
import Analysis from "./pages/Analysis.jsx";
import Knowledge from "./pages/Knowledge.jsx";
import Settings from "./pages/Settings.jsx";

function Shell({ user, onLogout }) {
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">Recruitment<br />Assistant</div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/candidates">Kandidat</NavLink>
          <NavLink to="/jobs">Lowongan</NavLink>
          <NavLink to="/knowledge">Knowledge base</NavLink>
          <NavLink to="/settings">Pengaturan</NavLink>
        </nav>
        <div className="who">
          <div>{user.name}</div>
          <div className="muted small">{user.role === "admin" ? "Admin" : "Recruiter"}</div>
          <button className="btn ghost sm" onClick={onLogout}>Keluar</button>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/candidates/:id" element={<CandidateDetail />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/analysis/:id" element={<Analysis />} />
          <Route path="/knowledge" element={<Knowledge user={user} />} />
          <Route path="/settings" element={<Settings user={user} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!hasToken());
  const nav = useNavigate();
  useEffect(() => { if (hasToken()) api.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true)); }, []);
  const logout = () => { setToken(null); setUser(null); nav("/login"); };
  if (!ready) return <p className="muted pad">Memuat…</p>;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login onLogin={(u) => { setUser(u); nav("/"); }} />} />
      <Route path="/*" element={user ? <Shell user={user} onLogout={logout} /> : <Navigate to="/login" />} />
    </Routes>
  );
}
