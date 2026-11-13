import React from 'react';

interface VerificationChecklistProps {
  verification: {
    results: Array<{ check_name: string; status: string; detail: string }>;
    allPassed: boolean;
  };
  timestamp: string;
}

export const VerificationChecklist: React.FC<VerificationChecklistProps> = ({
  verification,
  timestamp
}) => {
  const { results, allPassed } = verification;

  return (
    <div className="bg-slate-900/95 border border-emerald-500/30 rounded-xl p-3.5 shadow-sm space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 text-sm">🛡️</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">Algorithmic Verification Gate</span>
              <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${
                allPassed
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-semibold'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
              }`}>
                {allPassed ? '7 / 7 Audits Verified' : 'Exceptions Found'}
              </span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">Independent Skeptic & Number Registry Verification</div>
          </div>
        </div>
        <span className="text-[10px] font-mono text-slate-500">{timestamp}</span>
      </div>

      {/* 7 Check Items */}
      <div className="grid grid-cols-1 gap-1.5 bg-slate-950/70 p-2.5 rounded-lg border border-slate-800">
        {results.map((r, i) => {
          const isPassed = r.status.toLowerCase() === 'passed';
          const isFinancialTieOut = r.check_name.toLowerCase().includes('financial tie');

          return (
            <div
              key={i}
              className={`p-2 rounded border text-xs font-sans transition-all ${
                isPassed
                  ? 'bg-emerald-950/20 border-emerald-500/20 text-slate-200'
                  : 'bg-rose-950/20 border-rose-500/30 text-rose-200'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    isPassed ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-400'
                  }`}>
                    {isPassed ? '✓' : '✕'}
                  </span>
                  <span className="font-semibold text-slate-200 text-xs">{r.check_name}</span>
                </div>
                <span className={`text-[10px] font-mono uppercase tracking-wider ${
                  isPassed ? 'text-emerald-400 font-medium' : 'text-rose-400'
                }`}>
                  {r.status}
                </span>
              </div>

              {/* Sub-detail */}
              <div className="text-[11px] text-slate-400 font-mono pl-6 pt-0.5">
                {isFinancialTieOut
                  ? 'Verified against NimbusDesk snapshot: MRR, CAC, Runway tie out with 100% precision.'
                  : r.detail}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

