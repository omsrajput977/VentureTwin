import React, { useRef, useEffect, useState, useCallback } from 'react';
import { WarRoomMessage, SimulationCell } from '../../orchestration/useOrchestrationModel';
import { FindingBubble } from './messages/FindingBubble';
import { SkepticChallenge } from './messages/SkepticChallenge';
import { RebuttalBubble } from './messages/RebuttalBubble';
import { ConflictCard } from './messages/ConflictCard';
import { SimulationMatrix } from './messages/SimulationMatrix';
import { VerificationChecklist } from './messages/VerificationChecklist';
import { SystemNotice } from './messages/SystemNotice';
import { SealedCard } from './messages/SealedCard';
import { FindingItem } from '../../api';

interface WarRoomProps {
  messages: WarRoomMessage[];
  simMatrix: SimulationCell[];
  completedSimCount: number;
  isInstant?: boolean;
  onOpenReport: () => void;
  onInspectFinding?: (finding: FindingItem) => void;
}

export const WarRoom: React.FC<WarRoomProps> = ({
  messages,
  simMatrix,
  completedSimCount,
  isInstant = false,
  onOpenReport,
  onInspectFinding
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false);

  // Auto-scroll logic
  const scrollToBottom = useCallback(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: isInstant ? 'auto' : 'smooth'
      });
      setUserHasScrolledUp(false);
    }
  }, [isInstant]);

  useEffect(() => {
    if (!userHasScrolledUp) {
      scrollToBottom();
    }
  }, [messages.length, completedSimCount, userHasScrolledUp, scrollToBottom]);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    if (distanceFromBottom > 80) {
      setUserHasScrolledUp(true);
    } else {
      setUserHasScrolledUp(false);
    }
  };

  return (
    <div className="relative flex flex-col h-full bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-lg backdrop-blur-sm">
      {/* War Room Header */}
      <div className="px-4 py-3 border-b border-slate-800/90 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="text-xs font-bold text-slate-200 tracking-wider font-mono uppercase">
            Executive War Room
          </h3>
          <span className="text-[10px] text-slate-500 font-mono">live synthesis</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-slate-400">
            {messages.length} contributions
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-3.5 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent"
      >
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-2">
            <div className="w-10 h-10 rounded-full bg-slate-800/60 border border-slate-700/60 flex items-center justify-center text-slate-400 text-lg">
              💬
            </div>
            <p className="text-xs font-mono text-slate-400">Awaiting strategic intake prompt...</p>
            <p className="text-[11px] text-slate-600 max-w-xs">
              Agent findings, skeptic challenges, simulation runs, and verification audits will stream here in real time.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            switch (msg.type) {
              case 'finding':
                if (!msg.finding) return null;
                return (
                  <FindingBubble
                    key={msg.id}
                    finding={msg.finding}
                    agent={msg.agent}
                    timestamp={msg.timestamp}
                    isInstant={isInstant}
                    onInspect={() => msg.finding && onInspectFinding && onInspectFinding(msg.finding)}
                  />
                );

              case 'challenge':
                return (
                  <SkepticChallenge
                    key={msg.id}
                    finding={msg.finding}
                    content={msg.content}
                    timestamp={msg.timestamp}
                  />
                );

              case 'rebuttal':
                if (!msg.rebuttal) return null;
                return (
                  <RebuttalBubble
                    key={msg.id}
                    rebuttal={msg.rebuttal}
                    timestamp={msg.timestamp}
                  />
                );

              case 'conflict':
                if (!msg.conflict) return null;
                return (
                  <ConflictCard
                    key={msg.id}
                    conflict={msg.conflict}
                    timestamp={msg.timestamp}
                  />
                );

              case 'simulation':
                return (
                  <SimulationMatrix
                    key={msg.id}
                    matrix={simMatrix}
                    completedCount={completedSimCount}
                  />
                );

              case 'verification':
                if (!msg.verification) return null;
                return (
                  <VerificationChecklist
                    key={msg.id}
                    verification={msg.verification}
                    timestamp={msg.timestamp}
                  />
                );

              case 'system':
                return (
                  <SystemNotice
                    key={msg.id}
                    title={msg.title}
                    content={msg.content}
                    agent={msg.agent}
                    timestamp={msg.timestamp}
                  />
                );

              case 'sealed':
                return (
                  <SealedCard
                    key={msg.id}
                    sealed={msg.sealed}
                    timestamp={msg.timestamp}
                    onOpenReport={onOpenReport}
                  />
                );

              default:
                return null;
            }
          })
        )}
      </div>

      {/* Floating Jump to Latest Button */}
      {userHasScrolledUp && (
        <div className="absolute bottom-3 right-4 z-10 animate-bounce">
          <button
            onClick={scrollToBottom}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-teal-500/90 hover:bg-teal-400 text-slate-950 font-mono text-[11px] font-bold shadow-lg shadow-teal-500/30 transition-all cursor-pointer"
          >
            <span>&darr; Jump to latest</span>
          </button>
        </div>
      )}
    </div>
  );
};

