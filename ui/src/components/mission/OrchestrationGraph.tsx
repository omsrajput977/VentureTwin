import React from 'react';
import { FindingItem, TaskItem } from '../../api';
import { getAgentMeta } from '../../orchestration/agentMeta';
import { ActivePacket } from '../../orchestration/useOrchestrationModel';

interface Props {
  tasks: Record<string, TaskItem>;
  findings: FindingItem[];
  nodeStatusOverrides: Record<string, string>;
  completedNodeIds: Set<string>;
  activePackets: ActivePacket[];
  onSelectFinding: (finding: FindingItem) => void;
  isIdleStandby?: boolean;
}

interface NodeCoord {
  id: string;
  name: string;
  agent: string;
  x: number;
  y: number;
  radius: number;
  kind: 'supervisor' | 'specialist' | 'synthesis' | 'seal';
}

export const OrchestrationGraph: React.FC<Props> = ({
  tasks,
  findings,
  nodeStatusOverrides,
  completedNodeIds,
  activePackets,
  onSelectFinding,
  isIdleStandby = false
}) => {
  // Static topological coordinates (viewBox 0 0 980 380)
  const nodes: NodeCoord[] = [
    // Hub
    { id: 'hub_supervisor', name: 'Supervisor Hub', agent: 'supervisor', x: 70, y: 160, radius: 28, kind: 'supervisor' },

    // Layer 1: Specialists
    { id: 'task_cfo_analysis', name: 'CFO', agent: 'cfo', x: 250, y: 40, radius: 24, kind: 'specialist' },
    { id: 'task_growth_analysis', name: 'Growth', agent: 'growth', x: 250, y: 100, radius: 24, kind: 'specialist' },
    { id: 'task_cto_analysis', name: 'CTO', agent: 'cto', x: 250, y: 160, radius: 24, kind: 'specialist' },
    { id: 'task_customer_analysis', name: 'Customer', agent: 'customer', x: 250, y: 220, radius: 24, kind: 'specialist' },
    { id: 'task_product_analysis', name: 'Product', agent: 'product', x: 250, y: 280, radius: 24, kind: 'specialist' },

    // Layer 2: Audit & Resolution
    { id: 'task_skeptic_audit', name: 'Skeptic Audit', agent: 'skeptic', x: 450, y: 160, radius: 26, kind: 'specialist' },
    { id: 'task_agent_discussion', name: 'Discussion', agent: 'supervisor', x: 600, y: 160, radius: 24, kind: 'synthesis' },
    { id: 'task_conflict_resolution', name: 'Conflict Res', agent: 'supervisor', x: 740, y: 160, radius: 24, kind: 'synthesis' },

    // Layer 3: Simulation & Verification
    { id: 'task_simulation_engine', name: 'Simulation Engine', agent: 'supervisor', x: 880, y: 210, radius: 26, kind: 'synthesis' },
    { id: 'task_report_draft', name: 'Report Draft', agent: 'supervisor', x: 740, y: 310, radius: 22, kind: 'synthesis' },
    { id: 'task_workflow_verification', name: 'Verification', agent: 'skeptic', x: 550, y: 310, radius: 24, kind: 'synthesis' },
    { id: 'task_report_finalize', name: 'Report Sealed', agent: 'supervisor', x: 360, y: 310, radius: 26, kind: 'seal' }
  ];

  const specialistIds = [
    'task_cfo_analysis',
    'task_growth_analysis',
    'task_cto_analysis',
    'task_customer_analysis',
    'task_product_analysis'
  ];

  const allSpecialistsDone = specialistIds.every(
    (id) => completedNodeIds.has(id) || tasks[id]?.status === 'done'
  );

  const getNodeState = (node: NodeCoord) => {
    if (isIdleStandby) return 'standby';
    if (node.id === 'hub_supervisor') return 'done';

    if (nodeStatusOverrides[node.id]) {
      return nodeStatusOverrides[node.id];
    }

    const t = tasks[node.id];
    if (t?.status === 'done' || completedNodeIds.has(node.id)) {
      return 'done';
    }
    if (t?.status === 'running') {
      return 'running';
    }
    if (t?.status === 'failed') {
      return 'failed';
    }
    if (t?.status === 'retrying') {
      return 'retrying';
    }
    return 'pending';
  };

  return (
    <div className="relative w-full h-full bg-slate-950/70 rounded-2xl border border-slate-800/80 p-3 flex flex-col justify-between overflow-hidden shadow-2xl">
      {/* Top Overlay Legend */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 z-10 px-2 pt-1 border-b border-slate-900 pb-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-200 tracking-wide uppercase text-[10px]">
            {isIdleStandby ? 'Standby DAG Blueprint' : 'Multi-Agent Orchestration Topology'}
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-[10px] text-slate-400">11 Distributed Tasks · Dependency Order</span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span> Done
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping inline-block"></span> Running
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-purple-400 inline-block"></span> Backup
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400 inline-block"></span> Retrying
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="flex-1 w-full relative flex items-center justify-center min-h-[300px]">
        <svg
          viewBox="0 0 980 360"
          className="w-full h-full max-h-[360px] select-none"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Gradients */}
            <linearGradient id="gradTeal" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#14b8a6" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
            <linearGradient id="gradRose" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f43f5e" />
              <stop offset="100%" stopColor="#e11d48" />
            </linearGradient>
            <linearGradient id="gradPurple" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#7e22ce" />
            </linearGradient>

            {/* Glowing filter */}
            <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Keyframe animations for packets and rings */}
            <style>
              {`
                @keyframes pulseGlow {
                  0%, 100% { opacity: 0.4; transform: scale(1); }
                  50% { opacity: 0.9; transform: scale(1.08); }
                }
                @keyframes rotateArc {
                  from { transform: rotate(0deg); }
                  to { transform: rotate(360deg); }
                }
                @keyframes dashTravel {
                  to { stroke-dashoffset: -32; }
                }
                .rotating-arc {
                  transform-origin: center;
                  animation: rotateArc 2s linear infinite;
                }
                .active-edge {
                  stroke-dasharray: 6, 6;
                  animation: dashTravel 1s linear infinite;
                }
                .barrier-line {
                  transition: stroke 0.5s ease, stroke-width 0.5s ease;
                }
              `}
            </style>
          </defs>

          {/* 1. Static and Active Edges */}
          <g className="edges-layer" opacity={isIdleStandby ? 0.35 : 0.8}>
            {/* Hub to 5 Specialists */}
            {specialistIds.map((targetId) => {
              const targetNode = nodes.find((n) => n.id === targetId);
              if (!targetNode) return null;
              const isRunning = getNodeState(targetNode) === 'running';
              const isDone = getNodeState(targetNode) === 'done' || getNodeState(targetNode) === 'backup';

              return (
                <path
                  key={`edge_hub_${targetId}`}
                  d={`M 70 160 C 140 160, 160 ${targetNode.y}, ${targetNode.x - targetNode.radius} ${targetNode.y}`}
                  fill="none"
                  stroke={isRunning ? '#14b8a6' : isDone ? '#0f766e' : '#334155'}
                  strokeWidth={isRunning ? 2.5 : 1.5}
                  className={isRunning ? 'active-edge' : ''}
                />
              );
            })}

            {/* 5 Specialists to Converging Barrier */}
            {specialistIds.map((specId) => {
              const specNode = nodes.find((n) => n.id === specId);
              if (!specNode) return null;
              const isDone = getNodeState(specNode) === 'done' || getNodeState(specNode) === 'backup';

              return (
                <path
                  key={`edge_barrier_${specId}`}
                  d={`M ${specNode.x + specNode.radius} ${specNode.y} L 370 ${specNode.y} L 370 160`}
                  fill="none"
                  stroke={isDone ? '#10b981' : '#334155'}
                  strokeWidth={isDone ? 2 : 1}
                  opacity={isDone ? 0.9 : 0.4}
                />
              );
            })}

            {/* Converging Barrier line into Skeptic */}
            <line
              x1="370"
              y1="40"
              x2="370"
              y2="280"
              stroke={allSpecialistsDone ? '#10b981' : '#475569'}
              strokeWidth={allSpecialistsDone ? 3 : 1.5}
              strokeDasharray={allSpecialistsDone ? 'none' : '4, 4'}
              className="barrier-line"
            />
            <path
              d="M 370 160 L 424 160"
              fill="none"
              stroke={allSpecialistsDone ? '#f43f5e' : '#475569'}
              strokeWidth={allSpecialistsDone ? 2.5 : 1.5}
            />

            {/* Skeptic to Discussion */}
            <line
              x1="476"
              y1="160"
              x2="576"
              y2="160"
              fill="none"
              stroke={completedNodeIds.has('task_skeptic_audit') ? '#14b8a6' : '#334155'}
              strokeWidth={1.8}
            />

            {/* Discussion to Conflict Resolution */}
            <line
              x1="624"
              y1="160"
              x2="716"
              y2="160"
              fill="none"
              stroke={completedNodeIds.has('task_agent_discussion') ? '#14b8a6' : '#334155'}
              strokeWidth={1.8}
            />

            {/* Conflict to Simulation Engine */}
            <path
              d="M 764 160 C 820 160, 840 210, 854 210"
              fill="none"
              stroke={completedNodeIds.has('task_conflict_resolution') ? '#14b8a6' : '#334155'}
              strokeWidth={2}
            />

            {/* Simulation to Report Draft */}
            <path
              d="M 880 236 C 880 310, 820 310, 762 310"
              fill="none"
              stroke={completedNodeIds.has('task_simulation_engine') ? '#14b8a6' : '#334155'}
              strokeWidth={2}
            />

            {/* Draft to Verification */}
            <line
              x1="718"
              y1="310"
              x2="574"
              y2="310"
              stroke={completedNodeIds.has('task_report_draft') ? '#14b8a6' : '#334155'}
              strokeWidth={2}
            />

            {/* Verification to Report Finalize */}
            <line
              x1="526"
              y1="310"
              x2="386"
              y2="310"
              stroke={completedNodeIds.has('task_workflow_verification') ? '#10b981' : '#334155'}
              strokeWidth={2.5}
            />

            {/* Sealed Loopback Line to Hub */}
            <path
              d="M 334 310 C 180 310, 70 260, 70 188"
              fill="none"
              stroke={completedNodeIds.has('task_report_finalize') ? '#10b981' : '#1e293b'}
              strokeDasharray="4, 4"
              strokeWidth={1.5}
            />
          </g>

          {/* 2. Traveling Animated Packets */}
          {!isIdleStandby &&
            activePackets.map((pkt) => {
              const targetNode = nodes.find((n) => n.id === pkt.target);
              if (!targetNode) return null;
              return (
                <circle
                  key={pkt.id}
                  cx={(70 + targetNode.x) / 2}
                  cy={(160 + targetNode.y) / 2}
                  r="4.5"
                  fill={pkt.color}
                  filter="url(#glowEffect)"
                >
                  <animate
                    attributeName="opacity"
                    values="0.3;1;0.3"
                    dur="1.2s"
                    repeatCount="indefinite"
                  />
                </circle>
              );
            })}

          {/* 3. Graph Nodes */}
          {nodes.map((node) => {
            const state = getNodeState(node);
            const meta = getAgentMeta(node.agent);
            const isClickable = state === 'done' || state === 'backup';
            const finding = findings.find((f) => f.task_id === node.id);

            // Ring styling based on node state
            let ringStroke = '#334155';
            let strokeDash = 'none';
            let isSpinning = false;
            let ringFill = '#0f172a';

            if (isIdleStandby) {
              ringStroke = '#334155';
              strokeDash = '4, 4';
              ringFill = 'rgba(15, 23, 42, 0.6)';
            } else if (state === 'done') {
              ringStroke = meta.color.primary;
              ringFill = '#022c22';
            } else if (state === 'running') {
              ringStroke = meta.color.primary;
              isSpinning = true;
              ringFill = meta.color.bg;
            } else if (state === 'backup') {
              ringStroke = '#a855f7';
              ringFill = 'rgba(168, 85, 247, 0.2)';
            } else if (state === 'retrying') {
              ringStroke = '#f59e0b';
              ringFill = 'rgba(245, 158, 11, 0.2)';
              strokeDash = '3, 3';
            } else if (state === 'failed') {
              ringStroke = '#f43f5e';
              ringFill = 'rgba(244, 63, 94, 0.2)';
            } else {
              strokeDash = '3, 3';
              ringFill = '#0f172a';
            }

            return (
              <g
                key={node.id}
                onClick={() => {
                  if (finding && isClickable) onSelectFinding(finding);
                }}
                className={`transition-transform duration-200 ${
                  isClickable ? 'cursor-pointer hover:scale-110' : 'cursor-default'
                }`}
                tabIndex={isClickable ? 0 : -1}
                aria-label={`${node.name} (${state})`}
              >
                {/* Node Background Disc */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.radius}
                  fill={ringFill}
                  stroke={ringStroke}
                  strokeWidth={state === 'done' || state === 'backup' ? 2.5 : 1.5}
                  strokeDasharray={strokeDash}
                />

                {/* Rotating Arc for Running State */}
                {isSpinning && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.radius + 3}
                    fill="none"
                    stroke={meta.color.primary}
                    strokeWidth="2"
                    strokeDasharray="25 60"
                    className="rotating-arc"
                  />
                )}

                {/* Node Avatar or Icon */}
                <image
                  href={state === 'backup' ? getAgentMeta('backup').avatar : meta.avatar}
                  x={node.x - (node.radius - 6)}
                  y={node.y - (node.radius - 6)}
                  width={(node.radius - 6) * 2}
                  height={(node.radius - 6) * 2}
                  className={state === 'failed' ? 'opacity-40' : 'opacity-90'}
                />

                {/* Status Indicator Badges */}
                {state === 'done' && (
                  <circle
                    cx={node.x + node.radius - 4}
                    cy={node.y - node.radius + 4}
                    r="6.5"
                    fill="#10b981"
                    stroke="#022c22"
                    strokeWidth="1.5"
                  />
                )}
                {state === 'backup' && (
                  <g>
                    <circle
                      cx={node.x + node.radius - 4}
                      cy={node.y - node.radius + 4}
                      r="7.5"
                      fill="#a855f7"
                      stroke="#1e1b4b"
                      strokeWidth="1.5"
                    />
                    <text
                      x={node.x + node.radius - 4}
                      y={node.y - node.radius + 7}
                      fontSize="9"
                      fill="#ffffff"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      🛡️
                    </text>
                  </g>
                )}

                {/* Node Label Text */}
                <text
                  x={node.x}
                  y={node.y + node.radius + 14}
                  fill={state === 'standby' ? '#64748b' : state === 'done' ? '#f1f5f9' : '#94a3b8'}
                  fontSize="10"
                  fontFamily="Inter, sans-serif"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  {node.name}
                </text>

                {/* Sub-status Micro Text */}
                <text
                  x={node.x}
                  y={node.y + node.radius + 24}
                  fill={
                    state === 'running'
                      ? '#14b8a6'
                      : state === 'backup'
                      ? '#c084fc'
                      : state === 'retrying'
                      ? '#fbbf24'
                      : state === 'failed'
                      ? '#fb7185'
                      : '#64748b'
                  }
                  fontSize="8.5"
                  fontFamily="Inter, sans-serif"
                  textAnchor="middle"
                >
                  {state === 'running'
                    ? 'working...'
                    : state === 'backup'
                    ? 'recovered'
                    : state === 'retrying'
                    ? 'retrying...'
                    : state === 'failed'
                    ? 'failed'
                    : state === 'done'
                    ? 'verified'
                    : 'pending'}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Bottom Micro-Instruction */}
      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900 px-2">
        <span>Click any verified node to inspect its Pydantic Finding contract</span>
        <span>Deterministic Topological Dispatch</span>
      </div>
    </div>
  );
};

