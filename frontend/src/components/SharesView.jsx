import React, { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, FileText, Folder, Link2, Trash2 } from "lucide-react";
import { formatBytes, storageApi } from "../api";

export default function SharesView({ onOpenSharePreview }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState(null);

  async function loadShares() {
    setLoading(true);
    try {
      const data = await storageApi.listShares();
      setShares(data || []);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadShares();
  }, []);

  async function handleToggle(share) {
    try {
      await storageApi.toggleShare(share.id, !share.is_active);
      loadShares();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(share) {
    try {
      await storageApi.deleteShare(share.id);
      loadShares();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCopy(share) {
    const url = `${window.location.origin}/?share=${share.token}`;
    await navigator.clipboard.writeText(url);
    setCopiedId(share.id);
    setTimeout(() => setCopiedId(null), 1800);
  }

  return (
    <div>
      <div className="toolbar">
        <div>
          <h2 style={{ margin: "0 0 4px" }}>Shared Links</h2>
          <span style={{ color: "#64748b", fontSize: "0.88rem" }}>
            Control public download links for your files and folders
          </span>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="card">
        {loading ? (
          <p style={{ margin: 0, color: "#64748b" }}>Loading shared links...</p>
        ) : shares.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 0", color: "#64748b" }}>
            <Link2 size={28} style={{ marginBottom: 8 }} />
            <p style={{ margin: 0 }}>
              No share links created yet. Click the link icon on any file or folder in My Files.
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Target</th>
                  <th>Status</th>
                  <th>Downloads</th>
                  <th>Expires</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {shares.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div className="item-name-cell">
                        {s.target_type === "folder" ? (
                          <Folder size={17} color="#2563eb" />
                        ) : (
                          <FileText size={17} color="#475569" />
                        )}
                        <div>
                          <div style={{ fontWeight: 600 }}>{s.target_name}</div>
                          {s.target_size_bytes !== null && (
                            <small style={{ color: "#64748b" }}>
                              {formatBytes(s.target_size_bytes)}
                            </small>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      {s.is_active && !s.is_expired ? (
                        <span className="badge badge-green">Active</span>
                      ) : (
                        <span className="badge badge-red">
                          {s.is_expired ? "Expired" : "Revoked"}
                        </span>
                      )}
                    </td>
                    <td>{s.download_count}</td>
                    <td>{s.expires_at ? new Date(s.expires_at).toLocaleString() : "Never"}</td>
                    <td>
                      <div className="actions-row">
                        <button
                          className="btn-icon"
                          title="Copy share URL"
                          onClick={() => handleCopy(s)}
                        >
                          {copiedId === s.id ? <Check size={15} color="#16a34a" /> : <Copy size={15} />}
                        </button>
                        <button
                          className="btn-icon"
                          title="Preview public download page"
                          onClick={() => onOpenSharePreview(s.token)}
                        >
                          <ExternalLink size={15} />
                        </button>
                        <button
                          className="btn btn-outline"
                          style={{ padding: "5px 10px", fontSize: "0.78rem" }}
                          onClick={() => handleToggle(s)}
                        >
                          {s.is_active ? "Revoke" : "Enable"}
                        </button>
                        <button
                          className="btn-icon"
                          title="Delete link"
                          onClick={() => handleDelete(s)}
                        >
                          <Trash2 size={15} color="#dc2626" />
                        </button>
                      </div>
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
