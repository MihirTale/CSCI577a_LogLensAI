import { X, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react';
import type { GitHubIssueResponse } from '../types';

interface Props {
  result: GitHubIssueResponse | null;
  onClose: () => void;
}

export default function GitHubIssueModal({ result, onClose }: Props) {
  if (!result) return null;

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="card max-w-xl w-full max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-line">
          <h3 className="text-sm font-medium text-ink flex items-center gap-2">
            {result.success ? (
              <CheckCircle size={16} className="text-accent" />
            ) : (
              <AlertCircle size={16} className="text-sev-p0" />
            )}
            {result.preview ? 'Issue Preview' : result.success ? 'Issue Created' : 'Error'}
          </h3>
          <button onClick={onClose} className="btn btn-ghost p-1" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 overflow-y-auto flex-1 space-y-3">
          <p className="text-sm text-ink">{result.message}</p>

          {result.issue_url && (
            <a
              href={result.issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-hover font-medium"
            >
              <ExternalLink size={14} />
              View Issue #{result.issue_number}
            </a>
          )}

          {result.payload && (
            <div>
              <h4 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5">Payload</h4>
              <pre className="text-xs font-mono bg-subtle text-ink-muted p-3 rounded-md overflow-x-auto max-h-64 border border-line">
                {JSON.stringify(result.payload, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-line flex justify-end">
          <button onClick={onClose} className="btn btn-secondary">Close</button>
        </div>
      </div>
    </div>
  );
}
