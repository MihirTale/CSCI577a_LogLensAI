import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { RefreshCw, Sparkles, ExternalLink } from 'lucide-react';
import { api } from './api';
import type {
  LogEntry, GitHubIssueResponse,
  ErrorPattern, Incident, Runbook, HealthSummary,
  SeveritySeriesResponse, PatternAnalysis,
} from './types';
import LogPanel from './components/LogPanel';
import GitHubIssueModal from './components/GitHubIssueModal';
import PatternDetection from './components/PatternDetection';
import IncidentTimeline from './components/IncidentTimeline';
import RunbookSuggestions from './components/RunbookSuggestions';
import ThemeToggle from './components/ThemeToggle';
import HealthDashboard from './components/HealthDashboard';
import ChatPanel from './components/ChatPanel';
import ErrorRateChart from './components/ErrorRateChart';
import SeverityBreakdownChart from './components/SeverityBreakdownChart';
import PatternAnalysisCard from './components/PatternAnalysisCard';

type OncallTab = 'patterns' | 'timeline' | 'runbooks';

const SEVERITY_RANK: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };

export default function App() {
  // Core state
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [issueResult, setIssueResult] = useState<GitHubIssueResponse | null>(null);

  // Loading state
  const [logsLoading, setLogsLoading] = useState(true);

  // Health
  const [healthy, setHealthy] = useState(false);
  const [healthSummary, setHealthSummary] = useState<HealthSummary | null>(null);

  // Charts
  const [severitySeries, setSeveritySeries] = useState<SeveritySeriesResponse | null>(null);

  // Per-pattern analyses
  const [analyses, setAnalyses] = useState<PatternAnalysis[]>([]);
  const [analysesLoading, setAnalysesLoading] = useState(false);
  const [analysesIsMock, setAnalysesIsMock] = useState(false);
  const [analysesMockReason, setAnalysesMockReason] = useState<string | null>(null);
  const [creatingFor, setCreatingFor] = useState<string | null>(null);

  // Chat drawer
  const [chatOpen, setChatOpen] = useState(false);

  // Oncall tab state
  const [oncallTab, setOncallTab] = useState<OncallTab>('patterns');
  const [patterns, setPatterns] = useState<ErrorPattern[]>([]);
  const [totalErrors, setTotalErrors] = useState(0);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [oncallLoading, setOncallLoading] = useState(false);

  // Fetch logs
  const fetchLogs = useCallback(async () => {
    try {
      const data = await api.getLatestLogs(80);
      setLogs(data.logs);
      setLogsLoading(false);
    } catch {
      setLogsLoading(false);
    }
  }, []);

  // Health check
  useEffect(() => {
    api.health().then(() => setHealthy(true)).catch(() => setHealthy(false));
  }, []);

  // Poll logs every 3 seconds
  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  // Poll health summary + severity series every 5 seconds
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [hs, ss] = await Promise.all([
          api.getHealthSummary(),
          api.getSeveritySeries(),
        ]);
        if (!cancelled) {
          setHealthSummary(hs);
          setSeveritySeries(ss);
        }
      } catch {/* ignore */}
    };
    tick();
    const interval = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Fetch oncall data when tab changes
  const fetchOncallData = useCallback(async (tab: OncallTab) => {
    setOncallLoading(true);
    try {
      if (tab === 'patterns') {
        const data = await api.getPatterns();
        setPatterns(data.patterns);
        setTotalErrors(data.total_errors);
      } else if (tab === 'timeline') {
        const data = await api.getTimeline();
        setIncidents(data.incidents);
      } else {
        const data = await api.getRunbooks();
        setRunbooks(data.runbooks);
      }
    } catch (e) {
      console.error('Failed to fetch oncall data:', e);
    }
    setOncallLoading(false);
  }, []);

  useEffect(() => {
    fetchOncallData(oncallTab);
  }, [oncallTab, fetchOncallData]);

  // Per-pattern analyses: fetch on mount, refresh on demand
  const fetchAnalyses = useCallback(async (force = false) => {
    setAnalysesLoading(true);
    try {
      const data = await api.analyzePatterns(force);
      setAnalyses(data.analyses);
      setAnalysesIsMock(data.is_mock);
      setAnalysesMockReason(data.mock_reason ?? null);
    } catch (e) {
      console.error('Pattern analysis failed:', e);
    }
    setAnalysesLoading(false);
  }, []);

  // Initial pattern analysis on mount
  useEffect(() => {
    fetchAnalyses(false);
  }, [fetchAnalyses]);

  // Auto-trigger pattern analysis ONLY when a new ERROR/WARN log arrives.
  // Debounced 5s so a burst of errors causes a single analysis call.
  const lastErrorTsRef = useRef<string>('');
  const analyzeDebounceRef = useRef<number | null>(null);
  useEffect(() => {
    let latest = '';
    for (const l of logs) {
      if (l.level !== 'ERROR' && l.level !== 'WARN') continue;
      if (l.timestamp > latest) latest = l.timestamp;
    }
    if (!latest || latest === lastErrorTsRef.current) return;
    const isFirstSeen = lastErrorTsRef.current === '';
    lastErrorTsRef.current = latest;
    if (isFirstSeen) return;  // skip the initial population; mount-effect already analyzed
    if (analyzeDebounceRef.current) window.clearTimeout(analyzeDebounceRef.current);
    analyzeDebounceRef.current = window.setTimeout(() => fetchAnalyses(false), 5000);
  }, [logs, fetchAnalyses]);

  useEffect(() => () => {
    if (analyzeDebounceRef.current) window.clearTimeout(analyzeDebounceRef.current);
  }, []);

  const handleCreatePatternIssue = async (analysis: PatternAnalysis) => {
    setCreatingFor(analysis.pattern_id);
    try {
      const result = await api.createIssue(
        analysis.github_issue_title,
        analysis.github_issue_body,
        analysis.github_issue_labels.length > 0
          ? analysis.github_issue_labels
          : ['bug', 'ai-oncall', `severity-${analysis.severity.toLowerCase()}`],
        analysis.actionable_fixes.map(f => f.description),
      );
      setIssueResult(result);
    } catch (e) {
      console.error('Create issue failed:', e);
    } finally {
      setCreatingFor(null);
    }
  };

  // Sort analyses by severity (P0 → P1 → P2 → P3), then by count desc
  const sortedAnalyses = useMemo(
    () => [...analyses].sort((a, b) => {
      const sa = SEVERITY_RANK[a.severity] ?? 9;
      const sb = SEVERITY_RANK[b.severity] ?? 9;
      if (sa !== sb) return sa - sb;
      return b.count - a.count;
    }),
    [analyses],
  );

  const TABS: { id: OncallTab; label: string }[] = [
    { id: 'patterns', label: 'Error Patterns' },
    { id: 'timeline', label: 'Incident Timeline' },
    { id: 'runbooks', label: 'Runbooks' },
  ];

  return (
    <div className="min-h-screen bg-base flex flex-col">
      {/* Header */}
      <header className="border-b border-line bg-base/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-white" />
            </div>
            <h1 className="text-base font-semibold text-ink tracking-tight">LogLens</h1>
            <span className="text-xs text-ink-subtle">AI On-Call</span>
            <div className={`flex items-center gap-1.5 text-xs ml-2 ${healthy ? 'text-ink-muted' : 'text-sev-p0'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-accent live-dot' : 'bg-sev-p0'}`} />
              <span>{healthy ? 'Connected' : 'Disconnected'}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="http://localhost:5174"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost text-xs gap-1.5"
              title="Open the target service to trigger errors"
            >
              <ExternalLink size={12} />
              Target service
            </a>
            <button
              onClick={() => fetchAnalyses(true)}
              disabled={analysesLoading}
              className="btn btn-primary text-xs gap-1.5"
              title="Re-run per-pattern analysis"
            >
              <Sparkles size={12} />
              {analysesLoading ? 'Analyzing…' : 'Analyze'}
            </button>
            <div className="w-px h-6 bg-line mx-1" />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-5 space-y-4">
        {/* Service health hero */}
        <HealthDashboard summary={healthSummary} loading={!healthSummary} />

        {/* Two-column: live logs (left) | two stacked charts (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ height: '60vh' }}>
          <LogPanel logs={logs} loading={logsLoading} />
          <div className="grid grid-rows-2 gap-4 min-h-0">
            <ErrorRateChart series={severitySeries} />
            <SeverityBreakdownChart series={severitySeries} />
          </div>
        </div>

        {/* Per-pattern analysis cards */}
        <section className="card">
          <div className="flex items-center justify-between px-4 py-3 border-b border-line">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-accent" />
              <h2 className="text-sm font-medium text-ink">Pattern analyses</h2>
              <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">
                sorted by severity
              </span>
              {analysesIsMock && (
                <span
                  className="text-[10px] uppercase tracking-wider text-sev-p2 bg-sev-p2bg px-1.5 py-0.5 rounded cursor-help"
                  title={analysesMockReason || 'AI provider unavailable — showing deterministic mock analyses.'}
                >
                  mock
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-subtle tabular-nums">
                {sortedAnalyses.length} pattern{sortedAnalyses.length === 1 ? '' : 's'}
              </span>
              <button
                onClick={() => fetchAnalyses(true)}
                disabled={analysesLoading}
                className="btn btn-ghost p-1.5"
                title="Re-analyze"
                aria-label="Re-analyze"
              >
                <RefreshCw size={13} className={analysesLoading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>
          <div className="p-4 space-y-2 max-h-[70vh] overflow-y-auto">
            {analysesLoading && analyses.length === 0 ? (
              <div className="text-sm text-ink-subtle py-6 text-center">Analyzing patterns…</div>
            ) : sortedAnalyses.length === 0 ? (
              <div className="text-sm text-ink-subtle py-6 text-center">
                No error patterns detected yet. Trigger one from the 
                <a
                  href="http://localhost:5174"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:text-accent-hover underline"
                >
                  target service
                </a>.
              </div>
            ) : (
              sortedAnalyses.map((a, idx) => (
                <PatternAnalysisCard
                  key={a.pattern_id}
                  analysis={a}
                  onCreateIssue={handleCreatePatternIssue}
                  creating={creatingFor === a.pattern_id}
                  defaultExpanded={idx === 0}
                />
              ))
            )}
          </div>
        </section>

        {/* Oncall Dashboard */}
        <div className="card">
          <div className="flex items-center justify-between px-4 py-3 border-b border-line">
            <div className="flex items-center gap-1">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setOncallTab(tab.id)}
                  className={`text-sm font-medium px-3 py-1 rounded-md transition-colors ${
                    oncallTab === tab.id
                      ? 'text-accent bg-accent-soft'
                      : 'text-ink-muted hover:text-ink hover:bg-subtle'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchOncallData(oncallTab)}
              className="btn btn-ghost p-1.5"
              title="Refresh"
              aria-label="Refresh"
            >
              <RefreshCw size={13} />
            </button>
          </div>
          <div className="p-4 max-h-[42vh] overflow-y-auto">
            {oncallTab === 'patterns' && (
              <PatternDetection patterns={patterns} totalErrors={totalErrors} loading={oncallLoading} />
            )}
            {oncallTab === 'timeline' && (
              <IncidentTimeline incidents={incidents} loading={oncallLoading} />
            )}
            {oncallTab === 'runbooks' && (
              <RunbookSuggestions runbooks={runbooks} loading={oncallLoading} />
            )}
          </div>
        </div>
      </main>

      {/* GitHub Issue Modal */}
      <GitHubIssueModal result={issueResult} onClose={() => setIssueResult(null)} />

      {/* Chat drawer */}
      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />

      {/* Floating chat toggle */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-accent hover:bg-accent-hover text-white shadow-lg shadow-black/10 transition-colors"
          aria-label="Open AI chat"
        >
          <span className="w-2 h-2 rounded-full bg-white live-dot" />
          <span className="text-sm font-medium">Ask LogLens</span>
        </button>
      )}
    </div>
  );
}
