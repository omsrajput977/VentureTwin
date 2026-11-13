import React, { useEffect, useState } from 'react';
import { fetchHistory } from '../api';

export const CalibrationView: React.FC = () => {
  const [historyData, setHistoryData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory()
      .then(data => {
        setHistoryData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading decision calibration memory...</div>;
  }

  const seeded = historyData?.seeded_decisions || [];
  const live = historyData?.live_approved_decisions || [];
  const summary = historyData?.calibration_summary || {};

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-white">Decision Calibration & Outcome Memory</h2>
              <span className="px-2.5 py-0.5 text-xs font-semibold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-full">
                Seeded Demo Data
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Comparing predicted model projections against actual historical telemetry to diagnose forecast drift</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <div className="text-xs text-slate-400">Total Evaluated Past Decisions</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.total_evaluated_past_decisions ?? 0}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">Benchmarked over 24 months</div>
          </div>
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <div className="text-xs text-slate-400">Mean Revenue Variance (MAPE)</div>
            <div className="text-2xl font-bold text-brand-400 mt-1">{summary.mean_arr_error_pct ?? 0}%</div>
            <div className="text-[11px] text-slate-500 mt-0.5">Average prediction delta</div>
          </div>
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <div className="text-xs text-slate-400">Primary Variance Driver</div>
            <div className="text-base font-bold text-amber-400 mt-1">{summary.most_common_drift_factor || 'None'}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">Most common assumption error</div>
          </div>
        </div>
      </div>

      {/* Live Reviewed Decisions (Sign-Off Records) */}
      {live.length > 0 && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-bold text-white mb-1">Live Strategic Decision Records (Executive Sign-Off)</h3>
          <p className="text-xs text-slate-400 mb-4">Decisions reviewed by leadership (Approved, Changes Requested, or Rejected)</p>
          <div className="space-y-3">
            {live.map((item: any, idx: number) => {
              const action = item.action || 'approve';
              const isApproved = action === 'approve';
              const isRejected = action === 'reject';
              return (
                <div key={idx} className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-mono text-slate-400">ID: {item.decision_id}</div>
                    <div className="text-sm font-bold text-white mt-0.5">Strategy: {item.chosen_strategy}</div>
                    {item.notes && <div className="text-xs text-slate-400 mt-1">Notes: "{item.notes}"</div>}
                  </div>
                  <div className="text-right">
                    <span className={`px-2.5 py-1 text-xs font-semibold uppercase rounded-full border ${
                      isApproved
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : isRejected
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {isApproved ? 'Approved (Awaiting Outcome)' : isRejected ? 'Rejected by Executive' : 'Changes Requested'}
                    </span>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {isApproved ? 'Approved' : isRejected ? 'Rejected' : 'Reviewed'} {new Date(item.approved_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Seeded Past Decisions */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-1">Historical Decision Log (Seeded Telemetry)</h3>
        <p className="text-xs text-slate-400 mb-4">Audited outcomes showing where simulation models were accurate vs where assumptions broke</p>

        <div className="space-y-4">
          {seeded.map((dec: any) => (
            <div key={dec.id} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800/60">
                <div>
                  <div className="text-xs font-bold text-brand-400 uppercase tracking-wider">{dec.type.replace(/_/g, ' ')}</div>
                  <div className="text-sm font-bold text-white">{dec.question}</div>
                </div>
                <div className="text-right text-[11px] text-slate-500">
                  Chosen: <span className="text-slate-300 font-medium">{dec.chosen_strategy}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs mt-3">
                <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800/60">
                  <div className="text-slate-400 text-[11px]">Predicted Metrics</div>
                  <div className="font-mono text-white mt-1">
                    {Object.entries(dec.predicted_metrics).map(([k, v]: any) => (
                      <div key={k}>{k.replace(/_/g, ' ')}: {typeof v === 'number' && v > 1000 ? `$${v.toLocaleString()}` : v}</div>
                    ))}
                  </div>
                </div>

                <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800/60">
                  <div className="text-slate-400 text-[11px]">Actual Observed Outcome</div>
                  <div className="font-mono text-emerald-400 mt-1">
                    {Object.entries(dec.actual_metrics).map(([k, v]: any) => (
                      <div key={k}>{k.replace(/_/g, ' ')}: {typeof v === 'number' && v > 1000 ? `$${v.toLocaleString()}` : v}</div>
                    ))}
                  </div>
                </div>

                <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800/60">
                  <div className="text-slate-400 text-[11px]">Calibration Error & Drift</div>
                  <div className="text-white mt-1">
                    {dec.calibration_error && (
                      <>
                        <div className="text-amber-400 font-mono">Error: {String(Object.values(dec.calibration_error)[0])}%</div>
                        <div className="text-slate-400 text-[11px] mt-1">
                          Most wrong assumption: <span className="text-slate-200 font-medium">{dec.calibration_error.most_wrong_assumption}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
