import React from 'react';
import { CompanySnapshot } from '../api';

interface Props {
  snapshot: CompanySnapshot | null;
}

export const CompanySnapshotCard: React.FC<Props> = ({ snapshot }) => {
  if (!snapshot) {
    return <div className="p-4 bg-slate-900 rounded-xl border border-slate-800 animate-pulse text-slate-500">Loading company snapshot...</div>;
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold tracking-tight text-white">{snapshot.company_name}</h2>
            <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded-full">
              {snapshot.stage}
            </span>
            <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-full">
              Synthetic Data
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Operational Baseline Environment for Pricing & Packaging Simulations</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 pt-4">
        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Monthly Recurring Revenue</div>
          <div className="text-lg font-bold text-white mt-1">${snapshot.mrr.toLocaleString()}</div>
          <div className="text-[11px] text-slate-500">ARR: ${(snapshot.arr / 1000).toFixed(0)}k</div>
        </div>

        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Cash Runway</div>
          <div className="text-lg font-bold text-emerald-400 mt-1">{snapshot.runway_months.toFixed(1)} mo</div>
          <div className="text-[11px] text-slate-500">${(snapshot.cash_balance / 1000000).toFixed(2)}M balance</div>
        </div>

        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Paying Customers</div>
          <div className="text-lg font-bold text-white mt-1">{snapshot.paying_customers}</div>
          <div className="text-[11px] text-slate-500">Churn: {(snapshot.monthly_churn_rate * 100).toFixed(1)}%/mo</div>
        </div>

        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Unit Economics</div>
          <div className="text-lg font-bold text-white mt-1">${snapshot.cac} CAC</div>
          <div className="text-[11px] text-slate-500">LTV: ${snapshot.ltv}</div>
        </div>

        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Cloud Infrastructure</div>
          <div className="text-lg font-bold text-white mt-1">${(snapshot.infra_cost_monthly / 1000).toFixed(1)}k/mo</div>
          <div className="text-[11px] text-slate-500">Baseline spend</div>
        </div>

        <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          <div className="text-xs text-slate-400 font-medium">Support Operations</div>
          <div className="text-lg font-bold text-white mt-1">{snapshot.support_headcount} FTEs</div>
          <div className="text-[11px] text-slate-500">${(snapshot.support_cost_monthly / 1000).toFixed(0)}k/mo spend</div>
        </div>
      </div>
    </div>
  );
};
