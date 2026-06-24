import { useEffect, useMemo, useState } from "react";
import "./UserConversationsModal.css";
import { userApi } from "../../services/userApi";
import MessageBubble from "../chat/MessageBubble";

export default function UserConversationsModal({ user, isOpen, onClose }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const normalizedQuery = useMemo(() => debouncedSearch.trim(), [debouncedSearch]);

  const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const renderHighlightedText = (text, query) => {
    if (!text) return "";
    if (!query) return text;

    const pattern = new RegExp(`(${escapeRegex(query)})`, "ig");
    const parts = String(text).split(pattern);

    return parts.map((part, idx) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={`${part}-${idx}`} className="ucm-highlight">{part}</mark>
      ) : (
        <span key={`${part}-${idx}`}>{part}</span>
      )
    );
  };

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 280);

    return () => clearTimeout(handler);
  }, [search]);

  useEffect(() => {
    if (!isOpen || !user) return;
    setLoading(true);
    setError("");
    userApi.searchConversations(user.id, normalizedQuery)
      .then(res => {
        setResults(res.data || []);
      })
      .catch(() => setError("Failed to load conversations"))
      .finally(() => setLoading(false));
  }, [isOpen, user, normalizedQuery]);

  const openConversation = async (conv) => {
    setSelected(conv);
    setMessages([]);
    setLoadingMessages(true);
    setError("");
    try {
      const res = await userApi.getConversation(user.id, conv.id);
      setMessages(res.data.messages || []);
    } catch {
      setError("Failed to load conversation messages");
    } finally {
      setLoadingMessages(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="ucm-overlay" onClick={onClose}>
      <div className="ucm-modal" onClick={(event) => event.stopPropagation()}>
        <div className="ucm-header">
          <h3>Conversations — {user.full_name}</h3>
          <button className="ucm-close" onClick={onClose}>✕</button>
        </div>

        <div className="ucm-search">
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search titles or message text..." />
        </div>

        {error && <div className="ucm-error">{error}</div>}

        <div className="ucm-body">
          <div className="ucm-list">
            {loading ? <div className="ucm-loading">Loading…</div> : (
              results.length === 0 ? <div className="ucm-empty">No conversations found.</div> : (
                results.map(c => (
                  <div key={c.id} className={`ucm-card ${selected?.id === c.id ? 'selected' : ''}`} onClick={() => openConversation(c)}>
                    <div className="ucm-card-left">
                      <div className="ucm-card-avatar">{(c.title || "").slice(0,2).toUpperCase()}</div>
                    </div>
                    <div className="ucm-card-main">
                      <div className="ucm-card-title">{renderHighlightedText(c.title || "(no title)", normalizedQuery)}</div>
                      {c.match_source === "message" && c.preview ? (
                        <div className="ucm-card-preview ucm-card-snippet">{renderHighlightedText(c.preview, normalizedQuery)}</div>
                      ) : (
                        <div className="ucm-card-preview">{c.updated_at ? new Date(c.updated_at).toLocaleString() : ''}</div>
                      )}
                    </div>
                    <div className={`ucm-match-chip ${c.match_source === "message" ? "message" : "title"}`}>
                      {c.match_source === "message" ? "Message" : "Title"}
                    </div>
                  </div>
                ))
              )
            )}
          </div>

          <div className="ucm-detail">
            {selected ? (
              <>
                <div className="ucm-detail-header">
                  <h4 className="ucm-detail-title">{selected.title || "(no title)"}</h4>
                  <div className="ucm-detail-date">{new Date(selected.updated_at).toLocaleString()}</div>
                </div>
                <div className="chatbox-messages ucm-messages">
                  {loadingMessages ? <div>Loading messages…</div> : (
                    messages.length === 0 ? <div className="ucm-empty">No messages</div> : (
                      messages.map(m => (
                        <MessageBubble
                          key={m.id}
                          text={m.content}
                          sender={m.role === 'ai' ? 'bot' : 'user'}
                          highlightQuery={normalizedQuery}
                        />
                      ))
                    )
                  )}
                </div>
              </>
            ) : (
              <div className="ucm-placeholder">Select a conversation to view messages</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
