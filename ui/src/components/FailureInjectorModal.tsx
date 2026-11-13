import React, { useState } from 'react';

export interface StagedFault {
  agent: string;
  mode: string;
  persist: boolean;
  fail_attempts: number;
}

interface Props {
  onInject: (agent: string, mode: string, persist?: boolean, failAttempts?: number) => Promise<void> | void;
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
  const [agent, setAgent] = useState('growth');
  const [actionType, setActionType] = useState('transient_exception');
  const [injectedMsg, setInjectedMsg] = useState<string | null>(null);
  const [injectError, setInjectError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRunning = workflowStatus === 'running';

  // Decode actionType into mode, persist, and failAttempts
  const getActionParams = () => {
    switch (actionType) {
      case 'transient_exception':
        return { mode: 'exception', persist: false, failAttempts: 1, label: 'transient crash' };
      case 'transient_timeout':
        return { mode: 'timeout', persist: false, failAttempts: 1, label: 'transient timeout' };
      case 'transient_bad_output':
        return { mode: 'bad_output', persist: false, failAttempts: 1, label: 'transient schema corruption' };
      case 'fatal_exception':
        return { mode: 'exception', persist: true, failAttempts: 3, label: 'fatal crash (backup failover)' };
      case 'heal':
        return { mode: 'heal', persist: false, failAttempts: 0, label: 'restore primary agent' };
      default:
        return { mode: 'exception', persist: false, failAttempts: 1, label: 'transient crash' };
    }
  };

  const handleAction = async () => {
    setInjectError(null);
    const { mode, persist, failAttempts, label } = getActionParams();

    if (isRunning || mode === 'heal') {
      setIsSubmitting(true);
      try {
        await onInject(agent, mode, persist, failAttempts);
        if (mode === 'heal') {
          setInjectedMsg(`Agent restored: ${agent.toUpperCase()} has been re-injected with clean primary analysis.`);
        } else {
          const detail = persist ? 'persistent failure (backup failover)' : '1 attempt (autonomous retry)';
          setInjectedMsg(`Live fault injected: ${agent.toUpperCase()} will suffer ${mode} (${detail}).`);
        }
        setTimeout(() => setInjectedMsg(null), 5000);
      } catch (err: any) {
        setInjectError(err?.message || 'Failed to execute agent action');
        setTimeout(() => setInjectError(null), 6000);
      } finally {
        setIsSubmitting(false);
      }
    } else {
      onSetStagedFault({
        agent,
        mode,
        persist,
        fail_attempts: failAttempts
      });
      const detail = persist ? 'persistent failure' : `${failAttempts} attempt(s)`;
      setInjectedMsg(`Armed for next run: ${agent.toUpperCase()} will suffer ${mode} (${detail}).`);
      setTimeout(() => setInjectedMsg(null), 5000);
    }
  };

  const isHeal = actionType === 'heal';

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-semibold text-white flex items-center gap-2">
            <span>Live Fault Injection & Agent Recovery</span>
            {stagedFault && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/30">
                ARMED
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400">Trigger agent crashes, test autonomous retries, or re-inject restored agents</p>
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
            <option value="growth">Growth (Acquisition)</option>
            <option value="cfo">CFO (Financials)</option>
            <option value="cto">CTO (Infrastructure)</option>
            <option value="customer">Customer (Retention)</option>
            <option value="product">Product (Packaging)</option>
            <option value="skeptic">Skeptic (Audit)</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Action & Resilience Mode</label>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500 min-w-[280px]"
          >
            <option value="transient_exception">⚡ Transient Crash (Agent Retries & Recovers)</option>
            <option value="transient_timeout">⏱️ Transient Latency (Agent Retries & Recovers)</option>
            <option value="transient_bad_output">🧬 Transient Bad Output (Agent Retries & Recovers)</option>
            <option value="fatal_exception">🛑 Fatal Crash (Failover to Backup Analyst)</option>
            <option value="heal">🛡️ Re-inject & Restore Agent (Clean Primary Analysis)</option>
          </select>
        </div>

        <div className="pt-5 flex items-center gap-2">
          <button
            onClick={handleAction}
            disabled={isSubmitting}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition border ${
              isSubmitting
                ? 'opacity-50 cursor-not-allowed bg-slate-800 text-slate-400 border-slate-700'
                : isHeal
                ? 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border-emerald-500/30 shadow-lg shadow-emerald-500/10'
                : isRunning
                ? 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30'
                : stagedFault
                ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/30'
                : 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30'
            }`}
          >
            {isSubmitting
              ? 'Executing...'
              : isHeal
              ? '🛡️ Re-inject & Restore Agent'
              : isRunning
              ? '⚡ Inject Fault Mid-Run'
              : stagedFault
              ? 'Update Armed Fault'
              : 'Arm Fault for Next Run'}
          </button>

          {stagedFault && !isRunning && !isHeal && (
            <button
              onClick={() => onSetStagedFault(null)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg text-xs transition"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Explanatory Context Guide */}
      <div className="mt-3 text-[11px] text-slate-400">
        {actionType.startsWith('transient_') && (
          <span className="text-slate-400">
            💡 <strong className="text-slate-300">Transient Fault:</strong> Target agent experiences 1 attempt failure, then autonomously recovers on retry. The agent is <span className="text-emerald-400 font-medium">not removed</span> and its authentic domain analysis is preserved (<code className="text-[10px] text-emerald-400">Done (Retry 1)</code>).
          </span>
        )}
        {actionType === 'fatal_exception' && (
          <span className="text-rose-300/90">
            ⚠️ <strong className="text-rose-200">Fatal Crash:</strong> Agent fails all 3 retry attempts. The supervisor initiates Tier 2 recovery, delegating domain synthesis to <span className="text-purple-300 font-semibold">Backup Analyst</span> (<code className="text-[10px] text-purple-400">Recovered Backup</code>).
          </span>
        )}
        {actionType === 'heal' && (
          <span className="text-emerald-300/90">
            🛡️ <strong className="text-emerald-200">Re-inject Agent:</strong> Clears any fault or Backup Analyst fallback and re-executes clean primary analysis, injecting authentic domain recommendations and findings back into the live graph and report.
          </span>
        )}
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

      {injectError && (
        <div className="mt-3 p-2.5 bg-rose-500/20 border border-rose-500/50 rounded-lg text-xs text-rose-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{injectError}</span>
          </div>
          <button onClick={() => setInjectError(null)} className="text-rose-400 hover:text-white font-bold ml-2">✕</button>
        </div>
      )}

      {injectedMsg && (
        <div className={`mt-3 p-2.5 rounded-lg text-xs animate-pulse flex items-center gap-2 border ${
          isHeal
            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200'
            : 'bg-rose-500/20 border-rose-500/40 text-rose-200'
        }`}>
          <span>{isHeal ? '🛡️' : '⚡'}</span>
          <span>{injectedMsg}</span>
        </div>
      )}
    </div>
  );
};
