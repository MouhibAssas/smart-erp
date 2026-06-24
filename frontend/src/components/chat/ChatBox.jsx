import { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import MessageBubble from "./MessageBubble";
import InvoiceValidationForm from "./InvoiceValidationForm";
import { confirmInvoice, sendMessage, uploadFile } from "../../services/chatApi";
import { conversationApi } from "../../services/conversationApi";
import "./ChatBox.css";

export default function ChatBox() {
  const navigate = useNavigate();
  const { publicId } = useParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [pendingInvoice, setPendingInvoice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);
  const previousPublicIdRef = useRef(publicId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    let cancelled = false;
    const previousPublicId = previousPublicIdRef.current;
    previousPublicIdRef.current = publicId;

    const loadConversation = async () => {
      setSelectedFile(null);
      setInput("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      if (!publicId) {
        setPendingInvoice(null);
        setConversationId(null);
        setLoading(false);
        setMessages([]);
        return;
      }

      if (previousPublicId && previousPublicId !== publicId) {
        setPendingInvoice(null);
      }

      setLoading(true);
      setMessages([]);
      try {
        const { data } = await conversationApi.get(publicId);
        if (cancelled) {
          return;
        }

        setConversationId(data.conversation_id ?? data.id);
        const sortedMessages = [...(data.messages || [])].sort((a, b) => {
          const timeA = a?.created_at ? Date.parse(a.created_at) : 0;
          const timeB = b?.created_at ? Date.parse(b.created_at) : 0;
          if (timeA !== timeB) return timeA - timeB;
          return (a?.id || 0) - (b?.id || 0);
        });
        const loadedMessages = sortedMessages.map((msg, idx) => ({
          id: msg.id ?? idx,
          text: msg.content,
          sender: msg.role === "user" ? "user" : "bot",
        }));
        setMessages(loadedMessages);

        // Check if ChatHome passed extracted invoice data via session storage
        const pendingInvoiceJson = sessionStorage.getItem("pendingInvoiceData");
        if (pendingInvoiceJson) {
          try {
            const invoiceData = JSON.parse(pendingInvoiceJson);
            setPendingInvoice(invoiceData);
            sessionStorage.removeItem("pendingInvoiceData");
          } catch (e) {
            console.error("Failed to parse pending invoice data:", e);
          }
        }
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error("Failed to load conversation", err);
        setConversationId(null);
        setMessages([
          {
            id: Date.now(),
            text: err?.response?.status === 404 ? "Conversation not found." : "Unable to load this conversation.",
            sender: "bot",
          },
        ]);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadConversation();

    return () => {
      cancelled = true;
    };
  }, [publicId]);

  const handleSend = async () => {
    const text = input.trim();
    if ((!text && !selectedFile) || loading) return;

    const payloadMessage = text || "Extract invoice data.";
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

        if (uploadResult.public_id && uploadResult.public_id !== publicId) {
          navigate(`/chat/${uploadResult.public_id}`);
        }
      } else {
        const sendResult = await sendMessage(payloadMessage, conversationId);
        newConvId = sendResult.conversation_id;
        setConversationId(newConvId);
        response = sendResult.response;

        if (sendResult.public_id && sendResult.public_id !== publicId) {
          navigate(`/chat/${sendResult.public_id}`);
        }
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
            e.target.style.overflowY = "hidden";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
            e.target.style.overflowY = e.target.scrollHeight > 120 ? "auto" : "hidden";
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
          className="chathome-send-button"
          type="button"
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
  );
}
