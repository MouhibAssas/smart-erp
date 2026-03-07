import "./MessageBubble.css";

export default function MessageBubble({ text, sender }) {
  const isUser = sender === "user";

  return (
    <div className={`message-bubble-wrapper ${isUser ? "user" : "bot"}`}>
      {!isUser && (
        <div className="message-bubble-avatar">AI</div>
      )}
      <div className={`message-bubble-content ${isUser ? "user" : "bot"}`}>
        {text}
      </div>
    </div>
  );
}
