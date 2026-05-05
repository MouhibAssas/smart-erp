import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Chat from './pages/Chat.jsx'
import AdminPanel from './pages/AdminPanel.jsx'
import Dashboard from './pages/Dashboard'
import Layout from './components/layout/Layout.jsx'
import Login from './pages/Login.jsx'
import './App.css'

// Protected route wrapper — redirects to login if not authenticated
function ProtectedRoute({ element }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? element : <Navigate to="/login" replace />
}

function AppRoutes() {
  const { isAuthenticated, isAdmin } = useAuth();

  return (
    <Routes>
      {/* Public routes — no layout */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes — with layout */}
      <Route
        path="/"
        element={
          isAuthenticated ? <Layout /> : <Navigate to="/login" replace />
        }
      >
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<Chat />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="admin" element={isAdmin ? <AdminPanel /> : <Navigate to="/" replace />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App