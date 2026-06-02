import React, { useState, useCallback } from 'react';

// ─── Icons ────────────────────────────────────────────────────────────────────
function DocumentIcon({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function UploadIcon({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function XIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

// ─── Format bytes ─────────────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// ─── Status badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  if (status === 'ready') {
    return <span className="badge badge-success">Ready</span>;
  }
  if (status === 'processing' || status === 'pending') {
    return (
      <span className="badge badge-warning">
        <span className="spinner spinner-sm" style={{ borderTopColor: 'var(--warning)', borderColor: 'rgba(245,158,11,0.2)', width: '10px', height: '10px' }} />
        Processing
      </span>
    );
  }
  if (status === 'error' || status === 'failed') {
    return <span className="badge badge-error">Failed</span>;
  }
  return <span className="badge badge-accent">{status}</span>;
}

// ─── UploadPanel ──────────────────────────────────────────────────────────────
export default function UploadPanel({
  documents,
  documentsLoading,
  uploading,
  uploadProgress,
  onUpload,
  onDeleteDocument,
  onStartChat,
}) {
  const [pendingFiles, setPendingFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [selectedDocIds, setSelectedDocIds] = useState([]);

  // ── Drag handlers ───────────────────────────────────────────────────────────
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files).filter(
      (f) => f.type === 'application/pdf'
    );
    if (dropped.length > 0) {
      setPendingFiles((prev) => [...prev, ...dropped]);
    }
  }, []);

  const handleFileInput = useCallback((e) => {
    const selected = Array.from(e.target.files);
    if (selected.length > 0) {
      setPendingFiles((prev) => [...prev, ...selected]);
    }
    // Reset input so the same file can be re-added
    e.target.value = '';
  }, []);

  const removePendingFile = useCallback((index) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (pendingFiles.length === 0) return;
    const uploaded = await onUpload(pendingFiles);
    if (uploaded && uploaded.length > 0) {
      setPendingFiles([]);
    }
  }, [pendingFiles, onUpload]);

  const toggleDocSelection = useCallback((id) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  }, []);

  const handleStartChat = useCallback(() => {
    if (selectedDocIds.length === 0) return;
    onStartChat(selectedDocIds);
  }, [selectedDocIds, onStartChat]);

  const readyDocs = documents.filter((d) => d.status === 'ready');

  return (
    <div className="upload-panel">
      <div className="upload-panel-inner">
        {/* Hero */}
        <div className="upload-hero">
          <div className="upload-hero-icon" aria-hidden="true">
            <DocumentIcon size={40} />
          </div>
          <h1 className="upload-hero-title">Upload your PDFs</h1>
          <p className="upload-hero-subtitle">
            Drop your documents below to get started. Then select them and start
            an AI-powered conversation.
          </p>
          <div className="feature-list" aria-label="Features">
            <div className="feature-item"><span className="feature-dot" />Instant semantic search across all pages</div>
            <div className="feature-item"><span className="feature-dot" />Cited answers with page references</div>
            <div className="feature-item"><span className="feature-dot" />Chat with multiple documents at once</div>
          </div>
        </div>

        {/* Drop Zone */}
        <div
          id="upload-drop-zone"
          className={`drop-zone${dragActive ? ' drag-active' : ''}`}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          role="button"
          aria-label="Drop PDF files here or click to browse"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              document.getElementById('upload-file-input').click();
            }
          }}
        >
          <input
            id="upload-file-input"
            type="file"
            accept=".pdf,application/pdf"
            multiple
            className="drop-zone-input"
            onChange={handleFileInput}
            aria-hidden="true"
            tabIndex={-1}
          />
          <div className="drop-zone-icon" aria-hidden="true">
            <UploadIcon size={42} />
          </div>
          <p className="drop-zone-text">
            Drag & drop PDFs here, or{' '}
            <strong onClick={() => document.getElementById('upload-file-input').click()}>
              browse files
            </strong>
          </p>
          <p className="drop-zone-hint">Supports PDF files up to 50MB each</p>
        </div>

        {/* Pending Files Queue */}
        {pendingFiles.length > 0 && (
          <div className="file-queue">
            <div className="file-queue-header">
              <span>{pendingFiles.length} file{pendingFiles.length !== 1 ? 's' : ''} selected</span>
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={() => setPendingFiles([])}
              >
                Clear all
              </button>
            </div>
            {pendingFiles.map((file, idx) => (
              <div key={`${file.name}-${idx}`} className="file-queue-item">
                <span className="file-queue-icon" aria-hidden="true"><PdfIcon /></span>
                <div className="file-queue-info">
                  <div className="file-queue-name" title={file.name}>{file.name}</div>
                  <div className="file-queue-size">{formatBytes(file.size)}</div>
                </div>
                <button
                  className="file-queue-remove"
                  type="button"
                  onClick={() => removePendingFile(idx)}
                  aria-label={`Remove ${file.name}`}
                  title="Remove file"
                >
                  <XIcon />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Upload Progress */}
        {uploading && (
          <div className="upload-progress" role="status" aria-live="polite">
            <div className="upload-progress-bar-track">
              <div
                className="upload-progress-bar-fill"
                style={{ width: `${uploadProgress}%` }}
                aria-valuenow={uploadProgress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <p className="upload-progress-text">
              {uploadProgress < 100
                ? `Uploading… ${uploadProgress}%`
                : 'Processing documents…'}
            </p>
          </div>
        )}

        {/* Upload Button */}
        {pendingFiles.length > 0 && !uploading && (
          <button
            id="upload-submit-btn"
            className="btn btn-primary upload-btn"
            type="button"
            onClick={handleUpload}
            disabled={uploading}
          >
            <UploadIcon size={16} />
            Upload {pendingFiles.length} File{pendingFiles.length !== 1 ? 's' : ''}
          </button>
        )}

        {/* Library of uploaded documents */}
        {documentsLoading ? (
          <div className="docs-library">
            <div className="docs-library-header">
              <span className="docs-library-title">Your Documents</span>
            </div>
            <div className="skeleton" style={{ height: 56, borderRadius: 8 }} />
            <div className="skeleton" style={{ height: 56, borderRadius: 8 }} />
          </div>
        ) : documents.length > 0 ? (
          <div className="docs-library">
            <div className="docs-library-header">
              <span className="docs-library-title">
                Your Documents ({documents.length})
              </span>
              {selectedDocIds.length > 0 && (
                <span style={{ fontSize: '0.78rem', color: 'var(--text-accent)', fontWeight: 600 }}>
                  {selectedDocIds.length} selected
                </span>
              )}
            </div>

            {documents.map((doc) => {
              const isSelected = selectedDocIds.includes(doc.id);
              const isReady = doc.status === 'ready';
              return (
                <div
                  key={doc.id}
                  className="doc-item"
                  onClick={() => isReady && toggleDocSelection(doc.id)}
                  style={{ cursor: isReady ? 'pointer' : 'default' }}
                  role={isReady ? 'checkbox' : undefined}
                  aria-checked={isReady ? isSelected : undefined}
                  tabIndex={isReady ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isReady && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      toggleDocSelection(doc.id);
                    }
                  }}
                >
                  {isReady && (
                    <div
                      className={`doc-item-checkbox${isSelected ? ' checked' : ''}`}
                      aria-hidden="true"
                    >
                      {isSelected && <CheckIcon />}
                    </div>
                  )}
                  <span className="doc-item-icon" aria-hidden="true"><PdfIcon /></span>
                  <div className="doc-item-info">
                    <div className="doc-item-name" title={doc.filename}>{doc.filename}</div>
                    <div className="doc-item-meta">
                      <span className="doc-item-meta-text">{formatBytes(doc.file_size)}</span>
                      {doc.page_count && (
                        <span className="doc-item-meta-text">· {doc.page_count} pages</span>
                      )}
                      <StatusBadge status={doc.status} />
                    </div>
                  </div>
                  <button
                    className="doc-item-delete"
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteDocument(doc.id);
                    }}
                    aria-label={`Delete ${doc.filename}`}
                    title="Delete document"
                  >
                    <TrashIcon />
                  </button>
                </div>
              );
            })}

            {/* Start Chat button */}
            {selectedDocIds.length > 0 && readyDocs.length > 0 && (
              <button
                id="start-chat-btn"
                className="btn btn-primary start-chat-btn"
                type="button"
                onClick={handleStartChat}
              >
                <ChatIcon />
                Start Chatting with {selectedDocIds.length} Document{selectedDocIds.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
