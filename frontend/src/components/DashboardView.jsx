import React, { useRef, useState } from "react";
import { CloudDownload, CloudUpload, FileText, FolderOpen, Link2, ShieldCheck } from "lucide-react";
import { formatBytes, storageApi } from "../api";

export default function DashboardView({ stats, onRefresh, onOpenFiles, onOpenShares }) {
  const inputRef = useRef(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [uploadingName, setUploadingName] = useState("");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  async function handleFiles(fileList) {
    if (!fileList || fileList.length === 0) return;
    setError("");
    for (const file of Array.from(fileList)) {
      setUploadingName(file.name);
      setUploadProgress(5);
      try {
        await storageApi.uploadFile(file, null, (pct) => setUploadProgress(pct));
      } catch (err) {
        setError(err.message);
      }
    }
    setUploadProgress(null);
    setUploadingName("");
    onRefresh();
  }

  const breakdown = stats?.breakdown_bytes || {};
  const categories = [
    { key: "documents", label: "Documents", color: "#2563eb" },
    { key: "images", label: "Images", color: "#16a34a" },
    { key: "media", label: "Audio & Video", color: "#d97706" },
    { key: "archives", label: "Archives", color: "#7c3aed" },
    { key: "other", label: "Other", color: "#64748b" },
  ];

  return (
    <div>
      <div className="toolbar">
        <div>
          <h2 style={{ margin: "0 0 4px" }}>Storage Dashboard</h2>
          <span style={{ color: "#64748b", fontSize: "0.88rem" }}>
            Bucket Provider: <strong>{stats?.storage_provider || "Cloud Bucket"}</strong>
          </span>
        </div>
        <span className="badge badge-green">
          <ShieldCheck size={14} /> Encrypted at Rest (AES-256)
        </span>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="stats-grid">
        <div className="card stat-card">
          <span>Used Storage</span>
          <strong>{formatBytes(stats?.used_bytes || 0)}</strong>
          <small style={{ color: "#64748b" }}>{stats?.usage_percent || 0}% of quota</small>
        </div>
        <div className="card stat-card">
          <span>Available Storage</span>
          <strong>{formatBytes(stats?.available_bytes || 0)}</strong>
          <small style={{ color: "#64748b" }}>of {formatBytes(stats?.quota_bytes || 0)}</small>
        </div>
        <div className="card stat-card">
          <span>Total Files & Folders</span>
          <strong>
            {stats?.file_count || 0} / {stats?.folder_count || 0}
          </strong>
          <small style={{ color: "#64748b" }}>Files / Folders stored</small>
        </div>
        <div className="card stat-card">
          <span>Active Share Links</span>
          <strong>{stats?.active_share_count || 0}</strong>
          <small style={{ color: "#64748b" }}>Public download links</small>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="quota-label" style={{ fontSize: "0.9rem" }}>
          <strong>Storage Quota Usage</strong>
          <span>
            {formatBytes(stats?.used_bytes || 0)} used of {formatBytes(stats?.quota_bytes || 0)}
          </span>
        </div>
        <div className="progress-track" style={{ height: 12, marginBottom: 14 }}>
          <div
            className="progress-fill"
            style={{ width: `${Math.min(100, stats?.usage_percent || 0)}%` }}
          />
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
          {categories.map((cat) => (
            <div key={cat.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.84rem" }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: cat.color,
                  display: "inline-block",
                }}
              />
              <span style={{ color: "#64748b" }}>{cat.label}:</span>
              <strong>{formatBytes(breakdown[cat.key] || 0)}</strong>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Upload & Download Cards inspired by Slide 4 */}
      <div className="quick-actions-grid">
        <div
          className={`hero-action-card ${dragOver ? "drag-over" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
          <div className="hero-cloud-badge">
            <CloudUpload size={28} />
          </div>
          <h3 style={{ margin: "0 0 6px" }}>Upload Files</h3>
          <p style={{ margin: "0 0 12px", color: "#64748b", fontSize: "0.88rem" }}>
            Drag & drop or click to upload up to 100 MB (chunked auto-retry supported)
          </p>
          {uploadProgress !== null && (
            <div style={{ maxWidth: 280, margin: "0 auto" }}>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
              </div>
              <small style={{ color: "#2563eb", display: "block", marginTop: 6 }}>
                Uploading {uploadingName}... {uploadProgress}%
              </small>
            </div>
          )}
        </div>

        <div className="hero-action-card" style={{ borderStyle: "solid", cursor: "default" }}>
          <div className="hero-cloud-badge">
            <CloudDownload size={28} />
          </div>
          <h3 style={{ margin: "0 0 6px" }}>Download & Share Links</h3>
          <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: "0.88rem" }}>
            Browse your cloud folders, download files, or generate shareable links.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
            <button className="btn btn-primary" onClick={onOpenFiles}>
              <FolderOpen size={16} /> Open My Files
            </button>
            <button className="btn btn-outline" onClick={onOpenShares}>
              <Link2 size={16} /> Manage Links
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recent Files</h3>
        {!stats?.recent_files?.length ? (
          <p style={{ color: "#64748b", margin: 0 }}>
            No files uploaded yet. Upload a file above to get started.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size</th>
                  <th>Updated</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_files.map((f) => (
                  <tr key={f.id}>
                    <td>
                      <div className="item-name-cell">
                        <FileText size={16} color="#2563eb" />
                        <span>{f.name}</span>
                      </div>
                    </td>
                    <td>{formatBytes(f.size_bytes)}</td>
                    <td>{new Date(f.updated_at).toLocaleString()}</td>
                    <td>
                      <button
                        className="btn btn-outline"
                        style={{ padding: "5px 10px", fontSize: "0.8rem" }}
                        onClick={() => storageApi.downloadFile(f.id, f.name)}
                      >
                        <CloudDownload size={14} /> Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
