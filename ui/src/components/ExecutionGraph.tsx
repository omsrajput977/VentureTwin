import React from 'react';
import { TaskItem, FindingItem } from '../api';

interface Props {
  tasks: Record<string, TaskItem>;
  findings: FindingItem[];
  onSelectFinding: (finding: FindingItem) => void;
}

export const ExecutionGraph: React.FC<Props> = ({ tasks, findings, onSelectFinding }) => {
  const taskList = Object.values(tasks);

  if (taskList.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 text-center text-slate-500">
        No active execution graph. Submit a decision query above to launch the supervisor engine.
      </div>
    );
  }

  const getStatusBadge = (t: TaskItem, finding?: FindingItem) => {
    if (finding?.recovered_via_backup) {
      return (
        <span className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full font-semibold">
          🛡️ Recovered (Backup)
        </span>
      );
    }
    if (finding?.degraded) {
      return (
        <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-full font-semibold">
          ⚠️ Degraded (Prior)
        </span>
      );
    }
    if (t.status === 'done' && t.attempts > 1) {
      return (
        <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full">
          Done (Retry {t.attempts})
        </span>
      );
    }
    switch (t.status) {
      case 'running':
        return <span className="px-2 py-0.5 text-xs bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded-full animate-pulse">Running</span>;
      case 'retrying':
        return <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full animate-pulse">Retrying</span>;
      case 'done':
        return <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">Done</span>;
      case 'failed':
        return <span className="px-2 py-0.5 text-xs bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-full">Failed</span>;
      default:
        return <span className="px-2 py-0.5 text-xs bg-slate-800 text-slate-400 rounded-full">Pending</span>;
    }
  };

  const parallelAnalysisTasks = taskList.filter(t => t.depends_on.length === 0);
  const downstreamTasks = taskList.filter(t => t.depends_on.length > 0);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h3 className="font-semibold text-white">Multi-Agent Orchestration DAG</h3>
          <p className="text-xs text-slate-400">Parallel agent execution and downstream synthesis pipeline</p>
        </div>
        <div className="text-xs text-slate-400">
          Click any completed node to inspect agent findings
        </div>
      </div>

      <div className="space-y-6 pt-5">
        {/* Tier 1: Parallel Specialist Agents */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Stage 1: Parallel Functional Evaluation</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {parallelAnalysisTasks.map((t) => {
              const finding = findings.find(f => f.task_id === t.id);
              const isRecovered = finding?.recovered_via_backup;
              const isDegraded = finding?.degraded;
              return (
                <div
                  key={t.id}
                  onClick={() => finding && onSelectFinding(finding)}
                  className={`p-3.5 rounded-xl border transition cursor-pointer ${
                    isRecovered
                      ? 'bg-purple-950/30 border-purple-500/50 hover:bg-purple-900/40'
                      : isDegraded
                      ? 'bg-amber-950/30 border-amber-500/50 hover:bg-amber-900/40'
                      : finding
                      ? 'bg-slate-950/80 border-slate-700 hover:border-brand-500/50 hover:bg-slate-800/50'
                      : 'bg-slate-950/40 border-slate-800/80 cursor-default'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-white uppercase">{t.owner_agent}</span>
                    {getStatusBadge(t, finding)}
                  </div>
                  <div className="text-[11px] text-slate-400 line-clamp-2">
                    {finding ? (
                      <>
                        {isRecovered && <span className="text-purple-300 font-semibold mr-1">🛡️ [Backup]</span>}
                        {isDegraded && <span className="text-amber-300 font-semibold mr-1">⚠️ [Fallback]</span>}
                        {finding.claim}
                      </>
                    ) : (
                      `Evaluating ${t.owner_agent} domain parameters...`
                    )}
                  </div>
                  {finding && (
                    <div className="mt-2 text-[10px] text-brand-400 flex items-center justify-between">
                      <span>Rec: {finding.recommendation}</span>
                      <span>{(finding.confidence * 100).toFixed(0)}% conf</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Tier 2: Downstream Verification, Simulation & Synthesis */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Stage 2: Audit, Conflict Resolution, Simulation & Synthesis</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {downstreamTasks.map((t) => {
              const finding = findings.find(f => f.task_id === t.id);
              return (
                <div
                  key={t.id}
                  onClick={() => finding && onSelectFinding(finding)}
                  className={`p-3.5 rounded-xl border transition ${
                    t.status === 'done'
                      ? 'bg-slate-950/80 border-slate-700 hover:border-brand-500/50'
                      : 'bg-slate-950/40 border-slate-800/80'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-white">
                      {t.id.replace('task_', '').replace(/_/g, ' ')}
                    </span>
                    {getStatusBadge(t, finding)}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Agent: <span className="text-slate-300 font-medium">{t.owner_agent}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    Depends on: {t.depends_on.length} node(s)
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

