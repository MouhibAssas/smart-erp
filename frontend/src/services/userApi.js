import httpClient from "./httpClient";

const BASE = "/users/";

export const userApi = {
  getAll: () => httpClient.get(BASE),
  create: (data) => httpClient.post(BASE, data),
  update: (id, data) => httpClient.patch(`${BASE}${id}`, data),
  delete: (id) => httpClient.delete(`${BASE}${id}`),
  toggleActive: (id) => httpClient.patch(`${BASE}${id}/toggle-active`),
  // Admin: fetch conversations for a specific user
  getConversations: (userId) => httpClient.get(`${BASE}${userId}/conversations`),
  // Admin: search conversations by title and message content
  searchConversations: (userId, q = "") => httpClient.get(`${BASE}${userId}/conversations/search`, { params: { q } }),
  // Admin: fetch conversation detail for a specific user
  getConversation: (userId, conversationId) => httpClient.get(`${BASE}${userId}/conversations/${conversationId}`),
};