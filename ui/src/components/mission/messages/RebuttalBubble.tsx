import React from 'react';
import { getAgentMeta } from '../../../orchestration/agentMeta';

interface RebuttalBubbleProps {
  rebuttal: {
    agent: string;
    parameter: string;
    stance: 'concede' | 'defend' | 'compromise' | string;
    updated_low?: number;
    updated_base?: number;
    updated_high?: number;
    rationale?: string;
  };
  timestamp: string;
}

export const RebuttalBubble: React.FC<RebuttalBubbleProps> = ({ rebuttal, timestamp }) => {
  const meta = getAgentMeta(rebuttal.agent);

  const stanceLower = (rebuttal.stance || '').toLowerCase();
  let stanceStyle = 'bg-slate-800 text-slate-300 border-slate-700';
  let stanceIcon = '💬';

  if (stanceLower.includes('concede')) {
    stanceStyle = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
    stanceIcon = '🤝';
  } else if (stanceLower.includes('defend')) {
    stanceStyle = 'bg-rose-500/15 text-rose-300 border-rose-500/40';
    stanceIcon = '🛡️';
  } else if (stanceLower.includes('compromise')) {
    stanceStyle = 'bg-amber-500/15 text-amber-300 border-amber-500/40';
    stanceIcon = '⚖️';
  }

  const hasUpdatedBounds =
    rebuttal.updated_base !== undefined ||
    rebuttal.updated_low !== undefined ||
    rebuttal.updated_high !== undefined;

  return (
    <div className="ml-5 border-l-2 border-teal-500/40 pl-3 py-1 space-y-1.5">
      <div className="bg-slate-900/90 border border-slate-800/90 rounded-xl p-3 shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <img
              src={meta.avatar}
              alt={meta.name}
              className="w-5 h-5 rounded-full border border-slate-700 bg-slate-800 p-0.5"
            />
            <span className="text-xs font-semibold text-slate-200">{meta.name}</span>
            <span className="text-[10px] text-slate-400 font-mono">rebuttal stance:</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase tracking-wider font-semibold flex items-center gap-1 ${stanceStyle}`}>
              <span>{stanceIcon}</span>
              <span>{rebuttal.stance}</span>
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
        </div>

        {/* Parameter Tag */}
        {rebuttal.parameter && (
          <div className="mb-2">
            <span className="text-[10px] font-mono bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-teal-300">
              parameter: {rebuttal.parameter}
            </span>
          </div>
        )}

        {/* Rationale */}
        {rebuttal.rationale && (
          <p className="text-xs text-slate-300 leading-relaxed font-sans mb-2">
            {rebuttal.rationale}
          </p>
        )}

        {/* Parameter bounds adjustment if updated */}
        {hasUpdatedBounds && (
          <div className="flex items-center gap-2 text-[10px] font-mono bg-slate-950/80 px-2.5 py-1 rounded border border-teal-500/30 text-teal-300">
            <span className="text-slate-400">Calibrated bounds:</span>
            <span className="font-semibold text-teal-200">
              [{rebuttal.updated_low ?? '—'} &middot; {rebuttal.updated_base ?? '—'} &middot; {rebuttal.updated_high ?? '—'}]
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

