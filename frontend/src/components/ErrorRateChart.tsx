import { useEffect, useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import type { SeveritySeriesResponse } from '../types';

interface Props {
  series: SeveritySeriesResponse | null;
}

function readColor(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!v) return fallback;
  // Vars are stored as space-separated RGB triples for Tailwind's rgb(var(...)) usage
  return v.includes(' ') ? `rgb(${v})` : v;
}

export default function ErrorRateChart({ series }: Props) {
  // Re-read CSS vars when the theme toggles
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  useEffect(() => {
    const update = () => {
      setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // theme is reused via dependency below to force a re-read on toggle
  void theme;
  const accent = readColor('--color-accent', '#D97757');
  const grid = readColor('--color-line', '#E5DFD0');
  const ink = readColor('--color-ink', '#1F1E1D');
  const subtle = readColor('--color-ink-subtle', '#8C8782');
  const surface = readColor('--color-surface', '#FFFFFF');

  const data = (series?.buckets || []).map((b) => ({
    label: b.minute_offset === 0 ? 'now' : `${b.minute_offset}m`,
    total: b.total,
  }));

  const total = data.reduce((s, d) => s + d.total, 0);
  const max = Math.max(0, ...data.map((d) => d.total));

  return (
    <div className="card flex flex-col h-full min-h-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          <TrendingUp size={15} className="text-accent" />
          <h2 className="text-sm font-medium text-ink">Error rate</h2>
          <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">
            last {series?.window_minutes ?? 60} min
          </span>
        </div>
        <span className="text-xs text-ink-subtle tabular-nums">
          {total} events · peak {max}/min
        </span>
      </div>
      <div className="flex-1 min-h-0 px-2 py-2">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ink-subtle text-sm">
            Waiting for data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="errorRateFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={accent} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={grid} strokeDasharray="2 4" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: subtle, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: grid }}
                interval="preserveStartEnd"
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: subtle, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: grid }}
                width={28}
              />
              <Tooltip
                cursor={{ stroke: accent, strokeOpacity: 0.25 }}
                contentStyle={{
                  background: surface,
                  border: `1px solid ${grid}`,
                  borderRadius: 6,
                  fontSize: 12,
                  color: ink,
                }}
                labelStyle={{ color: subtle, fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke={accent}
                strokeWidth={1.75}
                fill="url(#errorRateFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
