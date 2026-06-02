import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getDocuments as apiGetDocuments,
  uploadDocuments as apiUploadDocuments,
  deleteDocument as apiDeleteDocument,
} from '../services/api';

const POLL_INTERVAL_MS = 1000;
const STALE_PROCESSING_MS = 5 * 60 * 1000;

function isDocumentStale(doc) {
  if (!(doc.status === 'processing' || doc.status === 'pending' || doc.status === 'queued')) {
    return false;
  }
  const updatedAt = doc.updated_at || doc.created_at;
  if (!updatedAt) return false;
  const updatedTs = new Date(updatedAt).getTime();
  return Number.isFinite(updatedTs) && Date.now() - updatedTs > STALE_PROCESSING_MS;
}

export function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);

  const pollTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // ── Fetch documents ─────────────────────────────────────────────────────────
  const fetchDocuments = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const docs = await apiGetDocuments();
      if (mountedRef.current) {
        setDocuments(docs);
        const staleDoc = docs.find(isDocumentStale);
        if (staleDoc) {
          setError(
            `Document "${staleDoc.filename}" looks stuck in processing. Refresh or re-upload if it does not recover.`
          );
        }
      }
      return docs;
    } catch (err) {
      if (mountedRef.current) {
        setError(
          err.response?.data?.detail || 'Failed to load documents.'
        );
      }
      return [];
    } finally {
      if (mountedRef.current) {
        if (!silent) setLoading(false);
      }
    }
  }, []);

  // ── Mount / unmount cleanup ─────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  // ── Polling: re-fetch when any document is processing ──────────────────────
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === 'processing' || d.status === 'pending' || d.status === 'queued'
    );

    if (hasProcessing) {
      pollTimerRef.current = setTimeout(async () => {
        if (mountedRef.current) {
          await fetchDocuments({ silent: true });
        }
      }, POLL_INTERVAL_MS);
    } else {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    }

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [documents, fetchDocuments]);

  // ── Upload files ────────────────────────────────────────────────────────────
  const uploadFiles = useCallback(async (files) => {
    if (!files || files.length === 0) return [];

    setUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      const uploaded = await apiUploadDocuments(files, (pct) => {
        if (mountedRef.current) {
          setUploadProgress(pct);
        }
      });

      if (mountedRef.current) {
        // Merge new docs with existing
        setDocuments((prev) => {
          const existingIds = new Set(prev.map((d) => d.id));
          const newDocs = uploaded.filter((d) => !existingIds.has(d.id));
          return [...newDocs, ...prev];
        });
        setUploadProgress(100);
      }

      // Immediately refresh from backend so queued uploads transition
      // into processing/ready without waiting for the next poll tick.
      await fetchDocuments({ silent: true });

      return uploaded;
    } catch (err) {
      if (mountedRef.current) {
        setError(
          err.response?.data?.detail ||
            'Upload failed. Please try again with valid PDF files.'
        );
      }
      return [];
    } finally {
      if (mountedRef.current) {
        setUploading(false);
        setTimeout(() => {
          if (mountedRef.current) setUploadProgress(0);
        }, 1500);
      }
    }
  }, [fetchDocuments]);

  // ── Delete document ─────────────────────────────────────────────────────────
  const deleteDocument = useCallback(async (id) => {
    setError(null);
    // Optimistic removal
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    try {
      await apiDeleteDocument(id);
    } catch (err) {
      // Restore on error
      if (mountedRef.current) {
        setError('Failed to delete document.');
        await fetchDocuments({ silent: true });
      }
    }
  }, [fetchDocuments]);

  // ── Clear error ─────────────────────────────────────────────────────────────
  const clearError = useCallback(() => setError(null), []);

  return {
    documents,
    loading,
    uploading,
    uploadProgress,
    error,
    fetchDocuments,
    uploadFiles,
    deleteDocument,
    clearError,
  };
}

export default useDocuments;
