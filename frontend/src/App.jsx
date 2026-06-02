import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from './hooks/useAuth.jsx';
import { useDocuments } from './hooks/useDocuments';
import { useChat } from './hooks/useChat';

import AuthPage from './components/Auth/AuthPage';
import Sidebar from './components/Layout/Sidebar';
import UploadPanel from './components/Upload/UploadPanel';
import ChatInterface from './components/Chat/ChatInterface';
import SourcePanel from './components/Sources/SourcePanel';

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const { user, loading: authLoading, wakingUp, isAuthenticated, handleGoogleCallback } = useAuth();
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);

  // ── Documents hook ──────────────────────────────────────────────────────────
  const {
    documents,
    loading: docsLoading,
    uploading,
    uploadProgress,
    fetchDocuments,
    uploadFiles,
    deleteDocument,
  } = useDocuments();

  // ── Chat hook ───────────────────────────────────────────────────────────────
  const {
    conversations,
    currentConversation,
    messages,
    streaming,
    streamingContent,
    sources,
    loading: convsLoading,
    messagesLoading,
    fetchConversations,
    createConversation,
    selectConversation,
    sendMessage,
    deleteConversation,
    clearSources,
  } = useChat();

  // ── Handle Google OAuth callback (?token= in URL) ────────────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('token')) {
      handleGoogleCallback();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load data on auth ────────────────────────────────────────────────────
  useEffect(() => {
    if (isAuthenticated) {
      fetchDocuments();
      fetchConversations();
    }
  }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Start chat from upload panel ─────────────────────────────────────────
  const handleStartChat = useCallback(
    async (documentIds) => {
      // Build a smart title from selected doc names
      const selectedDocs = documents.filter((d) => documentIds.includes(d.id));
      let title = 'Conversation';
      if (selectedDocs.length === 1) {
        title = selectedDocs[0].filename.replace(/\.pdf$/i, '');
      } else if (selectedDocs.length > 1) {
        title = `${selectedDocs.length} documents`;
      }

      try {
        await createConversation(title, documentIds);
      } catch {
        // error handled in hook
      }
    },
    [documents, createConversation]
  );

  // ── Handle new conversation button ───────────────────────────────────────
  const handleNewConversation = useCallback(() => {
    selectConversation(null);
    clearSources();
    setSourcePanelOpen(false);
  }, [selectConversation, clearSources]);

  // ── Handle select conversation ───────────────────────────────────────────
  const handleSelectConversation = useCallback(
    (conv) => {
      clearSources();
      setSourcePanelOpen(false);
      selectConversation(conv);
    },
    [selectConversation, clearSources]
  );

  // ── Open sources panel when sources arrive ────────────────────────────────
  useEffect(() => {
    if (sources && sources.length > 0) {
      setSourcePanelOpen(true);
    }
  }, [sources]);

  // ── Show loading screen while bootstrapping ───────────────────────────────
  if (authLoading) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary)',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            background: 'var(--gradient)',
            borderRadius: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-accent)',
          }}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
        </div>
        <span className="spinner spinner-lg spinner-accent" aria-label="Loading…" />
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          {wakingUp ? '☕ Server is waking up, please wait…' : 'Loading DocuMind…'}
        </p>
        {wakingUp && (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', maxWidth: 280, textAlign: 'center' }}>
            This may take up to 60 seconds on first load.
          </p>
        )}
      </div>
    );
  }

  // ── Not authenticated — show AuthPage ────────────────────────────────────
  if (!isAuthenticated) {
    return <AuthPage />;
  }

  // ── Authenticated — show main app ─────────────────────────────────────────
  return (
    <div className="app-layout">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversation={currentConversation}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={deleteConversation}
        conversationsLoading={convsLoading}
      />

      {/* Main content */}
      <div className="main-content">
        <div className="content-area">
          {currentConversation ? (
            // Chat view
            <ChatInterface
              conversation={currentConversation}
              messages={messages}
              messagesLoading={messagesLoading}
              streaming={streaming}
              streamingContent={streamingContent}
              sources={sources}
              onSendMessage={sendMessage}
              onShowSources={() => setSourcePanelOpen(true)}
              documents={documents}
            />
          ) : (
            // Upload / home view
            <UploadPanel
              documents={documents}
              documentsLoading={docsLoading}
              uploading={uploading}
              uploadProgress={uploadProgress}
              onUpload={uploadFiles}
              onDeleteDocument={deleteDocument}
              onStartChat={handleStartChat}
            />
          )}
        </div>

        {/* Sources side panel */}
        <SourcePanel
          sources={sources}
          open={sourcePanelOpen}
          onClose={() => setSourcePanelOpen(false)}
        />
      </div>
    </div>
  );
}
