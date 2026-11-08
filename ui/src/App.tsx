import React, { useState, useEffect } from 'react';
import {
  fetchCompany,
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
import { FailureInjector } from './components/FailureInjectorModal';
import { DecisionReportView } from './components/DecisionReportView';
import { CalibrationView } from './components/CalibrationView';
import { CompanyGraphView } from './components/CompanyGraphView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'console' | 'report' | 'calibration' | 'graph'>('console');
  const [company, setCompany] = useState<CompanySnapshot | null>(null);
  
  // Workflow state
  const [decisionQuery, setDecisionQuery] = useState('Should we launch a free plan?');
  const [currentDecisionId, setCurrentDecisionId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string>('idle');
  const [tasks, setTasks] = useState<Record<string, TaskItem>>({});
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [report, setReport] = useState<any>(null);
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);

  // Load initial company snapshot
  useEffect(() => {
    fetchCompany().then(setCompany).catch(console.error);
  }, []);

  // Poll workflow status when a decision is active
  useEffect(() => {
    if (!currentDecisionId || workflowStatus === 'completed' || workflowStatus === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const data = await fetchDecisionStatus(currentDecisionId);
        setWorkflowStatus(data.status);
        if (data.tasks) setTasks(data.tasks);
        if (data.findings) setFindings(data.findings);

        if (data.status === 'completed' || data.status === 'degraded') {
          clearInterval(interval);
          const rep = await fetchDecisionReport(currentDecisionId);
          setReport(rep);
        }
      } catch (err) {
        console.error(err);
      }
    }, 400);

    return () => clearInterval(interval);
  }, [currentDecisionId, workflowStatus]);

  // Connect to SSE stream
  useEffect(() => {
    if (!currentDecisionId) return;

    const eventSource = new EventSource(`/api/decisions/${currentDecisionId}/stream`);
    eventSource.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setEvents((prev) => [...prev, parsed]);
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

      const res = await submitDecision(q);
      setCurrentDecisionId(res.decision_id);
      setActiveTab('console');
    } catch (err: any) {
      alert(`Launch error: ${err.message}`);
      setWorkflowStatus('idle');
    }
  };

  const handleInjectFault = async (agent: string, mode: string) => {
    if (!currentDecisionId) return;
    try {
      await injectFailure(currentDecisionId, agent, mode);
    } catch (err: any) {
      alert(`Inject fault error: ${err.message}`);
    }
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
              onClick={() => setActiveTab('report')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'report' ? 'bg-brand-500 text-slate-950 font-bold shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Decision Report {report && '✓'}
            </button>
            <button
              onClick={() => setActiveTab('calibration')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'calibration' ? 'bg-brand-500 text-slate-950 font-bold shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Calibration & Memory
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'graph' ? 'bg-brand-500 text-slate-950 font-bold shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              Company Graph
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full space-y-6">
        {/* Persistent Company Snapshot Card */}
        <CompanySnapshotCard snapshot={company} />

        {/* Tab 1: Decision Console */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            {/* Decision Intake Box */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Strategic Question Intake
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={decisionQuery}
                  onChange={(e) => setDecisionQuery(e.target.value)}
                  placeholder="e.g. Should we launch a free plan?"
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
                    setDecisionQuery('What if we raise Starter plan price by 15%?');
                    handleLaunchDecision('What if we raise Starter plan price by 15%?');
                  }}
                  className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-800 text-slate-300 rounded-lg text-[11px] transition"
                >
                  What if we raise Starter price by 15%?
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
                disabled={workflowStatus !== 'running'}
              />
              <EventFeed events={events} />
            </div>
          </div>
        )}

        {/* Tab 2: Decision Report */}
        {activeTab === 'report' && (
          <DecisionReportView
            report={report}
            decisionId={currentDecisionId || ''}
            onApprovalDone={() => setActiveTab('calibration')}
          />
        )}

        {/* Tab 3: Calibration & Outcome Memory */}
        {activeTab === 'calibration' && <CalibrationView />}

        {/* Tab 4: Company Graph */}
        {activeTab === 'graph' && <CompanyGraphView />}
      </main>

      {/* Finding Inspector Modal */}
      {selectedFinding && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-white uppercase">{selectedFinding.agent} Finding</span>
                <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                  {selectedFinding.task_id}
                </span>
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
                {selectedFinding.claim}
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div>
                <span className="text-slate-400">Recommendation:</span>{' '}
                <span className="font-bold text-white capitalize">{selectedFinding.recommendation.replace(/_/g, ' ')}</span>
              </div>
              <div>
                <span className="text-slate-400">Confidence:</span>{' '}
                <span className="font-bold text-brand-400">{(selectedFinding.confidence * 100).toFixed(0)}%</span>
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

            <div className="pt-2 text-right">
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
