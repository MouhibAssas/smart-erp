import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Chat from './pages/Chat.jsx'
import Dashboard from './pages/Dashboard'
import './App.css'

function Home() {
  return (
    <div style={{ padding: "40px", maxWidth: "800px", margin: "0 auto" }}>
      <h1>Smart ERP Assistant</h1>
      <p>Welcome to the Smart ERP Assistant! This is a demo application showcasing the integration of a chatbot with an ERP system. You can ask questions about your business data, invoices, purchases, and more.</p>
      
      <div style={{ marginTop: "24px", display: "flex", gap: "16px" }}>
        <Link to="/chat" style={{
          padding: "12px 24px",
          background: "#3b82f6",
          color: "#fff",
          textDecoration: "none",
          borderRadius: "8px",
          fontWeight: 600,
        }}>
          Go to Chat
        </Link>
        <Link to="/dashboard" style={{
          padding: "12px 24px",
          background: "#1a1a2e",
          color: "#fff",
          textDecoration: "none",
          borderRadius: "8px",
          fontWeight: 600,
        }}>
          View Dashboard
        </Link>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App