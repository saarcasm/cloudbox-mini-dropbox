import React, { useEffect, useState } from "react";
import { Shield, Users } from "lucide-react";
import { authApi, formatBytes } from "../api";

export default function AdminView() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [quotaMbInput, setQuotaMbInput] = useState("500");

  async function loadUsers() {
    setLoading(true);
    try {
      const data = await authApi.adminUsers();
      setUsers(data.users || []);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function saveQuota(userId) {
    try {
      await authApi.adminSetQuota(userId, Number(quotaMbInput));
      setEditingId(null);
      loadUsers();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <div className="toolbar">
        <div>
          <h2 style={{ margin: "0 0 4px" }}>Admin Dashboard</h2>
          <span style={{ color: "#64748b", fontSize: "0.88rem" }}>
            User & Storage Quota Management
          </span>
        </div>
        <span className="badge badge-blue">
          <Shield size={14} /> Staff Access
        </span>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="card">
        {loading ? (
          <p>Loading users...</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Files / Folders</th>
                  <th>Used / Quota</th>
                  <th>Manage Quota</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="item-name-cell">
                        <Users size={16} color="#2563eb" />
                        <span>{u.username}</span>
                        {u.is_staff && <span className="badge badge-blue">Admin</span>}
                      </div>
                    </td>
                    <td>{u.email || "—"}</td>
                    <td>
                      {u.file_count} / {u.folder_count}
                    </td>
                    <td>
                      {formatBytes(u.used_bytes)} / {formatBytes(u.quota_bytes)}
                    </td>
                    <td>
                      {editingId === u.id ? (
                        <div className="actions-row">
                          <input
                            type="number"
                            min="1"
                            value={quotaMbInput}
                            onChange={(e) => setQuotaMbInput(e.target.value)}
                            style={{ width: 85, padding: "5px 8px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                          />
                          <span style={{ fontSize: "0.8rem", color: "#64748b" }}>MB</span>
                          <button className="btn btn-primary" style={{ padding: "5px 10px" }} onClick={() => saveQuota(u.id)}>
                            Save
                          </button>
                          <button className="btn btn-outline" style={{ padding: "5px 10px" }} onClick={() => setEditingId(null)}>
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          className="btn btn-outline"
                          style={{ padding: "5px 10px", fontSize: "0.8rem" }}
                          onClick={() => {
                            setEditingId(u.id);
                            setQuotaMbInput(String(Math.round(u.quota_bytes / (1024 * 1024))));
                          }}
                        >
                          Edit Quota
                        </button>
                      )}
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
