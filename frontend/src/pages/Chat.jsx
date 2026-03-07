import ChatBox from "../components/chat/ChatBox.jsx";
import "./Chat.css";

export default function Chat() {
  return (
    <div className="chat-container">
      {/* Sidebar */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-logo">SMART ERP</div>

        <div className="chat-sidebar-label">Navigation</div>

        {["Chat", "Dashboard", "Invoices"].map((item) => (
          <div
            key={item}
            className={`chat-nav-item ${item === "Chat" ? "active" : ""}`}
          >
            {item}
          </div>
        ))}
      </div>

      {/* Main */}
      <div className="chat-main">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-status-indicator" />
          <span className="chat-status-text">
            ERP Assistant — Connected to Odoo
          </span>
        </div>

        {/* Chat */}
        <div className="chat-content">
          <ChatBox />
        </div>
      </div>
    </div>
  );
}