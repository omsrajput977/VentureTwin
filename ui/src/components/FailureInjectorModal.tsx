import React, { useState } from 'react';

export interface StagedFault {
  agent: string;
  mode: string;
  persist: boolean;
  fail_attempts: number;
}

interface Props {
  onInject: (agent: string, mode: string, persist?: boolean, failAttempts?: number) => void;
  stagedFault: StagedFault | null;
  onSetStagedFault: (fault: StagedFault | null) => void;
  workflowStatus: string;
}

export const FailureInjector: React.FC<Props> = ({
  onInject,
  stagedFault,
  onSetStagedFault,
  workflowStatus
}) => {
  const [agent, setAgent] = useState('cto');
  const [mode, setMode] = useState('exception');
  const [persist, setPersist] = useState(false);
  const [failAttempts, setFailAttempts] = useState(1);
  const [injectedMsg, setInjectedMsg] = useState<string | null>(null);

  const isRunning = workflowStatus === 'running';

  const handleAction = () => {
    if (isRunning) {
      onInject(agent, mode, persist, failAttempts);
      const persistText = persist ? 'persistently' : `${failAttempts} attempt(s)`;
      setInjectedMsg(`Live fault injected: ${agent.toUpperCase()} will trigger ${mode} (${persistText}).`);
      setTimeout(() => setInjectedMsg(null), 4000);
    } else {
      onSetStagedFault({
        agent,
        mode,
        persist,
        fail_attempts: failAttempts
      });
      const persistText = persist ? 'persistently' : `${failAttempts} attempt(s)`;
      setInjectedMsg(`Armed for next run: ${agent.toUpperCase()} will trigger ${mode} (${persistText}).`);
      setTimeout(() => setInjectedMsg(null), 5000);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span>Live Fault Injection (Chaos Testing)</span>
            {stagedFault && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/30">
                ARMED
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400">Trigger mid-run agent crashes or latency to verify autonomous recovery</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-4">
        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Agent</label>
          <select
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
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
            disabled={persist}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 w-16 focus:outline-none focus:border-brand-500 disabled:opacity-40"
          />
        </div>

        <div className="flex items-center gap-1.5 pt-5">
          <input
            type="checkbox"
            id="persist_toggle"
            checked={persist}
            onChange={(e) => setPersist(e.target.checked)}
            className="rounded border-slate-800 text-brand-500 focus:ring-0"
          />
          <label htmlFor="persist_toggle" className="text-xs text-slate-300 cursor-pointer">
            Persist (All attempts)
          </label>
        </div>

        <div className="pt-5 flex items-center gap-2">
          <button
            onClick={handleAction}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition border ${
              isRunning
                ? 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30'
                : stagedFault
                ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/30'
                : 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30'
            }`}
          >
            {isRunning ? 'Inject Mid-Run Failure' : stagedFault ? 'Update Armed Fault' : 'Arm Fault for Run'}
          </button>

          {stagedFault && !isRunning && (
            <button
              onClick={() => onSetStagedFault(null)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg text-xs transition"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {stagedFault && !isRunning && (
        <div className="mt-3 p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold">⚡ Armed Chaos:</span>
            <span>
              Target <span className="font-mono uppercase font-bold">{stagedFault.agent}</span> will suffer{' '}
              <span className="font-mono font-semibold">{stagedFault.mode}</span> (
              {stagedFault.persist ? 'all attempts / persist' : `${stagedFault.fail_attempts} attempt(s)`}
              ).
            </span>
          </div>
          <span className="text-[11px] text-rose-400/80">Ready to test on next "Run Simulation"</span>
        </div>
      )}

      {injectedMsg && (
        <div className="mt-3 p-2.5 bg-rose-500/20 border border-rose-500/40 rounded-lg text-xs text-rose-200 animate-pulse flex items-center gap-2">
          <span>⚡</span>
          <span>{injectedMsg}</span>
        </div>
      )}
    </div>
  );
};
