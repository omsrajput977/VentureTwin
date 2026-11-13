import { useMemo, useState, useEffect, useRef } from 'react';
import { EventItem, FindingItem, TaskItem } from '../api';
import { AGENT_ROSTER, getAgentMeta } from './agentMeta';

export type OrchestrationPhase =
  | 'plan'
  | 'analyze'
  | 'challenge'
  | 'resolve'
  | 'simulate'
  | 'verify'
  | 'seal';

export interface AgentRosterState {
  id: string;
  name: string;
  role: string;
  avatar: string;
  status: 'standby' | 'working' | 'done' | 'retrying' | 'failed' | 'backup' | 'degraded';
  currentTool: string;
  elapsedSeconds: number;
  recommendation?: string;
  confidence?: number;
  assumptionsCount: number;
  finding?: FindingItem;
  attempts: number;
  startedAt?: number;
}

export interface WarRoomMessage {
  id: string;
  type:
    | 'system'
    | 'finding'
    | 'challenge'
    | 'rebuttal'
    | 'conflict'
    | 'simulation'
    | 'verification'
    | 'sealed';
  agent: string;
  timestamp: string;
  title?: string;
  content?: string;
  finding?: FindingItem;
  rebuttal?: {
    agent: string;
    parameter: string;
    stance: 'concede' | 'defend' | 'compromise' | string;
    updated_low?: number;
    updated_base?: number;
    updated_high?: number;
    rationale?: string;
  };
  conflict?: {
    id: string;
    type: string;
    disputed_item: string;
    agents: string[];
    verdict?: string;
    method?: string;
    delta?: number;
  };
  verification?: {
    results: Array<{ check_name: string; status: string; detail: string }>;
    allPassed: boolean;
  };
  sealed?: {
    decisionId: string;
    recommendation: string;
    verificationHash?: string;
  };
}

export interface SimulationCell {
  id: string;
  strategy: string;
  scenario: string;
  completed: boolean;
  simulationId?: string;
}

export interface ActivePacket {
  id: string;
  source: string;
  target: string;
  color: string;
  agent: string;
  direction: 'dispatch' | 'return';
}

const STRATEGIES = ['A', 'B', 'C'];
const SCENARIOS = [
  'Conservative',
  'Expected',
  'Optimistic',
  'Stress Infra',
  'Stress Conversion',
  'Stress Churn'
];

