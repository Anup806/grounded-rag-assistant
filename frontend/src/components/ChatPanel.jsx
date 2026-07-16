import { useEffect, useRef, useState } from 'react';
import { sendMessage, getHistory, clearHistory } from '../api/client';

export default function ChatPanel({ sessionId, onSessionChange }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastBooking, setLastBooking] = useState(null);
  const bottomRef = useRef(null);

  // Rehydrate history if a session already exists (e.g. after a page refresh)
  useEffect(() => {
    if (!sessionId) return;
    getHistory(sessionId)
      .then((data) => setMessages(data.history))
      .catch((err) => setError(err.message));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    // Optimistic UI: show the user's message immediately, don't wait for the round trip
    const optimisticIndex = messages.length;
    setMessages((prev) => [...prev, { role: 'user', content: text, failed: false }]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const data = await sendMessage(sessionId, text);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response }]);
      if (!sessionId) onSessionChange(data.session_id); // first message: capture the new session
      if (data.booking) setLastBooking(data.booking);
    } catch (err) {
      setError(err.message);
      // Mark the optimistic message as failed instead of silently leaving it as "sent"
      setMessages((prev) =>
        prev.map((m, i) => (i === optimisticIndex ? { ...m, failed: true } : m)),
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    if (sessionId) {
      try {
        await clearHistory(sessionId);
      } catch (err) {
        setError(err.message);
        return;
      }
    }
    setMessages([]);
    setLastBooking(null);
  }

  return (
    <section className="panel chat-panel">
      <div className="panel-header">
        <h2>Conversational RAG</h2>
        <div className="panel-header-actions">
          <span className="session-pill">
            {sessionId ? `Session: ${sessionId}` : 'No session yet'}
          </span>
          <button type="button" onClick={handleClear}>Clear</button>
        </div>
      </div>

      {lastBooking && (
        <div className="booking-banner">
          Booking confirmed — {lastBooking.name} on {lastBooking.date} at {lastBooking.time}
        </div>
      )}

      <div className="message-list">
        {messages.length === 0 && !loading && (
          <p className="empty-state">
            Ask a question about an uploaded document, or try: "book an interview, name John,
            email john@x.com, date 2026-07-20, time 3pm".
          </p>
        )}
        {messages.map((msg, idx) => (
          <div key={idx} className={`message message-${msg.role} ${msg.failed ? 'message-failed' : ''}`}>
            <span className="message-role">{msg.failed ? `${msg.role} · failed to send` : msg.role}</span>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && <div className="message message-assistant message-pending">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="error-text">{error}</p>}

      <form className="chat-input-row" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
    </section>
  );
}
