import React from 'react';
import { SimulationCell } from '../../../orchestration/useOrchestrationModel';

interface SimulationMatrixProps {
  matrix: SimulationCell[];
  completedCount: number;
}

const STRATEGIES = ['A', 'B', 'C'];
const SCENARIOS = [
  'Conservative',
  'Expected',
  'Optimistic',
  'Stress Infra',
  'Stress Conv',
  'Stress Churn'
];

export const SimulationMatrix: React.FC<SimulationMatrixProps> = ({
  matrix,
  completedCount
}) => {
  const total = matrix.length > 0 ? matrix.length : 18;
  const isAllDone = completedCount >= total;

  return (
    <div className="bg-slate-900/95 border border-teal-500/30 rounded-xl p-3.5 shadow-sm space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-teal-400 text-sm">🎲</span>
          <div>
            <span className="text-xs font-semibold text-slate-200">Simulation Engine Matrix</span>
            <div className="text-[10px] text-slate-400 font-mono">12-Month Monte Carlo & Discrete Solvers</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
          <span className="text-[10px] font-mono font-bold text-teal-400">
            {completedCount} / {total}
          </span>
          <span className="text-[9px] text-slate-500 font-mono">evaluated</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
        <div
          className={`h-full transition-all duration-300 rounded-full ${
            isAllDone ? 'bg-emerald-400' : 'bg-gradient-to-r from-teal-500 to-emerald-400'
          }`}
          style={{ width: `${Math.min(100, (completedCount / total) * 100)}%` }}
        />
      </div>

      {/* 3x6 Grid */}
      <div className="bg-slate-950/80 rounded-lg p-2.5 border border-slate-800/80 overflow-x-auto">
        <table className="w-full text-center border-collapse">
          <thead>
            <tr>
              <th className="text-[9px] font-mono text-slate-500 text-left pb-1.5 pl-1 w-10">Strat</th>
              {SCENARIOS.map((scen, idx) => (
                <th key={idx} className="text-[9px] font-mono text-slate-400 pb-1.5 px-1 truncate max-w-[55px]">
                  {scen}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {STRATEGIES.map((strat) => (
              <tr key={strat} className="border-t border-slate-900">
                <td className="text-[10px] font-mono font-bold text-slate-400 text-left py-1 pl-1">
                  {strat}
                </td>
                {SCENARIOS.map((scen, sIdx) => {
                  const cell = matrix.find(
                    (c) => c.strategy === strat && (c.scenario === scen || (sIdx < 3 && c.scenario.includes(scen.split(' ')[0])))
                  );
                  const isDone = cell?.completed ?? false;

                  return (
                    <td key={sIdx} className="py-1 px-1">
                      <div
                        className={`h-6 rounded border transition-all duration-200 flex items-center justify-center font-mono text-[9px] ${
                          isDone
                            ? 'bg-teal-500/20 border-teal-500/60 text-teal-300 shadow-[0_0_8px_rgba(20,184,166,0.25)] font-bold'
                            : 'bg-slate-900/60 border-slate-800/60 text-slate-600'
                        }`}
                        title={`${strat} - ${scen}: ${isDone ? 'Completed' : 'Pending'}`}
                      >
                        {isDone ? '✓' : '·'}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

