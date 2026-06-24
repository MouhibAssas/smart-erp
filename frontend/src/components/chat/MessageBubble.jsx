import { cloneElement, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./MessageBubble.css";

const FILE_REFERENCE_PATTERN = /\[(?:File|FILE):\s*([^\]]+)\]/;

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightText(value, query) {
  if (!query || !value) {
    return value;
  }

  const pattern = new RegExp(`(${escapeRegex(query)})`, "ig");
  const parts = String(value).split(pattern);

  return parts.map((part, index) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={`${part}-${index}`} className="ucm-highlight">{part}</mark>
    ) : (
      part
    )
  );
}

function highlightChildren(children, query) {
  if (!query) {
    return children;
  }

  if (Array.isArray(children)) {
    return children.map((child, index) => (
      <span key={`${index}`}>{highlightChildren(child, query)}</span>
    ));
  }

  if (typeof children === "string" || typeof children === "number") {
    return highlightText(children, query);
  }

  if (isValidElement(children) && children.props?.children !== undefined) {
    return cloneElement(children, {
      children: highlightChildren(children.props.children, query),
    });
  }

  return children;
}

function extractAttachment(content) {
  const match = content.match(FILE_REFERENCE_PATTERN);
  if (!match) {
    return { text: content, fileName: null };
  }

  const fileName = match[1].trim();
  const text = content.replace(FILE_REFERENCE_PATTERN, "").replace(/\n{3,}/g, "\n\n").trim();

  return { text, fileName };
}

export default function MessageBubble({ text, sender, highlightQuery = "" }) {
  const isUser = sender === "user";
  const content = String(text ?? "");
  const { text: displayText, fileName } = isUser ? extractAttachment(content) : { text: content, fileName: null };

  const markdownComponents = {
    p({ children, ...props }) {
      return (
        <p className="md-p" {...props}>
          {highlightChildren(children, highlightQuery)}
        </p>
      );
    },
    strong({ children, ...props }) {
      return (
        <strong className="md-strong" {...props}>
          {highlightChildren(children, highlightQuery)}
        </strong>
      );
    },
    h1({ children, ...props }) {
      return (
        <h1 className="md-h1" {...props}>
          {highlightChildren(children, highlightQuery)}
        </h1>
      );
    },
    h2({ children, ...props }) {
      return (
        <h2 className="md-h2" {...props}>
          {highlightChildren(children, highlightQuery)}
        </h2>
      );
    },
    h3({ children, ...props }) {
      return (
        <h3 className="md-h3" {...props}>
          {highlightChildren(children, highlightQuery)}
        </h3>
      );
    },
    ul({ children, ...props }) {
      return (
        <ul className="md-ul" {...props}>
          {highlightChildren(children, highlightQuery)}
        </ul>
      );
    },
    ol({ children, ...props }) {
      return (
        <ol className="md-ol" {...props}>
          {highlightChildren(children, highlightQuery)}
        </ol>
      );
    },
    li({ children, ...props }) {
      return (
        <li className="md-li" {...props}>
          {highlightChildren(children, highlightQuery)}
        </li>
      );
    },
    table({ children, ...props }) {
      return (
        <div className="md-table-wrapper">
          <table className="md-table" {...props}>
            {highlightChildren(children, highlightQuery)}
          </table>
        </div>
      );
    },
    thead({ children, ...props }) {
      return (
        <thead className="md-thead" {...props}>
          {highlightChildren(children, highlightQuery)}
        </thead>
      );
    },
    tbody({ children, ...props }) {
      return (
        <tbody className="md-tbody" {...props}>
          {highlightChildren(children, highlightQuery)}
        </tbody>
      );
    },
    tr({ children, ...props }) {
      return (
        <tr className="md-tr" {...props}>
          {highlightChildren(children, highlightQuery)}
        </tr>
      );
    },
    th({ children, ...props }) {
      return (
        <th className="md-th" {...props}>
          {highlightChildren(children, highlightQuery)}
        </th>
      );
    },
    td({ children, ...props }) {
      return (
        <td className="md-td" {...props}>
          {highlightChildren(children, highlightQuery)}
        </td>
      );
    },
    pre({ children, ...props }) {
      return (
        <pre className="md-code-block" {...props}>
          {children}
        </pre>
      );
    },
    a({ ...props }) {
      return <a {...props} target="_blank" rel="noreferrer noopener" />;
    },
    code({ className, children, ...props }) {
      const isInlineCode = !className;

      if (isInlineCode) {
        return (
          <code className="message-bubble-inline-code" {...props}>
            {highlightChildren(children, highlightQuery)}
          </code>
        );
      }

      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
  };

  return (
    <div className={`message-bubble-wrapper ${isUser ? "user" : "bot"}`}>
      {!isUser && (
        <div className="message-bubble-avatar">AI</div>
      )}
      <div className={`message-bubble-content ${isUser ? "user" : "bot"}`}>
        {isUser ? (
          <>
            {displayText && <div className="message-bubble-user-text">{highlightText(displayText, highlightQuery)}</div>}
            {fileName && (
              <div className="message-bubble-attachment" title={fileName}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21.44 11.05l-9.19 9.19a5.5 5.5 0 1 1-7.78-7.78l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.2 9.19a1.5 1.5 0 0 1-2.12-2.12l8.49-8.48" />
                </svg>
                <span className="message-bubble-attachment-label">{fileName}</span>
              </div>
            )}
          </>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {displayText}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
