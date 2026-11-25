import React, { useEffect, useState } from "react";
import { Archive, Cloud, CloudDownload, FileText, Folder, ShieldCheck } from "lucide-react";
import { formatBytes, storageApi } from "../api";

export default function PublicShareView({ token, onBackToApp }) {
  const [share, setShare] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    storageApi
      .getPublicShare(token)
      .then((data) => {
        setShare(data);
        setError("");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="center-page">
      <div className="card" style={{ width: "100%", maxWidth: 620 }}>
        <div className="toolbar" style={{ marginBottom: 18 }}>
          <div className="brand" style={{ padding: 0 }}>
            <div className="brand-icon">
              <Cloud size={20} />
            </div>
            <div>
              <h1>CloudBox Share</h1>
              <span>Secure Public Download Link</span>
            </div>
          </div>
          <button className="btn btn-outline" onClick={onBackToApp}>
            Open App
          </button>
        </div>

        {loading && <p>Loading shared resource...</p>}
        {error && <div className="alert-error">{error}</div>}

        {share && (
          <>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: 16,
              }}
            >
              <span style={{ color: "#64748b", fontSize: "0.88rem" }}>
                Shared by <strong>{share.owner}</strong> • {share.download_count} downloads
              </span>
              <span className="badge badge-green">
                <ShieldCheck size={13} /> Verified Cloud Link
              </span>
            </div>

            {share.target_type === "file" && share.file && (
              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 12,
                  padding: 20,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 14,
                }}
              >
                <div className="item-name-cell">
                  <FileText size={28} color="#2563eb" />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "1.02rem" }}>{share.file.name}</div>
                    <small style={{ color: "#64748b" }}>
                      {formatBytes(share.file.size_bytes)} • {share.file.content_type}
                    </small>
                  </div>
                </div>
                <a
                  className="btn btn-primary"
                  href={storageApi.getPublicDownloadUrl(share.token)}
                  download={share.file.name}
                  style={{ textDecoration: "none" }}
                >
                  <CloudDownload size={16} /> Download File
                </a>
              </div>
            )}

            {share.target_type === "folder" && share.folder && (
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 12,
                    marginBottom: 14,
                  }}
                >
                  <div className="item-name-cell">
                    <Folder size={24} color="#2563eb" />
                    <strong style={{ fontSize: "1.05rem" }}>{share.folder.name}</strong>
                  </div>
                  <a
                    className="btn btn-primary"
                    href={storageApi.getPublicDownloadUrl(share.token)}
                    style={{ textDecoration: "none" }}
                  >
                    <Archive size={16} /> Download Folder (.zip)
                  </a>
                </div>

                {share.folder.files.length === 0 ? (
                  <p style={{ color: "#64748b" }}>This shared folder is empty.</p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>File</th>
                          <th>Size</th>
                          <th>Download</th>
                        </tr>
                      </thead>
                      <tbody>
                        {share.folder.files.map((f) => (
                          <tr key={f.id}>
                            <td>
                              <div className="item-name-cell">
                                <FileText size={16} color="#2563eb" />
                                <span>{f.name}</span>
                              </div>
                            </td>
                            <td>{formatBytes(f.size_bytes)}</td>
                            <td>
                              <a
                                className="btn btn-outline"
                                style={{ padding: "5px 10px", fontSize: "0.8rem", textDecoration: "none" }}
                                href={storageApi.getPublicDownloadUrl(share.token, f.id)}
                                download={f.name}
                              >
                                <CloudDownload size={14} /> Download
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
