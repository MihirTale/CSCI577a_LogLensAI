import { useEffect, useState } from 'react';
import { Bug, AlertTriangle, Cpu, ShieldAlert, CreditCard, Workflow, Zap } from 'lucide-react';

const API = 'http://localhost:8002';

interface Scenario {
  id: string;
  label: string;
  description: string;
}

interface RecentEntry {
  scenario_id: string;
  label: string;
  summary: string;
  triggered_at: string;
}

const ICONS: Record<string, JSX.Element> = {
  db_timeout: <Workflow size={16} />,
  null_pointer: <Bug size={16} />,
  oom: <Cpu size={16} />,
  auth_failure: <ShieldAlert size={16} />,
  api_failure: <CreditCard size={16} />,
  race_condition: <AlertTriangle size={16} />,
};

function formatRelative(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  if (isNaN(t)) return iso;
  const diff = Math.max(0, Math.floor((now - t) / 1000));
  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return new Date(iso).toLocaleTimeString();
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [recent, setRecent] = useState<RecentEntry[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${API}/scenarios`)
      .then((r) => r.json())
      .then((d) => setScenarios(d.scenarios || []))
      .catch(() => setHealthy(false));

    fetch(`${API}/health`)
      .then((r) => r.ok ? setHealthy(true) : setHealthy(false))
      .catch(() => setHealthy(false));
  }, []);

  useEffect(() => {
    const tick = async () => {
      try {
        const r = await fetch(`${API}/recent`);
        const d = await r.json();
        setRecent(d.entries || []);
      } catch {
        /* ignore */
      }
    };
    tick();
    const i = setInterval(tick, 3000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const trigger = async (id: string) => {
    setPending(id);
    try {
      const res = await fetch(`${API}/trigger/${id}`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setToast(`${data.label} → ${data.summary}`);
      // Optimistically refresh recent
      const recentResp = await fetch(`${API}/recent`);
      setRecent((await recentResp.json()).entries || []);
    } catch (e) {
      setToast(`Failed: ${(e as Error).message}`);
    } finally {
      setPending(null);
    }
  };

  const triggerAll = async () => {
    for (const s of scenarios) {
      // small spacing between triggers so timeline grouping looks natural
      await trigger(s.id);
      await new Promise((r) => setTimeout(r, 350));
    }
  };

  return (
    <div className="app">
      <div className="header">
        <div>
          <div className="brand">
            <span className="brand-mark">
              <Zap size={14} />
            </span>
            <h1>Target Service</h1>
          </div>
          <p>
            Genuinely fail on demand. Errors flow into <code>backend/logs/app.log</code>{' '}
            and appear in the LogLens dashboard live.
          </p>
        </div>
        <div className="health-pill" data-status={healthy === false ? 'bad' : 'ok'}
             style={{}}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: healthy === false ? 'var(--sev-p0)' : '#16a34a',
            }}
          />
          {healthy === null ? 'connecting…' : healthy ? 'connected to :8002' : 'backend offline'}
        </div>
      </div>

      <div className="banner">
        Tip: keep the LogLens dashboard open at <code>http://localhost:5173</code> in
        another tab — every trigger here lights it up within seconds.
      </div>

      <div className="section-title">Scenarios</div>
      <div className="grid">
        {scenarios.map((s) => (
          <div className="scenario-card" key={s.id}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: 'var(--accent)' }}>{ICONS[s.id] || <Bug size={16} />}</span>
              {s.label}
            </h3>
            <p>{s.description}</p>
            <div className="meta">id: {s.id}</div>
            <button
              className="btn primary"
              disabled={pending !== null}
              onClick={() => trigger(s.id)}
            >
              {pending === s.id ? 'Triggering…' : 'Trigger'}
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
        <button className="btn danger" disabled={pending !== null || scenarios.length === 0} onClick={triggerAll}>
          Trigger every scenario
        </button>
      </div>

      <div className="section-title">Recent triggers</div>
      <div className="recent">
        {recent.length === 0 ? (
          <div className="empty">No triggers yet. Click any scenario above.</div>
        ) : (
          recent.map((e, i) => (
            <div className="recent-row" key={`${e.triggered_at}-${i}`}>
              <span className="when">{formatRelative(e.triggered_at)}</span>
              <span>
                <span className="label">{e.label}</span>
                <div className="summary">{e.summary}</div>
              </span>
              <span className="meta mono">{e.scenario_id}</span>
            </div>
          ))
        )}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
