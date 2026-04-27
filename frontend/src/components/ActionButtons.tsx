import { Zap, Search, Github, ChevronDown } from 'lucide-react';
import { useState } from 'react';

interface Props {
  onSimulateError: (type?: string) => void;
  onAnalyze: () => void;
  onCreateIssue: () => void;
  analyzing: boolean;
  hasAnalysis: boolean;
  simulatingError: boolean;
}

const ERROR_TYPES = [
  { value: 'db_timeout', label: 'DB Timeout' },
  { value: 'null_pointer', label: 'Null Pointer' },
  { value: 'oom', label: 'Out of Memory' },
  { value: 'auth_failure', label: 'Auth Failure' },
  { value: 'api_failure', label: 'API Failure' },
];

export default function ActionButtons({
  onSimulateError, onAnalyze, onCreateIssue,
  analyzing, hasAnalysis, simulatingError,
}: Props) {
  const [showDropdown, setShowDropdown] = useState(false);

  return (
    <div className="flex flex-wrap gap-2">
      {/* Simulate Error with dropdown */}
      <div className="relative">
        <div className="flex">
          <button
            onClick={() => onSimulateError()}
            disabled={simulatingError}
            className="btn btn-secondary rounded-r-none"
          >
            <Zap size={14} />
            {simulatingError ? 'Simulating…' : 'Simulate Error'}
          </button>
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="btn btn-secondary rounded-l-none border-l-0 px-2"
            aria-label="Choose error type"
          >
            <ChevronDown size={14} />
          </button>
        </div>
        {showDropdown && (
          <div className="absolute top-full right-0 mt-1 bg-surface border border-line rounded-md shadow-lg z-20 min-w-[180px] py-1">
            {ERROR_TYPES.map((type) => (
              <button
                key={type.value}
                onClick={() => {
                  onSimulateError(type.value);
                  setShowDropdown(false);
                }}
                className="w-full text-left px-3 py-1.5 text-sm text-ink hover:bg-subtle transition-colors"
              >
                {type.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <button onClick={onAnalyze} disabled={analyzing} className="btn btn-primary">
        <Search size={14} />
        {analyzing ? 'Analyzing…' : 'Analyze'}
      </button>

      {hasAnalysis && (
        <button onClick={onCreateIssue} className="btn btn-secondary">
          <Github size={14} />
          Create Issue
        </button>
      )}
    </div>
  );
}
