import React from 'react';
import { FindingItem } from '../../../api';
import { getAgentMeta } from '../../../orchestration/agentMeta';

interface SkepticChallengeProps {
  finding?: FindingItem;
  content?: string;
  timestamp: string;
}

export const SkepticChallenge: React.FC<SkepticChallengeProps> = ({
  finding,
  content,
  timestamp
}) => {
  const meta = getAgentMeta('skeptic');
  const claimText = content || finding?.claim || 'Audited peer assumptions for optimistic bias & provenance drift.';

  return (
    <div className="relative bg-slate-900/95 border-l-4 border-l-rose-500 border border-slate-800 rounded-xl p-3.5 shadow-sm space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <img
            src={meta.avatar}
            alt="Skeptic"
            className="w-6 h-6 rounded-full border border-rose-500/40 bg-rose-950/40 p-0.5"
          />
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-rose-300">Skeptic Audit</span>
              <span className="text-[10px] text-slate-400 font-mono">({meta.role})</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
            Adversarial Challenge
          </span>
          <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
        </div>
      </div>

      {/* Audit Claim */}
      <div className="bg-rose-950/20 rounded-lg p-2.5 border border-rose-500/20">
        <div className="flex items-start gap-2">
          <span className="text-rose-400 text-sm mt-0.5">⚠️</span>
          <p className="text-xs text-rose-100 leading-relaxed font-sans font-medium">
            {claimText}
          </p>
        </div>
      </div>

      {/* Assumptions under challenge if present */}
      {finding?.assumptions && finding.assumptions.length > 0 && (
        <div className="space-y-1 pt-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
            Challenged Domain Bounds
          </div>
          <div className="grid grid-cols-1 gap-1">
            {finding.assumptions.slice(0, 3).map((a, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-[11px] font-mono bg-slate-950/80 px-2 py-1 rounded border border-slate-800"
              >
                <span className="text-slate-300 text-[10px] truncate max-w-[140px]">{a.name}</span>
                <span className="text-rose-300 font-semibold text-[10px]">
                  [{a.low} &middot; {a.base} &middot; {a.high}{a.unit ? ` ${a.unit}` : ''}]
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

