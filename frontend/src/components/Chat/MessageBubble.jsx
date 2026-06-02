import React, { useState } from 'react';

// ─── Icons ────────────────────────────────────────────────────────────────────
function BotIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function BookOpenIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
      <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function ChevronUpIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  );
}

// ─── Format timestamp ─────────────────────────────────────────────────────────
function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const date = new Date(isoStr);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// ─── Render message content with basic markdown ───────────────────────────────
function MessageContent({ content }) {
  if (!content) return null;

  // Parse bold: **text**
  // Parse inline code: `code`
  // Parse code blocks: ```\n...\n```
  const parts = [];
  const codeBlockRegex = /```[\w]*\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.slice(lastIndex, match.index) });
    }
    parts.push({ type: 'codeblock', value: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.slice(lastIndex) });
  }

  return (
    <div className="message-content">
      {parts.map((part, i) => {
        if (part.type === 'codeblock') {
          return (
            <pre key={i}>
              <code>{part.value.trim()}</code>
            </pre>
          );
        }

        // Inline: split by inline code and bold
        const inline = part.value.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
        return (
          <p key={i}>
            {inline.map((seg, j) => {
              if (seg.startsWith('`') && seg.endsWith('`')) {
                return <code key={j}>{seg.slice(1, -1)}</code>;
              }
              if (seg.startsWith('**') && seg.endsWith('**')) {
                return <strong key={j}>{seg.slice(2, -2)}</strong>;
              }
              // Split on newlines for paragraphs
              return seg.split('\n').map((line, k, arr) => (
                <React.Fragment key={k}>
                  {line}
                  {k < arr.length - 1 && <br />}
                </React.Fragment>
              ));
            })}
          </p>
        );
      })}
    </div>
  );
}

// ─── Sources section inside assistant messages ────────────────────────────────
function InlineSources({ sources }) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ marginTop: '10px' }}>
      <button
        type="button"
        className="message-sources-toggle"
        onClick={() => setExpanded((p) => !p)}
        aria-expanded={expanded}
        aria-label={expanded ? 'Hide sources' : `Show ${sources.length} sources`}
      >
        <BookOpenIcon />
        {sources.length} Source{sources.length !== 1 ? 's' : ''}
        {expanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
      </button>

      {expanded && (
        <div className="message-sources-list" role="list" aria-label="Sources">
          {sources.map((src, i) => (
            <div key={i} className="message-source-chip" role="listitem">
              <div className="message-source-header">
                <span className="message-source-filename" title={src.filename}>
                  {src.filename}
                </span>
                <span className="message-source-page">p. {src.page_num}</span>
              </div>
              {src.text && (
                <p className="message-source-text">{src.text}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── MessageBubble ────────────────────────────────────────────────────────────
export default function MessageBubble({ message, isStreaming = false, streamingContent = '' }) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  const displayContent = isStreaming ? streamingContent : message.content;

  return (
    <div className="message-group" aria-label={`${isUser ? 'Your' : 'Assistant'} message`}>
      <div className={`message-row ${message.role}`}>
        {/* Avatar */}
        {isAssistant && (
          <div className={`message-avatar assistant`} aria-hidden="true">
            <BotIcon />
          </div>
        )}

        {/* Bubble */}
        <div className={`message-bubble-wrapper ${message.role}`}>
          <div className={`message-bubble ${message.role}`}>
            {isStreaming ? (
              <div className="message-content">
                <p>
                  {displayContent}
                  <span className="streaming-cursor" aria-hidden="true" />
                </p>
              </div>
            ) : (
              <MessageContent content={displayContent} />
            )}

            {/* Sources (only for assistant non-streaming) */}
            {isAssistant && !isStreaming && (
              <InlineSources sources={message.sources} />
            )}
          </div>

          {/* Timestamp */}
          {!isStreaming && message.created_at && (
            <div className={`message-meta${isUser ? '' : ''}`}>
              <time
                className="message-time"
                dateTime={message.created_at}
                title={new Date(message.created_at).toLocaleString()}
              >
                {formatTime(message.created_at)}
              </time>
            </div>
          )}
        </div>

        {/* User avatar */}
        {isUser && (
          <div className="message-avatar user" aria-hidden="true">
            <UserIcon />
          </div>
        )}
      </div>
    </div>
  );
}
