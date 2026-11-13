import React from 'react';
import { getAgentMeta } from '../../../orchestration/agentMeta';

interface ConflictCardProps {
  conflict: {
    id: string;
    type: string;
    disputed_item: string;
    agents: string[];
    verdict?: string;
    method?: string;
    delta?: number;
  };
  timestamp: string;
}

export const ConflictCard: React.FC<ConflictCardProps> = ({ conflict, timestamp }) => {
  const agentA = conflict.agents[0] ?? 'CFO';
  const agentB = conflict.agents[1] ?? 'Customer';

  const metaA = getAgentMeta(agentA.toLowerCase());
  const metaB = getAgentMeta(agentB.toLowerCase());

  const isResolved = Boolean(conflict.verdict);

  return (
    <div className="relative bg-slate-900/95 border-2 border-amber-500/30 rounded-xl p-3.5 shadow-md space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-amber-400 text-xs">⚔️</span>
          <span className="text-xs font-semibold text-amber-200 uppercase tracking-wider font-mono">
            Executive Conflict Arena
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${
            isResolved
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              : 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
          }`}>
            {isResolved ? 'Resolved by Simulation' : 'Active Disagreement'}
          </span>
          <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
        </div>
      </div>

      {/* Duel Visual: Agent A vs Agent B */}
      <div className="flex items-center justify-between bg-slate-950/80 rounded-lg p-2.5 border border-slate-800">
        <div className="flex items-center gap-2">
          <img
            src={metaA.avatar}
            alt={metaA.name}
            className="w-7 h-7 rounded-full border border-slate-700 bg-slate-900 p-0.5"
          />
          <div>
            <div className="text-xs font-semibold text-slate-200">{metaA.name}</div>
            <div className="text-[9px] text-slate-400 font-mono">{metaA.role}</div>
          </div>
        </div>

        <div className="flex flex-col items-center px-2">
          <span className="text-[10px] font-mono font-bold text-amber-400/80 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-500/30">
            VS
          </span>
        </div>

        <div className="flex items-center gap-2 flex-row-reverse text-right">
          <img
            src={metaB.avatar}
            alt={metaB.name}
            className="w-7 h-7 rounded-full border border-slate-700 bg-slate-900 p-0.5"
          />
          <div>
            <div className="text-xs font-semibold text-slate-200">{metaB.name}</div>
            <div className="text-[9px] text-slate-400 font-mono">{metaB.role}</div>
          </div>
        </div>
      </div>

      {/* Disputed item */}
      <div className="text-xs text-slate-300">
        <span className="text-slate-400 font-mono text-[10px]">Disputed Item: </span>
        <strong className="text-slate-200 font-semibold">{conflict.disputed_item}</strong>
      </div>

      {/* Resolution status / details */}
      {isResolved ? (
        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-lg p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-emerald-300 font-semibold">
            <span>✓</span>
            <span>Verdict: {conflict.verdict}</span>
          </div>
          {conflict.method && (
            <div className="text-[10px] font-mono text-slate-400">
              Resolution Method: {conflict.method}
            </div>
          )}
          {conflict.delta !== undefined && (
            <div className="text-[10px] font-mono text-emerald-400">
              Simulated 12mo Variance Impact: {conflict.delta > 0 ? `+${conflict.delta}` : `${conflict.delta}`}
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-[11px] font-mono text-amber-300/90 bg-amber-950/20 border border-amber-500/20 rounded-lg p-2">
          <div className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          <span>Simulating isolated scenarios to empirically break executive tie...</span>
        </div>
      )}
    </div>
  );
};

