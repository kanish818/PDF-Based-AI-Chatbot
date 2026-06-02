import React from 'react';
import { useAuth } from '../../hooks/useAuth.jsx';

// ─── Icons ────────────────────────────────────────────────────────────────────
function BrainIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M12 2C9.5 2 7.5 3.5 7.5 5.5C6 5.5 4 7 4 9C4 10.5 5 11.7 6.2 12.2C5.4 13 5 14 5 15.5C5 18 7 20 9.5 20H14.5C17 20 19 18 19 15.5C19 14 18.6 13 17.8 12.2C19 11.7 20 10.5 20 9C20 7 18 5.5 16.5 5.5C16.5 3.5 14.5 2 12 2Z"
        stroke="white"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12 6V12" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M9 9.5L12 12L15 9.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function ChatBubbleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

function LogOutIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function UploadCloudIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" />
    </svg>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
export default function Sidebar({
  conversations,
  currentConversation,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  conversationsLoading,
}) {
  const { user, logout } = useAuth();

  const avatarLetter = user
    ? (user.name || user.email || 'U').charAt(0).toUpperCase()
    : 'U';

  const displayName = user?.name || user?.email?.split('@')[0] || 'User';
  const displayEmail = user?.email || '';

  return (
    <nav className="sidebar" aria-label="Main navigation">
      {/* Header */}
      <div className="sidebar-header">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon" aria-hidden="true">
            <BrainIcon />
          </div>
          <span className="sidebar-logo-name">DocuMind</span>
        </div>

        {/* New Conversation Button */}
        <button
          id="sidebar-new-conversation-btn"
          className="btn btn-primary sidebar-new-btn"
          onClick={onNewConversation}
          type="button"
          title="Start a new conversation"
        >
          <PlusIcon />
          New Conversation
        </button>
      </div>

      {/* Body — conversations list */}
      <div className="sidebar-body">
        <div className="sidebar-section-label">Conversations</div>

        {conversationsLoading ? (
          // Skeleton loaders
          <>
            <div className="skeleton skeleton-conversation" />
            <div className="skeleton skeleton-conversation" />
            <div className="skeleton skeleton-conversation" />
          </>
        ) : conversations.length === 0 ? (
          <div className="sidebar-conversations-empty">
            <UploadCloudIcon />
            <p style={{ marginTop: '8px', lineHeight: 1.5 }}>
              No conversations yet.<br />Upload PDFs and start chatting!
            </p>
          </div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }} role="listbox" aria-label="Conversations">
            {conversations.map((conv) => {
              const isActive = currentConversation?.id === conv.id;
              return (
                <li key={conv.id}>
                  <div
                    role="option"
                    aria-selected={isActive}
                    className={`conversation-item${isActive ? ' active' : ''}`}
                    onClick={() => onSelectConversation(conv)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelectConversation(conv);
                      }
                    }}
                    title={conv.title || 'Untitled conversation'}
                  >
                    <span className="conversation-item-icon" aria-hidden="true">
                      <ChatBubbleIcon />
                    </span>
                    <span className="conversation-item-title">
                      {conv.title || 'Untitled conversation'}
                    </span>
                    <button
                      className="conversation-item-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      title="Delete conversation"
                      aria-label={`Delete conversation: ${conv.title}`}
                      type="button"
                    >
                      <TrashIcon />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Footer — user info */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-avatar" aria-hidden="true">{avatarLetter}</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">{displayName}</div>
            <div className="sidebar-user-email">{displayEmail}</div>
          </div>
          <button
            id="sidebar-logout-btn"
            className="sidebar-logout-btn"
            onClick={logout}
            title="Sign out"
            aria-label="Sign out"
            type="button"
          >
            <LogOutIcon />
          </button>
        </div>
      </div>
    </nav>
  );
}
