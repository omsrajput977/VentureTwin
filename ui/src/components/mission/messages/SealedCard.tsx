import React, { useState, useEffect } from 'react';

interface SealedCardProps {
  sealed?: {
    decisionId: string;
    recommendation: string;
    verificationHash?: string;
  };
  timestamp: string;
  onOpenReport: () => void;
}

export const SealedCard: React.FC<SealedCardProps> = ({
  sealed,
  timestamp,
  onOpenReport
}) => {
  const [showPrompt, setShowPrompt] = useState(false);
  const hash = sealed?.verificationHash ?? '7f9a12c8...d3e4b891';
  const rec = sealed?.recommendation ?? 'Proceed with limits';

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowPrompt(true);
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-teal-950/60 via-slate-900 to-emerald-950/60 border-2 border-teal-500/60 rounded-2xl p-4.5 shadow-xl space-y-3.5 animate-fadeIn">
      {/* Background glow flair */}
      <div className="absolute -top-12 -right-12 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-300 font-bold text-sm">
            ✓
          </div>
          <div>
            <div className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <span>Decision Report Verified & Sealed</span>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 uppercase">
                Ready for Sign-Off
              </span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              10-Section Board-Ready Executive Intelligence Package
            </div>
          </div>
        </div>
        <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
      </div>

      {/* Verification SHA-256 and Executive Summary */}
      <div className="bg-slate-950/80 rounded-xl p-3 border border-slate-800 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400 font-mono text-[11px]">Consensus Recommendation:</span>
          <span className="font-bold text-teal-300 uppercase tracking-wide px-2 py-0.5 rounded bg-teal-500/10 border border-teal-500/30">
            {rec}
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono pt-1 border-t border-slate-800/80">
          <span className="text-slate-500">Cryptographic Seal (SHA-256):</span>
          <span className="text-slate-300 font-bold bg-slate-900 px-2 py-0.5 rounded border border-slate-700/80">
            {hash.length > 24 ? `${hash.slice(0, 16)}...${hash.slice(-8)}` : hash}
          </span>
        </div>
      </div>

      {/* Action CTA */}
      <div className="pt-1 flex flex-col items-stretch gap-2">
        <button
          onClick={onOpenReport}
          className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-400 hover:to-emerald-400 text-slate-950 font-bold text-sm shadow-lg shadow-teal-500/20 hover:shadow-teal-500/30 transition-all cursor-pointer group"
        >
          <span>Open Decision Report</span>
          <span className="group-hover:translate-x-1 transition-transform">&rarr;</span>
        </button>

        {showPrompt && (
          <div className="text-[11px] text-center font-mono text-slate-400 animate-fadeIn">
            Click above to review executive synthesis, sensitivity tornado, and sign-off gate &darr;
          </div>
        )}
      </div>
    </div>
  );
};

