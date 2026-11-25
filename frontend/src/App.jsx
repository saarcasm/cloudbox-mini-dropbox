import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Cloud,
  FolderOpen,
  Layers,
  LayoutDashboard,
  Link2,
  LogOut,
  Search,
  Shield,
} from "lucide-react";
import { authApi, formatBytes, getToken, setToken, storageApi } from "./api";
import AdminView from "./components/AdminView";
import ArchitectureView from "./components/ArchitectureView";
import AuthScreen from "./components/AuthScreen";
import DashboardView from "./components/DashboardView";
import FilesView from "./components/FilesView";
import PublicShareView from "./components/PublicShareView";
import SharesView from "./components/SharesView";

function getShareTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("share") || "";
}

export default function App() {
  const [publicShareToken, setPublicShareToken] = useState(getShareTokenFromUrl);
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(Boolean(getToken()));
  const [tab, setTab] = useState("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [stats, setStats] = useState(null);
  const [toast, setToast] = useState("");

  function showToast(msg) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function refreshDashboard() {
    if (!getToken()) return;
    try {
      const data = await storageApi.dashboard();
      setStats(data);
    } catch {
      // Ignore transient dashboard refresh failures
    }
  }

  useEffect(() => {
    if (!getToken()) {
      setCheckingAuth(false);
      return;
    }
    authApi
      .me()
      .then((u) => {
        setUser(u);
        return refreshDashboard();
      })
      .catch(() => {
        setToken("");
        setUser(null);
      })
      .finally(() => setCheckingAuth(false));
  }, []);

  async function handleLogout() {
    try {
      await authApi.logout();
    } catch {
      // ignore
    }
    setToken("");
    setUser(null);
    setStats(null);
  }

  if (publicShareToken) {
    return (
      <PublicShareView
        token={publicShareToken}
        onBackToApp={() => {
          window.history.replaceState({}, "", "/");
          setPublicShareToken("");
        }}
      />
    );
  }

  if (checkingAuth) {
    return (
      <div className="center-page">
        <div className="card">Connecting to CloudBox...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <AuthScreen
        onAuthenticated={(loggedUser) => {
          setUser(loggedUser);
          refreshDashboard();
        }}
      />
    );
  }

  const usagePercent =
    stats?.usage_percent ??
    (user.quota_bytes ? Math.round((user.used_bytes / user.quota_bytes) * 100) : 0);
  const usedBytes = stats?.used_bytes ?? user.used_bytes ?? 0;
  const quotaBytes = stats?.quota_bytes ?? user.quota_bytes ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Cloud size={22} />
          </div>
          <div>
            <h1>CloudBox</h1>
            <span>Mini Dropbox</span>
          </div>
        </div>

        <nav className="nav-list">
          <button
            className={`nav-btn ${tab === "dashboard" ? "active" : ""}`}
            onClick={() => setTab("dashboard")}
          >
            <LayoutDashboard size={18} /> Dashboard
          </button>
          <button
            className={`nav-btn ${tab === "files" ? "active" : ""}`}
            onClick={() => setTab("files")}
          >
            <FolderOpen size={18} /> My Files
          </button>
          <button
            className={`nav-btn ${tab === "shares" ? "active" : ""}`}
            onClick={() => setTab("shares")}
          >
            <Link2 size={18} /> Shared Links
          </button>
          <button
            className={`nav-btn ${tab === "architecture" ? "active" : ""}`}
            onClick={() => setTab("architecture")}
          >
            <Layers size={18} /> Architecture
          </button>
          {user.is_staff && (
            <button
              className={`nav-btn ${tab === "admin" ? "active" : ""}`}
              onClick={() => setTab("admin")}
            >
              <Shield size={18} /> Admin
            </button>
          )}
        </nav>

        <div className="sidebar-quota">
          <div className="quota-label">
            <strong>Storage</strong>
            <span>{usagePercent}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${Math.min(100, usagePercent)}%` }} />
          </div>
          <small style={{ display: "block", marginTop: 8, color: "#64748b" }}>
            {formatBytes(usedBytes)} of {formatBytes(quotaBytes)} used
          </small>
        </div>

        <div className="user-footer">
          <div className="user-meta">
            <strong>{user.first_name || user.username}</strong>
            <small>{user.email || `@${user.username}`}</small>
          </div>
          <button className="btn-icon" title="Sign out" onClick={handleLogout}>
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="search-box">
            <Search size={16} color="#64748b" />
            <input
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (tab !== "files" && e.target.value.trim()) {
                  setTab("files");
                }
              }}
              placeholder="Search files and folders..."
            />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="badge badge-blue">@{user.username}</span>
            <button className="btn btn-outline" style={{ padding: "7px 12px" }} onClick={handleLogout}>
              <LogOut size={15} /> Sign Out
            </button>
          </div>
        </header>

        <main className="content">
          {tab === "dashboard" && (
            <DashboardView
              stats={stats}
              onRefresh={() => {
                refreshDashboard();
                showToast("Storage dashboard updated.");
              }}
              onOpenFiles={() => setTab("files")}
              onOpenShares={() => setTab("shares")}
            />
          )}
          {tab === "files" && (
            <FilesView
              searchQuery={searchQuery}
              onRefreshStats={refreshDashboard}
              onNotify={showToast}
            />
          )}
          {tab === "shares" && (
            <SharesView
              onOpenSharePreview={(token) => {
                window.history.replaceState({}, "", `/?share=${token}`);
                setPublicShareToken(token);
              }}
            />
          )}
          {tab === "architecture" && (
            <ArchitectureView storageProvider={stats?.storage_provider} />
          )}
          {tab === "admin" && user.is_staff && <AdminView />}
        </main>
      </div>

      {toast && (
        <div className="toast-banner">
          <CheckCircle2 size={16} color="#16a34a" />
          <span>{toast}</span>
        </div>
      )}

      <nav className="mobile-nav">
        <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
          <LayoutDashboard size={18} />
          Home
        </button>
        <button className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>
          <FolderOpen size={18} />
          Files
        </button>
        <button className={tab === "shares" ? "active" : ""} onClick={() => setTab("shares")}>
          <Link2 size={18} />
          Shares
        </button>
        <button className={tab === "architecture" ? "active" : ""} onClick={() => setTab("architecture")}>
          <Layers size={18} />
          Specs
        </button>
        {user.is_staff && (
          <button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>
            <Shield size={18} />
            Admin
          </button>
        )}
      </nav>
    </div>
  );
}
