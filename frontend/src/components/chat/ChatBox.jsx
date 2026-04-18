import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import InvoiceValidationForm from "./InvoiceValidationForm";
import { confirmInvoice, sendMessage, uploadFile } from "../../services/chatApi";
import "./ChatBox.css";

export default function ChatBox() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I'm your ERP assistant. Ask me anything about your invoices, purchases, HR data, or any business operations.",
      sender: "bot",
    },
  ]);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [pendingInvoice, setPendingInvoice] = useState(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getHistory = () =>
    messages.map((m) => ({
      role: m.sender === "user" ? "user" : "assistant",
      content: m.text,
    }));

      const handleSend = async () => {
    const text = input.trim();
    if ((!text && !selectedFile) || loading) return;

    const payloadMessage = text || "Please analyze this invoice document.";
    const userText = selectedFile ? `${payloadMessage}\n[File: ${selectedFile.name}]` : payloadMessage;

    const userMsg = { id: Date.now(), text: userText, sender: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      let response = "";

      if (selectedFile) {
        const uploadResult = await uploadFile(selectedFile, payloadMessage);
        // Store extracted invoice payload to open the validation form.
        if (uploadResult?.extracted_data) {
          setPendingInvoice(uploadResult.extracted_data);
          response = "✓ Invoice extracted successfully. Please review and confirm the details below.";
        } else {
          response = uploadResult?.response || "File processed. Please fill in the invoice details below.";
        }
      } else {
        const history = getHistory();
        response = await sendMessage(payloadMessage, history);
      }

      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, text: response, sender: "bot" },
      ]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          text: "Something went wrong. Please try again.",
          sender: "bot",
        },
      ]);
    } finally {
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

  return (
    <div className="chatbox-container">
      <div className="chatbox-scroll-area">
        {/* Messages */}
        <div className="chatbox-messages">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} text={msg.text} sender={msg.sender} />
          ))}

          {loading && (
            <div className="chatbox-loading">
              <div className="chatbox-loading-avatar">AI</div>
              <div className="chatbox-loading-dots">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="chatbox-loading-dot" />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Render invoice validation below chat when upload produced extracted data. */}
        {pendingInvoice && (
          <div className="chatbox-invoice-validation">
            <InvoiceValidationForm
              extractedData={pendingInvoice}
              onConfirm={async (payload) => {
                setPendingInvoice(null);
                try {
                  const result = await confirmInvoice(payload);
                  if (result?.status !== "created") {
                    throw new Error(
                      result?.error ||
                      result?.message ||
                      result?.agent_response ||
                      "Invoice creation failed."
                    );
                  }
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: Date.now() + 2,
                      text: "Invoice confirmed and created successfully in Odoo.",
                      sender: "bot",
                    },
                  ]);
                } catch (err) {
                  const msg = err?.message || "Invoice creation failed.";
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: Date.now() + 2,
                      text: msg,
                      sender: "bot",
                    },
                  ]);
                }
              }}
              onCancel={() => setPendingInvoice(null)}
            />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chatbox-input-container">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,image/*"
          className="chatbox-file-input"
          onChange={handleFileChange}
        />
        <button
          type="button"
          className="chatbox-attach-button"
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
          placeholder="Ask about invoices, purchases, HR data..."
          rows={1}
          className="chatbox-textarea"
          onInput={(e) => {
            e.target.style.height = "auto";
            e.target.style.height = e.target.scrollHeight + "px";
          }}
        />
        {selectedFile && (
          <div className="chatbox-file-pill">
            <span className="chatbox-file-name">{selectedFile.name}</span>
            <button
              type="button"
              className="chatbox-file-remove"
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
          className="chatbox-send-button"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
