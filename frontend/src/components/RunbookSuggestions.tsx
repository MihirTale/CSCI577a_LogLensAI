import { BookOpen, Terminal } from 'lucide-react';
import type { Runbook } from '../types';

interface Props {
  runbooks: Runbook[];
  loading: boolean;
}

export default function RunbookSuggestions({ runbooks, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-ink-subtle text-sm">
        <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin mr-2" />
        Loading runbooks…
      </div>
    );
  }

  if (runbooks.length === 0) {
    return (
      <div className="text-center py-8 text-ink-subtle text-sm">
        No matching runbooks for current errors.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {runbooks.map((runbook, idx) => (
        <div key={idx} className="bg-base border border-line rounded-md p-3">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen size={13} className="text-accent" />
            <span className="text-sm font-medium text-ink">{runbook.title}</span>
            <span className={`severity-badge severity-${runbook.severity}`}>
              {runbook.severity}
            </span>
          </div>
          <p className="text-xs text-ink-subtle mb-3">
            Pattern: <span className="font-mono">{runbook.error_pattern}</span>
          </p>
          <ol className="space-y-2">
            {runbook.steps.map((step) => (
              <li key={step.step} className="flex items-start gap-2">
                <span className="text-[10px] font-semibold text-accent bg-accent-soft w-5 h-5 rounded flex items-center justify-center flex-shrink-0 tabular-nums">
                  {step.step}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-ink">{step.action}</p>
                  {step.command && (
                    <div className="flex items-center gap-1 mt-1 bg-subtle rounded px-2 py-1 border border-line">
                      <Terminal size={10} className="text-ink-subtle flex-shrink-0" />
                      <code className="text-xs text-ink font-mono truncate">
                        {step.command}
                      </code>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
