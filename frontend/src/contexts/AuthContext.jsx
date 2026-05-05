import { createContext, useContext, useState, useEffect } from "react";
import { authService } from "../services/authService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => authService.isAuthenticated());
  const [isAdmin, setIsAdmin] = useState(() => authService.isAdmin());

  // Sync with localStorage on mount
  useEffect(() => {
    setIsAuthenticated(authService.isAuthenticated());
    setIsAdmin(authService.isAdmin());
  }, []);

  // Update auth state when we detect storage changes or after login/logout
  const updateAuth = (newState) => {
    // If caller passes boolean, use it for isAuthenticated; otherwise recompute
    if (typeof newState === "boolean") setIsAuthenticated(newState);
    else setIsAuthenticated(authService.isAuthenticated());
    // Always recompute admin flag from authService
    setIsAdmin(authService.isAdmin());
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isAdmin, updateAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
