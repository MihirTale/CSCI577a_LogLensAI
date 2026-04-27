import type {
  LogsResponse, AnalysisResult, GitHubIssueResponse,
  PatternsResponse, TimelineResponse, RunbooksResponse,
  HealthSummary, ChatMessage,
  SeveritySeriesResponse, PatternAnalysesResponse,
} from './types';

export const BASE = 'http://localhost:8001';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  getLatestLogs: (n = 50) => request<LogsResponse>(`/logs/latest?n=${n}`),
  simulateError: (errorType?: string) =>
    request<{ success: boolean; message: string }>('/simulate-error', {
      method: 'POST',
      body: JSON.stringify({ error_type: errorType || null }),
    }),
  analyze: (logLines = 50) =>
    request<AnalysisResult>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ log_lines: logLines }),
    }),
  getLatestAnalysis: () => request<AnalysisResult | null>('/analysis/latest'),
  createIssue: (title: string, body: string, labels: string[], selectedFixes: string[]) =>
    request<GitHubIssueResponse>('/issues/create', {
      method: 'POST',
      body: JSON.stringify({ title, body, labels, selected_fixes: selectedFixes }),
    }),
  getPatterns: () => request<PatternsResponse>('/oncall/patterns'),
  getTimeline: () => request<TimelineResponse>('/oncall/timeline'),
  getRunbooks: () => request<RunbooksResponse>('/oncall/runbooks'),
  getHealthSummary: () => request<HealthSummary>('/oncall/health-summary'),
  getSeveritySeries: (windowMinutes = 60) =>
    request<SeveritySeriesResponse>(`/oncall/severity-series?window_minutes=${windowMinutes}`),
  analyzePatterns: (force = false) =>
    request<PatternAnalysesResponse>(`/oncall/analyze-patterns${force ? '?force=true' : ''}`, {
      method: 'POST',
    }),
};

/**
 * Stream a chat response. Calls onToken for each text delta and onDone when finished.
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export function streamChat(
  question: string,
  history: ChatMessage[],
  onToken: (delta: string) => void,
  onDone: () => void,
  onError?: (e: unknown) => void,
): AbortController {
  const controller = new AbortController();
  (async () => {
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`Chat error: ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // Parse SSE events: lines beginning with "data: ", separated by blank lines
        const events = buf.split('\n\n');
        buf = events.pop() || '';
        for (const ev of events) {
          for (const line of ev.split('\n')) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') { onDone(); return; }
              try {
                const obj = JSON.parse(data);
                if (typeof obj.delta === 'string') onToken(obj.delta);
              } catch {
                // ignore malformed
              }
            }
          }
        }
      }
      onDone();
    } catch (e) {
      if ((e as DOMException).name !== 'AbortError') onError?.(e);
    }
  })();
  return controller;
}
