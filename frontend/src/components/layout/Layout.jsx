import { useState, useEffect, useCallback } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { authService } from "../../services/authService";
import { useAuth } from "../../contexts/AuthContext";
import { conversationApi } from "../../services/conversationApi";
import "./Layout.css";

const navItems = [
  { to: "/chat",      label: "Chat",      icon: "💬" },
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/admin",     label: "Admin",     icon: "👥", adminOnly: true },
];

export default function Layout() {
  const navigate = useNavigate();
  const { updateAuth, isAdmin } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [convsLoading, setConvsLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteCandidate, setDeleteCandidate] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingId, setRenamingId] = useState(null);

  const location = useLocation();
  const isOnChat = location.pathname.startsWith("/chat");
  const activeConversationPublicId = location.pathname.startsWith("/chat/")
    ? location.pathname.split("/")[2] ?? null
    : null;
  const user = authService.getUser();

  // Guard: redirect to login if not authenticated
  useEffect(() => {
    if (!authService.isAuthenticated()) {
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  // Close mobile menu on mount and handle window resize
  useEffect(() => {
    setMobileMenuOpen(false);
    
    const handleResize = () => {
      // Close mobile menu if screen is wider than 900px (desktop)
      if (window.innerWidth > 900) {
        setMobileMenuOpen(false);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Load conversations when on /chat
  const loadConversations = useCallback(async () => {
    if (!isOnChat || !authService.isAuthenticated()) return;
    setConvsLoading(true);
    try {
      const { data } = await conversationApi.list();
      setConversations(data);
    } catch {
      // silently ignore; user still sees chat
    } finally {
      setConvsLoading(false);
    }
  }, [isOnChat]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations, location.pathname]);

  // Expose refresh so ChatBox can call it after new message
  useEffect(() => {
    window.__refreshConversations = loadConversations;
    return () => { delete window.__refreshConversations; };
  }, [loadConversations]);

  const handleSelectConv = (conv) => {
    setMobileMenuOpen(false);
    navigate(`/chat/${conv.public_id}`);
  };

  const handleNewChat = () => {
    setMobileMenuOpen(false);
    navigate("/chat");
  };

  const handleDeleteConv = async (e, conv) => {
    e.stopPropagation();

    setDeleteCandidate(conv);
  };

  const confirmDeleteConv = async () => {
    if (!deleteCandidate) {
      return;
    }

    setDeletingId(deleteCandidate.public_id);
    try {
      await conversationApi.delete(deleteCandidate.public_id);
      setConversations((prev) => prev.filter((c) => c.public_id !== deleteCandidate.public_id));
      if (activeConversationPublicId === deleteCandidate.public_id) {
        navigate("/chat");
      }
    } catch {
      // ignore
    } finally {
      setDeletingId(null);
      setDeleteCandidate(null);
    }
  };

  const startRenameConv = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.public_id);
    setEditingTitle(conv.title || "");
  };

  const cancelRenameConv = useCallback(() => {
    setEditingId(null);
    setEditingTitle("");
  }, []);

  const submitRenameConv = async (e, conv) => {
    e.stopPropagation();
    const normalized = editingTitle.trim();

    if (!normalized) {
      cancelRenameConv();
      return;
    }

    if (normalized === conv.title) {
      cancelRenameConv();
      return;
    }

    setRenamingId(conv.public_id);
    try {
      await conversationApi.rename(conv.public_id, normalized);
      setConversations((prev) =>
        prev.map((c) =>
          c.public_id === conv.public_id
            ? { ...c, title: normalized }
            : c
        )
      );
      cancelRenameConv();
    } catch {
      // ignore for now
    } finally {
      setRenamingId(null);
    }
  };

  const handleLogout = () => {
    authService.clear();
    updateAuth(false); // Notify context that auth state changed
    navigate("/login");
  };

  const closeMobileMenu = () => setMobileMenuOpen(false);

  const formatDate = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
  };

  return (
    <div className="layout-root">
      {/* Mobile hamburger */}
      <button
        type="button"
        className="layout-mobile-toggle"
        aria-label="Open menu"
        aria-expanded={mobileMenuOpen}
        onClick={() => setMobileMenuOpen(true)}
      >
        <span /><span /><span />
      </button>

      {mobileMenuOpen && (
        <button
          type="button"
          className="layout-backdrop"
          aria-label="Close menu"
          onClick={closeMobileMenu}
        />
      )}

      <aside className={`layout-sidebar${mobileMenuOpen ? " open" : ""}`}>
        {/* Header */}
        <div className="layout-logo">Smart ERP</div>

        <button
          type="button"
          className="layout-mobile-close"
          aria-label="Close menu"
          onClick={closeMobileMenu}
        >✕</button>

        {/* Navigation */}
        <nav className="layout-nav">
          <span className="layout-nav-label">Menu</span>
          {navItems
            .filter((item) => !item.adminOnly || isAdmin)
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={closeMobileMenu}
                className={({ isActive }) =>
                  `layout-nav-item${isActive ? " active" : ""}`
                }
              >
                <span className="layout-nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
        </nav>

        {/* Spacer to push user section to bottom — only when conversations panel is hidden */}
        {!isOnChat && <div className="layout-spacer" />}

        {/* Conversations panel — only when on /chat */}
        {isOnChat && (
          <div className="layout-conversations">
            <div className="layout-conv-header">
              <span className="layout-nav-label">Conversations</span>
              <button
                type="button"
                className="layout-new-chat-btn"
                onClick={handleNewChat}
                title="New conversation"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
              </button>
            </div>

            {convsLoading && conversations.length === 0 && (
              <div className="layout-conv-loading">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="layout-conv-skeleton" />
                ))}
              </div>
            )}

            {!convsLoading && conversations.length === 0 && (
              <p className="layout-conv-empty">No conversations yet. Start chatting!</p>
            )}

            <div className="layout-conv-list">
              {conversations.map((conv) => (
                <div
                  key={conv.public_id ?? conv.id}
                  className={`layout-conv-item${activeConversationPublicId === conv.public_id ? " active" : ""}`}
                  onClick={() => editingId !== conv.public_id && handleSelectConv(conv)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && editingId !== conv.public_id) {
                      handleSelectConv(conv);
                    }
                  }}
                >
                  <div className="layout-conv-icon">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                  </div>
                  <div className="layout-conv-content">
                    {editingId === conv.public_id ? (
                      <form className="layout-conv-rename-form" onSubmit={(e) => submitRenameConv(e, conv)} onClick={(e) => e.stopPropagation()}>
                        <input
                          className="layout-conv-title-input"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          autoFocus
                          maxLength={120}
                          onKeyDown={(e) => {
                            if (e.key === "Escape") {
                              e.preventDefault();
                              cancelRenameConv();
                            }
                          }}
                        />
                      </form>
                    ) : (
                      <span className="layout-conv-title">{conv.title}</span>
                    )}
                    {conv.last_message && (
                      <span className="layout-conv-preview">{conv.last_message}</span>
                    )}
                    <span className="layout-conv-time">{formatDate(conv.updated_at)}</span>
                  </div>
                  <div className="layout-conv-actions">
                    {editingId === conv.public_id ? (
                      <>
                        <button
                          type="button"
                          className="layout-conv-rename-save"
                          onClick={(e) => submitRenameConv(e, conv)}
                          disabled={renamingId === conv.public_id}
                          title="Save title"
                          aria-label="Save title"
                        >
                          {renamingId === conv.public_id ? (
                            <span className="layout-conv-deleting" />
                          ) : (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          className="layout-conv-rename-cancel"
                          onClick={(e) => {
                            e.stopPropagation();
                            cancelRenameConv();
                          }}
                          title="Cancel rename"
                          aria-label="Cancel rename"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                          </svg>
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="layout-conv-rename"
                          onClick={(e) => startRenameConv(e, conv)}
                          title="Rename conversation"
                          aria-label="Rename conversation"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M12 20h9"/>
                            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="layout-conv-delete"
                          onClick={(e) => handleDeleteConv(e, conv)}
                          disabled={deletingId === conv.public_id}
                          title="Delete conversation"
                          aria-label="Delete conversation"
                        >
                          {deletingId === conv.public_id ? (
                            <span className="layout-conv-deleting" />
                          ) : (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6l-1 14H6L5 6"/>
                              <path d="M10 11v6M14 11v6"/>
                              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                            </svg>
                          )}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* User info + logout */}
        {user && (
          <div className="layout-user">
            <div className="layout-user-avatar">
              {user.full_name?.charAt(0)?.toUpperCase() || "U"}
            </div>
            <div className="layout-user-info">
              <span className="layout-user-name">{user.full_name}</span>
              <span className="layout-user-role">{user.role}</span>
            </div>
            <button
              type="button"
              className="layout-logout-btn"
              onClick={handleLogout}
              title="Sign out"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        )}
      </aside>

      <main className="layout-main">
        <Outlet />
      </main>

      {deleteCandidate && (
        <div className="layout-modal-backdrop" role="presentation" onClick={() => setDeleteCandidate(null)}>
          <div
            className="layout-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="layout-delete-title"
            aria-describedby="layout-delete-description"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="layout-delete-title" className="layout-modal-title">Delete Conversation</h3>
            <p id="layout-delete-description" className="layout-modal-description">
              Are you sure you want to delete this conversation: <strong>{`"${deleteCandidate.title || "this conversation"}"`}</strong>?
            </p>
            <div className="layout-modal-actions">
              <button
                type="button"
                className="layout-modal-btn layout-modal-btn-secondary"
                onClick={() => setDeleteCandidate(null)}
                disabled={deletingId === deleteCandidate.public_id}
              >
                Cancel
              </button>
              <button
                type="button"
                className="layout-modal-btn layout-modal-btn-danger"
                onClick={confirmDeleteConv}
                disabled={deletingId === deleteCandidate.public_id}
              >
                {deletingId === deleteCandidate.public_id ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}