import { useState } from 'react';
import UploadPanel from './components/UploadPanel';
import ChatPanel from './components/ChatPanel';
import BookingsPanel from './components/BookingsPanel';
import ConnectionStatus from './components/ConnectionStatus';
import { useSession } from './hooks/useSession';

const TABS = [
  { id: 'chat', label: 'Chat' },
  { id: 'upload', label: 'Upload' },
  { id: 'bookings', label: 'Bookings' },
];

export default function App() {
  const [tab, setTab] = useState('chat');
  const { sessionId, persistSession } = useSession();

  return (
    <main className="page-shell">
      <section className="hero hero-compact">
        <div className="eyebrow-row">
          <div className="eyebrow">Backend-RAG-with-Two-RESTAPI</div>
          <ConnectionStatus />
        </div>
        <h1>RAG Console</h1>
        <p>
          Upload documents, chat with the RAG assistant, and manage interview bookings
          against your local FastAPI backend.
        </p>
      </section>

      <nav className="tab-row">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab-button ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'chat' && <ChatPanel sessionId={sessionId} onSessionChange={persistSession} />}
      {tab === 'upload' && <UploadPanel />}
      {tab === 'bookings' && <BookingsPanel />}
    </main>
  );
}
