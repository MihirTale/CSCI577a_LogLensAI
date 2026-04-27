import { GitCommit, ExternalLink } from 'lucide-react';
import type { SuspectCommit } from '../types';

interface Props {
  commit: SuspectCommit;
}

function formatDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export default function SuspectCommitCard({ commit }: Props) {
  return (
    <div className="border border-line bg-accent-soft/40 rounded-md p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold text-ink-subtle uppercase tracking-wider">
          <GitCommit size={11} />
          Suspect commit
        </div>
        <span className="text-[10px] text-ink-subtle tabular-nums">
          score {commit.score.toFixed(2)}
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-1">
        <code className="text-xs font-mono text-accent font-semibold">{commit.short_sha}</code>
        <span className="text-sm text-ink truncate flex-1" title={commit.message}>
          {commit.message}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-ink-subtle">
        <span>{commit.author}</span>
        {commit.date && <span>{formatDate(commit.date)}</span>}
        {commit.html_url && (
          <a
            href={commit.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-accent hover:text-accent-hover ml-auto"
          >
            <ExternalLink size={11} /> View
          </a>
        )}
      </div>
      {commit.reasoning && (
        <div className="text-[11px] text-ink-muted mt-1.5 italic">
          {commit.reasoning}
        </div>
      )}
    </div>
  );
}
