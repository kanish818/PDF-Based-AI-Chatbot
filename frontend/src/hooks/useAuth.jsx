import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import { login as apiLogin, register as apiRegister, getMe } from '../services/api';

// ─── Context ─────────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

// ─── Provider ────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('pdf_chatbot_token'));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── Persist token helper ────────────────────────────────────────────────────
  const persistToken = useCallback((newToken) => {
    if (newToken) {
      localStorage.setItem('pdf_chatbot_token', newToken);
    } else {
      localStorage.removeItem('pdf_chatbot_token');
    }
    setToken(newToken);
  }, []);

  // ── Bootstrap: load user from stored token ──────────────────────────────────
  useEffect(() => {
    const storedToken = localStorage.getItem('pdf_chatbot_token');
    if (!storedToken) {
      setLoading(false);
      return;
    }

    (async () => {
      try {
        const me = await getMe();
        setUser(me);
      } catch {
        // Token invalid / expired — clear it
        persistToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handle Google OAuth callback (?token=xxx in URL) ───────────────────────
  const handleGoogleCallback = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const googleToken = params.get('token');
    if (!googleToken) return false;

    persistToken(googleToken);

    // Strip ?token from URL without triggering a reload
    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, '', cleanUrl);

    try {
      const me = await getMe();
      setUser(me);
      return true;
    } catch {
      persistToken(null);
      setError('Google sign-in failed. Please try again.');
      return false;
    }
  }, [persistToken]);

  // ── Login ───────────────────────────────────────────────────────────────────
  const login = useCallback(async (email, password) => {
    setError(null);
    try {
      const data = await apiLogin(email, password);
      persistToken(data.access_token);
      setUser(data.user);
      return data;
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Login failed. Please check your credentials.';
      setError(msg);
      throw new Error(msg);
    }
  }, [persistToken]);

  // ── Register ────────────────────────────────────────────────────────────────
  const register = useCallback(async (name, email, password) => {
    setError(null);
    try {
      const data = await apiRegister(name, email, password);
      persistToken(data.access_token);
      setUser(data.user);
      return data;
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Registration failed. Please try again.';
      setError(msg);
      throw new Error(msg);
    }
  }, [persistToken]);

  // ── Logout ──────────────────────────────────────────────────────────────────
  const logout = useCallback(() => {
    persistToken(null);
    setUser(null);
    setError(null);
  }, [persistToken]);

  // ── Clear error ─────────────────────────────────────────────────────────────
  const clearError = useCallback(() => setError(null), []);

  const value = {
    user,
    token,
    loading,
    error,
    login,
    register,
    logout,
    handleGoogleCallback,
    clearError,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}

export default useAuth;
