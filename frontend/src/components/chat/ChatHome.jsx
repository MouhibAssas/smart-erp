import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { sendMessage, uploadFile } from "../../services/chatApi";
import "./ChatHome.css";

const SUGGESTIONS = [
  "Show unpaid invoices",
  "Create a new invoice",
  "List my employees",
];

export default function ChatHome() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const handleSend = async () => {
    const text = input.trim();
    if ((!text && !selectedFile) || loading) return;

    setLoading(true);
    try {
      const payloadMessage = text || "Please analyze this invoice document.";

      let result;
      if (selectedFile) {
        result = await uploadFile(selectedFile, payloadMessage, null);
      } else {
        result = await sendMessage(payloadMessage, null);
      }

      if (result?.public_id) {
        // Pass extracted invoice data to ChatBox via session storage
        if (result?.extracted_data) {
          sessionStorage.setItem("pendingInvoiceData", JSON.stringify(result.extracted_data));
        }
        navigate(`/chat/${result.public_id}`);
      }
    } catch (err) {
      console.error("Failed to start conversation:", err);
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePickFile = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setInput(suggestion);
  };

  return (
    <div className="chathome-container">
      <div className="chathome-content">
        <div className="chathome-welcome">
          <h1 className="chathome-title">Smart ERP Assistant</h1>
          <p className="chathome-subtitle">
            Hello! I'm your ERP assistant. Ask me anything about invoices,
            purchases, HR data, or business operations.
          </p>
        </div>
      </div>

      <div className="chathome-input-area">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,image/*"
          className="chathome-file-input"
          onChange={handleFileChange}
        />

        <div className="chathome-input-wrapper">
          <button
            type="button"
            className="chathome-attach-button"
            onClick={handlePickFile}
            disabled={loading}
            title="Upload invoice PDF/image"
          >
            +
          </button>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            rows={1}
            className="chathome-textarea"
            disabled={loading}
            onInput={(e) => {
              e.target.style.height = "auto";
              e.target.style.height = e.target.scrollHeight + "px";
            }}
          />

          {selectedFile && (
            <div className="chathome-file-pill">
              <span className="chathome-file-name">{selectedFile.name}</span>
              <button
                type="button"
                className="chathome-file-remove"
                onClick={handleRemoveFile}
                disabled={loading}
                title="Remove file"
              >
                x
              </button>
            </div>
          )}

          <button
            onClick={handleSend}
            disabled={loading || (!input.trim() && !selectedFile)}
            className="chathome-send-button"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      <div className="chathome-suggestions">
        {SUGGESTIONS.map((suggestion, idx) => (
          <button
            key={idx}
            className="chathome-suggestion-chip"
            onClick={() => handleSuggestionClick(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
