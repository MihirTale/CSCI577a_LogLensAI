import { BarChart3 } from 'lucide-react';
import type { ErrorPattern } from '../types';

interface Props {
  patterns: ErrorPattern[];
  totalErrors: number;
  loading: boolean;
}

export default function PatternDetection({ patterns, totalErrors, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-ink-subtle text-sm">
        <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin mr-2" />
        Detecting patterns…
      </div>
    );
  }

  if (patterns.length === 0) {
    return (
      <div className="text-center py-8 text-ink-subtle text-sm">
        No error patterns detected.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-ink-subtle">
        <span>{patterns.length} unique patterns</span>
        <span className="tabular-nums">{totalErrors} total errors</span>
      </div>
      {patterns.map((pattern) => (
        <div key={pattern.pattern_id} className="bg-base border border-line rounded-md p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <BarChart3 size={13} className="text-accent" />
              <span className={`severity-badge severity-${pattern.severity}`}>
                {pattern.severity}
              </span>
              <span className="text-xs text-ink-muted font-mono bg-subtle px-1.5 py-0.5 rounded tabular-nums">
                ×{pattern.count}
              </span>
            </div>
            <span className="text-xs text-ink-subtle font-mono">{pattern.pattern_id}</span>
          </div>
          <p className="text-xs font-mono text-ink-muted truncate mb-2">
            {pattern.message_template}
          </p>
          <div className="flex items-center gap-3 text-xs text-ink-subtle">
            <span>First: {pattern.first_seen.split(' ')[1] || pattern.first_seen}</span>
            <span>Last: {pattern.last_seen.split(' ')[1] || pattern.last_seen}</span>
          </div>
          {pattern.sample_logs.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-ink-subtle cursor-pointer hover:text-ink-muted">
                Sample logs ({pattern.sample_logs.length})
              </summary>
              <div className="mt-1 space-y-1">
                {pattern.sample_logs.map((log, i) => (
                  <div key={i} className="text-xs font-mono text-ink-muted bg-subtle/60 px-2 py-1 rounded truncate">
                    {log}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
