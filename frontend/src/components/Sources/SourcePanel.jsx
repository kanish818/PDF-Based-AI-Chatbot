import React, { useState } from 'react';

// ─── Icons ────────────────────────────────────────────────────────────────────
function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function SourcesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
      <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function PageIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="8" y1="9" x2="16" y2="9" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="12" y2="17" />
    </svg>
  );
}

function ChevronIcon({ down }) {
  return down ? (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ) : (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  );
}

function EmptyIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" />
      <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
    </svg>
  );
}

// ─── Source Card ──────────────────────────────────────────────────────────────
function SourceCard({ source, index }) {
  const [excerptExpanded, setExcerptExpanded] = useState(false);
  const hasLongText = source.text && source.text.length > 180;

  return (
    <article
      className="source-card anim-fade-in"
      aria-label={`Source ${index + 1}: ${source.filename}`}
    >
      <div className="source-card-header">
        <span className="source-card-icon" aria-hidden="true">
          <PdfIcon />
        </span>
        <div className="source-card-meta">
          <div className="source-card-filename" title={source.filename}>
            {source.filename}
          </div>
          <div className="source-card-page">
            <PageIcon aria-hidden="true" />
            Page {source.page_num}
          </div>
        </div>
      </div>

      {source.text && (
        <>
          <p
            className={`source-card-excerpt${excerptExpanded ? '' : ' collapsed'}`}
          >
            {source.text}
          </p>
          {hasLongText && (
            <button
              type="button"
              className="source-card-expand-btn"
              onClick={() => setExcerptExpanded((p) => !p)}
              aria-expanded={excerptExpanded}
            >
              {excerptExpanded ? (
                <><ChevronIcon down={false} /> Show less</>
              ) : (
                <><ChevronIcon down /> Show more</>
              )}
            </button>
          )}
        </>
      )}
    </article>
  );
}

// ─── SourcePanel ──────────────────────────────────────────────────────────────
export default function SourcePanel({ sources, open, onClose }) {
  return (
    <aside
      className={`source-panel${open ? ' open' : ''}`}
      aria-label="Sources panel"
      aria-hidden={!open}
      role="complementary"
    >
      {/* Header */}
      <div className="source-panel-header">
        <h2 className="source-panel-title">
          <span className="source-panel-title-icon" aria-hidden="true">
            <SourcesIcon />
          </span>
          Sources
        </h2>
        <button
          id="source-panel-close-btn"
          className="source-panel-close"
          type="button"
          onClick={onClose}
          aria-label="Close sources panel"
          title="Close sources"
        >
          <CloseIcon />
        </button>
      </div>

      {/* Body */}
      <div className="source-panel-body">
        {sources && sources.length > 0 ? (
          <>
            <p className="source-panel-count">
              {sources.length} source{sources.length !== 1 ? 's' : ''} found
            </p>
            {sources.map((src, i) => (
              <SourceCard key={i} source={src} index={i} />
            ))}
          </>
        ) : (
          <div className="source-panel-empty">
            <div className="source-panel-empty-icon" aria-hidden="true">
              <EmptyIcon />
            </div>
            <p className="source-panel-empty-text">
              Sources will appear here after the AI responds with citations from your documents.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
