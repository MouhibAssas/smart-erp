import { useParams } from "react-router-dom";
import ChatBox from "../components/chat/ChatBox.jsx";
import ChatHome from "../components/chat/ChatHome.jsx";
import "./Chat.css";

export default function Chat() {
  const { publicId } = useParams();

  return (
    <div className="chat-container">

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
          {!publicId ? <ChatHome /> : <ChatBox />}
        </div>
      </div>
    </div>
  );
}