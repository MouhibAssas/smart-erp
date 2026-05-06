import httpClient from "./httpClient";

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  login:    (email, password) => httpClient.post("/auth/login", { email, password }),
  me:       () => httpClient.get("/auth/me"),
};

// ── Conversations ─────────────────────────────────────────────────────────────

export const conversationApi = {
  list:   ()         => httpClient.get("/conversations"),
  get:    (publicId)       => httpClient.get(`/conversations/${publicId}`),
  delete: (publicId)       => httpClient.delete(`/conversations/${publicId}`),
  rename: (publicId, title) => httpClient.patch(`/conversations/${publicId}/title`, { title }),
};

// ── Persistent chat ───────────────────────────────────────────────────────────

export const persistentChatApi = {
  send: (message, conversation_id = null) =>
    httpClient.post("/chat/persistent", { message, conversation_id }),

  upload: (file, message = "", conversation_id = null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("message", message);
    if (conversation_id) form.append("conversation_id", String(conversation_id));
    return httpClient.post("/chat/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};