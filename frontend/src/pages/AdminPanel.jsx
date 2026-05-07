import { useState, useEffect } from "react";
import "./AdminPanel.css";
import { userApi } from "../services/userApi";
import UserConversationsModal from "../components/admin/UserConversationsModal";

const ROLES = ["admin", "operator", "viewer"];

const initForm = { full_name: "", email: "", password: "", role: "operator" };

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editUser, setEditUser] = useState(null); // null = create mode
  const [form, setForm] = useState(initForm);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [showConvModal, setShowConvModal] = useState(false);
  const [selectedUserConv, setSelectedUserConv] = useState(null);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await userApi.getAll();
      setUsers(res.data);
      setError("");
    } catch {
      setError("Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const openCreate = () => {
    setEditUser(null);
    setForm(initForm);
    setFormError("");
    setShowModal(true);
  };

  const openEdit = (user) => {
    setEditUser(user);
    setForm({ full_name: user.full_name, email: user.email, password: "", role: user.role });
    setFormError("");
    setShowModal(true);
  };

  const closeModal = () => { setShowModal(false); setFormError(""); };

  const handleSubmit = async () => {
    if (!form.full_name.trim() || !form.email.trim()) {
      setFormError("Full name and email are required.");
      return;
    }
    if (!editUser && form.password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (editUser && form.password && form.password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      if (editUser) {
        const payload = { full_name: form.full_name, email: form.email, role: form.role };
        if (form.password) {
          payload.password = form.password;
        }
        await userApi.update(editUser.id, payload);
      } else {
        await userApi.create(form);
      }
      await fetchUsers();
      closeModal();
    } catch (e) {
      setFormError(e?.response?.data?.detail || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await userApi.toggleActive(user.id);
      await fetchUsers();
    } catch {
      setError("Failed to update user status.");
    }
  };

  const handleDelete = async (id) => {
    try {
      await userApi.delete(id);
      setDeleteConfirm(null);
      await fetchUsers();
    } catch {
      setError("Failed to delete user.");
    }
  };

  const roleClass = (role) =>
    role === "admin" ? "badge badge-admin" :
    role === "operator" ? "badge badge-operator" :
    "badge badge-viewer";

  const initials = (name) =>
    name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="admin-root">
      <div className="admin-header">
        <div>
          <h1 className="admin-title">User Management</h1>
          <p className="admin-sub">{users.length} registered user{users.length !== 1 ? "s" : ""}</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Add user</button>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <span>Loading users…</span>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={5} className="empty-row">No users found. Add one above.</td></tr>
              ) : users.map(user => (
                <tr key={user.id} className={!user.is_active ? "row-inactive" : ""}>
                  <td>
                    <div className="user-cell">
                      <div className={`avatar avatar-${user.role}`}>{initials(user.full_name)}</div>
                      <div>
                        <p className="user-name">{user.full_name}</p>
                        <p className="user-email">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td><span className={roleClass(user.role)}>{user.role}</span></td>
                  <td>
                    <button
                      className={`status-toggle ${user.is_active ? "status-active" : "status-inactive"}`}
                      onClick={() => handleToggleActive(user)}
                      title="Click to toggle"
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td className="date-cell">
                    {new Date(user.created_at).toLocaleDateString("en-GB", {
                      day: "2-digit", month: "short", year: "numeric"
                    })}
                  </td>
                  <td>
                    <div className="action-group">
                      <button type="button" className="btn-icon" onClick={() => openEdit(user)} title="Edit" aria-label={`Edit ${user.full_name}`}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        <span className="btn-icon-label">Edit</span>
                      </button>
                      <button type="button" className="btn-icon" onClick={() => { setSelectedUserConv(user); setShowConvModal(true); }} title="Conversations" aria-label={`Conversations ${user.full_name}`}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z"/></svg>
                        <span className="btn-icon-label">Conversations</span>
                      </button>
                      <button type="button" className="btn-icon btn-icon-danger" onClick={() => setDeleteConfirm(user)} title="Delete" aria-label={`Delete ${user.full_name}`}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
                        <span className="btn-icon-label">Delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editUser ? "Edit user" : "Add new user"}</h2>
              <button className="modal-close" onClick={closeModal}>✕</button>
            </div>

            <div className="modal-body">
              {formError && <div className="alert-error">{formError}</div>}

              <label className="field-label">Full name</label>
              <input
                className="field-input"
                placeholder="Ahmed Ben Ali"
                value={form.full_name}
                onChange={e => setForm({ ...form, full_name: e.target.value })}
              />

              <label className="field-label">Email</label>
              <input
                className="field-input"
                type="email"
                placeholder="ahmed@company.com"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
              />

              <label className="field-label">Password {editUser ? "(optional)" : ""}</label>
              <input
                className="field-input"
                type="password"
                placeholder={editUser ? "Leave blank to keep current password" : "Minimum 8 characters"}
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
              />

              <label className="field-label">Role</label>
              <select
                className="field-input"
                value={form.role}
                onChange={e => setForm({ ...form, role: e.target.value })}
              >
                {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
              </select>
            </div>

            <div className="modal-footer">
              <button className="btn-ghost" onClick={closeModal}>Cancel</button>
              <button className="btn-primary" onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Saving…" : editUser ? "Save changes" : "Create user"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal modal-sm" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete user</h2>
              <button className="modal-close" onClick={() => setDeleteConfirm(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="confirm-text">
                Are you sure you want to delete <strong>{deleteConfirm.full_name}</strong>?
                This action cannot be undone.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn-ghost" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn-danger" onClick={() => handleDelete(deleteConfirm.id)}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* User Conversations Modal (admin read-only) */}
      {showConvModal && selectedUserConv && (
        <UserConversationsModal
          user={selectedUserConv}
          isOpen={showConvModal}
          onClose={() => setShowConvModal(false)}
        />
      )}
    </div>
  );
}
