import { useCallback, useState } from 'react';

const STORAGE_KEY = 'rag_session_id';

/**
 * Tracks the active chat session_id in localStorage so a page refresh
 * doesn't lose the Redis-backed conversation.
 *
 * Trade-off worth knowing: localStorage survives refreshes but not
 * "clear browsing data", and it's readable by any JS on the page (XSS risk).
 * A production version with real auth would issue this as an httpOnly cookie instead.
 */
export function useSession() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE_KEY));

  const persistSession = useCallback((id) => {
    localStorage.setItem(STORAGE_KEY, id);
    setSessionId(id);
  }, []);

  const startNewSession = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
  }, []);

  return { sessionId, persistSession, startNewSession };
}
