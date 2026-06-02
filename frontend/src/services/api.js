import axios from 'axios';

const apiOrigin = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/+$/, '');
const API_BASE_URL = apiOrigin ? `${apiOrigin}/api` : '/api';

// ─── Axios Instance ──────────────────────────────────────────────────────────
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Request Interceptor ─────────────────────────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('pdf_chatbot_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Response Interceptor ────────────────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pdf_chatbot_token');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

// ─── Auth ────────────────────────────────────────────────────────────────────
export const login = async (email, password) => {
  const { data } = await api.post('/auth/login', { email, password });
  return data;
};

export const register = async (name, email, password) => {
  const { data } = await api.post('/auth/register', { name, email, password });
  return data;
};

export const getMe = async () => {
  const { data } = await api.get('/auth/me');
  return data;
};

export const googleAuth = () => {
  window.location.href = `${API_BASE_URL}/auth/google`;
};

// ─── Documents ───────────────────────────────────────────────────────────────
export const getDocuments = async () => {
  const { data } = await api.get('/documents');
  return data;
};

export const uploadDocuments = async (files, onProgress) => {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    formData.append('files', file);
  });

  const { data } = await api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(pct);
      }
    },
  });
  return data;
};

export const deleteDocument = async (id) => {
  const { data } = await api.delete(`/documents/${id}`);
  return data;
};

// ─── Chat / Conversations ────────────────────────────────────────────────────
export const getConversations = async () => {
  const { data } = await api.get('/chat/conversations');
  return data;
};

export const createConversation = async (title, documentIds) => {
  const { data } = await api.post('/chat/conversations', {
    title,
    document_ids: documentIds,
  });
  return data;
};

export const deleteConversation = async (id) => {
  const { data } = await api.delete(`/chat/conversations/${id}`);
  return data;
};

export const getMessages = async (conversationId) => {
  const { data } = await api.get(`/chat/conversations/${conversationId}/messages`);
  return data;
};

/**
 * Returns a fetch-based readable stream for SSE.
 * Caller is responsible for reading chunks.
 */
export const streamChat = async (conversationId, question, documentIds) => {
  const token = localStorage.getItem('pdf_chatbot_token');

  const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      question,
      document_ids: documentIds,
    }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('pdf_chatbot_token');
      window.location.href = '/';
    }
    throw new Error(`Stream request failed: ${response.status} ${response.statusText}`);
  }

  return response;
};

export default api;
