import React, { useState, useRef, useEffect, useCallback } from 'react';
import MessageBubble from './MessageBubble';

// ─── Icons ────────────────────────────────────────────────────────────────────
function ChatIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function SourcesIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
      <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
    </svg>
  );
}

function DocChipIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

// ─── ChatInterface ────────────────────────────────────────────────────────────
export default function ChatInterface({
  conversation,
  messages,
  messagesLoading,
  streaming,
  streamingContent,
  sources,
  onSendMessage,
  onShowSources,
  documents,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // ── Auto-scroll to bottom on new messages ───────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // ── Auto-resize textarea ────────────────────────────────────────────────────
  const handleInputChange = useCallback((e) => {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
    }
  }, []);

  // ── Send on Enter (Shift+Enter = newline) ───────────────────────────────────
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [input, streaming] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || streaming) return;

    // Determine which doc IDs to query
    const docIds = conversation?.document_ids || [];

    onSendMessage(trimmed, docIds);
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, streaming, conversation, onSendMessage]);

  // ── Get conversation document names ────────────────────────────────────────
  const conversationDocs = React.useMemo(() => {
    if (!conversation?.document_ids || !documents) return [];
    return documents.filter((d) => conversation.document_ids.includes(d.id));
  }, [conversation, documents]);

  // ── Message rendering ───────────────────────────────────────────────────────
  const renderMessages = () => {
    if (messagesLoading) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="skeleton-message">
            <div className="skeleton skeleton-avatar" />
            <div className="skeleton skeleton-bubble" style={{ height: 70, maxWidth: '55%' }} />
          </div>
          <div className="skeleton-message" style={{ justifyContent: 'flex-end' }}>
            <div className="skeleton skeleton-bubble" style={{ height: 48, maxWidth: '40%' }} />
            <div className="skeleton skeleton-avatar" />
          </div>
          <div className="skeleton-message">
            <div className="skeleton skeleton-avatar" />
            <div className="skeleton skeleton-bubble" style={{ height: 100, maxWidth: '65%' }} />
          </div>
        </div>
      );
    }

    if (messages.length === 0 && !streaming) {
      return (
        <div className="chat-messages-empty">
          <div className="chat-messages-empty-icon" aria-hidden="true">
            <ChatIcon />
          </div>
          <p className="chat-messages-empty-title">Ask anything about your documents</p>
          <p className="chat-messages-empty-hint">
            Type a question below and I'll search through your documents to find the answer.
          </p>
        </div>
      );
    }

    return (
      <>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Streaming message */}
        {streaming && (
          <MessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: '',
              sources: [],
              created_at: new Date().toISOString(),
            }}
            isStreaming
            streamingContent={streamingContent}
          />
        )}
      </>
    );
  };

  return (
    <div className="chat-interface" role="main" aria-label="Chat">
      {/* Top Bar */}
      <div className="chat-topbar">
        <span className="chat-topbar-icon" aria-hidden="true">
          <ChatIcon />
        </span>
        <div className="chat-topbar-info">
          <h2 className="chat-topbar-title">
            {conversation?.title || 'Conversation'}
          </h2>
          {conversationDocs.length > 0 && (
            <div className="chat-topbar-docs" aria-label="Documents in this conversation">
              {conversationDocs.map((doc) => (
                <span key={doc.id} className="chat-topbar-doc-chip" title={doc.filename}>
                  <DocChipIcon aria-hidden="true" />
                  {doc.filename}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Sources button */}
        {sources && sources.length > 0 && (
          <button
            id="chat-sources-panel-btn"
            className="btn btn-secondary btn-sm"
            type="button"
            onClick={onShowSources}
            aria-label={`Show ${sources.length} sources`}
            title="Show sources"
          >
            <SourcesIcon />
            Sources ({sources.length})
          </button>
        )}
      </div>

      {/* Messages */}
      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {renderMessages()}
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <div className="chat-input-box">
          <textarea
            id="chat-input-textarea"
            ref={textareaRef}
            className="chat-input-textarea"
            placeholder={streaming ? 'AI is responding…' : 'Ask a question about your documents…'}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={streaming}
            aria-label="Message input"
            aria-multiline="true"
          />
          <button
            id="chat-send-btn"
            className="chat-send-btn"
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            aria-label="Send message"
            title="Send message (Enter)"
          >
            {streaming ? (
              <span className="spinner spinner-sm" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.25)' }} aria-hidden="true" />
            ) : (
              <SendIcon aria-hidden="true" />
            )}
          </button>
        </div>
        <p className="chat-input-hint">
          Press <kbd style={{ background: 'var(--bg-glass)', padding: '1px 5px', borderRadius: '4px', fontSize: '0.72rem', border: '1px solid var(--border)' }}>Enter</kbd> to send &nbsp;·&nbsp;
          <kbd style={{ background: 'var(--bg-glass)', padding: '1px 5px', borderRadius: '4px', fontSize: '0.72rem', border: '1px solid var(--border)' }}>Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}