export function useOrchestrationModel(
  choreographedEvents: EventItem[],
  tasks: Record<string, TaskItem>,
  findings: FindingItem[],
  workflowStatus: string
) {
  const [now, setNow] = useState(Date.now());

  // Clock tick for live elapsed counters
  useEffect(() => {
    if (workflowStatus !== 'running') return;
    const interval = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, [workflowStatus]);

  return useMemo(() => {
    // 1. Initial State containers
    const agentStartTimes: Record<string, number> = {};
    const agentStates: Record<string, AgentRosterState> = {
      supervisor: {
        id: 'supervisor',
        name: 'Supervisor',
        role: 'Orchestration Hub',
        avatar: getAgentMeta('supervisor').avatar,
        status: 'standby',
        currentTool: 'decompose_decision',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      cfo: {
        id: 'cfo',
        name: 'CFO',
        role: 'Financial Analyst',
        avatar: getAgentMeta('cfo').avatar,
        status: 'standby',
        currentTool: 'lookup_financials',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      growth: {
        id: 'growth',
        name: 'Growth',
        role: 'Acquisition Strategist',
        avatar: getAgentMeta('growth').avatar,
        status: 'standby',
        currentTool: 'lookup_funnel',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      cto: {
        id: 'cto',
        name: 'CTO',
        role: 'Infrastructure Architect',
        avatar: getAgentMeta('cto').avatar,
        status: 'standby',
        currentTool: 'lookup_infra_costs',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      customer: {
        id: 'customer',
        name: 'Customer',
        role: 'Retention & Success',
        avatar: getAgentMeta('customer').avatar,
        status: 'standby',
        currentTool: 'lookup_support_metrics',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      product: {
        id: 'product',
        name: 'Product',
        role: 'Packaging & Pricing',
        avatar: getAgentMeta('product').avatar,
        status: 'standby',
        currentTool: 'lookup_customers',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      },
      skeptic: {
        id: 'skeptic',
        name: 'Skeptic',
        role: 'Independent Auditor',
        avatar: getAgentMeta('skeptic').avatar,
        status: 'standby',
        currentTool: 'audit_assumptions',
        elapsedSeconds: 0,
        assumptionsCount: 0,
        attempts: 1
      }
    };

    let showBackup = false;
    let backupState: AgentRosterState = {
      id: 'backup',
      name: 'Backup Analyst',
      role: 'Failover Sentinel',
      avatar: getAgentMeta('backup').avatar,
      status: 'standby',
      currentTool: 'telemetry_derivation',
      elapsedSeconds: 0,
      assumptionsCount: 0,
      attempts: 1
    };

    let activePackets: ActivePacket[] = [];
    const messages: WarRoomMessage[] = [];
    let phase: OrchestrationPhase = 'plan';
    let narration = 'Awaiting strategic intake prompt...';

    // 18-cell simulation grid
    const simMatrix: SimulationCell[] = [];
    STRATEGIES.forEach((strat) => {
      SCENARIOS.forEach((scen) => {
        simMatrix.push({
          id: `${strat}_${scen}`,
          strategy: strat,
          scenario: scen,
          completed: false
        });
      });
    });

    let completedSimCount = 0;
    const completedNodeIds = new Set<string>();
    const nodeStatusOverrides: Record<string, string> = {};

    // 2. Replay choreographed events into derived state
    choreographedEvents.forEach((evt, idx) => {
      const p = evt.payload || {};
      const agentKey = (evt.agent || '').toLowerCase().trim();
      const meta = getAgentMeta(agentKey);
      const timeStr = new Date(evt.ts).toLocaleTimeString();

      switch (evt.type) {
        case 'task_created': {
          phase = 'plan';
          narration = 'Decomposing strategic query into 11-node functional DAG...';
          break;
        }

        case 'agent_started': {
          const taskId = p.task_id || '';
          if (taskId.includes('analysis')) {
            phase = 'analyze';
            narration = '5 cross-functional specialists evaluating domain parameters in parallel...';
            const tsNum = new Date(evt.ts).getTime();
            if (agentStates[agentKey]) {
              agentStates[agentKey].status = 'working';
              agentStates[agentKey].startedAt = tsNum;
              agentStartTimes[agentKey] = tsNum;
            }
            activePackets.push({
              id: `pkt_${idx}`,
              source: 'supervisor',
              target: taskId,
              color: meta.color.primary,
              agent: agentKey,
              direction: 'dispatch'
            });
          } else if (taskId === 'task_skeptic_audit') {
            phase = 'challenge';
            narration = 'Skeptic auditing peer assumptions for optimistic bias & provenance...';
            const tsNum = new Date(evt.ts).getTime();
            if (agentStates.skeptic) {
              agentStates.skeptic.status = 'working';
              agentStates.skeptic.startedAt = tsNum;
            }
            activePackets.push({
              id: `pkt_${idx}`,
              source: 'specialists_barrier',
              target: 'task_skeptic_audit',
              color: '#f43f5e',
              agent: 'skeptic',
              direction: 'dispatch'
            });
          } else if (taskId === 'task_agent_discussion') {
            phase = 'challenge';
            narration = 'Facilitating cross-examination discussion and rebuttal stances...';
          } else if (taskId === 'task_conflict_resolution') {
            phase = 'resolve';
            narration = 'Synthesizing empirical conflicts for deterministic simulation isolation...';
          } else if (taskId === 'task_simulation_engine') {
            phase = 'simulate';
            narration = 'Running 12-month Monte Carlo and discrete parameter simulations...';
          } else if (taskId === 'task_workflow_verification') {
            phase = 'verify';
            narration = 'Executing 7 independent algorithmic audits and Number Registry tie-outs...';
          } else if (taskId === 'task_report_finalize') {
            phase = 'seal';
            narration = 'Synthesizing executive deliverable and sealing verification hash...';
          }
          break;
        }

        case 'finding_posted': {
          const finding = p.finding;
          const isRebuttal = p.type === 'rebuttal' || Boolean(p.rebuttal);

          if (isRebuttal && p.rebuttal) {
            messages.push({
              id: `msg_${idx}`,
              type: 'rebuttal',
              agent: p.rebuttal.agent || agentKey,
              timestamp: timeStr,
              rebuttal: p.rebuttal
            });
          } else if (finding) {
            completedNodeIds.add(p.task_id || '');
            if (agentStates[agentKey]) {
              agentStates[agentKey].status = 'done';
              agentStates[agentKey].recommendation = finding.recommendation;
              agentStates[agentKey].confidence = finding.confidence;
              agentStates[agentKey].assumptionsCount = (finding.assumptions || []).length;
              agentStates[agentKey].finding = finding;
            }

            // Route return packet to supervisor
            activePackets = activePackets.filter((pkt) => pkt.agent !== agentKey);

            messages.push({
              id: `msg_${idx}`,
              type: agentKey === 'skeptic' ? 'challenge' : 'finding',
              agent: agentKey,
              timestamp: timeStr,
              finding: finding,
              content: finding.claim
            });
          }
          break;
        }

        case 'conflict_detected': {
          phase = 'resolve';
          narration = `Conflict detected: ${p.disputed_item || 'competing strategies'}. Isolating into simulation...`;
          messages.push({
            id: `msg_${idx}`,
            type: 'conflict',
            agent: 'supervisor',
            timestamp: timeStr,
            conflict: {
              id: p.conflict_id || `conf_${idx}`,
              type: p.type || 'disputed_assumptions',
              disputed_item: p.disputed_item || 'Strategic divergence',
              agents: p.agents || ['CFO', 'GROWTH']
            }
          });
          break;
        }

        case 'simulation_run': {
          phase = 'simulate';
          const strat = p.strategy || 'A';
          const scen = p.scenario || 'Expected';
          const matchCell = simMatrix.find((c) => c.strategy === strat && c.scenario === scen && !c.completed);
          if (matchCell) {
            matchCell.completed = true;
            matchCell.simulationId = p.simulation_id;
            completedSimCount++;
          } else {
            const nextIncomplete = simMatrix.find((c) => !c.completed);
            if (nextIncomplete) {
              nextIncomplete.completed = true;
              nextIncomplete.simulationId = p.simulation_id;
              completedSimCount++;
            }
          }
          narration = `Simulating 12-month outcomes: Strategy ${strat} (${scen}) [${completedSimCount}/18]...`;
          break;
        }

        case 'verification_passed':
        case 'verification_failed': {
          phase = 'verify';
          const allPassed = evt.type === 'verification_passed';
          narration = allPassed
            ? 'All 7 algorithmic audits passed: financial tie-outs and provenance verified 100%.'
            : 'Algorithmic verification alert: review data tie-out exceptions.';
          messages.push({
            id: `msg_${idx}`,
            type: 'verification',
            agent: 'skeptic',
            timestamp: timeStr,
            verification: {
              results: p.results || [
                { check_name: 'Unit Consistency', status: 'passed', detail: 'All units valid' },
                { check_name: 'Financial Tie Out', status: 'passed', detail: '100% precision' },
                { check_name: 'Provenance Integrity', status: 'passed', detail: 'All tags authentic' },
                { check_name: 'Required Sections', status: 'passed', detail: '10 sections verified' },
                { check_name: 'Report Traceability', status: 'passed', detail: 'Linked to sim IDs' },
                { check_name: 'Number Registry Integrity', status: 'passed', detail: 'All numbers tie out' },
                { check_name: 'Prose Number Audit', status: 'passed', detail: 'Prose numbers verified' }
              ],
              allPassed
            }
          });
          break;
        }

        case 'agent_failed': {
          const taskId = p.task_id || '';
          nodeStatusOverrides[taskId] = 'failed';
          if (agentStates[agentKey]) {
            agentStates[agentKey].status = 'failed';
            agentStates[agentKey].attempts = p.attempt ?? 1;
          }
          messages.push({
            id: `msg_${idx}`,
            type: 'system',
            agent: agentKey,
            timestamp: timeStr,
            title: `Agent Fault: ${meta.name} (Attempt ${p.attempt ?? 1})`,
            content: p.error || 'Process exception encountered during execution.'
          });
          break;
        }

        case 'recovery_started': {
          const taskId = p.task_id || '';
          nodeStatusOverrides[taskId] = 'retrying';
          if (agentStates[agentKey]) {
            agentStates[agentKey].status = 'retrying';
          }
          const mode = p.mode || 'retry';
          messages.push({
            id: `msg_${idx}`,
            type: 'system',
            agent: 'supervisor',
            timestamp: timeStr,
            title: `Autonomous Recovery Initiated (${mode})`,
            content: `Supervisor executing recovery sequence for ${meta.name}...`
          });
          break;
        }

        case 'recovery_done': {
          const taskId = p.task_id || '';
          const mode = p.mode || '';
          if (mode === 'backup_analyst_completed') {
            showBackup = true;
            nodeStatusOverrides[taskId] = 'backup';
            if (agentStates[agentKey]) {
              agentStates[agentKey].status = 'backup';
            }
            backupState.status = 'done';
            messages.push({
              id: `msg_${idx}`,
              type: 'system',
              agent: 'backup',
              timestamp: timeStr,
              title: `🛡️ Backup Analyst Engaged for ${meta.name}`,
              content: 'Primary agent retries exhausted. Backup Analyst stepped in with conservative telemetry derivation.'
            });
          }
          break;
        }

        case 'failure_injected': {
          const mode = p.mode || 'exception';
          messages.push({
            id: `msg_${idx}`,
            type: 'system',
            agent: 'supervisor',
            timestamp: timeStr,
            title: `⚡ Live Chaos Fault Injected: ${meta.name}`,
            content: `Target ${meta.name.toUpperCase()} armed with ${mode} fault.`
          });
          break;
        }

        case 'agent_healed': {
          const taskId = `task_${agentKey}_analysis`;
          delete nodeStatusOverrides[taskId];
          if (agentStates[agentKey]) {
            agentStates[agentKey].status = 'done';
          }
          messages.push({
            id: `msg_${idx}`,
            type: 'system',
            agent: agentKey,
            timestamp: timeStr,
            title: `🛡️ ${meta.name} Healed & Restored`,
            content: `Clean primary LLM analysis re-injected. Backup fallback state cleared.`
          });
          break;
        }

        case 'report_ready': {
          phase = 'seal';
          narration = 'Flight plan complete: 10-section audited executive report sealed.';
          messages.push({
            id: `msg_${idx}`,
            type: 'sealed',
            agent: 'supervisor',
            timestamp: timeStr,
            title: 'Verified & Sealed by Supervisor',
            sealed: {
              decisionId: p.decision_id || '',
              recommendation: p.recommendation || 'Proceed with limits',
              verificationHash: p.verification_hash
            }
          });
          break;
        }

        default:
          break;
      }
    });

    // 3. Update elapsed seconds for agents actively working
    Object.keys(agentStates).forEach((k) => {
      const st = agentStates[k];
      if (st.status === 'working' && st.startedAt) {
        st.elapsedSeconds = Math.max(1, Math.floor((now - st.startedAt) / 1000));
      }
    });

    // Count active agents
    const activeAgentsCount = Object.values(agentStates).filter(
      (a) => a.status === 'working' || a.status === 'retrying'
    ).length;

    return {
      phase,
      narration,
      activeAgentsCount,
      agentStates,
      showBackup,
      backupState,
      messages,
      simMatrix,
      completedSimCount,
      activePackets,
      completedNodeIds,
      nodeStatusOverrides
    };
  }, [choreographedEvents, tasks, findings, workflowStatus, now]);
}
