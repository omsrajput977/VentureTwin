import React from 'react';
import { EventItem } from '../api';

interface Props {
  events: EventItem[];
}

export const EventFeed: React.FC<Props> = ({ events }) => {
  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col h-[340px]">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-semibold text-white">Live Event Stream</h3>
          <p className="text-xs text-slate-400">Real-time SSE event bus telemetry</p>
        </div>
        <span className="text-xs font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-300">
          {events.length} events
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pt-3 font-mono text-xs pr-1">
        {events.length === 0 ? (
          <div className="text-slate-500 text-center py-10 font-sans">Awaiting orchestrator events...</div>
        ) : (
          events.map((e, idx) => {
            const timeStr = new Date(e.ts).toLocaleTimeString();
            let color = 'text-slate-300';
            if (e.type.includes('failed')) color = 'text-rose-400';
            if (e.type.includes('recovery')) color = 'text-amber-400';
            if (e.type.includes('conflict')) color = 'text-purple-400';
            if (e.type.includes('ready') || e.type.includes('passed')) color = 'text-emerald-400';

            return (
              <div key={idx} className="p-2 rounded bg-slate-950/60 border border-slate-800/60 flex items-start gap-2">
                <span className="text-slate-500 text-[10px] shrink-0 mt-0.5">{timeStr}</span>
                <span className="px-1.5 py-0.2 text-[10px] bg-slate-800 rounded font-semibold text-brand-300 shrink-0 uppercase">
                  {e.agent}
                </span>
                <span className={`text-[11px] font-medium ${color}`}>
                  {e.type}
                </span>
                {e.payload?.task_id && (
                  <span className="text-slate-500 text-[10px] shrink-0">[{e.payload.task_id}]</span>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
