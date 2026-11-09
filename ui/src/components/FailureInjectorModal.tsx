import React, { useState } from 'react';

interface Props {
  onInject: (agent: string, mode: string, persist?: boolean, failAttempts?: number) => void;
  disabled: boolean;
}

export const FailureInjector: React.FC<Props> = ({ onInject, disabled }) => {
  const [agent, setAgent] = useState('cto');
  const [mode, setMode] = useState('exception');
  const [persist, setPersist] = useState(false);
  const [failAttempts, setFailAttempts] = useState(1);
  const [injectedMsg, setInjectedMsg] = useState<string | null>(null);

  const handleInject = () => {
    onInject(agent, mode, persist, failAttempts);
    const persistText = persist ? 'persistently' : `${failAttempts} attempt(s)`;
    setInjectedMsg(`Fault injected: ${agent.toUpperCase()} will trigger ${mode} (${persistText}).`);
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

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Attempts</label>
          <input
            type="number"
            min={1}
            max={5}
            value={failAttempts}
            onChange={(e) => setFailAttempts(Math.max(1, parseInt(e.target.value) || 1))}
            disabled={disabled || persist}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 w-16 focus:outline-none focus:border-brand-500 disabled:opacity-40"
          />
        </div>

        <div className="flex items-center gap-1.5 pt-5">
          <input
            type="checkbox"
            id="persist_toggle"
            checked={persist}
            onChange={(e) => setPersist(e.target.checked)}
            disabled={disabled}
            className="rounded border-slate-800 text-brand-500 focus:ring-0"
          />
          <label htmlFor="persist_toggle" className="text-xs text-slate-300 cursor-pointer">
            Persist (All attempts)
          </label>
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
        <div className="mt-3 p-2 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300">
          ⚠️ {injectedMsg}
        </div>
      )}
    </div>
  );
};
