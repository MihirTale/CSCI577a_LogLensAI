import { Layers, AlertOctagon, TrendingUp, Clock, Heart } from 'lucide-react';
import type { HealthSummary } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  P0: 'text-sev-p0 bg-sev-p0bg',
  P1: 'text-sev-p1 bg-sev-p1bg',
  P2: 'text-sev-p2 bg-sev-p2bg',
  P3: 'text-sev-p3 bg-sev-p3bg',
};

interface Props {
  summary: HealthSummary | null;
  loading: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  down: 'Down',
};

const STATUS_CLASS: Record<string, string> = {
  healthy: 'text-sev-p3 bg-sev-p3bg',
  degraded: 'text-sev-p2 bg-sev-p2bg',
  down: 'text-sev-p0 bg-sev-p0bg',
};

function Sparkline({ data }: { data: number[] }) {
  if (!data.length) return null;
  const w = 60;
  const h = 18;
  const max = Math.max(1, ...data);
  const step = w / Math.max(1, data.length - 1);
  const points = data
    .map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * h).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={w} height={h} className="text-accent" aria-hidden>
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Card({
  icon,
  label,
  children,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`card px-4 py-3 ${accent ? 'border-accent/40' : ''}`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-ink-subtle font-semibold mb-1.5">
        {icon}
        <span>{label}</span>
      </div>
      {children}
    </div>
  );
}

export default function HealthDashboard({ summary, loading }: Props) {
  if (!summary && loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="card px-4 py-3 h-[68px] animate-pulse">
            <div className="h-2 w-16 bg-subtle rounded mb-2" />
            <div className="h-5 w-12 bg-subtle rounded" />
          </div>
        ))}
      </div>
    );
  }
  if (!summary) return null;

  const {
    error_rate_per_min, error_rate_series, window_minutes,
    active_incidents, severity_counts, mttr_minutes, status,
  } = summary;

  const windowLabel = `last ${window_minutes} min`;
  const totalSev =
    (severity_counts?.P0 || 0) + (severity_counts?.P1 || 0) +
    (severity_counts?.P2 || 0) + (severity_counts?.P3 || 0);

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      <Card icon={<TrendingUp size={11} />} label="Error rate / min">
        <div className="flex items-end justify-between gap-2">
          <span className="text-2xl font-semibold text-ink tabular-nums leading-none">
            {error_rate_per_min.toFixed(1)}
          </span>
          <Sparkline data={error_rate_series} />
        </div>
        <div className="text-[10px] text-ink-subtle mt-1">{windowLabel}</div>
      </Card>

      <Card icon={<AlertOctagon size={11} />} label="Active incidents">
        <div className="text-2xl font-semibold text-ink tabular-nums leading-none">
          {active_incidents}
        </div>
        <div className="text-[10px] text-ink-subtle mt-1">P0 + P1 (all time)</div>
      </Card>

      <Card icon={<Layers size={11} />} label="By severity">
        <div className="grid grid-cols-4 gap-1">
          {(['P0', 'P1', 'P2', 'P3'] as const).map((sev) => (
            <div
              key={sev}
              className={`flex flex-col items-center justify-center rounded px-1 py-1 ${SEVERITY_COLORS[sev]}`}
            >
              <span className="text-[10px] font-semibold leading-none">{sev}</span>
              <span className="text-sm font-semibold tabular-nums leading-tight">
                {severity_counts?.[sev] ?? 0}
              </span>
            </div>
          ))}
        </div>
        <div className="text-[10px] text-ink-subtle mt-1">{totalSev} total · all time</div>
      </Card>

      <Card icon={<Clock size={11} />} label="MTTR">
        <div className="text-2xl font-semibold text-ink tabular-nums leading-none">
          {mttr_minutes != null ? `${mttr_minutes}m` : '—'}
        </div>
        <div className="text-[10px] text-ink-subtle mt-1">resolved incidents</div>
      </Card>

      <Card icon={<Heart size={11} />} label="Service status" accent>
        <div className={`inline-flex items-center gap-1.5 text-sm font-semibold px-2 py-0.5 rounded ${STATUS_CLASS[status] || ''}`}>
          <span className={`w-1.5 h-1.5 rounded-full bg-current ${status !== 'healthy' ? 'live-dot' : ''}`} />
          {STATUS_LABEL[status] || status}
        </div>
        <div className="text-[10px] text-ink-subtle mt-1">target service connectivity</div>
      </Card>
    </div>
  );
}
