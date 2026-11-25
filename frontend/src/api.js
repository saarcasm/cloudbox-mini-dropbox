const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const CHUNK_THRESHOLD_BYTES = 2 * 1024 * 1024; // Use chunked upload with retry above 2 MB
const CHUNK_SIZE_BYTES = 1024 * 1024; // 1 MB per chunk

export function getToken() {
  return localStorage.getItem("cloudbox_token") || "";
}

export function setToken(token) {
  if (token) {
    localStorage.setItem("cloudbox_token", token);
  } else {
    localStorage.removeItem("cloudbox_token");
  }
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token && !options.skipAuth) {
    headers.set("Authorization", `Token ${token}`);
  }
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 204) {
    return null;
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    const msg =
      data?.detail ||
      (typeof data === "object" && data
        ? Object.values(data).flat().join(" ")
        : "Request failed");
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data;
}

export const authApi = {
  register: (payload) =>
    apiFetch("/auth/register/", { method: "POST", body: JSON.stringify(payload), skipAuth: true }),
  login: (payload) =>
    apiFetch("/auth/login/", { method: "POST", body: JSON.stringify(payload), skipAuth: true }),
  logout: () => apiFetch("/auth/logout/", { method: "POST" }),
  me: () => apiFetch("/auth/me/"),
  adminUsers: () => apiFetch("/auth/admin/users/"),
  adminSetQuota: (userId, quotaMb) =>
    apiFetch(`/auth/admin/users/${userId}/quota/`, {
      method: "PATCH",
      body: JSON.stringify({ quota_mb: quotaMb }),
    }),
};

export const storageApi = {
  dashboard: () => apiFetch("/storage/dashboard/"),
  items: (folderId = null, query = "") => {
    const params = new URLSearchParams();
    if (folderId) params.set("folder", folderId);
    if (query) params.set("q", query);
    const qs = params.toString();
    return apiFetch(`/storage/items/${qs ? `?${qs}` : ""}`);
  },
  createFolder: (name, parent = null) =>
    apiFetch("/storage/folders/", {
      method: "POST",
      body: JSON.stringify({ name, parent }),
    }),
  renameFolder: (folderId, name) =>
    apiFetch(`/storage/folders/${folderId}/`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteFolder: (folderId) =>
    apiFetch(`/storage/folders/${folderId}/`, { method: "DELETE" }),
  renameFile: (fileId, name) =>
    apiFetch(`/storage/files/${fileId}/rename/`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteFile: (fileId) =>
    apiFetch(`/storage/files/${fileId}/`, { method: "DELETE" }),
  downloadFile: async (fileId, filename) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/storage/files/${fileId}/download/?url_only=1`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (!res.ok) throw new Error("Download failed");
    const ct = (res.headers.get("Content-Type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      const data = await res.json();
      const a = document.createElement("a");
      a.href = data.download_url;
      a.download = data.filename || filename;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  fetchPreviewBlob: async (fileId) => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/storage/files/${fileId}/download/?inline=1&url_only=1`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (!res.ok) throw new Error("Preview failed");
    const ct = (res.headers.get("Content-Type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      const data = await res.json();
      const s3Res = await fetch(data.download_url);
      if (!s3Res.ok) throw new Error("Preview fetch from S3 failed");
      return s3Res.blob();
    }
    return res.blob();
  },
  uploadFile: async (file, folderId = null, onProgress = () => {}) => {
    // Check if backend is configured for direct-to-S3 presigned uploads
    const presign = await apiFetch("/storage/files/upload/presign/", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        total_size: file.size,
        folder: folderId,
        content_type: file.type || "application/octet-stream",
      }),
    });

    if (presign?.mode === "presigned") {
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", presign.upload_url);
        Object.entries(presign.headers || {}).forEach(([k, v]) => {
          xhr.setRequestHeader(k, v);
        });
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            onProgress(Math.min(95, Math.round((e.loaded / e.total) * 95)));
          }
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`S3 upload failed (${xhr.status})`));
          }
        };
        xhr.onerror = () => reject(new Error("Network error uploading directly to S3"));
        xhr.send(file);
      });

      const confirmed = await apiFetch("/storage/files/upload/confirm/", {
        method: "POST",
        body: JSON.stringify({
          file_id: presign.file_id,
          object_key: presign.object_key,
          filename: file.name,
          folder: folderId,
          content_type: file.type || "application/octet-stream",
        }),
      });
      onProgress(100);
      return confirmed;
    }

    // Use chunked upload with automatic retry for larger files in server/local mode
    if (file.size > CHUNK_THRESHOLD_BYTES) {
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE_BYTES);
      const init = await apiFetch("/storage/files/upload/init/", {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          total_size: file.size,
          total_chunks: totalChunks,
          folder: folderId,
          content_type: file.type || "application/octet-stream",
        }),
      });

      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE_BYTES;
        const end = Math.min(file.size, start + CHUNK_SIZE_BYTES);
        const chunkBlob = file.slice(start, end);

        let attempt = 0;
        let uploaded = false;
        while (attempt < 3 && !uploaded) {
          attempt += 1;
          try {
            const fd = new FormData();
            fd.append("upload_id", init.upload_id);
            fd.append("chunk_index", String(i));
            fd.append("chunk", chunkBlob, `${file.name}.part${i}`);
            await apiFetch("/storage/files/upload/chunk/", { method: "POST", body: fd });
            uploaded = true;
          } catch (err) {
            if (attempt >= 3) throw err;
            await new Promise((r) => setTimeout(r, 600 * attempt));
          }
        }
        onProgress(Math.round(((i + 1) / totalChunks) * 95));
      }

      const completed = await apiFetch("/storage/files/upload/complete/", {
        method: "POST",
        body: JSON.stringify({ upload_id: init.upload_id }),
      });
      onProgress(100);
      return completed;
    }

    // Standard XHR upload with progress for smaller files
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/storage/files/upload/`);
      xhr.setRequestHeader("Authorization", `Token ${getToken()}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300) {
            onProgress(100);
            resolve(data);
          } else {
            reject(new Error(data.detail || `Upload failed (${xhr.status})`));
          }
        } catch {
          reject(new Error(`Upload failed (${xhr.status})`));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));

      const fd = new FormData();
      fd.append("file", file);
      if (folderId) fd.append("folder", folderId);
      xhr.send(fd);
    });
  },
  listShares: () => apiFetch("/storage/shares/"),
  createShare: (payload) =>
    apiFetch("/storage/shares/", { method: "POST", body: JSON.stringify(payload) }),
  toggleShare: (shareId, isActive) =>
    apiFetch(`/storage/shares/${shareId}/`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
  deleteShare: (shareId) =>
    apiFetch(`/storage/shares/${shareId}/`, { method: "DELETE" }),
  getPublicShare: (token) => apiFetch(`/share/${token}/`, { skipAuth: true }),
  getPublicDownloadUrl: (token, fileId = null) => {
    const base = `${API_BASE}/share/${token}/download/`;
    return fileId ? `${base}?file_id=${encodeURIComponent(fileId)}` : base;
  },
};

export function formatBytes(bytes = 0) {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const idx = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const val = bytes / Math.pow(1024, idx);
  return `${val >= 10 || idx === 0 ? val.toFixed(1) : val.toFixed(2)} ${units[idx]}`;
}
