import React, { useState } from "react";
import { useAuth, demoOfficer } from "../auth/AuthContext.jsx";

export function Login() {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(identifier, password);
    } catch (e) {
      setError(e.message || "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  function useDemoAccess() {
    setIdentifier(demoOfficer.email);
    setPassword("Field@123");
    setError("");
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-mark">DC</div>
          <div>
            <strong>Drug Companion</strong>
            <span>FIELD INTELLIGENCE CONSOLE</span>
          </div>
        </div>

        <div className="auth-copy">
          <div className="panel-eyebrow">SECURE OFFICER ACCESS</div>
          <h1>Sign in to your field console.</h1>
          <p>
            Access field analysis, case records, evidence integrity, and
            operational analytics from one authenticated workspace.
          </p>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <label>
            <span>OFFICER ID OR EMAIL</span>
            <input
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="FO-0017 or officer@example.com"
              required
            />
          </label>

          <label>
            <span>PASSWORD</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Authenticating…" : "Sign in to console →"}
          </button>
        </form>

        <button className="demo-access" type="button" onClick={useDemoAccess}>
          Use prototype officer access
        </button>

        <div className="auth-notice">
          Prototype authentication is local to this browser. Production
          deployment should connect this interface to server-side identity,
          session management, MFA, and role-based access control.
        </div>
      </section>
    </main>
  );
}
