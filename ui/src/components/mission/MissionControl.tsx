import React, { useState } from 'react';
import { EventItem, FindingItem, TaskItem } from '../../api';
import { useOrchestrationModel } from '../../orchestration/useOrchestrationModel';
import { PhaseStepper } from './PhaseStepper';
import { AgentRoster } from './AgentRoster';
import { OrchestrationGraph } from './OrchestrationGraph';
import { WarRoom } from './WarRoom';
import { EventFeed } from '../EventFeed';
import { FailureInjector, StagedFault } from '../FailureInjectorModal';

export interface MissionControlProps {
  choreographedEvents: EventItem[];
  rawEvents: EventItem[];
  tasks: Record<string, TaskItem>;
  findings: FindingItem[];
  workflowStatus: string;
  playbackSpeed: 'cinematic' | 'instant';
  onTogglePlaybackSpeed: (speed: 'cinematic' | 'instant') => void;
  onSkipToReport: () => void;
  onOpenReport: () => void;
  onInspectFinding: (finding: FindingItem) => void;
  onInjectFault: (agent: string, mode: string, persist?: boolean, failAttempts?: number) => Promise<void> | void;
  stagedFault: StagedFault | null;
  onSetStagedFault: (fault: StagedFault | null) => void;
}

export const MissionControl: React.FC<MissionControlProps> = ({
  choreographedEvents,
  rawEvents,
  tasks,
  findings,
  workflowStatus,
  playbackSpeed,
  onTogglePlaybackSpeed,
  onSkipToReport,
  onOpenReport,
  onInspectFinding,
  onInjectFault,
  stagedFault,
  onSetStagedFault
}) => {
  const [controlTab, setControlTab] = useState<'chaos' | 'telemetry'>('chaos');
  const [isSplitView, setIsSplitView] = useState(false);

  // Derive model state from choreographed events
  const model = useOrchestrationModel(choreographedEvents, tasks, findings, workflowStatus);

  const isIdle = workflowStatus === 'idle';
  const isComplete = workflowStatus === 'completed' || workflowStatus === 'degraded';

  const handleInspectAgent = (agentId: string) => {
    const finding = findings.find((f) => (f.agent || '').toLowerCase() === agentId.toLowerCase());
    if (finding) {
      onInspectFinding(finding);
    }
  };

  return (
    <div className="flex flex-col gap-5 w-full">
      {/* 1. Top Phase Stepper & Live Narration Ticker */}
      <PhaseStepper
        currentPhase={model.phase}
        narration={model.narration}
        activeAgentsCount={model.activeAgentsCount}
        playbackSpeed={playbackSpeed}
        onTogglePlaybackSpeed={onTogglePlaybackSpeed}
        onSkipToReport={onSkipToReport}
        isComplete={isComplete}
      />

      {/* 2. Row 1: Agent Roster (Left) + Multi-Agent Orchestration Topology (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-[460px]">
        {/* Left Column: Agent Roster (col-span-4 or 3 on xl) */}
        <div className="lg:col-span-4 xl:col-span-3 h-[460px]">
          <AgentRoster
            agentStates={model.agentStates}
            showBackup={model.showBackup}
            backupState={model.backupState}
            onInspectAgent={handleInspectAgent}
          />
        </div>

        {/* Right Column: Dynamic SVG DAG Graph (col-span-8 or 9 on xl) */}
        <div className="lg:col-span-8 xl:col-span-9 h-[460px]">
          <OrchestrationGraph
            tasks={tasks}
            findings={findings}
            nodeStatusOverrides={model.nodeStatusOverrides}
            completedNodeIds={model.completedNodeIds}
            activePackets={model.activePackets}
            onSelectFinding={onInspectFinding}
            isIdleStandby={isIdle}
          />
        </div>
      </div>

      {/* 3. Row 2: Executive War Room (Left) + Live Fault Injection & Event Telemetry (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-[520px]">
        {/* Left Column: Executive War Room (placed below the top two columns) */}
        <div className="lg:col-span-7 xl:col-span-7 h-[520px]">
          <WarRoom
            messages={model.messages}
            simMatrix={model.simMatrix}
            completedSimCount={model.completedSimCount}
            isInstant={playbackSpeed === 'instant'}
            onOpenReport={onOpenReport}
            onInspectFinding={onInspectFinding}
          />
        </div>

        {/* Right Column: Live Fault Injection & Agent Recovery + Event Telemetry */}
        <div className="lg:col-span-5 xl:col-span-5 h-[520px] flex flex-col bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          {/* Header Bar with Mode Switcher & Armed Status */}
          <div className="px-4 py-2.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setControlTab('chaos')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer ${
                  controlTab === 'chaos' && !isSplitView
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>⚡ Live Fault Injection</span>
                {stagedFault && (
                  <span className="w-2 h-2 rounded-full bg-rose-400 animate-ping" />
                )}
              </button>

              <button
                onClick={() => setControlTab('telemetry')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer ${
                  controlTab === 'telemetry' && !isSplitView
                    ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>📟 Live Event Stream</span>
                <span className="text-[10px] bg-slate-800 px-1.5 py-0.2 rounded text-slate-300 font-bold">
                  {rawEvents.length}
                </span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              {stagedFault && (
                <span className="text-[9px] font-mono text-rose-300 bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 rounded-full font-bold uppercase animate-pulse">
                  Armed: {stagedFault.agent}
                </span>
              )}
              <button
                onClick={() => setIsSplitView(!isSplitView)}
                className={`text-[10px] font-mono px-2 py-1 rounded border transition cursor-pointer ${
                  isSplitView
                    ? 'bg-brand-500/20 text-brand-300 border-brand-500/40 font-bold'
                    : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
                title="Toggle split view to show Fault Injection and Event Telemetry simultaneously"
              >
                {isSplitView ? 'Tab View' : 'Split View'}
              </button>
            </div>
          </div>

          {/* Content Pane: Split view (both stacked) or Tabbed view */}
          {isSplitView ? (
            <div className="flex-1 flex flex-col overflow-y-auto divide-y divide-slate-800 scrollbar-thin scrollbar-thumb-slate-800">
              <div className="p-3 bg-slate-950/40">
                <FailureInjector
                  onInject={onInjectFault}
                  stagedFault={stagedFault}
                  onSetStagedFault={onSetStagedFault}
                  workflowStatus={workflowStatus}
                />
              </div>
              <div className="p-3 bg-slate-950/60 flex-1 min-h-[220px]">
                <EventFeed events={rawEvents} />
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-slate-800">
              {controlTab === 'chaos' ? (
                <FailureInjector
                  onInject={onInjectFault}
                  stagedFault={stagedFault}
                  onSetStagedFault={onSetStagedFault}
                  workflowStatus={workflowStatus}
                />
              ) : (
                <EventFeed events={rawEvents} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
