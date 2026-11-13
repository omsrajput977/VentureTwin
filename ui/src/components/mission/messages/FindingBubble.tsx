import React from 'react';
import { FindingItem } from '../../../api';
import { getAgentMeta } from '../../../orchestration/agentMeta';
import { useTypewriter } from '../useTypewriter';

interface FindingBubbleProps {
  finding: FindingItem;
  agent: string;
  timestamp: string;
  isInstant?: boolean;
  onInspect?: () => void;
}

export const FindingBubble: React.FC<FindingBubbleProps> = ({
  finding,
  agent,
  timestamp,
  isInstant = false,
  onInspect
}) => {
  const meta = getAgentMeta(agent);
  const streamedClaim = useTypewriter(finding.claim, 14, isInstant);

  // Recommendation chip styling
  const rec = (finding.recommendation || '').toLowerCase();
  let recStyle = 'bg-slate-800 text-slate-300 border-slate-700';
  let recLabel = finding.recommendation || 'Evaluated';

  if (rec.includes('proceed_with_limits') || rec.includes('limits')) {
    recStyle = 'bg-teal-500/15 text-teal-300 border-teal-500/40';
    recLabel = 'Proceed with Limits';
  } else if (rec.includes('proceed')) {
    recStyle = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
    recLabel = 'Proceed';
  } else if (rec.includes('reject')) {
    recStyle = 'bg-rose-500/15 text-rose-300 border-rose-500/40';
    recLabel = 'Reject';
  } else if (rec.includes('needs_more_info') || rec.includes('info')) {
    recStyle = 'bg-amber-500/15 text-amber-300 border-amber-500/40';
    recLabel = 'Needs More Info';
  }

  const confidencePct = Math.round((finding.confidence ?? 0.8) * 100);

  return (
    <div
      onClick={onInspect}
      className="group relative bg-slate-900/90 hover:bg-slate-850 border border-slate-800/90 hover:border-slate-700 rounded-xl p-3.5 transition-all shadow-sm cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <img
            src={meta.avatar}
            alt={meta.name}
            className="w-6 h-6 rounded-full border border-slate-700 bg-slate-800 p-0.5"
          />
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-slate-200">{meta.name}</span>
              <span className="text-[10px] text-slate-400 font-mono">({meta.role})</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
        </div>
      </div>

      {/* Rec & Confidence bar */}
      <div className="flex items-center gap-2 mb-2.5 flex-wrap">
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase tracking-wider font-semibold ${recStyle}`}>
          {recLabel}
        </span>
        <div className="flex items-center gap-1.5 bg-slate-950/60 px-2 py-0.5 rounded-md border border-slate-800/60">
          <span className="text-[10px] text-slate-400 font-mono">Conf:</span>
          <span className="text-[10px] font-mono font-bold text-teal-400">{confidencePct}%</span>
          <div className="w-10 h-1 bg-slate-800 rounded-full overflow-hidden ml-1">
            <div
              className="h-full bg-teal-400 rounded-full transition-all"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>

        {finding.recovered_via_backup && (
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-purple-500/40 bg-purple-500/10 text-purple-300">
            🛡️ Backup Telemetry
          </span>
        )}
      </div>

      {/* Claim Body */}
      <p className="text-xs text-slate-300 leading-relaxed font-sans mb-3">
        {streamedClaim}
      </p>

      {/* Key Assumptions Pills */}
      {finding.assumptions && finding.assumptions.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-slate-800/60">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center justify-between">
            <span>Model Assumptions ({finding.assumptions.length})</span>
            <span className="text-[9px] text-slate-500">bounds [low - base - high]</span>
          </div>
          <div className="grid grid-cols-1 gap-1">
            {finding.assumptions.slice(0, 3).map((a, i) => {
              const prov = a.provenance || 'ai_assumption';
              const isVerified = prov === 'verified_data';
              const isResearch = prov === 'external_research';

              const badgeColor = isVerified
                ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
                : isResearch
                ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-300';

              return (
                <div
                  key={i}
                  className="flex items-center justify-between gap-1 text-[11px] font-mono bg-slate-950/70 px-2 py-1 rounded border border-slate-800/80"
                >
                  <span className="text-slate-300 truncate font-mono text-[10px] max-w-[140px]" title={a.name}>
                    {a.name}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400 text-[10px]">
                      [{a.low} &middot; <strong className="text-slate-200">{a.base}</strong> &middot; {a.high}{a.unit ? ` ${a.unit}` : ''}]
                    </span>
                    <span className={`text-[8px] px-1 py-0.2 rounded border font-sans uppercase ${badgeColor}`}>
                      {prov.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              );
            })}
            {finding.assumptions.length > 3 && (
              <div className="text-[9px] text-slate-500 font-mono text-right pt-0.5">
                +{finding.assumptions.length - 3} more assumptions &rarr;
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

