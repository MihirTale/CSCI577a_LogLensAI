import { Terminal, AlertTriangle, Info } from 'lucide-react';
import type { LogEntry } from '../types';

interface Props {
  logs: LogEntry[];
  loading: boolean;
}

export default function LogPanel({ logs, loading }: Props) {
  const levelIcon = (level: string) => {
    if (level === 'ERROR') return <AlertTriangle size={12} className="text-sev-p0 flex-shrink-0" />;
    if (level === 'WARN') return <AlertTriangle size={12} className="text-sev-p2 flex-shrink-0" />;
    return <Info size={12} className="text-ink-subtle flex-shrink-0" />;
  };

  const levelClass = (level: string) => {
    if (level === 'ERROR') return 'error';
    if (level === 'WARN') return 'warn';
    return 'info';
  };

  return (
    <div className="card flex flex-col h-full min-h-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          <Terminal size={15} className="text-accent" />
          <h2 className="text-sm font-medium text-ink">Live Logs</h2>
        </div>
        <div className="flex items-center gap-2">
          {loading && (
            <div className="w-1.5 h-1.5 rounded-full bg-accent live-dot" />
          )}
          <span className="text-xs text-ink-subtle tabular-nums">{logs.length} lines</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto py-1 min-h-0 bg-base/40">
        {logs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ink-subtle text-sm">
            Waiting for logs...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className={`log-line ${levelClass(log.level)} flex items-start gap-2`}>
              {levelIcon(log.level)}
              <span className="text-ink-subtle select-none whitespace-nowrap">
                {log.timestamp.split(' ')[1] || log.timestamp}
              </span>
              <span className="truncate">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
