"use client";

import { FormEvent, useEffect, useState } from "react";

type User = {
  id: string;
  username: string;
  roles: string[];
  permissions: string[];
  is_active: boolean;
  created_at: string;
};

const API_URL = "";

const navigation = [
  { label: "Overview", icon: "◈", active: true },
  { label: "Assistant", icon: "✦", active: false },
  { label: "Tasks", icon: "□", active: false },
  { label: "Notes", icon: "▤", active: false },
];

const metrics = [
  { label: "System status", value: "Foundation ready", detail: "Health endpoints online", tone: "green" },
  { label: "AI provider", value: "Disabled", detail: "Enable in a future milestone", tone: "purple" },
  { label: "Storage", value: "SQLite ready", detail: "Identity persistence online", tone: "blue" },
];

function csrfHeader(): Record<string, string> {
  const prefix = "nexus_csrf=";
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  if (!cookie) return {};
  const csrf = decodeURIComponent(cookie.slice(prefix.length));
  return csrf ? { "X-CSRF-Token": csrf } : {};
}

async function readUser(): Promise<User | null> {
  let response = await fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" });
  if (response.status === 401) {
    const refreshed = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: csrfHeader(),
    });
    if (refreshed.ok) {
      response = await fetch(`${API_URL}/api/v1/auth/me`, { credentials: "include" });
    }
  }
  if (!response.ok) return null;
  return response.json() as Promise<User>;
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        setError("Unable to sign in with those credentials.");
        return;
      }
      const body = (await response.json()) as { user: User };
      onLogin(body.user);
    } catch {
      setError("NexusOS is unavailable. Check that the API is running.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="login-heading">
        <div className="brand auth-brand">
          <div className="brand-mark">N</div>
          <div>
            <strong>NexusOS</strong>
            <span>Personal command center</span>
          </div>
        </div>
        <p className="eyebrow">Private workspace</p>
        <h1 id="login-heading">Welcome back.</h1>
        <p className="auth-copy">Sign in to your local NexusOS workspace.</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            Username
            <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Password
            <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button auth-submit" disabled={submitting} type="submit">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="auth-footnote">Local-first. Private by default.</p>
      </section>
    </main>
  );
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div>
            <strong>NexusOS</strong>
            <span>Personal command center</span>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="nav-list">
          <p className="eyebrow">Workspace</p>
          {navigation.map((item) => (
            <a className={`nav-item${item.active ? " active" : ""}`} href="#" key={item.label}>
              <span aria-hidden="true" className="nav-icon">{item.icon}</span>
              {item.label}
              {item.active && <span className="active-dot" aria-label="Current page" />}
            </a>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="connection-dot" />
          <div>
            <strong>Local mode</strong>
            <span>Private by default</span>
          </div>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Workspace / Overview</p>
            <h1>Good morning, {user.username}.</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" aria-label="Open command palette">⌘ K</button>
            <button className="avatar" aria-label="Sign out" onClick={onLogout}>↪</button>
          </div>
        </header>

        <div className="hero-card">
          <div className="hero-copy">
            <span className="status-pill"><span /> Milestone 2 identity online</span>
            <h2>Your digital life, <em>connected.</em></h2>
            <p>Your private workspace is authenticated. Persistence and session security are now ready for the next Nexus modules.</p>
            <button className="primary-button">Explore the foundation <span aria-hidden="true">→</span></button>
          </div>
          <div className="hero-orbit" aria-hidden="true">
            <div className="orbit orbit-one"><span>AI</span></div>
            <div className="orbit orbit-two"><span>SYS</span></div>
            <div className="orbit orbit-three"><span>✦</span></div>
            <div className="core">N</div>
          </div>
        </div>

        <section className="section-block" aria-labelledby="status-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">At a glance</p>
              <h2 id="status-heading">System status</h2>
            </div>
            <span className="updated">Authenticated locally</span>
          </div>
          <div className="metric-grid">
            {metrics.map((metric) => (
              <article className="metric-card" key={metric.label}>
                <div className={`metric-indicator ${metric.tone}`} />
                <p>{metric.label}</p>
                <strong>{metric.value}</strong>
                <span>{metric.detail}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="next-card" aria-labelledby="next-heading">
          <div className="next-icon">✦</div>
          <div>
            <p className="eyebrow">Next up</p>
            <h2 id="next-heading">Build your personal workspace</h2>
            <p>Tasks, notes, and conversations remain intentionally locked until their approved milestones.</p>
          </div>
          <span className="lock-label">Next modules pending</span>
        </section>

        <footer>Local-first. Private by default. <span>NexusOS 0.1.0</span></footer>
      </section>
    </main>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    readUser().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  async function logout() {
    await fetch(`${API_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: csrfHeader(),
    });
    setUser(null);
  }

  if (loading) {
    return <main className="auth-shell"><p className="loading-copy">Loading your local workspace…</p></main>;
  }
  return user ? <Dashboard user={user} onLogout={logout} /> : <Login onLogin={setUser} />;
}
