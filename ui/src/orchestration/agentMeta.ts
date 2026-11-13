import supervisorSvg from '../assets/agents/supervisor.svg';
import cfoSvg from '../assets/agents/cfo.svg';
import growthSvg from '../assets/agents/growth.svg';
import ctoSvg from '../assets/agents/cto.svg';
import customerSvg from '../assets/agents/customer.svg';
import productSvg from '../assets/agents/product.svg';
import skepticSvg from '../assets/agents/skeptic.svg';
import backupSvg from '../assets/agents/backup.svg';

export interface AgentMeta {
  id: string;
  name: string;
  role: string;
  department: string;
  color: {
    primary: string;
    bg: string;
    border: string;
    text: string;
    glow: string;
    halo: string;
  };
  avatar: string;
  primaryTool: string;
  tools: string[];
  workingStatusText: string;
  charter: string;
}

export const AGENT_ROSTER: Record<string, AgentMeta> = {
  supervisor: {
    id: 'supervisor',
    name: 'Supervisor',
    role: 'Orchestration Hub',
    department: 'Executive Coordination',
    color: {
      primary: '#14b8a6', // teal-500
      bg: 'rgba(20, 184, 166, 0.12)',
      border: 'rgba(20, 184, 166, 0.4)',
      text: '#5eead4', // teal-300
      glow: 'rgba(20, 184, 166, 0.35)',
      halo: 'ring-teal-500/50'
    },
    avatar: supervisorSvg,
    primaryTool: 'decompose_decision',
    tools: ['decompose_decision', 'reconcile_assumptions', 'run_simulation', 'build_report'],
    workingStatusText: 'Coordinating multi-agent DAG execution...',
    charter: 'Divides complex strategic queries into tasks, routes data, settles empirical conflicts, and finalizes reports.'
  },
  cfo: {
    id: 'cfo',
    name: 'CFO',
    role: 'Financial Analyst',
    department: 'Finance & Treasury',
    color: {
      primary: '#10b981', // emerald-500
      bg: 'rgba(16, 185, 129, 0.12)',
      border: 'rgba(16, 185, 129, 0.4)',
      text: '#6ee7b7', // emerald-300
      glow: 'rgba(16, 185, 129, 0.35)',
      halo: 'ring-emerald-500/50'
    },
    avatar: cfoSvg,
    primaryTool: 'lookup_financials',
    tools: ['lookup_financials'],
    workingStatusText: 'Pulling financials & cash runway...',
    charter: 'Protects gross margins, enforces the 10-month runway floor, and models unit economic sensitivity.'
  },
  growth: {
    id: 'growth',
    name: 'Growth',
    role: 'Acquisition Strategist',
    department: 'Marketing & Sales',
    color: {
      primary: '#0ea5e9', // sky-500
      bg: 'rgba(14, 165, 233, 0.12)',
      border: 'rgba(14, 165, 233, 0.4)',
      text: '#7dd3fc', // sky-300
      glow: 'rgba(14, 165, 233, 0.35)',
      halo: 'ring-sky-500/50'
    },
    avatar: growthSvg,
    primaryTool: 'lookup_funnel',
    tools: ['lookup_funnel'],
    workingStatusText: 'Evaluating top-of-funnel conversion & CAC...',
    charter: 'Maximizes customer acquisition velocity, expansion loops, and free-to-paid conversion efficiency.'
  },
  cto: {
    id: 'cto',
    name: 'CTO',
    role: 'Infrastructure Architect',
    department: 'Engineering & DevOps',
    color: {
      primary: '#8b5cf6', // violet-500
      bg: 'rgba(139, 92, 246, 0.12)',
      border: 'rgba(139, 92, 246, 0.4)',
      text: '#c4b5fd', // violet-300
      glow: 'rgba(139, 92, 246, 0.35)',
      halo: 'ring-violet-500/50'
    },
    avatar: ctoSvg,
    primaryTool: 'lookup_infra_costs',
    tools: ['lookup_infra_costs'],
    workingStatusText: 'Profiling cloud infrastructure compute scale...',
    charter: 'Analyzes hosting elasticity, per-user cloud resource consumption, and reliability overhead.'
  },
  customer: {
    id: 'customer',
    name: 'Customer',
    role: 'Retention & Success',
    department: 'Customer Experience',
    color: {
      primary: '#f59e0b', // amber-500
      bg: 'rgba(245, 158, 11, 0.12)',
      border: 'rgba(245, 158, 11, 0.4)',
      text: '#fcd34d', // amber-300
      glow: 'rgba(245, 158, 11, 0.35)',
      halo: 'ring-amber-500/50'
    },
    avatar: customerSvg,
    primaryTool: 'lookup_support_metrics',
    tools: ['lookup_customers', 'lookup_support_metrics'],
    workingStatusText: 'Analyzing cohort churn rates & ticket volume...',
    charter: 'Protects user retention, evaluates NPS impact, and monitors support headcount bandwidth.'
  },
  product: {
    id: 'product',
    name: 'Product',
    role: 'Packaging & Pricing',
    department: 'Product Management',
    color: {
      primary: '#ec4899', // pink-500
      bg: 'rgba(236, 72, 153, 0.12)',
      border: 'rgba(236, 72, 153, 0.4)',
      text: '#f9a8d4', // pink-300
      glow: 'rgba(236, 72, 153, 0.35)',
      halo: 'ring-pink-500/50'
    },
    avatar: productSvg,
    primaryTool: 'lookup_customers',
    tools: ['lookup_customers'],
    workingStatusText: 'Evaluating tier packaging & feature ceilings...',
    charter: 'Designs feature gates, usage quotas, tier value proposition, and prevents cannibalization.'
  },
  skeptic: {
    id: 'skeptic',
    name: 'Skeptic',
    role: 'Independent Auditor',
    department: 'Internal Governance',
    color: {
      primary: '#f43f5e', // rose-500
      bg: 'rgba(244, 63, 94, 0.12)',
      border: 'rgba(244, 63, 94, 0.4)',
      text: '#fda4af', // rose-300
      glow: 'rgba(244, 63, 94, 0.35)',
      halo: 'ring-rose-500/50'
    },
    avatar: skepticSvg,
    primaryTool: 'audit_assumptions',
    tools: ['audit_assumptions', 'verify_provenance'],
    workingStatusText: 'Auditing peer assumptions for optimistic bias...',
    charter: 'Adversarial auditor poking holes in optimistic projections and benchmarking historical plausibility.'
  },
  backup: {
    id: 'backup',
    name: 'Backup Analyst',
    role: 'Failover Sentinel',
    department: 'Resilience Layer',
    color: {
      primary: '#a855f7', // purple-500
      bg: 'rgba(168, 85, 247, 0.15)',
      border: 'rgba(168, 85, 247, 0.5)',
      text: '#d8b4fe', // purple-300
      glow: 'rgba(168, 85, 247, 0.4)',
      halo: 'ring-purple-500/60'
    },
    avatar: backupSvg,
    primaryTool: 'telemetry_derivation',
    tools: ['telemetry_derivation'],
    workingStatusText: 'Deriving conservative fallback estimates...',
    charter: 'Automated Tier 2 failover agent providing safe conservative estimates when primary agents crash.'
  }
};

export function getAgentMeta(agentName?: string): AgentMeta {
  if (!agentName) return AGENT_ROSTER.supervisor;
  const key = agentName.toLowerCase().trim().replace(/[^a-z]/g, '');
  if (key.includes('backup')) return AGENT_ROSTER.backup;
  if (key.includes('cfo')) return AGENT_ROSTER.cfo;
  if (key.includes('growth')) return AGENT_ROSTER.growth;
  if (key.includes('cto')) return AGENT_ROSTER.cto;
  if (key.includes('customer')) return AGENT_ROSTER.customer;
  if (key.includes('product')) return AGENT_ROSTER.product;
  if (key.includes('skeptic')) return AGENT_ROSTER.skeptic;
  return AGENT_ROSTER.supervisor;
}
