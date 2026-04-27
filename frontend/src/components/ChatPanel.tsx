import { useEffect, useRef, useState } from 'react';
import { X, Send, Sparkles } from 'lucide-react';
import { streamChat } from '../api';
import type { ChatMessage } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
}

const SUGGESTED = [
  'Summarise the last 15 minutes',
  'Why is checkout failing?',
  'Are we under attack?',
  'What changed recently?',
];

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words ${
          isUser
            ? 'bg-accent text-white'
            : 'bg-subtle text-ink border border-line'
        }`}
      >
        {msg.content || <span className="text-ink-subtle italic">…thinking</span>}
      </div>
    </div>
  );
}

export default function ChatPanel({ open, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on close
  useEffect(() => {
    if (!open) abortRef.current?.abort();
  }, [open]);

  const send = (questionRaw?: string) => {
    const question = (questionRaw ?? input).trim();
    if (!question || streaming) return;

    const history = [...messages];
    setMessages([...history, { role: 'user', content: question }, { role: 'assistant', content: '' }]);
    setInput('');
    setStreaming(true);

    abortRef.current = streamChat(
      question,
      history,
      (delta) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, content: last.content + delta };
          }
          return next;
        });
      },
      () => setStreaming(false),
      (err) => {
        console.error('Chat stream failed:', err);
        setStreaming(false);
      },
    );
  };

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
        aria-hidden
      />
      <aside className="fixed top-0 right-0 bottom-0 w-full sm:w-[420px] bg-base border-l border-line z-50 flex flex-col shadow-xl">
        <header className="flex items-center justify-between px-4 py-3 border-b border-line">
          <div className="flex items-center gap-2">
            <Sparkles size={15} className="text-accent" />
            <h2 className="text-sm font-medium text-ink">Ask LogLens</h2>
            <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">beta</span>
          </div>
          <button onClick={onClose} className="btn btn-ghost p-1" aria-label="Close chat">
            <X size={16} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-sm text-ink-muted">
              <p className="mb-3">
                Ask anything about the recent logs, errors, or current incidents. Grounded on the live log buffer and the most recent analysis.
              </p>
              <div className="space-y-1.5">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="w-full text-left text-sm px-3 py-2 rounded-md border border-line bg-surface hover:bg-subtle text-ink transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} />
          ))}
          <div ref={bottomRef} />
        </div>

        <form
          className="border-t border-line p-3 flex items-end gap-2"
          onSubmit={(e) => { e.preventDefault(); send(); }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Message LogLens…"
            rows={1}
            className="flex-1 resize-none bg-surface border border-line rounded-md px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:border-accent max-h-32"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="btn btn-primary p-2"
            aria-label="Send"
          >
            <Send size={14} />
          </button>
        </form>
      </aside>
    </>
  );
}
