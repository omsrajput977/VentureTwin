import React from 'react';
import { AgentRosterState } from '../../orchestration/useOrchestrationModel';
import { getAgentMeta } from '../../orchestration/agentMeta';

interface AgentRosterProps {
  agentStates: Record<string, AgentRosterState>;
  showBackup: boolean;
  backupState: AgentRosterState;
  onInspectAgent?: (agentId: string) => void;
}

const ROSTER_ORDER = ['supervisor', 'cfo', 'growth', 'cto', 'customer', 'product', 'skeptic'];

export const AgentRoster: React.FC<AgentRosterProps> = ({
  agentStates,
  showBackup,
  backupState,
  onInspectAgent
}) => {
  return (
    <div className="flex flex-col h-full bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-lg backdrop-blur-sm">
      {/* Roster Header */}
      <div className="px-3.5 py-3 border-b border-slate-800/90 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-200 tracking-wider font-mono uppercase">
            Agent Roster
          </span>
          <span className="text-[10px] text-slate-500 font-mono">
            ({showBackup ? '8' : '7'} agents)
          </span>
        </div>
        <span className="text-[9px] font-mono text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/30">
          Autonomous
        </span>
      </div>

      {/* Roster List Scroll */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
        {ROSTER_ORDER.map((agentId) => {
          const agent = agentStates[agentId];
          if (!agent) return null;
          const meta = getAgentMeta(agentId);

          return (
            <AgentCard
              key={agentId}
              agent={agent}
              meta={meta}
              onClick={() => onInspectAgent && onInspectAgent(agentId)}
            />
          );
        })}

        {/* 8th Failover Backup Analyst if engaged */}
        {showBackup && (
          <div className="pt-1 border-t border-purple-500/30">
            <AgentCard
              agent={backupState}
              meta={getAgentMeta('backup')}
              isBackup
              onClick={() => onInspectAgent && onInspectAgent('backup')}
            />
          </div>
        )}
      </div>
    </div>
  );
};

interface AgentCardProps {
  agent: AgentRosterState;
  meta: ReturnType<typeof getAgentMeta>;
  isBackup?: boolean;
  onClick?: () => void;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, meta, isBackup = false, onClick }) => {
  const { status, currentTool, elapsedSeconds, recommendation, confidence, attempts } = agent;

  // Halo / Border styling
  let haloClass = 'border-slate-700 bg-slate-800/50';
  let badgeText = 'Standing by';
  let badgeColor = 'text-slate-500 bg-slate-900 border-slate-800';

  if (status === 'working') {
    haloClass = 'border-teal-400 shadow-[0_0_10px_rgba(20,184,166,0.5)] animate-pulse bg-teal-500/10';
    badgeText = 'Working';
    badgeColor = 'text-teal-300 bg-teal-500/20 border-teal-500/40';
  } else if (status === 'retrying') {
    haloClass = 'border-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.5)] animate-pulse bg-amber-500/10';
    badgeText = `Retry ${attempts}/3`;
    badgeColor = 'text-amber-300 bg-amber-500/20 border-amber-500/40';
  } else if (status === 'failed') {
    haloClass = 'border-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)] bg-rose-500/10';
    badgeText = 'Fault';
    badgeColor = 'text-rose-300 bg-rose-500/20 border-rose-500/40';
  } else if (status === 'backup') {
    haloClass = 'border-purple-400 shadow-[0_0_10px_rgba(192,132,252,0.5)] bg-purple-500/10';
    badgeText = 'Recovered (Backup)';
    badgeColor = 'text-purple-300 bg-purple-500/20 border-purple-500/40';
  } else if (status === 'done') {
    haloClass = 'border-emerald-500/80 bg-emerald-500/5';
    badgeText = 'Done';
    badgeColor = 'text-emerald-300 bg-emerald-500/20 border-emerald-500/40';
  }

  const confidencePct = confidence !== undefined ? Math.round(confidence * 100) : undefined;

  return (
    <div
      onClick={onClick}
      className={`group relative p-2.5 rounded-xl border transition-all cursor-pointer ${
        isBackup
          ? 'bg-purple-950/20 border-purple-500/40 hover:border-purple-400'
          : 'bg-slate-900/90 border-slate-800/90 hover:border-slate-700 hover:bg-slate-850'
      }`}
    >
      <div className="flex items-start gap-2.5">
        {/* Avatar with dynamic halo */}
        <div className="relative shrink-0">
          <img
            src={agent.avatar}
            alt={agent.name}
            className={`w-9 h-9 rounded-full p-0.5 border-2 transition-all ${haloClass}`}
          />
          {status === 'done' && (
            <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-500 border border-slate-900 flex items-center justify-center text-[8px] text-slate-950 font-bold">
              ✓
            </div>
          )}
          {status === 'working' && (
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-teal-400 animate-ping opacity-75" />
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1 mb-0.5">
            <span className="text-xs font-bold text-slate-100 truncate">{agent.name}</span>
            <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded border uppercase font-medium ${badgeColor}`}>
              {badgeText}
            </span>
          </div>

          <div className="text-[10px] text-slate-400 font-sans truncate mb-1">
            {agent.role}
          </div>

          {/* Dynamic Status / Tool / Live elapsed line */}
          {status === 'working' && (
            <div className="flex items-center justify-between text-[10px] font-mono bg-slate-950 px-1.5 py-0.5 rounded border border-teal-500/30 text-teal-300">
              <span className="truncate max-w-[130px] flex items-center gap-1">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-teal-400 animate-spin" />
                {currentTool}()
              </span>
              <span className="text-teal-400 font-bold shrink-0">{elapsedSeconds}s</span>
            </div>
          )}

          {status === 'retrying' && (
            <div className="text-[10px] font-mono text-amber-300 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-500/30">
              Recovering: attempt {attempts} of 3...
            </div>
          )}

          {status === 'failed' && (
            <div className="text-[10px] font-mono text-rose-300 bg-rose-950/40 px-1.5 py-0.5 rounded border border-rose-500/30">
              Process crash &middot; Failover armed
            </div>
          )}

          {status === 'done' && (
            <div className="space-y-1 pt-0.5">
              {recommendation && (
                <div className="flex items-center justify-between text-[9px] font-mono">
                  <span className="text-slate-400 uppercase truncate max-w-[120px]">
                    {recommendation.replace(/_/g, ' ')}
                  </span>
                  {confidencePct !== undefined && (
                    <span className="text-teal-400 font-bold">{confidencePct}%</span>
                  )}
                </div>
              )}
              {confidencePct !== undefined && (
                <div className="w-full h-1 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="h-full bg-teal-400 rounded-full"
                    style={{ width: `${confidencePct}%` }}
                  />
                </div>
              )}
            </div>
          )}

          {status === 'standby' && (
            <div className="text-[10px] font-mono text-slate-500">
              Awaiting dispatch
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

