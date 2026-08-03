"use client";

import { FormEvent, useState } from "react";
import { login } from "../lib/auth";
import type { User } from "../lib/auth";

export function LoadingScreen() {
  return (
    <main className="state-shell">
      <div className="loading-card" role="status">
        <span className="loading-orb" aria-hidden="true" />
        <strong>Opening your workspace</strong>
        <span>Checking your local session…</span>
      </div>
    </main>
  );
}

export function ConnectionError({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="state-shell">
      <section aria-labelledby="connection-heading" className="state-card">
        <span className="state-icon error-icon" aria-hidden="true">!</span>
        <p className="eyebrow">Connection issue</p>
        <h1 id="connection-heading">NexusOS is unavailable.</h1>
        <p>Make sure the local API is running, then try opening your workspace again.</p>
        <button className="primary-button" onClick={onRetry} type="button">Try again <span aria-hidden="true">↻</span></button>
      </section>
    </main>
  );
}

export function LoginScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      onLogin(await login(username, password));
    } catch {
      setError("Unable to sign in with those credentials.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section aria-labelledby="login-heading" className="auth-card">
        <div className="brand auth-brand">
          <div className="brand-mark">N</div>
          <div><strong>NexusOS</strong><span>Personal command center</span></div>
        </div>
        <p className="eyebrow">Private workspace</p>
        <h1 id="login-heading">Welcome back.</h1>
        <p className="auth-copy">Sign in to your local NexusOS workspace.</p>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="username">Username</label>
          <input autoComplete="username" id="username" onChange={(event) => setUsername(event.target.value)} required value={username} />
          <label htmlFor="password">Password</label>
          <input autoComplete="current-password" id="password" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
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
