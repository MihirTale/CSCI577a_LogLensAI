import { useState } from 'react';
import {
  ChevronDown, ChevronRight, GitPullRequestArrow, Hash,
  AlertTriangle, Lightbulb, Users, FileText, Sparkles,
} from 'lucide-react';
import type { PatternAnalysis } from '../types';

interface Props {
  analysis: PatternAnalysis;
  onCreateIssue: (analysis: PatternAnalysis) => void;
  creating: boolean;
  defaultExpanded?: boolean;
}

function formatTimestamp(ts: string): string {
  // Logs are 'YYYY-MM-DD HH:MM:SS.fff'
  const [, time] = ts.split(' ');
  return time?.split('.')[0] || ts;
}

export default function PatternAnalysisCard({ analysis, onCreateIssue, creating, defaultExpanded }: Props) {
  const [expanded, setExpanded] = useState(!!defaultExpanded);

  const a = analysis;
  return (
    <div className="card overflow-hidden">
      {/* Header (always visible) */}
      <div className="flex items-start gap-3 px-4 py-3 hover:bg-subtle/50 transition-colors">
        <button
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse' : 'Expand'}
          className="mt-0.5 flex-shrink-0 text-ink-subtle hover:text-ink"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <div
          className="flex-1 min-w-0 cursor-pointer"
          onClick={() => setExpanded((e) => !e)}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`severity-badge severity-${a.severity}`}>{a.severity}</span>
            <span className="text-sm font-medium text-ink truncate">{a.title}</span>
            {a.is_mock && (
              <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">
                mock
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-[11px] text-ink-subtle font-mono">
            <span className="inline-flex items-center gap-1">
              <Hash size={10} /> {a.pattern_id}
            </span>
            <span>×{a.count}</span>
            <span>
              {formatTimestamp(a.first_seen)} → {formatTimestamp(a.last_seen)}
            </span>
            <span className="tabular-nums">conf {(a.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCreateIssue(a);
          }}
          disabled={creating}
          className="btn btn-primary text-xs px-2.5 py-1.5 flex-shrink-0"
        >
          <GitPullRequestArrow size={12} />
          {creating ? 'Creating…' : 'Create issue'}
        </button>
      </div>

      {/* Body (expandable) */}
      {expanded && (
        <div className="border-t border-line px-4 py-3 space-y-3 bg-base/40">
          {a.user_impact && (
            <div className="bg-accent-soft border border-accent/20 rounded-md px-3 py-2 flex items-start gap-2">
              <Users size={13} className="text-accent flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-0.5">
                  User impact
                </div>
                <p className="text-sm text-ink">{a.user_impact}</p>
              </div>
            </div>
          )}

          <div>
            <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <AlertTriangle size={11} /> Root cause
            </h3>
            <p className="text-sm text-ink leading-relaxed">{a.root_cause}</p>
          </div>

          {a.evidence.length > 0 && (
            <div>
              <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <FileText size={11} /> Evidence
              </h3>
              <div className="space-y-1">
                {a.evidence.slice(0, 4).map((e, i) => (
                  <div
                    key={i}
                    className="font-mono text-[11px] text-ink-muted bg-subtle/60 border border-line rounded px-2 py-1 truncate"
                    title={e}
                  >
                    {e}
                  </div>
                ))}
              </div>
            </div>
          )}

          {a.actionable_fixes.length > 0 && (
            <div>
              <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <Lightbulb size={11} /> Actionable fixes
              </h3>
              <ul className="space-y-1.5">
                {a.actionable_fixes.map((f) => (
                  <li key={f.id} className="text-sm text-ink flex items-start gap-2">
                    <span
                      className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0 ${
                        f.priority === 'high'
                          ? 'bg-sev-p1bg text-sev-p1'
                          : 'bg-subtle text-ink-muted'
                      }`}
                    >
                      {f.priority}
                    </span>
                    <div className="min-w-0">
                      <div>{f.description}</div>
                      {f.file_path && (
                        <div className="font-mono text-[11px] text-ink-subtle mt-0.5">
                          {f.file_path}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {a.recommended_next_steps.length > 0 && (
            <div>
              <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <Sparkles size={11} /> Next steps
              </h3>
              <ul className="text-sm text-ink space-y-1 list-disc pl-5">
                {a.recommended_next_steps.slice(0, 4).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {a.github_issue_labels.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {a.github_issue_labels.map((l) => (
                <span
                  key={l}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-subtle text-ink-muted border border-line"
                >
                  {l}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
