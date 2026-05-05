import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import InvoiceValidationForm from "./InvoiceValidationForm";
import { confirmInvoice, sendMessage, uploadFile } from "../../services/chatApi";
import { conversationApi } from "../../services/conversationApi";
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
  const [conversationId, setConversationId] = useState(null);
  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Listen for load-conversation event from Layout
  useEffect(() => {
    const handleLoadConversation = async (e) => {
      const conv = e.detail;
      setConversationId(conv.id);
      setMessages([
        {
          id: 0,
          text: "Hello! I'm your ERP assistant. Ask me anything about your invoices, purchases, HR data, or any business operations.",
          sender: "bot",
        },
      ]);
      setLoading(true);
      try {
        const { data } = await conversationApi.get(conv.id);
        const loadedMessages = data.messages.map((msg, idx) => ({
          id: idx,
          text: msg.content,
          sender: msg.role === "user" ? "user" : "bot",
        }));
        setMessages(loadedMessages);
      } catch (err) {
        console.error("Failed to load conversation", err);
      } finally {
        setLoading(false);
      }
    };

    window.addEventListener("load-conversation", handleLoadConversation);
    return () => window.removeEventListener("load-conversation", handleLoadConversation);
  }, []);

  // Listen for new-conversation event from Layout
  useEffect(() => {
    const handleNewConversation = () => {
      setConversationId(null);
      setMessages([
        {
          id: 1,
          text: "Hello! I'm your ERP assistant. Ask me anything about your invoices, purchases, HR data, or any business operations.",
          sender: "bot",
        },
      ]);
    };

    window.addEventListener("new-conversation", handleNewConversation);
    return () => window.removeEventListener("new-conversation", handleNewConversation);
  }, []);

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
      let newConvId = conversationId;

      if (selectedFile) {
        const uploadResult = await uploadFile(selectedFile, payloadMessage, conversationId);

        newConvId = uploadResult.conversation_id;
        setConversationId(newConvId);

        if (uploadResult?.extracted_data) {
          setPendingInvoice(uploadResult.extracted_data);
        }

        // ✅ Always use backend response
        response = uploadResult.response;
      } else {
        const sendResult = await sendMessage(payloadMessage, conversationId);
        newConvId = sendResult.conversation_id;
        setConversationId(newConvId);
        response = sendResult.response;
      }

      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, text: response, sender: "bot" },
      ]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // Refresh conversations in sidebar
      if (window.__refreshConversations) {
        window.__refreshConversations();
      }
      // Mark conversation as active
      if (window.__setActiveConvId) {
        window.__setActiveConvId(newConvId);
      }
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          text: err?.response?.data?.detail || "Something went wrong. Please try again.",
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
              conversationId={conversationId}
              onConfirm={async (payload) => {
                setPendingInvoice(null);
                setLoading(true);
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
                      text: result?.message || "Invoice creation failed.",
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
                } finally {
                  setLoading(false);
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
