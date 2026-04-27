import { Clock, AlertTriangle } from 'lucide-react';
import type { Incident } from '../types';

interface Props {
  incidents: Incident[];
  loading: boolean;
}

export default function IncidentTimeline({ incidents, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-ink-subtle text-sm">
        <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin mr-2" />
        Loading timeline…
      </div>
    );
  }

  if (incidents.length === 0) {
    return (
      <div className="text-center py-8 text-ink-subtle text-sm">
        No incidents detected in recent logs.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {incidents.map((incident) => (
        <div key={incident.incident_id} className="bg-base border border-line rounded-md p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={13} className={
                incident.severity === 'P0' ? 'text-sev-p0' :
                incident.severity === 'P1' ? 'text-sev-p1' : 'text-sev-p2'
              } />
              <span className="text-sm font-medium text-ink">{incident.incident_id}</span>
              <span className={`severity-badge severity-${incident.severity}`}>
                {incident.severity}
              </span>
            </div>
            <span className={`text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded ${
              incident.status === 'active' ? 'bg-sev-p0bg text-sev-p0' : 'bg-sev-p3bg text-sev-p3'
            }`}>
              {incident.status}
            </span>
          </div>
          <div className="flex items-center gap-1 text-xs text-ink-subtle mb-2 tabular-nums">
            <Clock size={10} />
            <span>{incident.started_at}</span>
            {incident.ended_at && incident.ended_at !== incident.started_at && (
              <span>→ {incident.ended_at}</span>
            )}
          </div>
          <div className="space-y-1 ml-3 border-l border-line pl-3">
            {incident.events.slice(0, 5).map((event, i) => (
              <div key={i} className="text-xs">
                <span className={`font-medium ${
                  event.level === 'ERROR' ? 'text-sev-p0' : 'text-sev-p2'
                }`}>{event.level}</span>
                <span className="text-ink-muted ml-2">{event.message.slice(0, 100)}</span>
              </div>
            ))}
            {incident.events.length > 5 && (
              <div className="text-xs text-ink-subtle">
                +{incident.events.length - 5} more events
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
