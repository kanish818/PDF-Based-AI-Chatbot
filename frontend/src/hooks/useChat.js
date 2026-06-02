import { useState, useCallback, useRef, useEffect } from 'react';
import {
  getConversations as apiGetConversations,
  createConversation as apiCreateConversation,
  deleteConversation as apiDeleteConversation,
  getMessages as apiGetMessages,
  streamChat as apiStreamChat,
} from '../services/api';

export function useChat() {
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState(null);

  const mountedRef = useRef(true);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Cancel any in-flight stream on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ── Fetch conversations ─────────────────────────────────────────────────────
  const fetchConversations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const convs = await apiGetConversations();
      if (mountedRef.current) {
        setConversations(convs);
      }
      return convs;
    } catch (err) {
      if (mountedRef.current) {
        setError(err.response?.data?.detail || 'Failed to load conversations.');
      }
      return [];
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // ── Select a conversation and load its messages ────────────────────────────
  const selectConversation = useCallback(async (conversation) => {
    if (!conversation) {
      setCurrentConversation(null);
      setMessages([]);
      setSources([]);
      return;
    }

    setCurrentConversation(conversation);
    setSources([]);
    setStreamingContent('');
    setMessagesLoading(true);
    setError(null);

    try {
      const msgs = await apiGetMessages(conversation.id);
      if (mountedRef.current) {
        setMessages(msgs);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.response?.data?.detail || 'Failed to load messages.');
        setMessages([]);
      }
    } finally {
      if (mountedRef.current) {
        setMessagesLoading(false);
      }
    }
  }, []);

  // ── Create a new conversation ───────────────────────────────────────────────
  const createConversation = useCallback(async (title, documentIds) => {
    setError(null);
    try {
      const conv = await apiCreateConversation(title, documentIds);
      if (mountedRef.current) {
        setConversations((prev) => [conv, ...prev]);
        setCurrentConversation(conv);
        setMessages([]);
        setSources([]);
      }
      return conv;
    } catch (err) {
      const msg =
        err.response?.data?.detail || 'Failed to create conversation.';
      if (mountedRef.current) {
        setError(msg);
      }
      throw new Error(msg);
    }
  }, []);

  // ── Delete a conversation ───────────────────────────────────────────────────
  const deleteConversation = useCallback(
    async (id) => {
      // Optimistic
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversation?.id === id) {
        setCurrentConversation(null);
        setMessages([]);
        setSources([]);
      }

      try {
        await apiDeleteConversation(id);
      } catch {
        // Restore
        if (mountedRef.current) {
          await fetchConversations();
        }
      }
    },
    [currentConversation, fetchConversations]
  );

  // ── Send a message (SSE streaming) ─────────────────────────────────────────
  const sendMessage = useCallback(
    async (question, documentIds = []) => {
      if (!currentConversation || streaming) return;

      const userMessage = {
        id: `temp-user-${Date.now()}`,
        role: 'user',
        content: question,
        sources: [],
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setStreaming(true);
      setStreamingContent('');
      setSources([]);
      setError(null);

      // Cancel any previous stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      let accumulatedContent = '';
      let finalSources = [];

      try {
        const response = await apiStreamChat(
          currentConversation.id,
          question,
          documentIds
        );

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE data lines
          const lines = buffer.split('\n');
          buffer = lines.pop(); // keep incomplete last line

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data:')) continue;

            const jsonStr = trimmed.slice(5).trim();
            if (jsonStr === '[DONE]') continue;

            let event;
            try {
              event = JSON.parse(jsonStr);
            } catch {
              continue;
            }

            if (event.type === 'chunk') {
              accumulatedContent += event.content || '';
              if (mountedRef.current) {
                setStreamingContent(accumulatedContent);
              }
            } else if (event.type === 'sources') {
              finalSources = event.sources || [];
              if (mountedRef.current) {
                setSources(finalSources);
              }
            } else if (event.type === 'done') {
              break;
            }
          }
        }

        // Flush any remaining buffer
        if (buffer.trim() && buffer.includes('data:')) {
          const jsonStr = buffer.replace(/^data:\s*/, '').trim();
          if (jsonStr && jsonStr !== '[DONE]') {
            try {
              const event = JSON.parse(jsonStr);
              if (event.type === 'chunk') {
                accumulatedContent += event.content || '';
              } else if (event.type === 'sources') {
                finalSources = event.sources || [];
                if (mountedRef.current) setSources(finalSources);
              }
            } catch {
              // ignore parse error on leftover buffer
            }
          }
        }

        // Finalize: add the assistant message to the messages array
        if (mountedRef.current) {
          const assistantMessage = {
            id: `temp-assistant-${Date.now()}`,
            role: 'assistant',
            content: accumulatedContent,
            sources: finalSources,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMessage]);
          setStreamingContent('');
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        if (mountedRef.current) {
          setError('Failed to get a response. Please try again.');
          // If we accumulated anything, still show it
          if (accumulatedContent) {
            const assistantMessage = {
              id: `temp-assistant-err-${Date.now()}`,
              role: 'assistant',
              content: accumulatedContent,
              sources: finalSources,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
          }
          setStreamingContent('');
        }
      } finally {
        if (mountedRef.current) {
          setStreaming(false);
        }
      }
    },
    [currentConversation, streaming]
  );

  // ── Clear sources panel ─────────────────────────────────────────────────────
  const clearSources = useCallback(() => setSources([]), []);

  // ── Clear error ─────────────────────────────────────────────────────────────
  const clearError = useCallback(() => setError(null), []);

  return {
    conversations,
    currentConversation,
    messages,
    streaming,
    streamingContent,
    sources,
    loading,
    messagesLoading,
    error,
    fetchConversations,
    createConversation,
    selectConversation,
    sendMessage,
    deleteConversation,
    clearSources,
    clearError,
  };
}

export default useChat;
