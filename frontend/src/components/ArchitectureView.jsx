import React from "react";
import { ArrowDown, CheckCircle2, Cloud, Database, Layers, Server, ShieldCheck, Users } from "lucide-react";

export default function ArchitectureView({ storageProvider }) {
  const stack = [
    { label: "Frontend", value: "React.js + Vite (Responsive Web & Mobile)" },
    { label: "Backend API", value: "Django + Django REST Framework" },
    { label: "Database", value: "MySQL (Production) / SQLite (Dev)" },
    { label: "Cloud Storage", value: `AWS S3 (Active: ${storageProvider || "Local S3 Bucket"})` },
    { label: "Authentication", value: "Token Auth + Owner-Scoped Access Control" },
    { label: "Version Control", value: "GitHub" },
  ];

  const nfrs = [
    "Large File Uploads: Chunked upload (>2 MB) with 3x auto-retry up to 100 MB.",
    "Security: Encrypted at rest (AES-256 in S3), SHA-256 checksums, revocable share tokens.",
    "Scalability: Stateless REST API + S3 object storage for concurrent multi-user access.",
    "Usability: Clean responsive interface tested across desktop and mobile viewports.",
  ];

  return (
    <div>
      <div className="toolbar">
        <div>
          <h2 style={{ margin: "0 0 4px" }}>System Architecture & Project Overview</h2>
          <span style={{ color: "#64748b", fontSize: "0.88rem" }}>
            Cloud-Based File Storage System (Mini Dropbox) — CSE Mini Project
          </span>
        </div>
        <span className="badge badge-blue">
          <Users size={14} /> Saar • Rohan • Saksham
        </span>
      </div>

      {/* Live System Architecture Diagram */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginTop: 0, textAlign: "center" }}>
          System Architecture Diagram — CloudBox (Mini Dropbox)
        </h3>
        <div className="arch-diagram">
          <div className="arch-node arch-amber">
            <strong>User (Web / Mobile)</strong>
            <small>Responsive Browser Client</small>
          </div>
          <ArrowDown size={20} color="#64748b" />
          <div className="arch-node arch-sky">
            <strong>Frontend (React.js)</strong>
            <small>Dashboard | File Explorer | Share Links | Chunked Uploader</small>
          </div>
          <ArrowDown size={20} color="#64748b" />
          <div className="arch-node arch-green" style={{ maxWidth: 460, width: "100%" }}>
            <strong>Backend API (Django REST Framework)</strong>
            <small>Authentication | File Management | Sharing | Quota Enforcement</small>
          </div>
          <div className="arch-branches">
            <div className="arch-node arch-purple">
              <Database size={18} style={{ marginBottom: 4 }} />
              <strong>Database (MySQL / SQLite)</strong>
              <small>Users, Quotas, Folder Tree, File Metadata & Share Tokens</small>
            </div>
            <div className="arch-node arch-pink">
              <Cloud size={18} style={{ marginBottom: 4 }} />
              <strong>Cloud Storage (AWS S3)</strong>
              <small>AES-256 Encrypted Object Storage & Streaming Downloads</small>
            </div>
            <div className="arch-node arch-indigo">
              <Server size={18} style={{ marginBottom: 4 }} />
              <strong>Admin Dashboard</strong>
              <small>User & Storage Quota Management</small>
            </div>
          </div>
        </div>
      </div>

      <div className="quick-actions-grid">
        <div className="card">
          <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <Layers size={18} color="#2563eb" /> Technology Stack
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {stack.map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  paddingBottom: 8,
                  borderBottom: "1px solid #f1f5f9",
                  fontSize: "0.9rem",
                }}
              >
                <span style={{ color: "#64748b", fontWeight: 600 }}>{item.label}</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <ShieldCheck size={18} color="#16a34a" /> Non-Functional & Risk Mitigations
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            {nfrs.map((item) => (
              <div key={item} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: "0.9rem" }}>
                <CheckCircle2 size={17} color="#16a34a" style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{item}</span>
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: 16,
              padding: 12,
              borderRadius: 10,
              background: "#f8fafc",
              fontSize: "0.84rem",
              color: "#475569",
            }}
          >
            <strong>Team Credits:</strong> Submitted by Saar Ravindra Singh, Rohan Tiwari, and
            Saksham Garg to <strong>Mr. Mradul Jain</strong> (CSE Deptt.).
          </div>
        </div>
      </div>
    </div>
  );
}
