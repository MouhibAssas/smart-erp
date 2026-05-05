// Auth service — manages JWT token and current user state

const TOKEN_KEY = "erp_token";
const USER_KEY  = "erp_user";

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

  save: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};