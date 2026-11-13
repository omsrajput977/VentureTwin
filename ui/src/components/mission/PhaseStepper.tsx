import React from 'react';
import { OrchestrationPhase } from '../../orchestration/useOrchestrationModel';

interface PhaseStepperProps {
  currentPhase: OrchestrationPhase;
  narration: string;
  activeAgentsCount: number;
  playbackSpeed: 'cinematic' | 'instant';
  onTogglePlaybackSpeed: (speed: 'cinematic' | 'instant') => void;
  onSkipToReport: () => void;
  isComplete: boolean;
}

interface StepMeta {
  key: OrchestrationPhase;
  label: string;
  num: number;
}

const PHASES: StepMeta[] = [
  { key: 'plan', label: 'Plan', num: 1 },
  { key: 'analyze', label: 'Analyze', num: 2 },
  { key: 'challenge', label: 'Challenge', num: 3 },
  { key: 'resolve', label: 'Resolve', num: 4 },
  { key: 'simulate', label: 'Simulate', num: 5 },
  { key: 'verify', label: 'Verify', num: 6 },
  { key: 'seal', label: 'Seal', num: 7 }
];

export const PhaseStepper: React.FC<PhaseStepperProps> = ({
  currentPhase,
  narration,
  activeAgentsCount,
  playbackSpeed,
  onTogglePlaybackSpeed,
  onSkipToReport,
  isComplete
}) => {
  const currentIdx = PHASES.findIndex((p) => p.key === currentPhase);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-3 shadow-md backdrop-blur-sm space-y-2.5">
      {/* Top Bar: Stepper & Controls */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {/* 7-Step Stepper */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {PHASES.map((step, idx) => {
            const isCompleted = isComplete || idx < currentIdx;
            const isCurrent = !isComplete && idx === currentIdx;

            return (
              <React.Fragment key={step.key}>
                <div
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono transition-all ${
                    isCurrent
                      ? 'bg-teal-500/20 border border-teal-400 text-teal-300 shadow-[0_0_12px_rgba(20,184,166,0.35)]'
                      : isCompleted
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium'
                      : 'bg-slate-950/60 border border-slate-800/80 text-slate-500'
                  }`}
                >
                  <span
                    className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isCurrent
                        ? 'bg-teal-400 text-slate-950 animate-pulse'
                        : isCompleted
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {isCompleted ? '✓' : step.num}
                  </span>
                  <span className="font-semibold">{step.label}</span>
                </div>

                {idx < PHASES.length - 1 && (
                  <span
                    className={`text-[10px] font-mono select-none ${
                      idx < currentIdx || isComplete ? 'text-emerald-500/60' : 'text-slate-700'
                    }`}
                  >
                    &rarr;
                  </span>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Right Controls: Active Agent Badge & Playback Controls */}
        <div className="flex items-center gap-2">
          {/* Active Agents Badge */}
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800 text-xs font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                activeAgentsCount > 0 ? 'bg-teal-400 animate-ping' : 'bg-slate-600'
              }`}
            />
            <span className="text-slate-400">Agents:</span>
            <span className="font-bold text-teal-300">{activeAgentsCount}/7 active</span>
          </div>

          {/* Speed Toggle: Cinematic / Instant */}
          <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px] font-mono">
            <button
              onClick={() => onTogglePlaybackSpeed('cinematic')}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                playbackSpeed === 'cinematic'
                  ? 'bg-teal-500 text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Cinematic
            </button>
            <button
              onClick={() => onTogglePlaybackSpeed('instant')}
              className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                playbackSpeed === 'instant'
                  ? 'bg-teal-500 text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Instant
            </button>
          </div>

          {/* Skip to Report Button */}
          {!isComplete && (
            <button
              onClick={onSkipToReport}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 text-[11px] font-mono text-slate-300 hover:text-white transition-all cursor-pointer"
              title="Skip choreography animation and view complete findings"
            >
              Skip to Report &rarr;
            </button>
          )}
        </div>
      </div>

      {/* Narration Ticker */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-950/80 rounded-xl border border-slate-800/80 text-xs font-mono">
        <span className="text-teal-400 font-bold shrink-0">SUPERVISOR:</span>
        <span className="text-slate-300 truncate font-sans">{narration}</span>
      </div>
    </div>
  );
};

