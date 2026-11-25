import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronRight,
  CloudDownload,
  CloudUpload,
  Copy,
  Edit3,
  Eye,
  FileText,
  Folder,
  FolderPlus,
  Home,
  Link2,
  Trash2,
  X,
} from "lucide-react";
import { formatBytes, storageApi } from "../api";

function isPreviewable(file) {
  const ct = (file.content_type || "").toLowerCase();
  const name = file.name.toLowerCase();
  return (
    ct.startsWith("image/") ||
    ct.startsWith("text/") ||
    ct === "application/pdf" ||
    name.endsWith(".svg") ||
    name.endsWith(".csv") ||
    name.endsWith(".md") ||
    name.endsWith(".json") ||
    name.endsWith(".txt")
  );
}

export default function FilesView({ searchQuery, onRefreshStats, onNotify }) {
  const fileInputRef = useRef(null);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([]);
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(null);
  const [uploadingName, setUploadingName] = useState("");
  const [dragOver, setDragOver] = useState(false);

  // Modals
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [shareModal, setShareModal] = useState(null);
  const [copied, setCopied] = useState(false);

  // File Preview Modal
  const [previewState, setPreviewState] = useState(null); // { file, kind, url, text }

  async function loadDirectory(folderId = currentFolderId, q = searchQuery) {
    setLoading(true);
    try {
      const data = await storageApi.items(folderId, q);
      setBreadcrumbs(data.breadcrumbs || []);
      setFolders(data.folders || []);
      setFiles(data.files || []);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDirectory(currentFolderId, searchQuery);
  }, [currentFolderId, searchQuery]);

  useEffect(() => {
    return () => {
      if (previewState?.url) {
        URL.revokeObjectURL(previewState.url);
      }
    };
  }, [previewState]);

  async function handleUploadFiles(fileList) {
    if (!fileList || fileList.length === 0) return;
    setError("");
    let uploadedCount = 0;
    for (const file of Array.from(fileList)) {
      setUploadingName(file.name);
      setUploadProgress(5);
      try {
        await storageApi.uploadFile(file, currentFolderId, (pct) => setUploadProgress(pct));
        uploadedCount += 1;
      } catch (err) {
        setError(err.message);
      }
    }
    setUploadProgress(null);
    setUploadingName("");
    await loadDirectory(currentFolderId, searchQuery);
    onRefreshStats();
    if (uploadedCount > 0 && onNotify) {
      onNotify(`Uploaded ${uploadedCount} file${uploadedCount > 1 ? "s" : ""} to cloud storage.`);
    }
  }

  async function handleCreateFolder(e) {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    try {
      const created = await storageApi.createFolder(newFolderName.trim(), currentFolderId);
      setNewFolderName("");
      setShowNewFolder(false);
      await loadDirectory(currentFolderId, searchQuery);
      onRefreshStats();
      onNotify?.(`Created folder "${created.name}".`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRenameSubmit(e) {
    e.preventDefault();
    if (!renameTarget || !renameValue.trim()) return;
    try {
      if (renameTarget.type === "file") {
        await storageApi.renameFile(renameTarget.id, renameValue.trim());
      } else {
        await storageApi.renameFolder(renameTarget.id, renameValue.trim());
      }
      setRenameTarget(null);
      await loadDirectory(currentFolderId, searchQuery);
      onNotify?.(`Renamed to "${renameValue.trim()}".`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(type, id, name) {
    if (!window.confirm(`Delete ${type} "${name}"? This cannot be undone.`)) return;
    try {
      if (type === "file") {
        await storageApi.deleteFile(id);
      } else {
        await storageApi.deleteFolder(id);
      }
      await loadDirectory(currentFolderId, searchQuery);
      onRefreshStats();
      onNotify?.(`Deleted ${type} "${name}".`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function openPreview(file) {
    try {
      const blob = await storageApi.fetchPreviewBlob(file.id);
      const ct = (file.content_type || "").toLowerCase();
      const lower = file.name.toLowerCase();
      if (ct.startsWith("image/") || lower.endsWith(".svg")) {
        const url = URL.createObjectURL(blob);
        setPreviewState({ file, kind: "image", url });
      } else if (ct === "application/pdf" || lower.endsWith(".pdf")) {
        const url = URL.createObjectURL(blob);
        setPreviewState({ file, kind: "pdf", url });
      } else {
        const text = await blob.text();
        setPreviewState({ file, kind: "text", text });
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function openShareDialog(type, id, name) {
    setCopied(false);
    setShareModal({ type, id, name, link: null, expiresHours: "" });
    try {
      const payload = type === "file" ? { file_id: id } : { folder_id: id };
      const link = await storageApi.createShare(payload);
      setShareModal({ type, id, name, link, expiresHours: "" });
    } catch (err) {
      setError(err.message);
      setShareModal(null);
    }
  }

  async function regenerateWithExpiry() {
    if (!shareModal) return;
    const payload =
      shareModal.type === "file" ? { file_id: shareModal.id } : { folder_id: shareModal.id };
    if (shareModal.expiresHours) {
      payload.expires_hours = Number(shareModal.expiresHours);
    }
    try {
      const link = await storageApi.createShare(payload);
      setShareModal({ ...shareModal, link });
      setCopied(false);
      onNotify?.("Share link updated.");
    } catch (err) {
      setError(err.message);
    }
  }

  function getShareUrl(token) {
    return `${window.location.origin}/?share=${token}`;
  }

  async function copyLink(token) {
    const url = getShareUrl(token);
    await navigator.clipboard.writeText(url);
    setCopied(true);
    onNotify?.("Shareable link copied to clipboard.");
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div>
      <div className="toolbar">
        <div className="breadcrumbs">
          <button
            className="crumb-btn"
            onClick={() => setCurrentFolderId(null)}
            style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
          >
            <Home size={15} /> My CloudBox
          </button>
          {breadcrumbs.map((crumb) => (
            <React.Fragment key={crumb.id}>
              <ChevronRight size={15} color="#94a3b8" />
              <button className="crumb-btn" onClick={() => setCurrentFolderId(crumb.id)}>
                {crumb.name}
              </button>
            </React.Fragment>
          ))}
          {searchQuery && (
            <span className="badge badge-blue" style={{ marginLeft: 8 }}>
              Search: "{searchQuery}"
            </span>
          )}
        </div>

        <div className="actions-row">
          <button className="btn btn-outline" onClick={() => setShowNewFolder(true)}>
            <FolderPlus size={16} /> New Folder
          </button>
          <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>
            <CloudUpload size={16} /> Upload File
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => handleUploadFiles(e.target.files)}
          />
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div
        className={`hero-action-card ${dragOver ? "drag-over" : ""}`}
        style={{ padding: "16px 20px", marginBottom: 16 }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleUploadFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
          <CloudUpload size={20} color="#2563eb" />
          <span style={{ fontSize: "0.9rem", color: "#475569" }}>
            Drag & drop files here or click to upload into{" "}
            <strong>{breadcrumbs.at(-1)?.name || "My CloudBox"}</strong>
          </span>
        </div>
        {uploadProgress !== null && (
          <div style={{ maxWidth: 360, margin: "12px auto 0" }}>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <small style={{ color: "#2563eb", display: "block", marginTop: 4 }}>
              Uploading {uploadingName}... {uploadProgress}%
            </small>
          </div>
        )}
      </div>

      <div className="card">
        {loading ? (
          <p style={{ margin: 0, color: "#64748b" }}>Loading files...</p>
        ) : folders.length === 0 && files.length === 0 ? (
          <p style={{ margin: 0, color: "#64748b" }}>
            This folder is empty. Upload a file or create a subfolder to begin.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size / Items</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {folders.map((folder) => (
                  <tr key={folder.id}>
                    <td>
                      <div className="item-name-cell">
                        <Folder size={18} color="#2563eb" fill="#dbeafe" />
                        <button className="item-link" onClick={() => setCurrentFolderId(folder.id)}>
                          {folder.name}
                        </button>
                      </div>
                    </td>
                    <td>{folder.item_count} items</td>
                    <td>{new Date(folder.updated_at).toLocaleDateString()}</td>
                    <td>
                      <div className="actions-row">
                        <button
                          className="btn-icon"
                          title="Share folder link"
                          onClick={() => openShareDialog("folder", folder.id, folder.name)}
                        >
                          <Link2 size={15} />
                        </button>
                        <button
                          className="btn-icon"
                          title="Rename folder"
                          onClick={() => {
                            setRenameTarget({ type: "folder", id: folder.id, name: folder.name });
                            setRenameValue(folder.name);
                          }}
                        >
                          <Edit3 size={15} />
                        </button>
                        <button
                          className="btn-icon"
                          title="Delete folder"
                          onClick={() => handleDelete("folder", folder.id, folder.name)}
                        >
                          <Trash2 size={15} color="#dc2626" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}

                {files.map((file) => (
                  <tr key={file.id}>
                    <td>
                      <div className="item-name-cell">
                        <FileText size={18} color="#475569" />
                        {isPreviewable(file) ? (
                          <button className="item-link" onClick={() => openPreview(file)}>
                            {file.name}
                          </button>
                        ) : (
                          <span>{file.name}</span>
                        )}
                        {file.active_share_token && <span className="badge badge-blue">Shared</span>}
                      </div>
                    </td>
                    <td>{formatBytes(file.size_bytes)}</td>
                    <td>{new Date(file.updated_at).toLocaleString()}</td>
                    <td>
                      <div className="actions-row">
                        {isPreviewable(file) && (
                          <button
                            className="btn-icon"
                            title="Preview file"
                            onClick={() => openPreview(file)}
                          >
                            <Eye size={15} color="#0f172a" />
                          </button>
                        )}
                        <button
                          className="btn-icon"
                          title="Download file"
                          onClick={() => storageApi.downloadFile(file.id, file.name)}
                        >
                          <CloudDownload size={15} color="#2563eb" />
                        </button>
                        <button
                          className="btn-icon"
                          title="Generate shareable link"
                          onClick={() => openShareDialog("file", file.id, file.name)}
                        >
                          <Link2 size={15} />
                        </button>
                        <button
                          className="btn-icon"
                          title="Rename file"
                          onClick={() => {
                            setRenameTarget({ type: "file", id: file.id, name: file.name });
                            setRenameValue(file.name);
                          }}
                        >
                          <Edit3 size={15} />
                        </button>
                        <button
                          className="btn-icon"
                          title="Delete file"
                          onClick={() => handleDelete("file", file.id, file.name)}
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

      {/* File Preview Modal */}
      {previewState && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 760 }}>
            <div className="modal-header">
              <div>
                <h3 style={{ marginBottom: 2 }}>{previewState.file.name}</h3>
                <small style={{ color: "#64748b" }}>
                  {formatBytes(previewState.file.size_bytes)} • {previewState.file.content_type}
                </small>
              </div>
              <div className="actions-row">
                <button
                  className="btn btn-primary"
                  style={{ padding: "6px 12px" }}
                  onClick={() => storageApi.downloadFile(previewState.file.id, previewState.file.name)}
                >
                  <CloudDownload size={15} /> Download
                </button>
                <button className="btn-icon" onClick={() => setPreviewState(null)}>
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="preview-surface">
              {previewState.kind === "image" && (
                <img
                  src={previewState.url}
                  alt={previewState.file.name}
                  style={{ maxWidth: "100%", maxHeight: "62vh", borderRadius: 8 }}
                />
              )}
              {previewState.kind === "pdf" && (
                <iframe
                  title={previewState.file.name}
                  src={previewState.url}
                  style={{ width: "100%", height: "62vh", border: "none", borderRadius: 8 }}
                />
              )}
              {previewState.kind === "text" && (
                <pre className="preview-text">{previewState.text}</pre>
              )}
            </div>
          </div>
        </div>
      )}

      {/* New Folder Modal */}
      {showNewFolder && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Create Folder</h3>
              <button className="btn-icon" onClick={() => setShowNewFolder(false)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreateFolder}>
              <div className="form-field">
                <label>Folder Name</label>
                <input
                  autoFocus
                  required
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  placeholder="e.g., CSE Mini Project"
                />
              </div>
              <div className="actions-row" style={{ justifyContent: "flex-end" }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowNewFolder(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Folder
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {renameTarget && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Rename {renameTarget.type === "file" ? "File" : "Folder"}</h3>
              <button className="btn-icon" onClick={() => setRenameTarget(null)}>
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleRenameSubmit}>
              <div className="form-field">
                <label>New Name</label>
                <input
                  autoFocus
                  required
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                />
              </div>
              <div className="actions-row" style={{ justifyContent: "flex-end" }}>
                <button type="button" className="btn btn-outline" onClick={() => setRenameTarget(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Name
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Share Link Modal */}
      {shareModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Share "{shareModal.name}"</h3>
              <button className="btn-icon" onClick={() => setShareModal(null)}>
                <X size={16} />
              </button>
            </div>
            {!shareModal.link ? (
              <p>Generating secure link...</p>
            ) : (
              <>
                <div className="form-field">
                  <label>Shareable Public Link</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      readOnly
                      value={getShareUrl(shareModal.link.token)}
                      style={{ flex: 1, background: "#f8fafc" }}
                    />
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => copyLink(shareModal.link.token)}
                    >
                      {copied ? <Check size={15} /> : <Copy size={15} />}
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
                <div className="form-field">
                  <label>Optional Expiry (Hours)</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      type="number"
                      min="1"
                      placeholder="Never expires"
                      value={shareModal.expiresHours}
                      onChange={(e) =>
                        setShareModal({ ...shareModal, expiresHours: e.target.value })
                      }
                      style={{ flex: 1 }}
                    />
                    <button type="button" className="btn btn-outline" onClick={regenerateWithExpiry}>
                      Set Expiry
                    </button>
                  </div>
                </div>
                <small style={{ color: "#64748b" }}>
                  Anyone with this link can view and download this {shareModal.type}. You can revoke it anytime from Shared Links.
                </small>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
