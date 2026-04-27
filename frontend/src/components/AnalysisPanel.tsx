import { CheckCircle, AlertTriangle, Target, FileText, Lightbulb, Users } from 'lucide-react';
import type { AnalysisResult } from '../types';
import SuspectCommitCard from './SuspectCommitCard';

interface Props {
  analysis: AnalysisResult | null;
  loading: boolean;
  selectedFixes: Set<string>;
  onToggleFix: (fixId: string) => void;
}

export default function AnalysisPanel({ analysis, loading, selectedFixes, onToggleFix }: Props) {
  if (loading) {
    return (
      <div className="card p-6 flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-ink-muted">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Analyzing logs...</span>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="card p-6 flex items-center justify-center h-full">
        <div className="text-center text-ink-subtle">
          <Target size={28} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Click “Analyze” to inspect recent errors</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card flex flex-col h-full min-h-0 overflow-hidden overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-line">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-ink flex items-center gap-2">
            <Target size={15} className="text-accent" />
            Analysis
          </h2>
          <div className="flex items-center gap-2">
            <span className={`severity-badge severity-${analysis.severity}`}>
              {analysis.severity}
            </span>
            {analysis.is_mock && (
              <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">mock</span>
            )}
          </div>
        </div>
        <p className="text-base font-medium text-ink mt-2">{analysis.title}</p>
      </div>

      <div className="p-4 space-y-4 flex-1">
        {/* Confidence */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1 bg-subtle rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${analysis.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-ink-muted tabular-nums">{Math.round(analysis.confidence * 100)}% confidence</span>
        </div>

        {/* User impact */}
        {analysis.user_impact && (
          <div className="bg-accent-soft border border-accent/20 rounded-md px-3 py-2 flex items-start gap-2">
            <Users size={13} className="text-accent flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-0.5">User impact</div>
              <p className="text-sm text-ink">{analysis.user_impact}</p>
            </div>
          </div>
        )}

        {/* Suspect commit */}
        {analysis.suspect_commit && (
          <SuspectCommitCard commit={analysis.suspect_commit} />
        )}

        {/* Root Cause */}
        <div>
          <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <AlertTriangle size={11} /> Root Cause
          </h3>
          <p className="text-sm text-ink leading-relaxed">{analysis.root_cause}</p>
        </div>

        {/* Evidence */}
        {analysis.evidence.length > 0 && (
          <div>
            <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <FileText size={11} /> Evidence
            </h3>
            <div className="space-y-1">
              {analysis.evidence.map((e, i) => (
                <div key={i} className="text-xs font-mono bg-subtle/60 text-ink-muted px-2 py-1 rounded truncate">
                  {e}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actionable Fixes */}
        {analysis.actionable_fixes.length > 0 && (
          <div>
            <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-2 flex items-center gap-1">
              <Lightbulb size={11} /> Actionable Fixes
            </h3>
            <div className="space-y-2">
              {analysis.actionable_fixes.map((fix) => {
                const selected = selectedFixes.has(fix.id);
                return (
                  <button
                    key={fix.id}
                    onClick={() => onToggleFix(fix.id)}
                    className={`w-full text-left p-3 rounded-md border transition-all ${
                      selected
                        ? 'border-accent bg-accent-soft'
                        : 'border-line bg-base hover:border-ink-subtle'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                        selected ? 'bg-accent border-accent' : 'border-ink-subtle'
                      }`}>
                        {selected && <CheckCircle size={11} className="text-white" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded ${
                            fix.priority === 'high' ? 'bg-sev-p0bg text-sev-p0' :
                            fix.priority === 'medium' ? 'bg-sev-p2bg text-sev-p2' :
                            'bg-sev-p3bg text-sev-p3'
                          }`}>
                            {fix.priority}
                          </span>
                          {fix.file_path && (
                            <span className="text-xs text-ink-subtle font-mono truncate">{fix.file_path}</span>
                          )}
                        </div>
                        <p className="text-sm text-ink mt-1">{fix.description}</p>
                        {fix.code_snippet && (
                          <pre className="text-xs font-mono bg-subtle text-ink p-2 mt-2 rounded overflow-x-auto border border-line">
                            {fix.code_snippet}
                          </pre>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Next Steps */}
        {analysis.recommended_next_steps.length > 0 && (
          <div>
            <h3 className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5">Next Steps</h3>
            <ol className="list-decimal list-inside text-sm text-ink-muted space-y-1">
              {analysis.recommended_next_steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}
