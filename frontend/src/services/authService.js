// Auth service — manages JWT token and current user state

import axios from "axios";

const TOKEN_KEY = "erp_token";
const USER_KEY = "erp_user";

export const authService = {
  getToken: () => localStorage.getItem(TOKEN_KEY),

  getUser: () => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated: () => !!localStorage.getItem(TOKEN_KEY),

  isAdmin: () => {
    const user = authService.getUser();
    return user?.role === "admin";
  },

  saveToken: (token) => {
    localStorage.setItem(TOKEN_KEY, token);
  },

  saveUser: (user) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  save: (token, user) => {
    authService.saveToken(token);
    authService.saveUser(user);
  },

  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  logout: async () => {
    try {
      await axios.post((import.meta.env.VITE_API_URL || "http://localhost:8000") + "/auth/logout", {}, { withCredentials: true });
    } catch {
      // ignore errors — cookie will expire naturally
    }
    authService.clear();
  },
};