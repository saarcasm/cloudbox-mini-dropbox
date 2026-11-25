import React, { useState } from "react";
import { Cloud, Lock, Mail, Sparkles, User } from "lucide-react";
import { authApi, setToken } from "../api";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const cleanUsername = username.trim();
    if (mode === "register" && !/^[A-Za-z0-9@.+-_]+$/.test(cleanUsername)) {
      setError("Username can only contain letters, numbers, and @/./+/-/_ (no spaces).");
      return;
    }
    setLoading(true);
    try {
      const data =
        mode === "login"
          ? await authApi.login({ username: cleanUsername, password })
          : await authApi.register({
              username: cleanUsername,
              email: email.trim(),
              password,
              first_name: firstName.trim(),
            });
      setToken(data.token);
      onAuthenticated(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDemoLogin(demoUsername) {
    setError("");
    setLoading(true);
    try {
      const data = await authApi.login({ username: demoUsername, password: "demo1234" });
      setToken(data.token);
      onAuthenticated(data.user);
    } catch (err) {
      setError(`${err.message} (Run seed_demo first if demo accounts are not created yet.)`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="center-page">
      <div className="card auth-card">
        <div className="brand" style={{ justifyContent: "center", marginBottom: 16 }}>
          <div className="brand-icon">
            <Cloud size={22} />
          </div>
          <div>
            <h1>CloudBox</h1>
            <span>Mini Dropbox — Secure Cloud Storage</span>
          </div>
        </div>

        <div className="tab-row">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Create Account
          </button>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>{mode === "login" ? "Username or Email" : "Username"}</label>
            <div className="search-box" style={{ maxWidth: "100%" }}>
              <User size={16} color="#64748b" />
              <input
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={mode === "login" ? "saar or saar@cloudbox.edu" : "saar"}
              />
            </div>
          </div>

          {mode === "register" && (
            <>
              <div className="form-field">
                <label>Full Name</label>
                <input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Saar Ravindra Singh"
                />
              </div>
              <div className="form-field">
                <label>Email</label>
                <div className="search-box" style={{ maxWidth: "100%" }}>
                  <Mail size={16} color="#64748b" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
              </div>
            </>
          )}

          <div className="form-field">
            <label>Password</label>
            <div className="search-box" style={{ maxWidth: "100%" }}>
              <Lock size={16} color="#64748b" />
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
              />
            </div>
          </div>

          <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Sign In to CloudBox"
                : "Create CloudBox Account"}
          </button>
        </form>

        <div className="demo-box">
          <div className="demo-box-title">
            <Sparkles size={14} color="#2563eb" /> Quick Presentation Demo Login
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <button
              type="button"
              className="btn btn-outline"
              style={{ fontSize: "0.8rem", padding: "8px 10px" }}
              disabled={loading}
              onClick={() => handleDemoLogin("saar")}
            >
              Demo Admin (saar)
            </button>
            <button
              type="button"
              className="btn btn-outline"
              style={{ fontSize: "0.8rem", padding: "8px 10px" }}
              disabled={loading}
              onClick={() => handleDemoLogin("rohan")}
            >
              Demo User (rohan)
            </button>
          </div>
        </div>

        <p className="credits-footer">
          Submitted by <strong>Saar Ravindra Singh</strong>, <strong>Rohan Tiwari</strong>,{" "}
          <strong>Saksham Garg</strong>
          <br />
          Submitted to <strong>Mr. Mradul Jain</strong> • CSE Deptt.
        </p>
      </div>
    </div>
  );
}
