import React, { useState } from 'react';

interface Props {
  onInject: (agent: string, mode: string) => void;
  disabled: boolean;
}

export const FailureInjector: React.FC<Props> = ({ onInject, disabled }) => {
  const [agent, setAgent] = useState('cto');
  const [mode, setMode] = useState('exception');
  const [injectedMsg, setInjectedMsg] = useState<string | null>(null);

  const handleInject = () => {
    onInject(agent, mode);
    setInjectedMsg(`Fault injected: ${agent.toUpperCase()} will trigger ${mode} on next execution.`);
    setTimeout(() => setInjectedMsg(null), 4000);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-semibold text-white">Live Fault Injection (Chaos Testing)</h3>
          <p className="text-xs text-slate-400">Trigger mid-run agent crashes or latency to verify autonomous recovery</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-4">
        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Agent</label>
          <select
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            disabled={disabled}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
          >
            <option value="cto">CTO (Infrastructure)</option>
            <option value="cfo">CFO (Financials)</option>
            <option value="growth">Growth (Acquisition)</option>
            <option value="customer">Customer (Retention)</option>
            <option value="product">Product (Packaging)</option>
            <option value="skeptic">Skeptic (Audit)</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Fault Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            disabled={disabled}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
          >
            <option value="exception">Process Exception (Crash)</option>
            <option value="timeout">Execution Timeout (Latency)</option>
            <option value="bad_output">Schema Corruption (Invalid Output)</option>
          </select>
        </div>

        <div className="pt-5">
          <button
            onClick={handleInject}
            disabled={disabled}
            className="px-4 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 rounded-lg text-xs font-semibold transition disabled:opacity-50"
          >
            Inject Failure
          </button>
        </div>
      </div>

      {injectedMsg && (
        <div className="mt-3 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 p-2 rounded-lg">
          {injectedMsg}
        </div>
      )}
    </div>
  );
};

