import React, { useState } from 'react';
import { approveDecision } from '../api';

interface Props {
  report: any;
  decisionId: string;
  onApprovalDone: () => void;
}

export const DecisionReportView: React.FC<Props> = ({ report, decisionId, onApprovalDone }) => {
  const [approvalNotes, setApprovalNotes] = useState('');
  const [approvalStatus, setApprovalStatus] = useState<string | null>(null);

  if (!report) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center text-slate-500">
        No report available yet. Complete a workflow run to review the consolidated report.
      </div>
    );
  }

  const handleAction = async (action: 'approve' | 'reject' | 'request_changes') => {
    try {
      await approveDecision(decisionId, action, approvalNotes);
      setApprovalStatus(`Decision recorded as "${action}". Visible in Calibration & History.`);
      onApprovalDone();
    } catch (e: any) {
      alert(`Approval error: ${e.message}`);
    }
  };

  const sec = report.sections || {};
  const currentPos = sec.current_position || {};
  const strategies = sec.strategies_compared || [];
  const scenarios = sec.scenario_table || [];
  const conflicts = sec.conflicts_resolution || [];
  const tornado = sec.tornado_sensitivity || [];
  const flip = sec.flip_points || {};
  const ledger = sec.assumption_ledger || [];
  const verifs = sec.verification_summary || [];
  const risks = sec.risks_and_triggers || [];
  const conf = sec.confidence_assessment || { level: report.confidence, score: 0.8, reasons: [] };

  return (
    <div className="space-y-6">
      {/* 1. Header & Recommendation */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs uppercase font-mono tracking-wider text-slate-400">Consolidated Report</span>
              <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full font-semibold">
                Status: Verified
              </span>
            </div>
            <h2 className="text-2xl font-bold text-white mt-2">{report.recommendation}</h2>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-400 font-medium">Confidence Rating</div>
            <div className={`text-xl font-bold ${conf.level === 'High' ? 'text-emerald-400' : conf.level === 'Medium' ? 'text-amber-400' : 'text-rose-400'}`}>
              {conf.level} ({((conf.score || 0.75) * 100).toFixed(0)}%)
            </div>
          </div>
        </div>

        <div className="pt-4 text-sm text-slate-300 leading-relaxed bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
          {sec.executive_summary}
        </div>

        {conf.reasons && conf.reasons.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-800/60">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Confidence Assessment Drivers:</div>
            <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
              {conf.reasons.map((r: string, idx: number) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 2. Strategies Compared */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Strategy Ranking & Feasibility</h3>
        <p className="text-xs text-slate-400 mb-4">Evaluated against company runway constraints and 12-month net contribution</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {strategies.map((strat: any) => (
            <div
              key={strat.strategy}
              className={`p-4 rounded-xl border ${
                strat.rank === 1
                  ? 'bg-slate-950 border-brand-500/50 shadow-brand-500/10 shadow-lg'
                  : 'bg-slate-950/60 border-slate-800'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Rank #{strat.rank}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${strat.is_feasible ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                  {strat.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}
                </span>
              </div>
              <div className="text-sm font-bold text-white capitalize">{strat.strategy.replace(/_/g, ' ')}</div>
              <div className="mt-3 space-y-1 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>12mo Net Contribution:</span>
                  <span className="font-mono text-white">${strat.net_contribution_12.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>12mo Cash Runway:</span>
                  <span className="font-mono text-emerald-400">{strat.runway_months_12.toFixed(1)} mo</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>12mo Gross Margin:</span>
                  <span className="font-mono text-white">{(strat.gross_margin_12 * 100).toFixed(1)}%</span>
                </div>
              </div>
              <div className="text-[11px] text-slate-500 mt-3 pt-2 border-t border-slate-800/80">
                {strat.feasibility_reason}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Scenario Matrix & Sensitivity Tornado */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scenario Table */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-bold text-white mb-1">Scenario Outcome Matrix</h3>
          <p className="text-xs text-slate-400 mb-4">Outcomes across Conservative, Expected, and Optimistic parameter sets</p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-2 font-semibold">Strategy</th>
                  <th className="p-2 font-semibold">Scenario</th>
                  <th className="p-2 font-semibold text-right">Net 12mo</th>
                  <th className="p-2 font-semibold text-right">Runway</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {scenarios.map((row: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="p-2 font-sans font-medium text-slate-300">{row.strategy.split('_')[0]}</td>
                    <td className="p-2 text-slate-400 capitalize">{row.scenario}</td>
                    <td className="p-2 text-right text-white">${row.net_contribution_12.toLocaleString()}</td>
                    <td className="p-2 text-right text-emerald-400">{row.runway_months_12.toFixed(1)}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Sensitivity Tornado & Flip Point */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold text-white mb-1">Sensitivity Analysis (Tornado)</h3>
            <p className="text-xs text-slate-400 mb-4">Ranked variance impact on 12-month net contribution</p>
            <div className="space-y-3">
              {tornado.map((t: any) => (
                <div key={t.assumption_name} className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-white">#{t.impact_rank} {t.assumption_name.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-brand-400">Swing: ${t.swing.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-500 font-mono">
                    <span>Low ({t.low_value}): ${t.net_contribution_at_low.toLocaleString()}</span>
                    <span>High ({t.high_value}): ${t.net_contribution_at_high.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-3 bg-brand-500/10 border border-brand-500/20 rounded-xl">
            <div className="text-xs font-bold text-brand-300 uppercase tracking-wider mb-1">Decision Flip Point</div>
            <div className="text-xs text-slate-300">
              {flip.statement || 'No crossing threshold detected in evaluated range.'}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Conflict Resolution Panel */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Empirical Conflict Resolution</h3>
        <p className="text-xs text-slate-400 mb-4">Disagreements between agents resolved through deterministic simulation runs</p>

        <div className="space-y-3">
          {conflicts.map((c: any) => (
            <div key={c.id} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded font-bold uppercase">
                    {c.type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-white font-semibold">
                    {c.agents.join(' vs ')} on {c.disputed_item}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-slate-500">
                  Simulations: {c.simulation_ids?.join(', ')}
                </span>
              </div>
              <div className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded border border-slate-800/60">
                {c.resolution}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Assumption Ledger with Provenance */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Assumption Ledger with Provenance</h3>
        <p className="text-xs text-slate-400 mb-4">Audit trail of all agent assumptions, parameter ranges, and skeptic verifications</p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="p-2.5">Assumption</th>
                <th className="p-2.5">Range (Low / Base / High)</th>
                <th className="p-2.5">Provenance</th>
                <th className="p-2.5">Proposed By</th>
                <th className="p-2.5 text-center">Skeptic Audited</th>
                <th className="p-2.5 text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {ledger.map((asm: any, idx: number) => {
                let badgeColor = 'bg-slate-800 text-slate-300';
                if (asm.provenance === 'verified_data') badgeColor = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                if (asm.provenance === 'simulated_estimate') badgeColor = 'bg-sky-500/20 text-sky-400 border border-sky-500/30';
                if (asm.provenance === 'external_research') badgeColor = 'bg-purple-500/20 text-purple-400 border border-purple-500/30';
                if (asm.provenance === 'ai_assumption') badgeColor = 'bg-amber-500/20 text-amber-400 border border-amber-500/30';

                return (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="p-2.5 font-medium text-white">{asm.name.replace(/_/g, ' ')}</td>
                    <td className="p-2.5 font-mono text-slate-300">
                      [{asm.low} / <span className="font-bold text-white">{asm.base}</span> / {asm.high}] {asm.unit}
                    </td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 text-[10px] rounded-full font-semibold ${badgeColor}`}>
                        {asm.provenance}
                      </span>
                    </td>
                    <td className="p-2.5 text-slate-400">{asm.proposed_by}</td>
                    <td className="p-2.5 text-center">
                      {asm.challenged_by_skeptic ? (
                        <span className="text-amber-400 font-bold" title="Challenged and confidence adjusted by Skeptic">Challenged</span>
                      ) : (
                        <span className="text-emerald-400">Passed</span>
                      )}
                    </td>
                    <td className="p-2.5 text-right font-mono text-slate-300">
                      {(asm.confidence * 100).toFixed(0)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. Verification Summary */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Deterministic Verification Layer</h3>
        <p className="text-xs text-slate-400 mb-4">Independent algorithmic audits of mathematics, financial tie-outs, and simulation traceability</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {verifs.map((v: any, idx: number) => {
            const isPassed = v.status === 'passed';
            return (
              <div key={idx} className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-start gap-3">
                <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase mt-0.5 ${isPassed ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>
                  {v.status}
                </span>
                <div>
                  <div className="text-xs font-semibold text-white capitalize">{v.check_name.replace(/_/g, ' ')}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{v.detail}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 7. Human-in-the-Loop Approval Gate */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Human-in-the-Loop Sign-Off Gate</h3>
        <p className="text-xs text-slate-400 mb-4">Strategic recommendations require explicit human approval before persisting as official board records</p>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Executive Notes & Context</label>
            <input
              type="text"
              value={approvalNotes}
              onChange={(e) => setApprovalNotes(e.target.value)}
              placeholder="e.g. Approved for pilot rollout in Q1 with $79 Starter guardrails..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => handleAction('approve')}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/20 transition"
            >
              Approve Recommendation
            </button>
            <button
              onClick={() => handleAction('request_changes')}
              className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition"
            >
              Request Changes
            </button>
            <button
              onClick={() => handleAction('reject')}
              className="px-5 py-2.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-600/30 rounded-xl text-xs font-semibold transition"
            >
              Reject
            </button>
          </div>

          {approvalStatus && (
            <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-xl">
              {approvalStatus}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
