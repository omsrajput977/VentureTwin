import React, { useState, useEffect } from 'react';
import {
  fetchCompany,
  fetchHealth,
  submitDecision,
  fetchDecisionStatus,
  fetchDecisionReport,
  injectFailure,
  CompanySnapshot,
  TaskItem,
  FindingItem,
  EventItem
} from './api';
import { CompanySnapshotCard } from './components/CompanySnapshotCard';
import { ExecutionGraph } from './components/ExecutionGraph';
import { EventFeed } from './components/EventFeed';
import { FailureInjector, StagedFault } from './components/FailureInjectorModal';
import { DecisionReportView } from './components/DecisionReportView';
import { CalibrationView } from './components/CalibrationView';
import { CompanyGraphView } from './components/CompanyGraphView';
import { ErrorBoundary } from './components/ErrorBoundary';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'console' | 'report' | 'calibration' | 'graph'>('console');
  const [company, setCompany] = useState<CompanySnapshot | null>(null);
  const [health, setHealth] = useState<{ llm_mode: string; provider: string; model: string } | null>(null);
  
  // Workflow state
  const [decisionQuery, setDecisionQuery] = useState('Should we launch a free plan?');
  const [currentDecisionId, setCurrentDecisionId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string>('idle');
  const [tasks, setTasks] = useState<Record<string, TaskItem>>({});
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [report, setReport] = useState<any>(null);
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [stagedFault, setStagedFault] = useState<StagedFault | null>(null);

  const hasGivenPrompt = Boolean(currentDecisionId);

  // Guard tabs: if user has not given a prompt, restrict to console
  useEffect(() => {
    if (!hasGivenPrompt && activeTab !== 'console') {
      setActiveTab('console');
    }
  }, [hasGivenPrompt, activeTab]);

  // Load initial company snapshot and health
  useEffect(() => {
    fetchCompany().then(setCompany).catch(console.error);
    fetchHealth().then(setHealth).catch(console.error);
  }, []);

  // Poll workflow status when a decision is active
  useEffect(() => {
    if (!currentDecisionId || report) return;

    const interval = setInterval(async () => {
      try {
        const data = await fetchDecisionStatus(currentDecisionId);
        setWorkflowStatus(data.status);
        if (data.tasks) setTasks(data.tasks);
        if (data.findings) setFindings(data.findings);

        if (data.has_report || data.status === 'completed' || data.status === 'degraded') {
          try {
            const rep = await fetchDecisionReport(currentDecisionId);
            if (rep) {
              setReport(rep);
              clearInterval(interval);
            }
          } catch (e) {
            // Report is still generating in background, keep polling
          }
        } else if (data.status === 'failed') {
          clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
      }
    }, 500);

    return () => clearInterval(interval);
  }, [currentDecisionId, report]);

  // Connect to SSE stream
  useEffect(() => {
    if (!currentDecisionId) return;

    const eventSource = new EventSource(`/api/decisions/${currentDecisionId}/stream`);
    eventSource.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setEvents((prev) => [...prev, parsed]);

        if (parsed.type === 'report_ready' || parsed.type === 'workflow_completed' || parsed.type === 'workflow_degraded') {
          fetchDecisionStatus(currentDecisionId).then((data) => {
            setWorkflowStatus(data.status);
            if (data.tasks) setTasks(data.tasks);
            if (data.findings) setFindings(data.findings);
          }).catch(console.error);

          fetchDecisionReport(currentDecisionId).then((rep) => {
            if (rep) setReport(rep);
          }).catch(console.error);
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [currentDecisionId]);

  const handleLaunchDecision = async (queryToUse?: string) => {
    const q = queryToUse || decisionQuery;
    try {
      setWorkflowStatus('running');
      setTasks({});
      setFindings([]);
      setEvents([]);
      setReport(null);

      const res = await submitDecision(q, undefined, stagedFault || undefined);
      setCurrentDecisionId(res.decision_id);
      setStagedFault(null);
      setActiveTab('console');
    } catch (err: any) {
      alert(`Launch error: ${err.message}`);
      setWorkflowStatus('idle');
    }
  };

  const handleInjectFault = async (agent: string, mode: string, persist: boolean = false, failAttempts: number = 1) => {
    if (!currentDecisionId) {
      throw new Error('No active decision running. Please submit a question first.');
    }
    await injectFailure(currentDecisionId, agent, mode, persist, failAttempts);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-emerald-600 flex items-center justify-center font-bold text-slate-950 text-base shadow-lg shadow-brand-500/20">
              VT
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight text-white">VentureTwin</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase bg-slate-800 text-slate-300">
                  SwarmFlow Engine
                </span>
              </div>
              <p className="text-[10px] text-slate-400">AI Flight Simulator & Operational Digital Twin for SaaS CEOs</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('console')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'console' ? 'bg-brand-500 text-slate-950 font-bold shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Decision Console
            </button>
            <button
              disabled={!hasGivenPrompt || (workflowStatus === 'running' && !report)}
              onClick={async () => {
                if (!hasGivenPrompt) return;
                setActiveTab('report');
                if (!report && currentDecisionId) {
                  try {
                    const rep = await fetchDecisionReport(currentDecisionId);
                    if (rep) setReport(rep);
                  } catch (e) {
                    console.warn('Report fetch notice:', e);
                  }
                }
              }}
              title={
                !hasGivenPrompt
                  ? 'Please submit a prompt in the Decision Console first'
                  : !report && workflowStatus === 'running'
                  ? 'Report will be available once the simulation completes'
                  : 'View verified decision report'
              }
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                !hasGivenPrompt || (workflowStatus === 'running' && !report)
                  ? 'opacity-40 cursor-not-allowed text-slate-600'
                  : activeTab === 'report'
                  ? 'bg-brand-500 text-slate-950 font-bold shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Decision Report {report ? '✓' : workflowStatus === 'running' ? '⏳' : ''}
            </button>
            <button
              disabled={!hasGivenPrompt}
              onClick={() => {
                if (!hasGivenPrompt) return;
                setActiveTab('calibration');
              }}
              title={
                !hasGivenPrompt
                  ? 'Please submit a prompt in the Decision Console first'
                  : 'View decision calibration & outcome memory'
              }
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                !hasGivenPrompt
                  ? 'opacity-40 cursor-not-allowed text-slate-600'
                  : activeTab === 'calibration'
                  ? 'bg-brand-500 text-slate-950 font-bold shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Calibration & Memory
            </button>
            <button
              disabled={!hasGivenPrompt}
              onClick={() => {
                if (!hasGivenPrompt) return;
                setActiveTab('graph');
              }}
              title={
                !hasGivenPrompt
                  ? 'Please submit a prompt in the Decision Console first'
                  : 'View company dependency graph'
              }
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                !hasGivenPrompt
                  ? 'opacity-40 cursor-not-allowed text-slate-600'
                  : activeTab === 'graph'
                  ? 'bg-brand-500 text-slate-950 font-bold shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Company Graph
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full space-y-6">
        <ErrorBoundary onReset={() => setActiveTab('console')}>
        {/* Mode & Health Banners */}
        {((health?.llm_mode || '').trim() === 'real') && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 flex items-center justify-between text-xs text-emerald-200">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold uppercase tracking-wider text-[10px]">
                Live LLM Mode
              </span>
              <span>
                Connected to {health?.provider} ({health?.model}) with live multi-agent orchestration.
              </span>
            </div>
            <span className="text-[11px] text-emerald-400/80">LLM_MODE=real</span>
          </div>
        )}

        {((health?.llm_mode || '').trim() === 'mock') && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 flex items-center justify-between text-xs text-amber-200">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold uppercase tracking-wider text-[10px]">
                Deterministic Mock Mode
              </span>
              <span>
                Agents invoke data-driven mock handlers computing structured assumptions from tool telemetry. No static string literals.
              </span>
            </div>
            <span className="text-[11px] text-amber-400/80">LLM_MODE=mock</span>
          </div>
        )}

        {workflowStatus === 'degraded' && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-3 flex items-center justify-between text-xs text-orange-200">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-400 font-bold uppercase tracking-wider text-[10px]">
                Degraded Execution
              </span>
              <span>
                One or more agent processes encountered unrecoverable runtime faults. Backup Analyst or fallback estimates applied.
              </span>
            </div>
            <span className="text-[11px] text-orange-400/80">Workflow Degraded</span>
          </div>
        )}

        {/* Persistent Company Snapshot Card */}
        <CompanySnapshotCard snapshot={company} />

        {/* Tab 1: Decision Console */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            {/* Decision Intake Box */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Strategic Question Intake
                </label>
                {stagedFault && (
                  <span className="text-[11px] font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2.5 py-0.5 rounded-full flex items-center gap-1.5 animate-pulse">
                    <span>⚡ Chaos Armed:</span>
                    <span className="font-mono uppercase font-bold">{stagedFault.agent}</span>
                    <span>({stagedFault.mode})</span>
                  </span>
                )}
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={decisionQuery}
                  onChange={(e) => setDecisionQuery(e.target.value)}
                  placeholder="Ask any strategic SaaS question (e.g. Should we raise price by 20%?)"
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-brand-500"
                />
                <button
                  onClick={() => handleLaunchDecision()}
                  disabled={workflowStatus === 'running'}
                  className="px-6 py-2.5 bg-gradient-to-r from-brand-500 to-emerald-500 hover:from-brand-600 hover:to-emerald-600 text-slate-950 font-bold rounded-xl text-sm transition shadow-lg shadow-brand-500/20 disabled:opacity-50 shrink-0"
                >
                  {workflowStatus === 'running' ? 'Simulating...' : 'Run Simulation'}
                </button>
              </div>

              {/* Example Question Chips */}
              <div className="flex flex-wrap items-center gap-2 mt-3 text-xs text-slate-400">
                <span className="text-[11px] font-medium text-slate-500">Example queries:</span>
                <button
                  onClick={() => {
                    setDecisionQuery('Should we launch a free plan?');
                    handleLaunchDecision('Should we launch a free plan?');
                  }}
                  className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 rounded-lg text-[11px] transition"
                >
                  Should we launch a free plan?
                </button>
                <button
                  onClick={() => {
                    setDecisionQuery('Should we raise Starter price by 20%?');
                    handleLaunchDecision('Should we raise Starter price by 20%?');
                  }}
                  className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 rounded-lg text-[11px] transition"
                >
                  Should we raise Starter price by 20%?
                </button>
                <button
                  onClick={() => {
                    setDecisionQuery('Can we introduce an enterprise tier with custom SLAs?');
                    handleLaunchDecision('Can we introduce an enterprise tier with custom SLAs?');
                  }}
                  className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 rounded-lg text-[11px] transition"
                >
                  Can we introduce an enterprise tier?
                </button>
                <button
                  onClick={() => {
                    setDecisionQuery('How do we reduce customer churn and preserve runway?');
                    handleLaunchDecision('How do we reduce customer churn and preserve runway?');
                  }}
                  className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 rounded-lg text-[11px] transition"
                >
                  How do we reduce customer churn?
                </button>
              </div>
            </div>

            {/* Execution Graph */}
            <ExecutionGraph
              tasks={tasks}
              findings={findings}
              onSelectFinding={setSelectedFinding}
            />

            {/* Bottom Row: Failure Injector and Event Stream */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FailureInjector
                onInject={handleInjectFault}
                stagedFault={stagedFault}
                onSetStagedFault={setStagedFault}
                workflowStatus={workflowStatus}
              />
              <EventFeed events={events} />
            </div>
          </div>
        )}

        {/* Tab 2: Decision Report */}
        {activeTab === 'report' && (
          hasGivenPrompt && report ? (
            <DecisionReportView
              report={report}
              decisionId={currentDecisionId || ''}
              onApprovalDone={() => setActiveTab('calibration')}
            />
          ) : (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-12 text-center shadow-xl space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-slate-800 flex items-center justify-center text-slate-400 text-xl font-bold">
                🔒
              </div>
              <h3 className="text-lg font-bold text-white">Decision Report Unavailable</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                {!hasGivenPrompt
                  ? 'Please submit a strategic question prompt in the Decision Console first to generate a decision report.'
                  : 'Simulation is currently running. The verified decision report will be available once all agent analysis waves complete.'}
              </p>
              <button
                onClick={() => setActiveTab('console')}
                className="px-5 py-2 bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg transition"
              >
                Go to Decision Console
              </button>
            </div>
          )
        )}

        {/* Tab 3: Calibration & Outcome Memory */}
        {activeTab === 'calibration' && (
          hasGivenPrompt ? (
            <CalibrationView />
          ) : (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-12 text-center shadow-xl space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-slate-800 flex items-center justify-center text-slate-400 text-xl font-bold">
                🔒
              </div>
              <h3 className="text-lg font-bold text-white">Calibration &amp; Memory Locked</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                Please submit a strategic question prompt in the Decision Console first to initialize simulation telemetry and calibration memory.
              </p>
              <button
                onClick={() => setActiveTab('console')}
                className="px-5 py-2 bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg transition"
              >
                Go to Decision Console
              </button>
            </div>
          )
        )}

        {/* Tab 4: Company Graph */}
        {activeTab === 'graph' && (
          hasGivenPrompt ? (
            <CompanyGraphView />
          ) : (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-12 text-center shadow-xl space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-slate-800 flex items-center justify-center text-slate-400 text-xl font-bold">
                🔒
              </div>
              <h3 className="text-lg font-bold text-white">Company Graph Locked</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto">
                Please submit a strategic question prompt in the Decision Console first to inspect the company dependency graph for your scenario.
              </p>
              <button
                onClick={() => setActiveTab('console')}
                className="px-5 py-2 bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg transition"
              >
                Go to Decision Console
              </button>
            </div>
          )
        )}
        </ErrorBoundary>
      </main>

      {/* Finding Inspector Modal */}
      {selectedFinding && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-white uppercase">{selectedFinding.agent || 'Agent'} Finding</span>
                <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                  {selectedFinding.task_id || ''}
                </span>
                {selectedFinding.recovered_via_backup && (
                  <span className="text-xs px-2 py-0.5 rounded font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    🛡️ Recovered by Backup Analyst
                  </span>
                )}
                {selectedFinding.degraded && (
                  <span className="text-xs px-2 py-0.5 rounded font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    ⚠️ Degraded Prior
                  </span>
                )}
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Core Claim</div>
              <div className="text-sm text-slate-200 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                {selectedFinding.claim || 'No claim recorded'}
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div>
                <span className="text-slate-400">Recommendation:</span>{' '}
                <span className="font-bold text-white capitalize">{String(selectedFinding.recommendation || 'proceed').replace(/_/g, ' ')}</span>
              </div>
              <div>
                <span className="text-slate-400">Confidence:</span>{' '}
                <span className="font-bold text-brand-400">{(Number(selectedFinding.confidence ?? 0.5) * 100).toFixed(0)}%</span>
              </div>
            </div>

            {selectedFinding.assumptions?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Proposed Assumptions</div>
                <div className="space-y-2">
                  {selectedFinding.assumptions.map((asm: any, idx: number) => (
                    <div key={idx} className="p-2.5 bg-slate-950/40 rounded-lg border border-slate-800 text-xs font-mono">
                      <div className="flex justify-between text-slate-300 font-semibold font-sans">
                        <span>{asm.name}</span>
                        <span className="text-slate-400 font-mono">[{asm.low} - {asm.base} - {asm.high}] {asm.unit}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        Provenance: <span className="text-brand-400 font-sans">{asm.provenance}</span> | Source: {asm.source_ref || 'None'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-2 flex items-center justify-between">
              {(selectedFinding.recovered_via_backup || selectedFinding.degraded) ? (
                <button
                  onClick={async () => {
                    try {
                      await handleInjectFault(selectedFinding.agent, 'heal');
                      setSelectedFinding(null);
                    } catch (e: any) {
                      console.error(e);
                    }
                  }}
                  className="px-4 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold rounded-lg transition flex items-center gap-1.5"
                >
                  <span>🛡️</span>
                  <span>Re-inject & Restore Primary {selectedFinding.agent}</span>
                </button>
              ) : <div />}
              <button
                onClick={() => setSelectedFinding(null)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white rounded-lg transition"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

