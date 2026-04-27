import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import { Layers } from 'lucide-react';
import type { SeveritySeriesResponse } from '../types';

interface Props {
  series: SeveritySeriesResponse | null;
}

function readColor(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!v) return fallback;
  return v.includes(' ') ? `rgb(${v})` : v;
}

export default function SeverityBreakdownChart({ series }: Props) {
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
  void theme;

  const grid = readColor('--color-line', '#E5DFD0');
  const ink = readColor('--color-ink', '#1F1E1D');
  const subtle = readColor('--color-ink-subtle', '#8C8782');
  const surface = readColor('--color-surface', '#FFFFFF');
  const p0 = readColor('--color-sev-p0', '#C0392B');
  const p1 = readColor('--color-sev-p1', '#D97757');
  const p2 = readColor('--color-sev-p2', '#B89139');
  const p3 = readColor('--color-sev-p3', '#5C7DB5');

  const data = (series?.buckets || []).map((b) => ({
    label: b.minute_offset === 0 ? 'now' : `${b.minute_offset}m`,
    P0: b.P0, P1: b.P1, P2: b.P2, P3: b.P3,
  }));

  const counts = data.reduce(
    (acc, d) => {
      acc.P0 += d.P0; acc.P1 += d.P1; acc.P2 += d.P2; acc.P3 += d.P3;
      return acc;
    },
    { P0: 0, P1: 0, P2: 0, P3: 0 },
  );

  return (
    <div className="card flex flex-col h-full min-h-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          <Layers size={15} className="text-accent" />
          <h2 className="text-sm font-medium text-ink">Severity breakdown</h2>
          <span className="text-[10px] uppercase tracking-wider text-ink-subtle bg-subtle px-1.5 py-0.5 rounded">
            per minute
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-ink-subtle tabular-nums">
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm" style={{ background: p0 }} /> P0 {counts.P0}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm" style={{ background: p1 }} /> P1 {counts.P1}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm" style={{ background: p2 }} /> P2 {counts.P2}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm" style={{ background: p3 }} /> P3 {counts.P3}
          </span>
        </div>
      </div>
      <div className="flex-1 min-h-0 px-2 py-2">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-ink-subtle text-sm">
            Waiting for data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
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
                cursor={{ fill: grid, fillOpacity: 0.3 }}
                contentStyle={{
                  background: surface,
                  border: `1px solid ${grid}`,
                  borderRadius: 6,
                  fontSize: 12,
                  color: ink,
                }}
                labelStyle={{ color: subtle, fontSize: 11 }}
              />
              <Legend wrapperStyle={{ display: 'none' }} />
              <Bar dataKey="P0" stackId="sev" fill={p0} radius={[0, 0, 0, 0]} />
              <Bar dataKey="P1" stackId="sev" fill={p1} radius={[0, 0, 0, 0]} />
              <Bar dataKey="P2" stackId="sev" fill={p2} radius={[0, 0, 0, 0]} />
              <Bar dataKey="P3" stackId="sev" fill={p3} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
