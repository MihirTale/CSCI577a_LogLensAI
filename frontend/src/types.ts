export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  source?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  total: number;
}

export interface ActionableFix {
  id: string;
  description: string;
  code_snippet?: string;
  file_path?: string;
  priority: string;
}

export interface SuspectCommit {
  sha: string;
  short_sha: string;
  message: string;
  author: string;
  date: string;
  html_url: string;
  score: number;
  reasoning: string;
}

export interface AnalysisResult {
  title: string;
  severity: string;
  root_cause: string;
  evidence: string[];
  actionable_fixes: ActionableFix[];
  recommended_next_steps: string[];
  confidence: number;
  user_impact?: string;
  github_issue_title: string;
  github_issue_body: string;
  github_issue_labels: string[];
  suspect_commit?: SuspectCommit;
  analyzed_at: string;
  is_mock: boolean;
  ai_provider?: string;
  ai_model?: string;
}

export interface HealthSummary {
  error_rate_per_min: number;
  error_rate_series: number[];        // one bucket per minute, oldest → newest
  window_minutes: number;
  active_incidents: number;
  severity_counts: { P0: number; P1: number; P2: number; P3: number };
  top_error?: { message_template: string; count: number; severity: string } | null;
  mttr_minutes: number | null;
  status: 'healthy' | 'degraded' | 'down';
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface SeverityBucket {
  minute_offset: number;
  P0: number;
  P1: number;
  P2: number;
  P3: number;
  total: number;
}

export interface SeveritySeriesResponse {
  buckets: SeverityBucket[];
  window_minutes: number;
}

export interface PatternAnalysis {
  pattern_id: string;
  title: string;
  severity: string;
  count: number;
  message_template: string;
  first_seen: string;
  last_seen: string;
  root_cause: string;
  user_impact?: string;
  evidence: string[];
  actionable_fixes: ActionableFix[];
  recommended_next_steps: string[];
  confidence: number;
  github_issue_title: string;
  github_issue_body: string;
  github_issue_labels: string[];
  is_mock: boolean;
}

export interface PatternAnalysesResponse {
  analyses: PatternAnalysis[];
  total_patterns: number;
  is_mock: boolean;
  mock_reason?: string | null;
  ai_provider?: string;
  ai_model?: string;
}

export interface GitHubIssueResponse {
  success: boolean;
  issue_url?: string;
  issue_number?: number;
  preview: boolean;
  payload?: Record<string, unknown>;
  message: string;
}

export interface ErrorPattern {
  pattern_id: string;
  message_template: string;
  count: number;
  first_seen: string;
  last_seen: string;
  severity: string;
  sample_logs: string[];
}

export interface PatternsResponse {
  patterns: ErrorPattern[];
  total_errors: number;
}

export interface IncidentEvent {
  timestamp: string;
  level: string;
  message: string;
  source?: string;
}

export interface Incident {
  incident_id: string;
  started_at: string;
  ended_at?: string;
  events: IncidentEvent[];
  severity: string;
  status: string;
}

export interface TimelineResponse {
  incidents: Incident[];
}

export interface RunbookStep {
  step: number;
  action: string;
  command?: string;
}

export interface Runbook {
  error_pattern: string;
  title: string;
  severity: string;
  steps: RunbookStep[];
}

export interface RunbooksResponse {
  runbooks: Runbook[];
}
